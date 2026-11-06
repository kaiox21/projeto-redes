# NetMon: monitoramento de serviços de rede

Projeto 1 de CIC0124 Redes de Computadores (UnB, 2026/2).

**Agentes** medem de verdade se serviços de rede estão no ar e quanto tempo levam para responder:
o tempo de conexão TCP (≈ 1 RTT) e o tempo de resposta a um `GET` HTTP. Eles enviam as medições ao
**servidor NetMon** por socket TCP (porta 5050), com um protocolo de aplicação próprio em texto.
O servidor guarda o histórico, gera alertas (serviço fora do ar, serviço lento) e atende um
**painel web** por HTTP (porta 8765).

- Protocolo: [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md)
- Relação entre o projeto e os slides da disciplina: [`referencias/MAPA-SLIDES.md`](referencias/MAPA-SLIDES.md)

## Requisitos

- Python **3.7 ou mais novo** (`python3 --version`). Não precisa instalar nada: o projeto usa só a
  biblioteca padrão (`socket`, `threading`, `sqlite3`, `http.server`, `json`). O matplotlib só
  é necessário para gerar os gráficos dos experimentos.
- Um navegador.

## Como executar

Abra um terminal na pasta do projeto (a raiz deste repositório, onde está este README) para cada programa.

**1. Servidor NetMon**
```bash
python3 servidor/servidor.py
```

**2. Agentes** (um terminal por agente)
```bash
python3 clientes/agente.py --agente-id agente-01 --chave chave-01
```
Sem `--alvos`, o agente mede `gaia.cs.umass.edu:80` (o servidor do livro, usado no slide C2 31),
`aprender.unb.br:443` e o próprio painel em `127.0.0.1:8765`. Para escolher os alvos:
```bash
python3 clientes/agente.py --agente-id agente-02 --chave chave-02 \
    --alvos http:192.168.0.20:9000 tcp:aprender.unb.br:443 --intervalo 2
```
Cada alvo é `http:host:porta` (mede conexão TCP e resposta HTTP) ou `tcp:host:porta` (só a conexão).
Para encerrar um agente, use Ctrl+C: ele envia `BYE` antes de sair.

**3. Painel:** abra <http://127.0.0.1:8765> e entre com `painel1` / `redes2026`.
Para dois clientes ao mesmo tempo, abra uma janela anônima e entre com `painel2` / `redes2026`.

### Alvo local para a demo e os experimentos

Para não depender da internet, qualquer máquina do grupo pode servir de alvo HTTP:
```bash
python3 -m http.server 9000
```
Depois é só usar `--alvos http:<IP dessa máquina>:9000`. Desligar esse servidor (Ctrl+C) faz o
NetMon gerar o alerta "fora do ar", o que é bom para a demonstração.

### Em mais de uma máquina (mesma rede)

1. Descubra o IP do servidor NetMon: macOS `ipconfig getifaddr en0` · Linux `hostname -I` · Windows `ipconfig`.
2. Nas outras máquinas: `python3 clientes/agente.py --servidor <IP> ...` ou abra `http://<IP>:8765`.
3. No macOS, permita conexões de entrada para o Python quando o firewall perguntar.

### Se aparecer "a porta ... já está sendo usada por outro programa"

O servidor confere, ao iniciar, se as portas 5050 e 8765 estão livres. Se outro programa (ou um
NetMon antigo ainda aberto) já usa uma delas, feche esse programa ou troque `PORTA_AGENTES` /
`PORTA_HTTP` no começo de `servidor/servidor.py`. Use sempre `127.0.0.1` no navegador, não
`localhost`: o servidor escuta só em IPv4 (`AF_INET`), e o `localhost` pode ser traduzido para o
endereço IPv6 `::1`, onde outro programa pode estar usando a mesma porta.

## Dados de teste (não sensíveis)

| Tipo | Identificação | Senha ou chave |
|---|---|---|
| Painel | `painel1`, `painel2` | `redes2026` |
| Agente | `agente-01` a `agente-05` | `chave-01` a `chave-05` |

O banco é criado em `dados/netmon.db` na primeira execução. Para começar do zero, apague a pasta `dados/`.

## Teste do protocolo

Com o servidor rodando:
```bash
python3 testes/teste_protocolo.py
```
São 38 verificações de casos normais e de erro, no canal TCP e na API HTTP. O teste usa o agente-05
(deixe-o desligado) e grava algumas medições de teste no banco, com alvos chamados `t<número>-...`;
por isso, rode-o antes de apagar `dados/` para a demonstração. Pode ser repetido à vontade.

## Experimentos e Wireshark

Roteiro completo, com as condições local, lan, internet e de atraso/perda: [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md).
Resumo (com o servidor rodando e, para o D, `python3 experimentos/eco_servidor.py` em outro terminal):
```bash
python3 experimentos/exp_a_rtt.py --condicao local              # A: RTT da aplicação (30 medições)
python3 experimentos/exp_a_rtt.py --condicao local --http       # A: tempo de resposta HTTP
python3 experimentos/exp_b_throughput.py --condicao local       # B: vazão por tamanho
python3 experimentos/exp_c_concorrencia.py --condicao local     # C: 1, 2 e 5 agentes
python3 experimentos/exp_d_tcp_udp.py --condicao local          # D: TCP x UDP
python3 -m venv .venv && .venv/bin/pip install matplotlib      # só uma vez, para os gráficos
.venv/bin/python experimentos/graficos.py                       # gráficos em resultados/graficos/
```
Os resultados ficam em CSV em `resultados/`. As capturas estão descritas em [`docs/WIRESHARK.md`](docs/WIRESHARK.md).

## Testando à mão com netcat

Como o protocolo é texto, dá para conversar com o servidor digitando (C2 31):
```bash
nc 127.0.0.1 5050
HELLO agente-04 chave-04
MEDICAO exemplo.com:80 UP 25.3 40.1
PING teste
BYE
```

## Logs

Uma linha por evento, com data e hora, no terminal do servidor e em `logs/servidor.log`:
conexões e desconexões de agentes com o motivo, cada comando recebido e a resposta, alertas e
requisições HTTP com o tempo de resposta.

## Estrutura

```
servidor/servidor.py     servidor NetMon: socket TCP dos agentes + HTTP do painel + SQLite + alertas + logs
clientes/agente.py       agente de medição (cliente TCP)
web/                     painel (HTML, CSS e JavaScript, sem bibliotecas)
testes/                  teste do protocolo
experimentos/            scripts dos experimentos A a D, servidor de eco (D) e gráficos
resultados/              CSVs e gráficos gerados pelos experimentos
docs/PROTOCOLO.md        especificação do protocolo de aplicação
docs/EXPERIMENTOS.md     roteiro dos experimentos A a E
docs/WIRESHARK.md        guia das capturas
docs/capturas/           prints das capturas do Wireshark usadas no relatório
docs/ROTEIRO-TESTES.md   roteiro para testar tudo do zero
docs/arquitetura.png     diagrama de arquitetura (fonte: docs/arquitetura.mmd)
referencias/             slides da disciplina e mapa requisito → slide (slides fora do repositório)
```

## Bibliotecas, ferramentas e uso de IA

- Bibliotecas: o código usa apenas a biblioteca padrão do Python (`socket`, `threading`, `sqlite3`,
  `http.server` e `json`); a biblioteca matplotlib foi usada somente para gerar os gráficos.
- Ferramentas: foram usados o Wireshark [7], o netcat (testes manuais do protocolo) e o dnctl/pfctl
  do macOS, que usam o dummynet [6]; no celular, os scripts rodaram no terminal a-Shell.
- Uso de IA: o assistente de IA Claude (Anthropic) foi usado como apoio ao longo do projeto: na
  revisão e na procura de possíveis problemas no código (servidor, agente, painel, teste e scripts dos
  experimentos), na geração dos gráficos, na síntese do roteiro usado para gravação e na edição do
  vídeo. O grupo escolheu o tema, revisou e aprovou as decisões de projeto, executou todos os
  experimentos e as capturas no Wireshark, gravou a demonstração e revisou, testou e validou todo o
  material entregue.

## Referências

A numeração é a mesma do relatório.

1. J. F. Kurose e K. W. Ross. *Redes de Computadores e a Internet: Uma Abordagem Top-Down*, 8ª ed.
   São Paulo: Pearson, 2021.
2. R. Fielding, M. Nottingham e J. Reschke. "HTTP Semantics", RFC 9110, IETF, jun. 2022.
   <https://www.rfc-editor.org/rfc/rfc9110>
3. W. Eddy. "Transmission Control Protocol (TCP)", RFC 9293, IETF, ago. 2022.
   <https://www.rfc-editor.org/rfc/rfc9293>
4. J. Postel. "User Datagram Protocol", RFC 768, IETF, ago. 1980.
   <https://www.rfc-editor.org/rfc/rfc768>
5. Python Software Foundation. "socket — Low-level networking interface", documentação do Python 3,
   acesso em nov. 2026. <https://docs.python.org/3/library/socket.html>
6. L. Rizzo. "Dummynet: A simple approach to the evaluation of network protocols", *ACM SIGCOMM
   Computer Communication Review*, v. 27, n. 1, p. 31–41, 1997.
7. Wireshark Foundation. "Wireshark User's Guide", documentação on-line, acesso em nov. 2026.
   <https://www.wireshark.org/docs/wsug_html_chunked/>
8. V. Paxson, M. Allman, J. Chu e M. Sargent. "Computing TCP's Retransmission Timer", RFC 6298, IETF,
   jun. 2011. <https://www.rfc-editor.org/rfc/rfc6298>
9. The Linux Foundation. "tc-netem(8): Network emulator", página de manual do Linux, acesso em
   nov. 2026. <https://man7.org/linux/man-pages/man8/tc-netem.8.html>
