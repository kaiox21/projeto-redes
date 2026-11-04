# Resumo dos experimentos: condição "local" (e "internet" do exp. A)

Rodados em 2026-11-03, das 20:47 às 20:48, no Mac (IP na Wi-Fi: 172.29.123.135).
Python 3.9.6. Nenhum agente ligado durante os experimentos.

Teste do protocolo (`testes/teste_protocolo.py`): **38 de 38 verificações passaram**.
Depois do teste, a pasta `dados/` foi apagada e o servidor foi reiniciado antes dos experimentos.

Os dados brutos estão nos CSVs desta pasta (coluna `condicao`) e os gráficos em `graficos/`.
Abaixo está a saída que cada experimento imprimiu, copiada sem alterações.

## Experimento A: RTT

`python3 experimentos/exp_a_rtt.py --condicao local`
```
ping_app (127.0.0.1:5050, local): n=30  média=0.137  mediana=0.129  desvio=0.044  mín=0.056  máx=0.238 (ms)
ilustração C3 85-86: EstimatedRTT=0.130 ms  DevRTT=0.021 ms  TimeoutInterval=0.215 ms
```

`python3 experimentos/exp_a_rtt.py --condicao local --http`
```
resposta_http (127.0.0.1:8765, local): n=30  média=0.722  mediana=0.527  desvio=0.875  mín=0.293  máx=5.233 (ms)
ilustração C3 85-86: EstimatedRTT=0.661 ms  DevRTT=0.194 ms  TimeoutInterval=1.437 ms
```

`python3 experimentos/exp_a_rtt.py --alvo gaia.cs.umass.edu:80 --condicao internet`
```
connect_tcp (gaia.cs.umass.edu:80, internet): n=30  média=163.477  mediana=155.955  desvio=19.479  mín=153.513  máx=239.248 (ms)
ilustração C3 85-86: EstimatedRTT=158.962 ms  DevRTT=5.793 ms  TimeoutInterval=182.133 ms
```

`python3 experimentos/exp_a_rtt.py --alvo aprender.unb.br:443 --condicao internet`
```
connect_tcp (aprender.unb.br:443, internet): n=30  média=10.116  mediana=6.285  desvio=14.532  mín=4.770  máx=85.641 (ms)
ilustração C3 85-86: EstimatedRTT=7.848 ms  DevRTT=2.415 ms  TimeoutInterval=17.506 ms
```

## Experimento B: vazão

`python3 experimentos/exp_b_throughput.py --condicao local`
```
vazão com 1000 bytes (local): n=10  média=77.386  mediana=79.602  desvio=6.936  mín=65.107  máx=85.830 (Mbit/s)
vazão com 10000 bytes (local): n=10  média=813.131  mediana=811.164  desvio=148.128  mín=583.409  máx=1005.227 (Mbit/s)
vazão com 100000 bytes (local): n=10  média=8143.419  mediana=8228.803  desvio=954.950  mín=6005.600  máx=9329.446 (Mbit/s)
vazão com 1000000 bytes (local): n=10  média=44859.960  mediana=53494.366  desvio=18111.988  mín=16131.764  máx=59627.181 (Mbit/s)
vazão com 10000000 bytes (local): n=10  média=33161.985  mediana=31925.983  desvio=6927.561  mín=22128.484  máx=45542.966 (Mbit/s)
```

## Experimento C: concorrência

`python3 experimentos/exp_c_concorrencia.py --condicao local`
```
1 agente(s): 200 mensagens em 0.09 s -> 2172.3 msg/s | atraso média=0.459 mediana=0.431 p95=0.630 desvio=0.088 máx=0.860 ms
2 agente(s): 400 mensagens em 0.21 s -> 1938.9 msg/s | atraso média=0.858 mediana=0.461 p95=2.959 desvio=2.388 máx=41.846 ms
5 agente(s): 1000 mensagens em 0.48 s -> 2081.0 msg/s | atraso média=2.033 mediana=0.428 p95=5.138 desvio=9.337 máx=145.148 ms
```

## Experimento D: TCP × UDP

`python3 experimentos/exp_d_tcp_udp.py --condicao local`
```
TCP: 500 enviadas, 500 voltaram, 0 perdidas (0.0%)
  RTT TCP: n=500  média=0.098  mediana=0.097  desvio=0.028  mín=0.046  máx=0.457 (ms)
  vazão útil durante as trocas: 8.182 Mbit/s
UDP: 500 enviadas, 500 voltaram, 0 perdidas (0.0%)
  RTT UDP: n=500  média=0.120  mediana=0.112  desvio=0.036  mín=0.044  máx=0.455 (ms)
  vazão útil durante as trocas: 6.690 Mbit/s
UDP: 0 respostas chegaram atrasadas, depois do prazo de 1 s
```

## Arquivos gerados

- `exp_a_rtt.csv`, `exp_b_throughput.csv`, `exp_c_concorrencia.csv`, `exp_d_tcp_udp.csv`
- `graficos/exp_a_rtt.png`, `graficos/exp_b_throughput.png`, `graficos/exp_c_concorrencia.png`, `graficos/exp_d_tcp_udp.png`
