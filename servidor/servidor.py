"""
NetMon: servidor do Projeto 1 (CIC0124 Redes de Computadores).

Monitoramento de serviços de rede. Agentes medem se servidores estão no ar e quanto tempo
levam para responder, e mandam as medições para este servidor, que guarda o histórico e
gera alertas.

Este programa tem dois serviços:
  - porta 5050/TCP: recebe os agentes, com o protocolo de texto de docs/PROTOCOLO.md.
    Usa socket TCP como no TCPServer dos slides (C2 106-109). Cada agente tem seu próprio socket
    no servidor (C3 23) e é atendido por uma thread (multithreading, citado no C2 113).
  - porta 8765/TCP: servidor HTTP do painel web (C2 19-30).

Usa só a biblioteca padrão do Python.

Uso:
    python3 servidor/servidor.py
"""
import hashlib
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import *
from urllib.parse import parse_qs, urlparse

PORTA_AGENTES = 5050
PORTA_HTTP = 8765
TAM_MAX_LINHA = 1024   # uma linha do protocolo tem no máximo 1024 bytes
TIMEOUT_AGENTE = 30    # segundos sem nenhuma mensagem até considerar o agente caído
TAM_MAX_CORPO = 20_000_000   # maior corpo HTTP aceito (bytes)

# Experimento extra (docs/EXPERIMENTOS.md): True faz cada resposta HTTP sair em dois envios
# (cabeçalho e corpo separados), para medir o efeito disso no Experimento B.
RESPOSTA_EM_DOIS_ENVIOS = False

RAIZ = Path(__file__).resolve().parent.parent
ARQ_BANCO = RAIZ / "dados" / "netmon.db"
ARQ_LOG = RAIZ / "logs" / "servidor.log"
PASTA_WEB = RAIZ / "web"

# Dados de teste (não sensíveis)
USUARIOS = [("painel1", "redes2026"), ("painel2", "redes2026")]
AGENTES = [("agente-0%d" % i, "chave-0%d" % i) for i in range(1, 6)]
REGRAS = [  # (métrica, limiar em ms, medições seguidas, nível)
    ("fora_do_ar", 0, 2, "critico"),
    ("tcp_ms", 200, 3, "aviso"),
    ("http_ms", 500, 3, "aviso"),
]

# Estado compartilhado entre as threads. A trava impede que duas threads mexam ao mesmo tempo.
trava = threading.Lock()
online = {}       # agente_id -> socket da conexão desse agente
contadores = {}   # (agente_id, alvo, regra_id) -> (violações seguidas, alerta já disparado?)
sessoes = {}      # cookie de sessão -> usuário do painel


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def log(texto):
    """Escreve uma linha com data e hora no terminal e em logs/servidor.log."""
    linha = agora() + "  " + texto
    print(linha, flush=True)
    with open(ARQ_LOG, "a", encoding="utf-8") as arquivo:
        arquivo.write(linha + "\n")


# ---------------------------------------------------------------------------
# Banco de dados (SQLite)
# ---------------------------------------------------------------------------
def sql(comando, parametros=()):
    """Executa um comando SQL e devolve (linhas, id da última linha inserida).
    Cada chamada abre sua própria conexão, então várias threads podem usar o banco;
    o próprio SQLite organiza o acesso."""
    conexao = sqlite3.connect(str(ARQ_BANCO), timeout=10)
    conexao.row_factory = sqlite3.Row
    try:
        cursor = conexao.execute(comando, parametros)
        linhas = [dict(linha) for linha in cursor.fetchall()]
        conexao.commit()
        return linhas, cursor.lastrowid
    finally:
        conexao.close()


def resumo(texto):
    """Hash SHA-256: o banco guarda o resumo da senha, não a senha."""
    return hashlib.sha256(texto.encode()).hexdigest()


def criar_banco():
    ARQ_BANCO.parent.mkdir(exist_ok=True)
    ARQ_LOG.parent.mkdir(exist_ok=True)
    sql("CREATE TABLE IF NOT EXISTS usuarios (usuario TEXT PRIMARY KEY, senha_hash TEXT)")
    sql("CREATE TABLE IF NOT EXISTS agentes (agente_id TEXT PRIMARY KEY, chave_hash TEXT)")
    sql("""CREATE TABLE IF NOT EXISTS medicoes (id INTEGER PRIMARY KEY AUTOINCREMENT,
           agente_id TEXT, alvo TEXT, estado TEXT, tcp_ms REAL, http_ms REAL, ts TEXT)""")
    sql("""CREATE TABLE IF NOT EXISTS regras (id INTEGER PRIMARY KEY AUTOINCREMENT,
           metrica TEXT, limiar REAL, consecutivas INTEGER, nivel TEXT)""")
    sql("""CREATE TABLE IF NOT EXISTS alertas (id INTEGER PRIMARY KEY AUTOINCREMENT,
           agente_id TEXT, alvo TEXT, regra_id INTEGER, nivel TEXT, mensagem TEXT, ts TEXT)""")
    if not sql("SELECT 1 FROM usuarios")[0]:
        for usuario, senha in USUARIOS:
            sql("INSERT INTO usuarios VALUES (?, ?)", (usuario, resumo(usuario + ":" + senha)))
        for agente_id, chave in AGENTES:
            sql("INSERT INTO agentes VALUES (?, ?)", (agente_id, resumo(agente_id + ":" + chave)))
        for regra in REGRAS:
            sql("INSERT INTO regras (metrica, limiar, consecutivas, nivel) VALUES (?, ?, ?, ?)", regra)


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
def registrar_alerta(agente_id, alvo, regra_id, nivel, mensagem):
    sql("INSERT INTO alertas (agente_id, alvo, regra_id, nivel, mensagem, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (agente_id, alvo, regra_id, nivel, mensagem, agora()))
    log("ALERTA %s: %s" % (nivel, mensagem))


def avaliar_regras(agente_id, alvo, estado, tcp_ms, http_ms):
    """Confere cada regra. Só alerta depois de N medições seguidas fora do normal,
    e só uma vez, até o serviço voltar ao normal."""
    valores = {"tcp_ms": tcp_ms, "http_ms": http_ms}
    regras, _ = sql("SELECT * FROM regras")
    for regra in regras:
        if regra["metrica"] == "fora_do_ar":
            violou = estado == "DOWN"
        else:
            valor = valores[regra["metrica"]]
            if valor is None:      # métrica não medida nesta vez (ex.: alvo sem HTTP)
                continue
            violou = valor > regra["limiar"]

        chave = (agente_id, alvo, regra["id"])
        with trava:
            seguidas, ja_disparou = contadores.get(chave, (0, False))
            if violou:
                seguidas = seguidas + 1
            else:
                seguidas, ja_disparou = 0, False
            disparar = violou and seguidas >= regra["consecutivas"] and not ja_disparou
            contadores[chave] = (seguidas, ja_disparou or disparar)

        if disparar:
            vezes = "1 medição" if seguidas == 1 else "%d medições seguidas" % seguidas
            if regra["metrica"] == "fora_do_ar":
                mensagem = "%s fora do ar (%s, agente %s)" % (alvo, vezes, agente_id)
            else:
                mensagem = "%s: %s = %.1f ms, acima de %g ms (%s, agente %s)" % (
                    alvo, regra["metrica"], valores[regra["metrica"]], regra["limiar"], vezes, agente_id)
            registrar_alerta(agente_id, alvo, regra["id"], regra["nivel"], mensagem)


# ---------------------------------------------------------------------------
# Canal dos agentes: socket TCP, uma thread por agente
# ---------------------------------------------------------------------------
def processar_medicao(partes, agente_id):
    """MEDICAO <alvo> <UP|DOWN> <tcp_ms> <http_ms>. Devolve o texto da resposta."""
    if len(partes) != 5:
        return "400 FORMATO_INVALIDO use: MEDICAO <alvo> <UP|DOWN> <tcp_ms> <http_ms>"
    alvo, estado = partes[1], partes[2]
    host, _, porta = alvo.rpartition(":")
    if not host or not porta.isdigit() or not 1 <= int(porta) <= 65535:
        return "400 FORMATO_INVALIDO alvo deve ser host:porta"
    if estado not in ("UP", "DOWN"):
        return "400 FORMATO_INVALIDO estado deve ser UP ou DOWN"

    tempos = []   # "-" significa "não medido"
    for texto in (partes[3], partes[4]):
        if texto == "-":
            tempos.append(None)
        else:
            try:
                tempos.append(float(texto))
            except ValueError:
                return "400 FORMATO_INVALIDO tempo '%s' não é número nem -" % texto
    tcp_ms, http_ms = tempos

    if estado == "UP" and tcp_ms is None:
        return "422 VALOR_INVALIDO serviço UP precisa de tcp_ms"
    if estado == "DOWN" and (tcp_ms is not None or http_ms is not None):
        return "422 VALOR_INVALIDO serviço DOWN não tem tempos; use -"
    for valor in (tcp_ms, http_ms):
        if valor is not None and not 0 <= valor <= 60000:
            return "422 VALOR_INVALIDO tempo fora de 0 a 60000 ms"

    _, medicao_id = sql("INSERT INTO medicoes (agente_id, alvo, estado, tcp_ms, http_ms, ts) VALUES (?, ?, ?, ?, ?, ?)",
                        (agente_id, alvo, estado, tcp_ms, http_ms, agora()))
    avaliar_regras(agente_id, alvo, estado, tcp_ms, http_ms)
    return "200 OK %d" % medicao_id


def tratar_linha(linha, agente_id):
    """Interpreta uma linha recebida.
    Devolve (resposta, agente_id da conexão, encerrar a conexão?)."""
    partes = linha.split()
    comando = partes[0].upper()

    if comando == "HELLO":
        if agente_id is not None:
            return "403 HELLO_REPETIDO HELLO já foi feito nesta conexão", agente_id, False
        if len(partes) != 3:
            return "400 FORMATO_INVALIDO use: HELLO <agente_id> <chave>", None, False
        encontrados, _ = sql("SELECT chave_hash FROM agentes WHERE agente_id = ?", (partes[1],))
        if not encontrados or encontrados[0]["chave_hash"] != resumo(partes[1] + ":" + partes[2]):
            return "401 NAO_AUTENTICADO agente ou chave incorretos", None, True
        with trava:
            ja_conectado = partes[1] in online
        if ja_conectado:
            return "403 JA_CONECTADO %s já tem uma conexão aberta" % partes[1], None, True
        return "200 OK bem-vindo " + partes[1], partes[1], False

    if agente_id is None:
        return "403 SEM_HELLO envie HELLO primeiro", None, False
    if comando == "MEDICAO":
        return processar_medicao(partes, agente_id), agente_id, False
    if comando == "PING":
        return "200 PONG " + " ".join(partes[1:]), agente_id, False
    if comando == "BYE":
        return "200 OK tchau", agente_id, True
    return "400 COMANDO_DESCONHECIDO " + comando[:30], agente_id, False


def atender_agente(connectionSocket, addr):
    """Conversa com um agente até ele sair. Cada agente tem uma thread só dele."""
    cliente = "%s:%d" % addr
    # recv() desiste depois de 30 s (C2 113-116). É assim que o servidor percebe um agente cuja
    # máquina ou rede caiu: nesse caso nenhum FIN chega, e o recv() ficaria esperando para sempre.
    connectionSocket.settimeout(TIMEOUT_AGENTE)
    agente_id = None
    motivo = "desconhecido"
    buffer = b""
    log("TCP  conexão de %s" % cliente)
    try:
        encerrar = False
        while not encerrar:
            pedaco = connectionSocket.recv(1024)
            if not pedaco:                       # recv() vazio: o agente fechou a conexão (chegou o FIN)
                motivo = "agente fechou a conexão"
                break
            # O TCP entrega um fluxo de bytes, não mensagens (C3 80, C2 101): um recv() pode trazer
            # meia linha ou várias linhas juntas. Guardamos tudo no buffer e processamos
            # cada linha completa, que termina em '\n'.
            buffer = buffer + pedaco
            while b"\n" in buffer and not encerrar:
                bruto, buffer = buffer.split(b"\n", 1)
                if len(bruto) > TAM_MAX_LINHA:
                    connectionSocket.sendall(b"413 LINHA_GRANDE maximo de 1024 bytes por linha\n")
                    motivo, encerrar = "linha grande demais", True
                    break
                linha = bruto.decode("utf-8", errors="replace").strip()
                if not linha:
                    continue
                resposta, novo_id, encerrar = tratar_linha(linha, agente_id)
                connectionSocket.sendall((resposta + "\n").encode())

                if agente_id is None and novo_id is not None:   # HELLO aceito
                    agente_id = novo_id
                    with trava:
                        online[agente_id] = connectionSocket
                if linha.upper().startswith("HELLO"):
                    linha = "HELLO ***"                          # não grava a chave no log
                log("TCP  %s  %s -> %s" % (agente_id or cliente, linha, resposta))
                if encerrar:
                    motivo = "BYE" if resposta.startswith("200") else resposta

            if len(buffer) > TAM_MAX_LINHA:      # passou de 1024 bytes sem '\n'
                connectionSocket.sendall(b"413 LINHA_GRANDE maximo de 1024 bytes por linha\n")
                motivo = "linha grande demais"
                break
    except timeout:
        motivo = "sem mensagens por %d s" % TIMEOUT_AGENTE
    except OSError as erro:
        motivo = "erro de rede: %s" % erro
    finally:
        connectionSocket.close()
        caiu = False
        with trava:
            if agente_id is not None and online.get(agente_id) is connectionSocket:
                del online[agente_id]
                caiu = motivo != "BYE"
        log("TCP  %s desconectou (%s)" % (agente_id or cliente, motivo))
        if caiu:
            registrar_alerta(agente_id, None, None, "aviso", "agente %s offline (%s)" % (agente_id, motivo))


def servidor_agentes():
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)   # permite reabrir a porta logo após reiniciar
    serverSocket.bind(("", PORTA_AGENTES))
    serverSocket.listen(10)
    log("TCP  esperando agentes na porta %d" % PORTA_AGENTES)
    while True:
        connectionSocket, addr = serverSocket.accept()      # um socket novo para cada agente (C3 23)
        threading.Thread(target=atender_agente, args=(connectionSocket, addr), daemon=True).start()


# ---------------------------------------------------------------------------
# Servidor HTTP do painel
# ---------------------------------------------------------------------------
ARQUIVOS_WEB = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def numero(parametros, nome, padrao, maximo):
    """Lê um parâmetro inteiro da URL (ex.: ?limite=50). Devolve None se for inválido."""
    texto = parametros.get(nome, str(padrao))
    if not texto.isdigit() or int(texto) > maximo:
        return None
    return int(texto)


def resumo_alvos():
    """Última medição de cada alvo."""
    alvos, _ = sql("SELECT DISTINCT alvo FROM medicoes ORDER BY alvo")
    resultado = []
    for linha in alvos:
        ultima, _ = sql("SELECT * FROM medicoes WHERE alvo = ? ORDER BY id DESC LIMIT 1", (linha["alvo"],))
        resultado.append(ultima[0])
    return resultado


def alterar_regra(texto_id, dados, usuario):
    if not texto_id.isdigit() or not sql("SELECT 1 FROM regras WHERE id = ?", (int(texto_id),))[0]:
        return 404, {"erro": "regra %s não existe" % texto_id}
    if dados is None:
        return 400, {"erro": "corpo deve ser JSON"}
    try:
        limiar = float(dados["limiar"])
        consecutivas = int(dados["consecutivas"])
        nivel = dados["nivel"]
    except (KeyError, TypeError, ValueError):
        return 400, {"erro": "informe limiar (número), consecutivas (inteiro) e nivel"}
    if not 0 <= limiar <= 60000 or not 1 <= consecutivas <= 100 or nivel not in ("aviso", "critico"):
        return 400, {"erro": "limiar de 0 a 60000, consecutivas de 1 a 100, nivel aviso ou critico"}
    regra_id = int(texto_id)
    sql("UPDATE regras SET limiar = ?, consecutivas = ?, nivel = ? WHERE id = ?", (limiar, consecutivas, nivel, regra_id))
    with trava:   # recomeça a contagem dessa regra
        for chave in list(contadores):
            if chave[2] == regra_id:
                del contadores[chave]
    log("HTTP regra %d alterada por %s: limiar %g, consecutivas %d, %s" % (regra_id, usuario, limiar, consecutivas, nivel))
    return 200, sql("SELECT * FROM regras WHERE id = ?", (regra_id,))[0][0]


class Painel(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # conexão persistente: várias requisições na mesma conexão TCP (C2 25)

    def log_message(self, *args):   # desliga o log padrão; usamos o nosso
        pass

    def do_GET(self):
        self.atender("GET")

    def do_POST(self):
        self.atender("POST")

    def do_PUT(self):
        self.atender("PUT")

    def enviar(self, status, corpo, tipo, cookie=None):
        """Monta a mensagem de resposta HTTP inteira, no formato do slide C2 29: linha de status,
        cabeçalhos, linha em branco e corpo. Tudo sai num único envio (ver RESPOSTA_EM_DOIS_ENVIOS)."""
        resposta = "HTTP/1.1 %d %s\r\n" % (status, HTTPStatus(status).phrase)
        resposta += "Content-Type: %s\r\n" % tipo
        resposta += "Content-Length: %d\r\n" % len(corpo)
        if cookie:
            resposta += "Set-Cookie: %s\r\n" % cookie
        resposta += "\r\n"
        if RESPOSTA_EM_DOIS_ENVIOS:
            self.wfile.write(resposta.encode())
            self.wfile.write(corpo)
        else:
            self.wfile.write(resposta.encode() + corpo)

    def ler_corpo(self):
        """Lê o corpo da requisição. Devolve None se o Content-Length for inválido ou grande demais."""
        texto = self.headers.get("Content-Length", "0")
        if not texto.isdigit() or int(texto) > TAM_MAX_CORPO:
            self.close_connection = True   # o corpo não será lido: a conexão não pode ser reaproveitada
            return None
        return self.rfile.read(int(texto))

    def ler_json(self):
        corpo = self.ler_corpo()
        if corpo is None:
            return None
        try:
            dados = json.loads(corpo or b"{}")
        except ValueError:
            return None
        return dados if isinstance(dados, dict) else None

    def cookie_sessao(self):
        for parte in self.headers.get("Cookie", "").split(";"):
            nome, _, valor = parte.strip().partition("=")
            if nome == "sessao":
                return valor
        return None

    def atender(self, metodo):
        inicio = time.perf_counter()
        url = urlparse(self.path)
        if metodo == "GET" and url.path in ARQUIVOS_WEB:          # arquivos do painel
            nome, tipo = ARQUIVOS_WEB[url.path]
            self.enviar(200, (PASTA_WEB / nome).read_bytes(), tipo)
            return
        parametros = {nome: valores[0] for nome, valores in parse_qs(url.query).items()}
        cookie = None
        try:
            status, dados, cookie = self.rotear(metodo, url.path, parametros)
        except Exception as erro:          # um erro numa requisição não derruba o servidor
            log("HTTP erro interno em %s: %r" % (url.path, erro))
            status, dados = 500, {"erro": "erro interno"}
        self.enviar(status, json.dumps(dados, ensure_ascii=False).encode(), "application/json; charset=utf-8", cookie)
        log("HTTP %s:%d %s %s -> %d (%.1f ms)" % (self.client_address[0], self.client_address[1],
                                                  metodo, self.path, status, (time.perf_counter() - inicio) * 1000))

    def rotear(self, metodo, caminho, p):
        """Devolve (status, dados em JSON, cookie a enviar ou None)."""
        if metodo == "POST" and caminho == "/api/login":
            return self.login()

        usuario = sessoes.get(self.cookie_sessao())
        if usuario is None:
            return 401, {"erro": "faça login primeiro"}, None

        if metodo == "POST" and caminho == "/api/logout":
            sessoes.pop(self.cookie_sessao(), None)
            return 200, {"ok": True}, "sessao=; Max-Age=0; Path=/"
        if metodo == "GET" and caminho == "/api/alvos":
            return 200, resumo_alvos(), None
        if metodo == "GET" and caminho == "/api/agentes":
            with trava:
                conectados = set(online)
            return 200, [{"agente_id": a, "online": a in conectados} for a, _ in AGENTES], None
        if metodo == "GET" and caminho == "/api/medicoes":
            desde, limite = numero(p, "desde", 0, 10**12), numero(p, "limite", 100, 1000)
            if desde is None or limite is None:
                return 400, {"erro": "desde e limite devem ser inteiros (limite até 1000)"}, None
            if p.get("alvo"):
                linhas, _ = sql("SELECT * FROM medicoes WHERE id > ? AND alvo = ? ORDER BY id DESC LIMIT ?",
                                (desde, p["alvo"], limite))
            else:
                linhas, _ = sql("SELECT * FROM medicoes WHERE id > ? ORDER BY id DESC LIMIT ?", (desde, limite))
            return 200, linhas, None
        if metodo == "GET" and caminho == "/api/alertas":
            desde, limite = numero(p, "desde", 0, 10**12), numero(p, "limite", 50, 1000)
            if desde is None or limite is None:
                return 400, {"erro": "desde e limite devem ser inteiros (limite até 1000)"}, None
            linhas, _ = sql("SELECT * FROM alertas WHERE id > ? ORDER BY id DESC LIMIT ?", (desde, limite))
            return 200, linhas, None
        if metodo == "GET" and caminho == "/api/regras":
            return 200, sql("SELECT * FROM regras ORDER BY id")[0], None
        if metodo == "PUT" and caminho.startswith("/api/regras/"):
            status, dados = alterar_regra(caminho.split("/")[-1], self.ler_json(), usuario)
            return status, dados, None
        if metodo == "POST" and caminho == "/api/carga":        # Experimento B (throughput)
            corpo = self.ler_corpo()
            if corpo is None:
                return 413, {"erro": "Content-Length inválido ou maior que %d bytes" % TAM_MAX_CORPO}, None
            return 200, {"bytes": len(corpo)}, None
        return 404, {"erro": "rota não existe: %s %s" % (metodo, caminho)}, None

    def login(self):
        dados = self.ler_json()
        if not dados or not isinstance(dados.get("usuario"), str) or not isinstance(dados.get("senha"), str):
            return 400, {"erro": "informe usuario e senha"}, None
        usuario = dados["usuario"]
        encontrados, _ = sql("SELECT senha_hash FROM usuarios WHERE usuario = ?", (usuario,))
        if not encontrados or encontrados[0]["senha_hash"] != resumo(usuario + ":" + dados["senha"]):
            log("HTTP login recusado: %s" % usuario)
            return 401, {"erro": "usuário ou senha incorretos"}, None
        cookie = secrets.token_hex(16)
        sessoes[cookie] = usuario
        log("HTTP login de %s" % usuario)
        # o navegador guarda o cookie e o reenvia em toda requisição seguinte (C2 32-35)
        return 200, {"usuario": usuario}, "sessao=%s; Path=/" % cookie


def porta_em_uso(porta):
    """Tenta conectar na porta. Se alguém atender, outro programa já está usando essa porta."""
    teste = socket(AF_INET, SOCK_STREAM)
    teste.settimeout(0.5)
    try:
        teste.connect(("127.0.0.1", porta))
        return True
    except OSError:
        return False
    finally:
        teste.close()


def main():
    for porta in (PORTA_AGENTES, PORTA_HTTP):
        if porta_em_uso(porta):
            print("ERRO: a porta %d já está sendo usada por outro programa (pode ser um NetMon antigo aberto)." % porta)
            print("Feche esse programa ou troque a porta no começo de servidor/servidor.py.")
            return
    criar_banco()
    threading.Thread(target=servidor_agentes, daemon=True).start()
    servidor_http = ThreadingHTTPServer(("", PORTA_HTTP), Painel)
    log("HTTP painel em http://127.0.0.1:%d  (Ctrl+C para encerrar)" % PORTA_HTTP)
    try:
        servidor_http.serve_forever()
    except KeyboardInterrupt:
        log("servidor encerrado")


if __name__ == "__main__":
    main()
