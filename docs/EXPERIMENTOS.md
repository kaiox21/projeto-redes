# Roteiro dos experimentos (seção 5 do enunciado)

Todos os scripts ficam em `experimentos/` e usam só a biblioteca padrão do Python, exceto os
gráficos (matplotlib). Cada execução **acrescenta** linhas num CSV em `resultados/`, com a
condição escolhida em `--condicao`. Assim, rodar o mesmo script em condições diferentes junta
tudo no mesmo arquivo, e o `graficos.py` compara as condições.

Antes de começar: apague `dados/` e `resultados/` para partir do zero, e anote o hardware, o
sistema operacional, a versão do Python e o tipo de rede (Wi-Fi ou cabo). Isso vai para a seção
"Descrição do Cenário" do relatório.

## Condições

| Condição (`--condicao`) | Onde roda o quê |
|---|---|
| `local` | servidor e clientes na mesma máquina, usando `127.0.0.1` |
| `lan` | servidor no Mac, clientes no notebook de um colega, mesma rede (use o IP do Mac) |
| `internet` | só no Experimento A, modo `--alvo`: tempo de conexão até `gaia.cs.umass.edu:80` e `aprender.unb.br:443` |
| `atraso50ms`, `perda2`, ... | Experimento E: as mesmas medidas com atraso ou perda simulados |

Para descobrir o IP do Mac: `ipconfig getifaddr en0`.

## Preparação (no Mac)

Terminal 1, servidor NetMon: `python3 servidor/servidor.py`
Terminal 2, servidor de eco do Experimento D: `python3 experimentos/eco_servidor.py`

Os experimentos A e C usam os agentes 04 e 01 a 05. **Desligue os outros agentes** antes de rodá-los;
se um deles estiver ligado, o script avisa com `403 JA_CONECTADO`.

## A — RTT e tempo de resposta (mínimo de 30 medições por condição)

```bash
python3 experimentos/exp_a_rtt.py --servidor 127.0.0.1 --condicao local             # RTT da aplicação
python3 experimentos/exp_a_rtt.py --servidor 127.0.0.1 --condicao local --http      # tempo de resposta HTTP
python3 experimentos/exp_a_rtt.py --servidor <IP do Mac> --condicao lan             # no notebook do colega
python3 experimentos/exp_a_rtt.py --servidor <IP do Mac> --condicao lan --http
python3 experimentos/exp_a_rtt.py --alvo gaia.cs.umass.edu:80 --condicao internet
python3 experimentos/exp_a_rtt.py --alvo aprender.unb.br:443 --condicao internet
```
- `ping_app`: RTT da aplicação (PING → PONG no canal do NetMon). Inclui o processamento do servidor.
- `resposta_http`: tempo de resposta do servidor HTTP do painel (`GET /` numa conexão persistente).
  É a medida de "tempo de resposta" pedida na seção 4 do enunciado.
- `connect_tcp`: tempo do `connect()`, que termina no SYN-ACK. É praticamente 1 RTT de rede.
- O script mostra média, mediana, desvio padrão, mínimo e máximo. Também aplica às amostras, como
  ilustração, as fórmulas do EstimatedRTT, do DevRTT e do TimeoutInterval (C3 85–86). Cuidado ao
  comentar: o TCP faz essa conta com as amostras dele (segmento → ACK), não com o RTT da aplicação.

## B — Throughput

```bash
python3 experimentos/exp_b_throughput.py --servidor 127.0.0.1 --condicao local
python3 experimentos/exp_b_throughput.py --servidor <IP do Mac> --condicao lan      # no notebook do colega
```
Envia corpos de 1 kB, 10 kB, 100 kB, 1 MB e 10 MB, 10 vezes cada, pela mesma conexão HTTP persistente.
Vazão útil = tamanho do corpo / tempo. O que discutir:
- Com conexão persistente, cada envio custa cerca de 1 RTT mais o tempo de transmissão (C2 25).
  Em mensagens pequenas, o RTT domina e a vazão útil fica baixa.
- Em `local` não há enlace físico: o limite é a memória e o processador. Em `lan`, o limite é o
  enlace mais lento do caminho (gargalo, C1 57–58), em geral o Wi-Fi.

## C — Concorrência (1, 2 e 5 agentes)

```bash
python3 experimentos/exp_c_concorrencia.py --servidor 127.0.0.1 --condicao local
python3 experimentos/exp_c_concorrencia.py --servidor <IP do Mac> --condicao lan     # no notebook do colega
```
Cada agente tem sua conexão TCP e roda numa thread. Todos enviam 200 MEDICAO. Para 1, 2 e 5 agentes,
o script mostra o atraso por mensagem (média, mediana, p95, desvio, máximo) e a taxa total em
mensagens por segundo.

O que olhar: compare a **média e o p95**, não só a mediana. Um efeito da concorrência pode aparecer
só na cauda (poucas mensagens esperando muito) e não mudar a mediana. Se a média ou o p95 crescerem
com mais agentes, uma hipótese a discutir (não um fato) é que o banco SQLite grava uma operação por
vez, então algumas gravações esperam a vez, numa analogia com o atraso de fila (C1 49–52).

## D — TCP × UDP (microteste com a mesma carga)

```bash
python3 experimentos/exp_d_tcp_udp.py --servidor 127.0.0.1 --condicao local
python3 experimentos/exp_d_tcp_udp.py --servidor <IP do Mac> --condicao lan          # no notebook do colega
```
500 mensagens de 100 bytes, uma de cada vez, para o eco TCP (porta 5051) e o eco UDP (porta 5052).
Mede o RTT, as perdas e as respostas UDP atrasadas (que chegam depois do prazo de 1 s).
- **Não afirmar que os dois são equivalentes:** o UDP não recupera perdas nem garante ordem; o TCP
  recupera, ao custo de atraso.
- **Ordenação:** com uma mensagem em trânsito por vez, as mensagens não têm como trocar de ordem neste
  teste. Discuta a ordenação pela teoria: o UDP não numera nem reordena (C3 27); o TCP entrega em
  ordem graças aos números de sequência (C3 80–82).
- Sem perda na rede, os dois têm RTT parecido. A diferença aparece no Experimento E.

## E — Atraso e perda simulados

Rode de novo A (`ping_app` e `--http`), B, C e D com atraso ou perda simulados, mudando `--condicao`.
Sugestão: `atraso50ms`, `perda2` e `atraso50ms_perda5`. **Anote onde a emulação foi aplicada
(qual máquina, qual interface, em que sentido) e onde as capturas do Wireshark foram feitas.**

### No Linux (notebook de um colega): `tc netem`

```bash
ip link                                                # descubra a interface (ex.: wlp2s0)
sudo tc qdisc add dev wlp2s0 root netem delay 50ms             # atraso de 50 ms na saída
sudo tc qdisc change dev wlp2s0 root netem loss 2%             # 2% de perda
sudo tc qdisc change dev wlp2s0 root netem delay 50ms loss 5%  # os dois
sudo tc qdisc del dev wlp2s0 root                              # desfaz (IMPORTANTE)
```
O `netem` atua só nos pacotes que **saem** da interface. Atraso de 50 ms no notebook dos clientes
aumenta o RTT em cerca de 50 ms. Na interface `lo` (tudo na mesma máquina), o pacote passa duas
vezes pela saída, e o RTT aumenta cerca de 100 ms.

### No macOS: `dnctl` e `pfctl`

Comandos ainda não validados pelo grupo. Antes de usar os resultados, confira com o Experimento A
que o RTT realmente aumentou.
```bash
sudo dnctl pipe 1 config delay 50 plr 0.02             # 50 ms de atraso e 2% de perda
echo "dummynet in quick proto { tcp, udp } from any to any port { 5050, 5051, 5052 } pipe 1" | sudo pfctl -f -
sudo pfctl -E
# ... rodar os experimentos ...
sudo pfctl -f /etc/pf.conf && sudo dnctl -q flush && sudo pfctl -d   # desfaz (IMPORTANTE)
```
Alternativa gráfica no Mac: o **Network Link Conditioner** (pacote "Additional Tools for Xcode",
site de desenvolvedores da Apple), com perfis de atraso e perda. Ele pode não afetar o `127.0.0.1`;
nesse caso, use a condição `lan`, com os clientes em outra máquina.

Se nenhuma das ferramentas funcionar, o enunciado aceita "quando tecnicamente viável". Nesse caso,
registre no relatório o que foi tentado.

### O que discutir no E
- **TCP com perda:** nenhuma mensagem se perde na aplicação, mas algumas têm RTT muito maior. Como o
  microteste manda uma mensagem por vez, não há segmentos seguintes para gerar ACKs duplicados; a
  recuperação é sempre por **timeout** (C3 84–86, C3 89), e o atraso extra fica na ordem do timeout
  mínimo do TCP (centenas de milissegundos).
- **UDP com perda:** a porcentagem de mensagens perdidas fica perto da perda configurada (ou perto do
  dobro, se a perda atua na ida e na volta), e o RTT das que chegam não muda.
- **Atraso:** soma ao RTT em todos os casos. No B, derruba a vazão das mensagens pequenas, cujo tempo
  é quase todo RTT.

## Gráficos

```bash
python3 -m venv .venv && .venv/bin/pip install matplotlib     # só uma vez
.venv/bin/python experimentos/graficos.py
```
(Se o `pip3 install matplotlib` funcionar direto no seu Python, também serve.) Gera
`resultados/graficos/exp_a_rtt.png`, `exp_b_throughput.png`, `exp_c_concorrencia.png` e
`exp_d_tcp_udp.png`, já com eixos, unidades e uma linha por condição.

## Experimento extra (opcional): resposta HTTP em um ou dois envios

O servidor monta cada resposta HTTP inteira (linha de status, cabeçalhos, linha em branco e corpo,
C2 29) e a envia de uma vez. Em `servidor/servidor.py` há uma opção, `RESPOSTA_EM_DOIS_ENVIOS`, que
faz o cabeçalho e o corpo saírem em dois envios separados. Para testar:

1. Rode o Experimento B normalmente com `--condicao um_envio`.
2. Mude `RESPOSTA_EM_DOIS_ENVIOS = True`, reinicie o servidor e rode o B com `--condicao dois_envios`.
3. Volte para `False` e reinicie o servidor.

Se a vazão com 1 kB cair muito no segundo caso, com cada resposta levando dezenas de milissegundos a
mais, o motivo provável é a combinação de dois mecanismos do TCP:
- o receptor atrasa o ACK, esperando um segundo segmento (ACK atrasado, C3 88);
- o emissor segura um segmento pequeno enquanto o anterior não foi confirmado (algoritmo de Nagle,
  RFC 896, que não está nos slides).

Isso só entra no relatório se o grupo medir o efeito. O comportamento pode ser diferente no macOS e
no Linux. Se não houver diferença, não citem.
