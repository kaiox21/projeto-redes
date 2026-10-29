# Guia de capturas no Wireshark (seção 6 do enunciado)

O enunciado pede **pelo menos três capturas comentadas**, cada uma com filtro, data e descrição do
cenário, correlacionadas com as medições da aplicação. Este guia propõe quatro. Salve cada captura em
`capturas/` (File → Save As, formato `.pcapng`) e tire prints para o relatório.

## Antes de capturar

- **Interface:** para testes com `127.0.0.1`, capture na interface de loopback (`lo0` no macOS, `lo`
  no Linux). Entre duas máquinas ou para a internet, capture na interface de rede (`en0` no macOS;
  no Linux, algo como `wlp2s0` ou `eth0`, veja com `ip link`).
- No loopback, a camada de enlace aparece como **Null/Loopback**, não como Ethernet, porque o pacote nem
  sai da máquina. Para mostrar o cabeçalho de enlace (H_l, C1 72–76 e C1 88) e o encapsulamento
  completo, use uma captura na interface de rede (capturas 3 e 4 na `lan`).
- **Filtro de exibição** é o que vai na barra verde. Anote o filtro usado em cada print.
- Para ver tempos entre pacotes: View → Time Display Format → Seconds Since Previous Displayed Packet.

## Captura 1: conexão TCP e protocolo NetMon

**Cenário:** servidor no Mac e um agente ligando (local ou lan).
**Filtro:** `tcp.port == 5050`

1. Comece a capturar e só depois inicie o agente.
2. Identifique o **handshake de 3 vias**: SYN, SYN-ACK, ACK (C3 99–104). Anote os números de sequência.
3. Clique num pacote do HELLO → botão direito → Follow → TCP Stream. Aparece a conversa em texto:
   `HELLO agente-01 chave-01`, `200 OK bem-vindo`, `MEDICAO ...`, `200 OK 17`. É o protocolo de
   aplicação próprio, visto na rede. A chave aparece em texto claro (seção 8 do protocolo, C2 16).
4. Num pacote de MEDICAO, abra as camadas no painel do meio e mostre o **encapsulamento**
   (C1 72–76): enlace → IPv4 (IP de origem e destino, C4 43) → TCP (porta de origem efêmera do
   agente, porta de destino 5050) → dados (a linha de texto). Anote os tamanhos de cada parte.
5. Com dois agentes ligados, mostre que são **duas conexões** para a mesma porta 5050, diferenciadas
   pela porta de origem: é a 4-tupla da demultiplexação orientada a conexão (C3 23).
6. Pare um agente com Ctrl+C: aparecem `BYE`, `200 OK tchau` e o encerramento com FIN (C3 106).

## Captura 2: painel por HTTP

**Cenário:** painel aberto no navegador, consultando a cada 2 s.
**Filtro:** `tcp.port == 8765 && http`

1. Mostre a linha de requisição (`GET /api/alvos HTTP/1.1`), os cabeçalhos e a resposta
   (`HTTP/1.1 200 OK`, `Content-Length`), como em C2 26–30.
2. **Conexão persistente (C2 25):** tire o `&& http` do filtro. Várias requisições usam a mesma porta
   de origem, sem um handshake novo a cada 2 s.
3. **Cookie (C2 32–35):** no `POST /api/login`, a resposta traz `Set-Cookie: sessao=...`; nas
   requisições seguintes, o navegador manda `Cookie: sessao=...`. A senha aparece em texto claro no
   corpo do login. É a limitação de segurança discutida no relatório.
4. Compare o tempo entre requisição e resposta com o "última levou ... ms" mostrado no painel.

## Captura 3: medição real de um serviço da internet

**Cenário:** agente medindo `gaia.cs.umass.edu:80` (servidor do livro, nos EUA).
**Filtro:** `host gaia.cs.umass.edu || dns`

1. Primeiro aparece a **consulta DNS** (sobre UDP, porta 53) que o agente faz com `gethostbyname()`
   antes de cronometrar (C2 67–78).
2. Depois, o handshake TCP com a gaia. Meça o tempo entre o SYN e o SYN-ACK no Wireshark e
   **compare com o `tcp_ms`** que o agente imprimiu para a mesma medição. Os dois devem ser quase
   iguais: é o mesmo RTT, visto pela rede e visto pela aplicação.
3. Em seguida, o `GET / HTTP/1.1` escrito à mão e a resposta. Compare o tempo GET → primeiro pacote da
   resposta com o `http_ms`.
4. No pacote de resposta HTTP, o campo `tcp.analysis.ack_rtt` mostra o RTT que o próprio Wireshark
   calcula.
5. **Comunicação fim a fim:** no SYN-ACK que veio da gaia, veja o campo TTL do cabeçalho IP (C4 43). Ele
   chega menor do que saiu, porque cada roteador do caminho diminui 1. Compare com o TTL de um pacote
   da rede local.

## Captura 4: TCP × UDP com perda (Experimento E)

**Cenário:** `exp_d_tcp_udp.py` rodando com perda simulada (ex.: `perda2`).
**Filtros:** `tcp.port == 5051 || udp.port == 5052`, e depois `tcp.analysis.retransmission`

**Cuidado metodológico (o enunciado pede):** o que a captura mostra depende de onde ela é feita em
relação ao ponto em que a perda é aplicada. Com `tc netem` na saída de uma máquina Linux, o pacote
descartado normalmente nem aparece numa captura feita nessa mesma máquina, porque o descarte acontece
antes do ponto de captura. Por isso:
- registre no relatório em que máquina e interface a perda foi aplicada e onde a captura foi feita;
- de preferência, capture na **outra** máquina (a que recebe), ou nas duas;
- não espere que o Wireshark marque todas as perdas: se ele nunca viu o segmento original, pode não
  marcar a retransmissão.

1. **TCP:** procure, na sequência de mensagens, intervalos de centenas de milissegundos entre um envio e
   a resposta. Eles correspondem às retransmissões por timeout (C3 84–86, C3 89). Onde o Wireshark viu
   as duas cópias do segmento, o filtro `tcp.analysis.retransmission` as marca.
2. **UDP:** cada mensagem começa com o número de sequência (`0|xxxx`, `1|xxxx`, ...). Falhas nessa
   numeração, entre as mensagens que chegaram, mostram quais se perderam. Compare com as "perdidas" do
   script. Não há retransmissão nem ACK.
3. Compare o tamanho dos cabeçalhos, para a mesma mensagem de 100 bytes: o UDP tem 8 bytes (C3 33); o
   TCP tem no mínimo 20 (C3 81), mas na captura deve aparecer mais (em geral 32), por causa das opções,
   como o carimbo de tempo (timestamp). Anote o valor que aparecer.

## Como apresentar no relatório

Para cada captura: o print (com a barra de filtro visível), a data, o cenário em uma frase e dois ou
três comentários ligando o que aparece à teoria e aos números medidos. Modelo: "o SYN-ACK chegou
[X] ms depois do SYN, e o agente registrou `tcp_ms` = [Y] ms na mesma medição".
