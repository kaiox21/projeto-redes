"""
Experimento B: throughput (vazão).

Envia corpos de tamanhos diferentes para POST /api/carga do servidor NetMon e mede o tempo até
a resposta. Vazão útil = bytes do corpo, sem os cabeçalhos HTTP, dividido pelo tempo (C1 56-58).

A requisição HTTP é montada à mão pelo socket (formato do C2 27, como no exemplo com netcat do
C2 31) e todas usam a mesma conexão TCP persistente (C2 25), para não contar um handshake por envio.

Uso (com o servidor NetMon rodando):
    python3 experimentos/exp_b_throughput.py --servidor 127.0.0.1 --condicao local
    python3 experimentos/exp_b_throughput.py --servidor 192.168.0.10 --condicao lan
"""
import argparse
import json
import time
from socket import *

from comum import http_pedido, login_http, mostrar_estatisticas, salvar_csv

TAMANHOS = [1_000, 10_000, 100_000, 1_000_000, 10_000_000]   # bytes


def main():
    parser = argparse.ArgumentParser(description="Experimento B: throughput")
    parser.add_argument("--servidor", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--condicao", required=True)
    parser.add_argument("--repeticoes", type=int, default=10)
    args = parser.parse_args()

    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(60)
    s.connect((args.servidor, args.porta))
    cookie = login_http(s, args.servidor)

    linhas = []
    for tamanho in TAMANHOS:
        corpo = b"x" * tamanho
        vazoes = []
        for repeticao in range(args.repeticoes):
            inicio = time.perf_counter()
            _, resposta = http_pedido(s, "POST", "/api/carga", args.servidor, corpo, cookie)
            segundos = time.perf_counter() - inicio
            recebido = json.loads(resposta)["bytes"]
            if recebido != tamanho:
                print("o servidor recebeu %d de %d bytes" % (recebido, tamanho))
            vazao = tamanho * 8 / segundos / 1_000_000   # Mbit/s
            vazoes.append(vazao)
            linhas.append((args.condicao, tamanho, repeticao, "%.4f" % (segundos * 1000), "%.4f" % vazao))
        mostrar_estatisticas("vazão com %d bytes (%s)" % (tamanho, args.condicao), vazoes, "Mbit/s")
    s.close()
    salvar_csv("exp_b_throughput.csv", ["condicao", "tamanho_bytes", "repeticao", "tempo_ms", "vazao_mbps"], linhas)


if __name__ == "__main__":
    main()
