"""
Teste do protocolo NetMon: casos normais e de erro, no canal TCP dos agentes e na API HTTP.

Grava algumas medições de teste no banco (alvos com nome "t<número>-..."), por isso convém
rodar antes de apagar dados/ para a demonstração. Pode ser repetido quantas vezes quiser.
Usa o agente-05: deixe-o desligado durante o teste.

Com o servidor rodando:
    python3 testes/teste_protocolo.py
"""
import json
import sys
import time
import urllib.error
import urllib.request
from socket import *

SERVIDOR = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
BASE = "http://%s:8765" % SERVIDOR
PREFIXO = "t%d" % int(time.time())   # nomes de alvo diferentes a cada execução
resultados = []


def verificar(condicao, descricao):
    resultados.append(bool(condicao))
    print(("  OK     " if condicao else "  FALHA  ") + descricao, flush=True)


def conectar():
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(5)
    s.connect((SERVIDOR, 5050))
    return s


def receber(s, linhas=1):
    """Lê até receber o número de linhas pedido (o TCP pode juntar ou partir as respostas)."""
    dados = b""
    while dados.count(b"\n") < linhas:
        pedaco = s.recv(1024)
        if not pedaco:
            break
        dados = dados + pedaco
    return dados.decode().strip()


def comando(s, linha):
    s.sendall((linha + "\n").encode())
    return receber(s)


def fechou(s):
    """True se o servidor fechou a conexão (recv volta vazio)."""
    try:
        return s.recv(1024) == b""
    except OSError:
        return True


def http(metodo, rota, corpo=None, cookie=None):
    cabecalhos = {"Content-Type": "application/json"}
    if cookie:
        cabecalhos["Cookie"] = cookie
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(BASE + rota, data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            return resposta.status, json.loads(resposta.read()), resposta.headers.get("Set-Cookie")
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read() or b"{}"), None


print("\n[Canal TCP dos agentes, porta 5050]")
s = conectar()
verificar(comando(s, "MEDICAO x:80 UP 1 -").startswith("403 SEM_HELLO"), "comando antes do HELLO -> 403")
verificar(comando(s, "HELLO agente-05 errada").startswith("401 NAO_AUTENTICADO"), "HELLO com chave errada -> 401")
verificar(fechou(s), "...e o servidor fecha a conexão")
s.close()

s = conectar()
verificar(comando(s, "HELLO agente-05 chave-05") == "200 OK bem-vindo agente-05", "HELLO correto -> 200 OK")
verificar(comando(s, "HELLO agente-05 chave-05").startswith("403 HELLO_REPETIDO"), "segundo HELLO -> 403 HELLO_REPETIDO")
s3 = conectar()
verificar(comando(s3, "HELLO agente-05 chave-05").startswith("403 JA_CONECTADO"), "mesmo agente em outra conexão -> 403 JA_CONECTADO")
s3.close()
verificar(comando(s, "MEDICAO teste:80 UP").startswith("400 FORMATO_INVALIDO"), "MEDICAO sem campos -> 400")
verificar(comando(s, "MEDICAO semporta UP 1 -").startswith("400 FORMATO_INVALIDO"), "alvo sem porta -> 400")
verificar(comando(s, "MEDICAO teste:80 TALVEZ 1 -").startswith("400 FORMATO_INVALIDO"), "estado inválido -> 400")
verificar(comando(s, "MEDICAO teste:80 UP abc -").startswith("400 FORMATO_INVALIDO"), "tempo não numérico -> 400")
verificar(comando(s, "MEDICAO teste:80 UP - -").startswith("422 VALOR_INVALIDO"), "UP sem tcp_ms -> 422")
verificar(comando(s, "MEDICAO teste:80 DOWN 5 -").startswith("422 VALOR_INVALIDO"), "DOWN com tempo -> 422")
verificar(comando(s, "MEDICAO teste:80 UP -3 -").startswith("422 VALOR_INVALIDO"), "tempo negativo -> 422")
verificar(comando(s, "XYZ").startswith("400 COMANDO_DESCONHECIDO"), "comando desconhecido -> 400")
verificar(comando(s, "PING 12345.6") == "200 PONG 12345.6", "PING -> PONG com o mesmo texto")
resposta = comando(s, "MEDICAO %s-ok:80 UP 12.5 30.25" % PREFIXO)
verificar(resposta.startswith("200 OK ") and resposta.split()[2].isdigit(), "MEDICAO válida -> 200 OK <id>")
s.sendall(b"PING a\nPING b\n")   # duas linhas num só envio: o servidor separa pelo '\n'
verificar(receber(s, 2).split("\n") == ["200 PONG a", "200 PONG b"], "duas linhas num só envio -> duas respostas")
s.sendall(b"PI")                 # uma linha em dois pedaços: o servidor espera o '\n'
time.sleep(0.2)
s.sendall(b"NG c\n")
verificar(receber(s) == "200 PONG c", "uma linha em dois pedaços -> uma resposta")

s2 = conectar()
s2.sendall(b"y" * 2000)
verificar(receber(s2).startswith("413 LINHA_GRANDE"), "2000 bytes sem '\\n' -> 413")
verificar(fechou(s2), "...e o servidor fecha a conexão")
s2.close()

print("\n[API HTTP, porta 8765]")
verificar(http("POST", "/api/login", {"usuario": "painel1", "senha": "errada"})[0] == 401, "login com senha errada -> 401")
verificar(http("POST", "/api/login", {"usuario": "painel1"})[0] == 400, "login sem senha -> 400")
verificar(http("GET", "/api/alvos")[0] == 401, "GET /api/alvos sem cookie -> 401")
status, _, set_cookie = http("POST", "/api/login", {"usuario": "painel1", "senha": "redes2026"})
cookie = set_cookie.split(";")[0] if set_cookie else None
verificar(status == 200 and cookie and cookie.startswith("sessao="), "login correto -> 200 + cookie")

status, alvos, _ = http("GET", "/api/alvos", cookie=cookie)
teste = [a for a in alvos if a["alvo"] == PREFIXO + "-ok:80"] if status == 200 else []
verificar(teste and teste[0]["tcp_ms"] == 12.5 and teste[0]["http_ms"] == 30.25, "alvo de teste aparece com os tempos enviados")
status, agentes, _ = http("GET", "/api/agentes", cookie=cookie)
verificar(status == 200 and {"agente_id": "agente-05", "online": True} in agentes, "agente-05 aparece online")
status, medicoes, _ = http("GET", "/api/medicoes?alvo=%s-ok:80&limite=5" % PREFIXO, cookie=cookie)
verificar(status == 200 and medicoes and medicoes[0]["alvo"] == PREFIXO + "-ok:80", "medição aparece no histórico")
verificar(http("GET", "/api/medicoes?limite=abc", cookie=cookie)[0] == 400, "limite inválido -> 400")
verificar(http("PUT", "/api/regras/999", {"limiar": 1, "consecutivas": 1, "nivel": "aviso"}, cookie)[0] == 404, "regra inexistente -> 404")
verificar(http("PUT", "/api/regras/2", {"limiar": 1, "consecutivas": 0, "nivel": "aviso"}, cookie)[0] == 400, "consecutivas = 0 -> 400")
verificar(http("GET", "/api/nada", cookie=cookie)[0] == 404, "rota inexistente -> 404")
status, corpo, _ = http("POST", "/api/carga", {"x": "y" * 1000}, cookie)
verificar(status == 200 and corpo["bytes"] > 1000, "POST /api/carga devolve o tamanho recebido")

print("\n[Alertas]")
regra2 = [r for r in http("GET", "/api/regras", cookie=cookie)[1] if r["id"] == 2][0]   # para restaurar no fim
_, antes, _ = http("GET", "/api/alertas?limite=1", cookie=cookie)
maior = antes[0]["id"] if antes else 0
comando(s, "MEDICAO %s-caiu:80 DOWN - -" % PREFIXO)
verificar(not http("GET", "/api/alertas?desde=%d" % maior, cookie=cookie)[1], "1 medição DOWN (regra pede 2) -> sem alerta")
comando(s, "MEDICAO %s-caiu:80 DOWN - -" % PREFIXO)
novos = http("GET", "/api/alertas?desde=%d" % maior, cookie=cookie)[1]
verificar(len(novos) == 1 and "fora do ar" in novos[0]["mensagem"], "2ª medição DOWN seguida -> alerta 'fora do ar'")
comando(s, "MEDICAO %s-caiu:80 DOWN - -" % PREFIXO)
verificar(len(http("GET", "/api/alertas?desde=%d" % maior, cookie=cookie)[1]) == 1, "3ª medição DOWN -> não repete o alerta")
http("PUT", "/api/regras/2", {"limiar": 100, "consecutivas": 1, "nivel": "aviso"}, cookie)
comando(s, "MEDICAO %s-lento:443 UP 150 -" % PREFIXO)
novos = http("GET", "/api/alertas?desde=%d" % maior, cookie=cookie)[1]
verificar(len(novos) == 2 and "tcp_ms" in novos[0]["mensagem"], "tcp_ms 150 com limiar 100 -> alerta de lentidão")
http("PUT", "/api/regras/2", {"limiar": regra2["limiar"], "consecutivas": regra2["consecutivas"], "nivel": regra2["nivel"]}, cookie)

verificar(comando(s, "BYE") == "200 OK tchau" and fechou(s), "BYE -> 200 OK e conexão fechada")
s.close()
s = conectar()
comando(s, "HELLO agente-05 chave-05")
s.close()   # sai sem BYE, como se o agente tivesse caído
time.sleep(0.5)
ultimo = http("GET", "/api/alertas?limite=1", cookie=cookie)[1]
verificar(ultimo and "offline" in ultimo[0]["mensagem"], "agente sai sem BYE -> alerta 'offline'")

print("\n%d de %d verificações passaram" % (sum(resultados), len(resultados)))
sys.exit(0 if all(resultados) else 1)
