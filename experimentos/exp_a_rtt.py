"""
Experimento A: RTT e tempo de resposta (pelo menos 30 medições por condição).

Três tipos de medida:
  - ping_app:      RTT da APLICAÇÃO. Tempo entre enviar "PING" pelo canal TCP do NetMon e receber
                   o "PONG". Inclui o processamento no servidor (C2 24: RTT = ida e volta).
  - resposta_http: tempo de resposta do servidor HTTP do painel: GET / repetido numa conexão
                   persistente (C2 25), do envio da requisição até o fim da resposta.
  - connect_tcp:   tempo do connect() até um alvo. O connect() termina quando chega o SYN-ACK
                   (handshake de 3 vias, C3 99-104), então mede aproximadamente 1 RTT de rede.

Como ilustração das fórmulas do C3 85-86, o script também aplica às amostras o cálculo do
EstimatedRTT, do DevRTT e do TimeoutInterval. Atenção: o TCP faz essa conta com as amostras dele
(segmento -> ACK), não com o RTT da aplicação.

Uso (com o servidor NetMon rodando):
    python3 experimentos/exp_a_rtt.py --servidor 127.0.0.1 --condicao local
    python3 experimentos/exp_a_rtt.py --servidor 127.0.0.1 --condicao local --http
    python3 experimentos/exp_a_rtt.py --alvo gaia.cs.umass.edu:80 --condicao internet
"""
import argparse
import time
from socket import *

from comum import conectar_agente, enviar_comando, http_pedido, mostrar_estatisticas, salvar_csv


def medir_ping(servidor, n, pausa):
    s = conectar_agente(servidor, "agente-04", "chave-04")
    rtts = []
    for i in range(n):
        inicio = time.perf_counter()
        resposta = enviar_comando(s, "PING %d" % i)
        rtt = (time.perf_counter() - inicio) * 1000
        if resposta != "200 PONG %d" % i:
            print("resposta inesperada:", resposta)
            continue
        rtts.append(rtt)
        time.sleep(pausa)
    enviar_comando(s, "BYE")
    s.close()
    return rtts


def medir_http(servidor, porta, n, pausa):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(10)
    s.connect((servidor, porta))
    tempos = []
    for i in range(n):
        inicio = time.perf_counter()
        cabecalhos, _ = http_pedido(s, "GET", "/", servidor)
        tempo = (time.perf_counter() - inicio) * 1000
        if cabecalhos.startswith("HTTP/1.1 200"):
            tempos.append(tempo)
        time.sleep(pausa)
    s.close()
    return tempos


def medir_connect(host, porta, n, pausa):
    ip = gethostbyname(host)   # DNS fora do cronômetro
    rtts = []
    for i in range(n):
        s = socket(AF_INET, SOCK_STREAM)
        s.settimeout(3)
        inicio = time.perf_counter()
        try:
            s.connect((ip, porta))
            rtts.append((time.perf_counter() - inicio) * 1000)
        except OSError as erro:
            print("medição %d falhou: %s" % (i, erro))
        finally:
            s.close()
        time.sleep(pausa)
    return rtts


def rtt_estimado(amostras, alfa=0.125, beta=0.25):
    """EstimatedRTT e DevRTT pelas fórmulas do C3 85-86, começando com a primeira amostra e DevRTT = 0."""
    estimado, desvio = amostras[0], 0.0
    for amostra in amostras[1:]:
        estimado = (1 - alfa) * estimado + alfa * amostra
        desvio = (1 - beta) * desvio + beta * abs(amostra - estimado)
    return estimado, desvio


def main():
    parser = argparse.ArgumentParser(description="Experimento A: RTT e tempo de resposta")
    parser.add_argument("--servidor", default="127.0.0.1", help="IP do servidor NetMon")
    parser.add_argument("--http", action="store_true", help="mede o tempo de resposta HTTP do painel")
    parser.add_argument("--porta-http", type=int, default=8765)
    parser.add_argument("--alvo", help="host:porta para medir o tempo de connect()")
    parser.add_argument("--condicao", required=True, help="nome da condição, ex.: local, lan, internet, atraso50ms")
    parser.add_argument("--n", type=int, default=30, help="número de medições (mínimo 30 pelo enunciado)")
    parser.add_argument("--pausa", type=float, default=0.1, help="segundos entre medições")
    args = parser.parse_args()

    if args.alvo:
        host, _, porta = args.alvo.rpartition(":")
        tipo, destino = "connect_tcp", args.alvo
        tempos = medir_connect(host, int(porta), args.n, args.pausa)
    elif args.http:
        tipo, destino = "resposta_http", "%s:%d" % (args.servidor, args.porta_http)
        tempos = medir_http(args.servidor, args.porta_http, args.n, args.pausa)
    else:
        tipo, destino = "ping_app", "%s:5050" % args.servidor
        tempos = medir_ping(args.servidor, args.n, args.pausa)

    if len(tempos) < 2:
        raise SystemExit("poucas medições válidas")
    mostrar_estatisticas("%s (%s, %s)" % (tipo, destino, args.condicao), tempos)
    estimado, desvio = rtt_estimado(tempos)
    print("ilustração C3 85-86: EstimatedRTT=%.3f ms  DevRTT=%.3f ms  TimeoutInterval=%.3f ms" % (
        estimado, desvio, estimado + 4 * desvio))
    salvar_csv("exp_a_rtt.csv", ["condicao", "tipo", "destino", "i", "rtt_ms"],
               [(args.condicao, tipo, destino, i, "%.4f" % t) for i, t in enumerate(tempos)])


if __name__ == "__main__":
    main()
