"""
Experimento D: microteste TCP x UDP, com a mesma carga nos dois.

Envia N mensagens de mesmo tamanho, uma de cada vez, para o servidor de eco
(experimentos/eco_servidor.py) e espera a volta de cada uma. Cada mensagem leva um número
de sequência, para saber se a resposta voltou, se voltou na ordem e quanto tempo levou.

  - TCP (porta 5051): entrega confiável e em ordem (C3 80, C3 89-90). Se um segmento se perde,
    o próprio TCP retransmite depois do timeout; a aplicação só percebe um atraso maior.
  - UDP (porta 5052): sem garantia (C3 27-28). Se a mensagem ou a resposta se perde, o
    cliente espera 1 s (settimeout) e conta como perdida. Uma resposta que chega depois desse
    prazo é contada como "atrasada".

Como só uma mensagem fica em trânsito por vez, não há como as mensagens trocarem de ordem neste
teste; a ordenação é discutida pela teoria (o UDP não numera nem reordena, C3 27; o TCP entrega
em ordem pelos números de sequência, C3 80-82).

Os dois NÃO são equivalentes: o UDP não recupera perdas. O teste mostra o custo e o
comportamento de cada um com a mesma carga, não que um substitui o outro.

Uso (com experimentos/eco_servidor.py rodando):
    python3 experimentos/exp_d_tcp_udp.py --servidor 127.0.0.1 --condicao local
"""
import argparse
import time
from socket import *

from comum import mostrar_estatisticas, salvar_csv

PORTA_TCP = 5051
PORTA_UDP = 5052


def mensagem(i, tamanho):
    """Número de sequência + preenchimento até o tamanho pedido, terminando em '\\n'."""
    cabeca = ("%d|" % i).encode()
    return cabeca + b"x" * (tamanho - len(cabeca) - 1) + b"\n"


def teste_tcp(servidor, n, tamanho, pausa):
    s = socket(AF_INET, SOCK_STREAM)
    s.settimeout(10)
    s.connect((servidor, PORTA_TCP))
    resultados = []
    for i in range(n):
        dados = mensagem(i, tamanho)
        inicio = time.perf_counter()
        s.sendall(dados)
        recebido = b""
        while len(recebido) < len(dados):   # TCP é fluxo de bytes: junta os pedaços (C3 80)
            pedaco = s.recv(2048)
            if not pedaco:
                raise ConnectionError("servidor de eco fechou a conexão")
            recebido = recebido + pedaco
        rtt = (time.perf_counter() - inicio) * 1000
        resultados.append((i, "ok" if recebido == dados else "corrompida", rtt))
        time.sleep(pausa)
    s.close()
    return resultados


def teste_udp(servidor, n, tamanho, pausa):
    s = socket(AF_INET, SOCK_DGRAM)
    s.settimeout(1.0)
    resultados = []
    atrasadas = 0
    for i in range(n):
        dados = mensagem(i, tamanho)
        inicio = time.perf_counter()
        s.sendto(dados, (servidor, PORTA_UDP))
        status, rtt = "perdida", None
        while True:
            try:
                resposta, _ = s.recvfrom(2048)
            except timeout:
                break                          # não voltou em 1 s: perdida
            numero = int(resposta.split(b"|")[0])
            if numero == i:
                rtt = (time.perf_counter() - inicio) * 1000
                status = "ok"
                break
            atrasadas += 1                     # resposta de uma mensagem anterior, chegou depois do prazo
        resultados.append((i, status, rtt))
        time.sleep(pausa)
    s.close()
    return resultados, atrasadas


def resumir(protocolo, resultados, tamanho):
    ok = [r for _, status, r in resultados if status == "ok"]
    perdidas = sum(1 for _, status, _ in resultados if status != "ok")
    print("%s: %d enviadas, %d voltaram, %d perdidas (%.1f%%)" % (
        protocolo, len(resultados), len(ok), perdidas, 100.0 * perdidas / len(resultados)))
    if len(ok) > 1:
        mostrar_estatisticas("  RTT %s" % protocolo, ok)
        vazao = len(ok) * tamanho * 8 / (sum(ok) / 1000) / 1_000_000
        print("  vazão útil durante as trocas: %.3f Mbit/s" % vazao)


def main():
    parser = argparse.ArgumentParser(description="Experimento D: TCP x UDP")
    parser.add_argument("--servidor", default="127.0.0.1")
    parser.add_argument("--condicao", required=True)
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--tamanho", type=int, default=100, help="bytes por mensagem (até 1400)")
    parser.add_argument("--pausa", type=float, default=0.005, help="segundos entre mensagens")
    args = parser.parse_args()

    tcp = teste_tcp(args.servidor, args.n, args.tamanho, args.pausa)
    udp, atrasadas = teste_udp(args.servidor, args.n, args.tamanho, args.pausa)
    resumir("TCP", tcp, args.tamanho)
    resumir("UDP", udp, args.tamanho)
    print("UDP: %d respostas chegaram atrasadas, depois do prazo de 1 s" % atrasadas)

    linhas = []
    for protocolo, resultados in (("TCP", tcp), ("UDP", udp)):
        for i, status, rtt in resultados:
            linhas.append((args.condicao, protocolo, args.tamanho, i, status, "" if rtt is None else "%.4f" % rtt))
    salvar_csv("exp_d_tcp_udp.csv", ["condicao", "protocolo", "tamanho_bytes", "i", "status", "rtt_ms"], linhas)


if __name__ == "__main__":
    main()
