# Roteiro final: testar tudo de uma vez (no Mac)

Siga na ordem. Cada passo diz o que deve aparecer. Se algo diferente aparecer, pare e anote a mensagem.
Tempo estimado: 1 h sem o Experimento E e o Wireshark; 2 h com tudo.

Em todos os terminais, comece por:
```bash
cd caminho/para/projeto-redes      # a pasta onde você clonou ou descompactou o repositório
```

## 0. Começar do zero

```bash
kill $(lsof -t -i :5050) $(lsof -t -i :8765) 2>/dev/null   # encerra NetMon antigo, se houver
rm -rf dados resultados logs
```

## 1. Servidor e teste do protocolo (5 min)

| Terminal | Comando | O que deve aparecer |
|---|---|---|
| 1 | `python3 servidor/servidor.py` | `TCP esperando agentes na porta 5050` e `HTTP painel em http://127.0.0.1:8765` |
| 2 | `python3 testes/teste_protocolo.py` | `38 de 38 verificações passaram` |
| 2 | `python3 testes/teste_protocolo.py` de novo | `38 de 38` outra vez (o teste pode ser repetido) |

Se aparecer `ERRO: a porta ... já está sendo usada`, volte ao passo 0.

O teste grava alvos de teste (`t<número>-ok`, `-caiu`, `-lento`). Para a demonstração ficar limpa:
pare o servidor (Ctrl+C no terminal 1), rode `rm -rf dados` e suba o servidor de novo.

## 2. Agentes e painel (10 min)

| Terminal | Comando | O que deve aparecer |
|---|---|---|
| 3 | `python3 -m http.server 9000` | `Serving HTTP on ... port 9000` (alvo local) |
| 2 | `python3 clientes/agente.py --agente-id agente-01 --chave chave-01 --intervalo 3` | linhas `MEDICAO gaia.cs.umass.edu:80 UP ... -> 200 OK ...` |
| 4 | `python3 clientes/agente.py --agente-id agente-02 --chave chave-02 --alvos http:127.0.0.1:9000 tcp:127.0.0.1:9` | `127.0.0.1:9000 UP` e `127.0.0.1:9 DOWN` |

No navegador, abra **http://127.0.0.1:8765**, com `painel1` / `redes2026`, e confira:
- [ ] tabela "Serviços monitorados" com gaia, aprender, 127.0.0.1:8765, :9000 e :9
- [ ] alerta "127.0.0.1:9 fora do ar" em poucos segundos
- [ ] agentes 01 e 02 como online
- [ ] em outra janela anônima, `painel2` entra ao mesmo tempo (dois clientes simultâneos)
- [ ] pare o terminal 3 (Ctrl+C): em ~10 s (duas medições do agente-02) aparece o alerta "127.0.0.1:9000 fora do ar"
- [ ] pare o terminal 4 (Ctrl+C): o agente-02 fica offline, sem alerta (saiu com BYE)
- [ ] em "Regras", mude o limiar da conexão TCP para 1 ms e salve: surge alerta de lentidão da gaia
      depois de 3 medições. Volte para 200 depois.
- [ ] em "Histórico", consulte um alvo
- [ ] pare o servidor (terminal 1) por 10 s e suba de novo: o painel mostra "servidor indisponível"
      e depois volta; o agente-01 reconecta sozinho

Pare o agente-01 (Ctrl+C) antes dos experimentos.

## 3. Experimentos A a D, condição local (15 min)

Terminal 1: servidor rodando. Terminal 3: `python3 experimentos/eco_servidor.py`.
```bash
python3 experimentos/exp_a_rtt.py --condicao local
python3 experimentos/exp_a_rtt.py --condicao local --http
python3 experimentos/exp_a_rtt.py --alvo gaia.cs.umass.edu:80 --condicao internet
python3 experimentos/exp_a_rtt.py --alvo aprender.unb.br:443 --condicao internet
python3 experimentos/exp_b_throughput.py --condicao local
python3 experimentos/exp_c_concorrencia.py --condicao local
python3 experimentos/exp_d_tcp_udp.py --condicao local
```
Cada um imprime as estatísticas e termina com `resultados acrescentados em .../resultados/...csv`.

## 4. Condição lan (20 min, com o notebook de um colega)

No Mac: `ipconfig getifaddr en0` (anote o IP). No notebook do colega, com a pasta do projeto:
```bash
python3 experimentos/exp_a_rtt.py --servidor <IP do Mac> --condicao lan
python3 experimentos/exp_a_rtt.py --servidor <IP do Mac> --condicao lan --http
python3 experimentos/exp_b_throughput.py --servidor <IP do Mac> --condicao lan
python3 experimentos/exp_c_concorrencia.py --servidor <IP do Mac> --condicao lan
python3 experimentos/exp_d_tcp_udp.py --servidor <IP do Mac> --condicao lan
```
Os CSVs ficam no notebook do colega: copie a pasta `resultados/` dele para o Mac e junte as linhas
nos CSVs do Mac (a primeira linha de cada arquivo, o cabeçalho, aparece uma vez só).

## 5. Experimento E (30 min)

Siga `docs/EXPERIMENTOS.md`, seção E. Rode de novo A (sem `--alvo`, com e sem `--http`), B, C e D com
`--condicao atraso50ms` e `--condicao perda2`. Anote onde a emulação foi aplicada. **Desfaça a emulação
no fim.**

## 6. Gráficos (2 min)

```bash
python3 -m venv .venv && .venv/bin/pip install matplotlib     # só na primeira vez
.venv/bin/python experimentos/graficos.py
```
Abra os 4 PNGs em `resultados/graficos/`.

## 7. Wireshark (30 min)

Siga `docs/WIRESHARK.md`: quatro capturas, salvas em `capturas/`, com prints.

## 8. Desligar tudo

Ctrl+C em cada terminal, ou:
```bash
kill $(lsof -t -i :5050) $(lsof -t -i :8765) $(lsof -t -i :5052) 2>/dev/null
```
