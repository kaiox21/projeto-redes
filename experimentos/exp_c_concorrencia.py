"""
Experimento C: concorrência com 1, 2 e 5 agentes ao mesmo tempo.

Cada agente tem sua própria conexão TCP (no servidor, cada conexão é um socket diferente,
identificado pela 4-tupla, C3 23) e roda numa thread. Todos enviam o mesmo número de MEDICAO,
esperando a resposta de cada uma. Para cada mensagem, mede o atraso entre enviar e receber a
resposta; no fim, calcula a taxa total de mensagens por segundo.

Rode com os outros agentes DESLIGADOS: o experimento usa os agentes 01 a 05.

Uso (com o servidor NetMon rodando):
    python3 experimentos/exp_c_concorrencia.py --servidor 127.0.0.1 --condicao local
"""
import argparse
import threading
import time

from comum import conectar_agente, enviar_comando, estatisticas, salvar_csv


def rodar_agente(s, numero, mensagens, atrasos):
    for i in range(mensagens):
        inicio = time.perf_counter()
        resposta = enviar_comando(s, "MEDICAO exp-c:%d UP 1.00 -" % numero)
        atraso = (time.perf_counter() - inicio) * 1000
        if resposta.startswith("200"):
            atrasos.append((numero, i, atraso))
    enviar_comando(s, "BYE")
    s.close()


def main():
    parser = argparse.ArgumentParser(description="Experimento C: concorrência")
    parser.add_argument("--servidor", default="127.0.0.1")
    parser.add_argument("--condicao", required=True)
    parser.add_argument("--clientes", type=int, nargs="+", default=[1, 2, 5])
    parser.add_argument("--mensagens", type=int, default=200, help="mensagens por agente")
    args = parser.parse_args()

    linhas = []
    for k in args.clientes:
        # primeiro conecta todos os agentes; só depois começa a contar o tempo
        sockets = [conectar_agente(args.servidor, "agente-0%d" % n, "chave-0%d" % n) for n in range(1, k + 1)]
        atrasos = []                         # list.append é seguro entre threads em Python
        threads = []
        for n in range(1, k + 1):
            threads.append(threading.Thread(target=rodar_agente, args=(sockets[n - 1], n, args.mensagens, atrasos)))
        inicio = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        segundos = time.perf_counter() - inicio

        valores = sorted(a for _, _, a in atrasos)
        e = estatisticas(valores)
        p95 = valores[int(0.95 * len(valores)) - 1]   # 95% das mensagens tiveram atraso até esse valor
        taxa = len(atrasos) / segundos
        print("%d agente(s): %d mensagens em %.2f s -> %.1f msg/s | atraso média=%.3f mediana=%.3f "
              "p95=%.3f desvio=%.3f máx=%.3f ms" % (k, len(atrasos), segundos, taxa, e["media"], e["mediana"],
                                                  p95, e["desvio"], e["maximo"]))
        for numero, i, atraso in atrasos:
            linhas.append((args.condicao, k, numero, i, "%.4f" % atraso, "%.2f" % taxa))
    salvar_csv("exp_c_concorrencia.csv", ["condicao", "clientes", "agente", "i", "atraso_ms", "taxa_total_msg_s"], linhas)


if __name__ == "__main__":
    main()
