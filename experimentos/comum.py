"""
Funções usadas por todos os experimentos: conversar com o servidor NetMon (canal TCP e HTTP),
calcular estatísticas e salvar resultados em CSV (na pasta resultados/).
"""
import csv
import statistics
from datetime import datetime
from pathlib import Path
from socket import *

PASTA_RESULTADOS = Path(__file__).resolve().parent.parent / "resultados"


def receber_linha(s):
    """Lê do socket até chegar o '\\n'. O TCP é um fluxo de bytes e pode entregar
    a resposta em mais de um pedaço (C3 80, C2 101)."""
    dados = b""
    while not dados.endswith(b"\n"):
        pedaco = s.recv(1024)
        if not pedaco:
            raise ConnectionError("o servidor fechou a conexão")
        dados = dados + pedaco
    return dados.decode().strip()


def enviar_comando(s, linha):
    s.sendall((linha + "\n").encode())
    return receber_linha(s)


def conectar_agente(servidor, agente_id, chave, porta=5050):
    """Abre a conexão TCP com o NetMon e faz o HELLO. Devolve o socket pronto."""
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(10)
    s.connect((servidor, porta))
    resposta = enviar_comando(s, "HELLO %s %s" % (agente_id, chave))
    if not resposta.startswith("200"):
        raise SystemExit("HELLO de %s recusado: %s (desligue os outros agentes)" % (agente_id, resposta))
    return s


def http_pedido(s, metodo, caminho, host, corpo=b"", cookie=""):
    """Envia uma requisição HTTP/1.1 montada à mão (formato do slide C2 27) por um socket TCP
    já conectado e devolve (cabeçalhos da resposta, corpo da resposta)."""
    pedido = "%s %s HTTP/1.1\r\nHost: %s\r\nContent-Length: %d\r\n" % (metodo, caminho, host, len(corpo))
    if cookie:
        pedido += "Cookie: %s\r\n" % cookie
    pedido += "\r\n"
    s.sendall(pedido.encode() + corpo)

    recebido = b""
    while b"\r\n\r\n" not in recebido:            # lê até a linha em branco que termina os cabeçalhos
        pedaco = s.recv(4096)
        if not pedaco:
            raise ConnectionError("o servidor fechou a conexão")
        recebido = recebido + pedaco
    cabecalhos, resto = recebido.split(b"\r\n\r\n", 1)
    cabecalhos = cabecalhos.decode()
    tamanho = 0
    for linha in cabecalhos.split("\r\n")[1:]:
        nome, _, valor = linha.partition(":")
        if nome.lower() == "content-length":
            tamanho = int(valor)
    while len(resto) < tamanho:                   # lê o corpo até completar o Content-Length
        pedaco = s.recv(4096)
        if not pedaco:
            raise ConnectionError("o servidor fechou a conexão no meio da resposta")
        resto = resto + pedaco
    return cabecalhos, resto


def login_http(s, host):
    """Faz o login no painel e devolve o cookie de sessão (ex.: 'sessao=ab12...')."""
    corpo = b'{"usuario": "painel1", "senha": "redes2026"}'
    cabecalhos, _ = http_pedido(s, "POST", "/api/login", host, corpo)
    for linha in cabecalhos.split("\r\n"):
        if linha.lower().startswith("set-cookie:"):
            return linha.split(":", 1)[1].strip().split(";")[0]
    raise SystemExit("login recusado")


def estatisticas(valores):
    """Média, mediana, desvio padrão, mínimo e máximo de uma lista de números."""
    return {
        "n": len(valores),
        "media": statistics.mean(valores),
        "mediana": statistics.median(valores),
        "desvio": statistics.stdev(valores) if len(valores) > 1 else 0.0,
        "minimo": min(valores),
        "maximo": max(valores),
    }


def mostrar_estatisticas(titulo, valores, unidade="ms"):
    e = estatisticas(valores)
    print("%s: n=%d  média=%.3f  mediana=%.3f  desvio=%.3f  mín=%.3f  máx=%.3f (%s)" % (
        titulo, e["n"], e["media"], e["mediana"], e["desvio"], e["minimo"], e["maximo"], unidade))
    return e


def salvar_csv(nome, cabecalho, linhas):
    """Acrescenta linhas em resultados/<nome>. Cada linha ganha a data e hora da execução,
    assim várias execuções (condições diferentes) ficam no mesmo arquivo."""
    PASTA_RESULTADOS.mkdir(exist_ok=True)
    arquivo = PASTA_RESULTADOS / nome
    novo = not arquivo.exists()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if novo:
            escritor.writerow(["data_hora"] + cabecalho)
        for linha in linhas:
            escritor.writerow([agora] + list(linha))
    print("resultados acrescentados em", arquivo)
