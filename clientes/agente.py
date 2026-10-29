"""
NetMon: agente de medição (cliente TCP, baseado no TCPClient dos slides, C2 108).

A cada ciclo, o agente mede de verdade cada serviço-alvo:
  - tcp_ms:  quanto demora o connect(). Ele só termina depois do handshake de 3 vias
             (C3 99-104), então esse tempo é aproximadamente 1 RTT até o alvo (C2 24).
  - http_ms: só para alvos "http:". Tempo entre enviar um GET escrito à mão, como no
             exemplo com netcat (C2 31), e chegar o primeiro pedaço da resposta.
Depois envia uma linha MEDICAO para o servidor NetMon.

Cada alvo é escrito como tipo:host:porta, por exemplo:
    http:gaia.cs.umass.edu:80     (mede TCP e HTTP)
    tcp:aprender.unb.br:443       (mede só a conexão TCP)

Uso:
    python3 clientes/agente.py --agente-id agente-01 --chave chave-01
    python3 clientes/agente.py --servidor 192.168.0.10 --agente-id agente-02 --chave chave-02 \
        --alvos http:192.168.0.20:9000 tcp:aprender.unb.br:443
"""
import argparse
import time
from socket import *

TIMEOUT_MEDICAO = 3   # segundos esperando o alvo antes de considerá-lo fora do ar
ALVOS_PADRAO = ["http:gaia.cs.umass.edu:80", "tcp:aprender.unb.br:443", "http:127.0.0.1:8765"]


def medir(tipo, host, porta):
    """Mede um alvo. Devolve (estado, tcp_ms, http_ms), com None no que não foi medido."""
    try:
        ip = gethostbyname(host)   # consulta DNS antes de cronometrar, para não somar o tempo do DNS
    except OSError:
        return "DOWN", None, None
    medidor = socket(AF_INET, SOCK_STREAM)
    medidor.settimeout(TIMEOUT_MEDICAO)
    try:
        inicio = time.perf_counter()
        medidor.connect((ip, porta))
        tcp_ms = (time.perf_counter() - inicio) * 1000

        http_ms = None
        if tipo == "http":
            pedido = "GET / HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % host
            inicio = time.perf_counter()
            medidor.sendall(pedido.encode())
            resposta = medidor.recv(1024)
            http_ms = (time.perf_counter() - inicio) * 1000
            if not resposta.startswith(b"HTTP/"):
                return "DOWN", None, None    # conectou, mas não respondeu como servidor HTTP
        return "UP", tcp_ms, http_ms
    except OSError:        # conexão recusada, sem resposta no prazo, ou caiu no meio
        return "DOWN", None, None
    finally:
        medidor.close()


def receber_linha(clientSocket):
    """Lê até chegar o '\\n'. O TCP é um fluxo de bytes e pode entregar a resposta em mais de um pedaço (C3 80)."""
    dados = b""
    while not dados.endswith(b"\n"):
        pedaco = clientSocket.recv(1024)
        if not pedaco:
            raise ConnectionError("o servidor fechou a conexão")
        dados = dados + pedaco
    return dados.decode().strip()


def enviar_comando(clientSocket, linha):
    """Envia uma linha do protocolo e devolve a resposta do servidor."""
    clientSocket.sendall((linha + "\n").encode())
    return receber_linha(clientSocket)


def em_ms(valor):
    return "-" if valor is None else "%.2f" % valor


def sessao(args, alvos):
    """Uma conexão com o servidor: HELLO e depois medições até cair ou Ctrl+C.
    Devolve False quando não vale a pena reconectar."""
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.settimeout(10)
    try:
        clientSocket.connect((args.servidor, args.porta))
        resposta = enviar_comando(clientSocket, "HELLO %s %s" % (args.agente_id, args.chave))
        print("[%s] %s" % (args.agente_id, resposta), flush=True)
        if resposta.startswith("401"):
            return False    # chave errada: tentar de novo não resolve
        if not resposta.startswith("200"):
            # ex.: 403 JA_CONECTADO, quando o servidor ainda não percebeu que a conexão antiga caiu
            raise ConnectionError(resposta)
        while True:
            for tipo, host, porta in alvos:
                estado, tcp_ms, http_ms = medir(tipo, host, porta)
                linha = "MEDICAO %s:%d %s %s %s" % (host, porta, estado, em_ms(tcp_ms), em_ms(http_ms))
                resposta = enviar_comando(clientSocket, linha)
                print("[%s] %s -> %s" % (args.agente_id, linha, resposta), flush=True)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        try:
            print("[%s] %s" % (args.agente_id, enviar_comando(clientSocket, "BYE")), flush=True)
        except OSError:
            pass
        return False
    finally:
        clientSocket.close()


def ler_alvos(textos):
    """Converte 'http:host:porta' em ('http', 'host', porta)."""
    alvos = []
    for texto in textos:
        tipo, _, resto = texto.partition(":")
        host, _, porta = resto.rpartition(":")
        if tipo not in ("http", "tcp") or not host or not porta.isdigit():
            raise SystemExit("alvo inválido: %s (use http:host:porta ou tcp:host:porta)" % texto)
        alvos.append((tipo, host, int(porta)))
    return alvos


def main():
    parser = argparse.ArgumentParser(description="Agente de medição NetMon")
    parser.add_argument("--servidor", default="127.0.0.1", help="IP do servidor NetMon")
    parser.add_argument("--porta", type=int, default=5050)
    parser.add_argument("--agente-id", default="agente-01")
    parser.add_argument("--chave", default="chave-01")
    parser.add_argument("--alvos", nargs="+", default=ALVOS_PADRAO, help="lista de tipo:host:porta")
    parser.add_argument("--intervalo", type=float, default=5, help="segundos entre ciclos (até 20)")
    args = parser.parse_args()
    if not 0 < args.intervalo <= 20:
        # o servidor derruba quem fica 30 s sem mandar nada; 20 s deixa folga para as medições
        raise SystemExit("--intervalo deve ser maior que 0 e no máximo 20 segundos")
    alvos = ler_alvos(args.alvos)

    try:
        while True:
            try:
                if sessao(args, alvos) is False:
                    break
            except OSError as erro:   # servidor fora do ar ou conexão caída
                print("[%s] sem conexão com o servidor (%s); nova tentativa em 3 s" % (args.agente_id, erro), flush=True)
                time.sleep(3)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
