"""
Gera os gráficos do relatório a partir dos CSVs em resultados/.

Precisa do matplotlib (biblioteca externa, só para os gráficos):
    pip3 install matplotlib

Uso:
    python3 experimentos/graficos.py
Os gráficos ficam em resultados/graficos/.
"""
import csv
import statistics
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")    # gera arquivos sem abrir janela
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
except ImportError:
    raise SystemExit("Instale o matplotlib primeiro: pip3 install matplotlib")

RESULTADOS = Path(__file__).resolve().parent.parent / "resultados"
GRAFICOS = RESULTADOS / "graficos"


# ordem das condições nos gráficos e nomes curtos para os rótulos
ORDEM = ["local", "lan", "atraso50ms", "perda2", "internet"]
NOME_COND = {"atraso50ms": "+50 ms", "perda2": "perda 2%"}
NOME_TIPO = {"ping_app": "ping", "resposta_http": "HTTP", "connect_tcp": "connect"}


def posicao(cond):
    return ORDEM.index(cond) if cond in ORDEM else len(ORDEM)


def ler(nome):
    arquivo = RESULTADOS / nome
    if not arquivo.exists():
        print("sem dados:", nome)
        return []
    with open(arquivo, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def salvar(nome):
    plt.tight_layout()
    plt.savefig(GRAFICOS / nome, dpi=200)
    plt.close()
    print("gerado:", GRAFICOS / nome)


def grafico_a():
    linhas = ler("exp_a_rtt.csv")
    if not linhas:
        return
    grupos, chaves = {}, {}
    for l in linhas:
        cond = l["condicao"]
        lugar = l["destino"].split(".")[0] if cond == "internet" else NOME_COND.get(cond, cond)
        rotulo = "%s\n%s" % (NOME_TIPO.get(l["tipo"], l["tipo"]), lugar)
        grupos.setdefault(rotulo, []).append(float(l["rtt_ms"]))
        chaves[rotulo] = (posicao(cond), l["tipo"], lugar)
    nomes = sorted(grupos, key=lambda n: chaves[n])
    plt.figure(figsize=(7, 3.5))
    plt.boxplot([grupos[n] for n in nomes])
    plt.xticks(range(1, len(nomes) + 1), nomes, fontsize=8)
    plt.ylabel("RTT (ms, escala logarítmica)")
    plt.yscale("log")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))   # mostra 0.1, 1, 10 em vez de 10^-1
    plt.title("Experimento A: RTT por condição (pelo menos %s medições por grupo)" % min(len(v) for v in grupos.values()), fontsize=10)
    plt.grid(axis="y", alpha=0.3)
    salvar("exp_a_rtt.png")


def grafico_b():
    linhas = ler("exp_b_throughput.csv")
    if not linhas:
        return
    condicoes = sorted(set(l["condicao"] for l in linhas))
    plt.figure(figsize=(6, 3.5))
    for c in condicoes:
        tamanhos = sorted(set(int(l["tamanho_bytes"]) for l in linhas if l["condicao"] == c))
        medias = [statistics.mean(float(l["vazao_mbps"]) for l in linhas
                                  if l["condicao"] == c and int(l["tamanho_bytes"]) == t) for t in tamanhos]
        plt.plot(tamanhos, medias, marker="o", label=c)
    plt.xscale("log")
    plt.yscale("log")
    plt.xlabel("tamanho do corpo enviado (bytes, escala logarítmica)")
    plt.ylabel("vazão útil média (Mbit/s, escala log.)")
    plt.title("Experimento B: vazão por tamanho de mensagem", fontsize=10)
    plt.legend(fontsize=8)
    plt.grid(alpha=0.3)
    salvar("exp_b_throughput.png")


def grafico_c():
    linhas = ler("exp_c_concorrencia.csv")
    if not linhas:
        return
    condicoes = sorted(set(l["condicao"] for l in linhas))
    figura, (esq, dir) = plt.subplots(1, 2, figsize=(7, 3.2))
    for n, c in enumerate(condicoes):
        cor = "C%d" % n    # mesma cor para a condição nos dois painéis
        ks = sorted(set(int(l["clientes"]) for l in linhas if l["condicao"] == c))
        medias, p95s, taxas = [], [], []
        for k in ks:
            grupo = [l for l in linhas if l["condicao"] == c and int(l["clientes"]) == k]
            atrasos = sorted(float(l["atraso_ms"]) for l in grupo)
            medias.append(statistics.mean(atrasos))
            p95s.append(atrasos[int(0.95 * len(atrasos)) - 1])
            # cada execução grava a sua taxa; tira a média entre execuções
            taxas.append(statistics.mean(set(float(l["taxa_total_msg_s"]) for l in grupo)))
        esq.plot(ks, medias, marker="o", color=cor, label="%s (média)" % c)
        esq.plot(ks, p95s, marker="s", linestyle="--", color=cor, label="%s (p95)" % c)
        dir.plot(ks, taxas, marker="o", color=cor, label=c)
    esq.set_xlabel("agentes simultâneos")
    esq.set_ylabel("atraso por mensagem (ms)")
    dir.set_xlabel("agentes simultâneos")
    dir.set_ylabel("taxa total (mensagens/s)")
    for eixo in (esq, dir):
        eixo.set_xticks([1, 2, 5])
        eixo.set_ylim(bottom=0)
        eixo.grid(alpha=0.3)
    esq.legend(fontsize=7)
    dir.legend(fontsize=7)
    figura.suptitle("Experimento C: concorrência (p95 = 95% das mensagens tiveram atraso até esse valor)", fontsize=9)
    salvar("exp_c_concorrencia.png")


def grafico_d():
    linhas = ler("exp_d_tcp_udp.csv")
    if not linhas:
        return
    grupos, perdas, ordem_d = {}, {}, {}
    for l in linhas:
        chave = "%s\n%s" % (l["protocolo"], NOME_COND.get(l["condicao"], l["condicao"]))
        ordem_d[chave] = (l["protocolo"], posicao(l["condicao"]))
        grupos.setdefault(chave, [])
        perdas.setdefault(chave, [0, 0])
        perdas[chave][1] += 1
        if l["status"] == "ok":
            grupos[chave].append(float(l["rtt_ms"]))
        else:
            perdas[chave][0] += 1
    nomes = sorted(grupos, key=lambda n: ordem_d[n])
    figura, (esq, dir) = plt.subplots(1, 2, figsize=(8, 3.4))
    esq.boxplot([grupos[n] if grupos[n] else [0] for n in nomes])
    esq.set_xticks(range(1, len(nomes) + 1))
    esq.set_xticklabels(nomes, fontsize=6)
    esq.set_ylabel("RTT das mensagens entregues\n(ms, escala logarítmica)")
    esq.set_yscale("log")   # local (~0,1 ms) e lan (~10 ms) no mesmo eixo
    esq.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    dir.bar(range(len(nomes)), [100.0 * perdas[n][0] / perdas[n][1] for n in nomes])
    dir.set_xticks(range(len(nomes)))
    dir.set_xticklabels(nomes, fontsize=6)
    dir.set_ylabel("mensagens perdidas (%)")
    dir.set_ylim(0, max(5, max(100.0 * perdas[n][0] / perdas[n][1] for n in nomes) * 1.2))
    for i, n in enumerate(nomes):   # escreve o valor em cima da barra, mesmo quando é 0
        dir.text(i, 100.0 * perdas[n][0] / perdas[n][1], "%d/%d" % (perdas[n][0], perdas[n][1]),
                 ha="center", va="bottom", fontsize=6)
    for eixo in (esq, dir):
        eixo.grid(axis="y", alpha=0.3)
    figura.suptitle("Experimento D: TCP x UDP com a mesma carga", fontsize=10)
    salvar("exp_d_tcp_udp.png")


if __name__ == "__main__":
    GRAFICOS.mkdir(parents=True, exist_ok=True)
    grafico_a()
    grafico_b()
    grafico_c()
    grafico_d()
