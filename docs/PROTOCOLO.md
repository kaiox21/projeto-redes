# Protocolo de Aplicação NetMon

NetMon é um sistema de monitoramento de serviços de rede. **Agentes** medem, de verdade, se
servidores estão no ar e quanto tempo levam para responder. Eles mandam as medições para o
**servidor NetMon**, que guarda o histórico e gera alertas. Um **painel web** mostra tudo.

## 1. Visão geral

| Comunicação | Transporte | Porta | Protocolo de aplicação |
|---|---|---|---|
| Agente → servidor NetMon (tempo real) | TCP | 5050 | **NetMon** (próprio, texto linha a linha) |
| Painel web → servidor NetMon | TCP | 8765 | HTTP/1.1 |
| Agente → serviço-alvo (a medição) | TCP | a do alvo | só conexão TCP, ou conexão + `GET` HTTP |

**O que o agente mede em cada alvo**
- `tcp_ms`: tempo do `connect()`. Ele só termina depois do handshake de 3 vias (C3 99–104), então esse
  tempo é aproximadamente **1 RTT** até o alvo (C2 24). O DNS é consultado antes de começar a contar,
  para não somar o tempo da consulta DNS.
- `http_ms`: só para alvos HTTP. Tempo entre enviar um `GET` escrito à mão, como no exemplo com netcat
  do slide C2 31, e chegar o primeiro pedaço da resposta. Também fica perto de 1 RTT, mais o tempo que
  o servidor-alvo leva para responder.
- Pelo slide C2 24, o tempo de resposta HTTP sem conexão persistente é **2 RTT + tempo de transmissão**.
  Somar `tcp_ms` com `http_ms` dá aproximadamente os 2 RTT dessa conta; o tempo de transmissão do
  objeto inteiro fica de fora, porque o agente para no primeiro pedaço da resposta.
- Alvos HTTPS (porta 443): o agente mede só `tcp_ms`, porque falar HTTP dentro do TLS está fora do
  escopo da disciplina.

**Por que TCP no canal agente → servidor** (C2 12–15, C3 27–28, C3 80–106)
- Cada medição precisa chegar, e na ordem, para o histórico e os alertas ficarem corretos.
  O TCP garante entrega confiável e ordenada; com UDP, uma medição perdida sumiria sem aviso.
- O agente fica conectado o tempo todo. Se o programa do agente é encerrado, o sistema dele fecha a
  conexão (FIN) e o `recv()` do servidor volta vazio na hora. Se a máquina ou a rede do agente cai,
  nenhum FIN chega; aí só o `settimeout()` de 30 s percebe. Nos dois casos sai o alerta "agente offline".
- Custo: um handshake por conexão e um cabeçalho de no mínimo 20 bytes, contra 8 do UDP (C3 33, C3 81).

**Por que HTTP no painel** (C2 19–30)
- O navegador não abre socket TCP puro; ele fala HTTP. O painel consulta o servidor a cada 2 s.
- Cada consulta custa pelo menos 1 RTT, mesmo sem dado novo. É o custo de usar requisição/resposta
  para algo de tempo real; o relatório compara com o canal TCP sempre aberto dos agentes.

## 2. Formato das mensagens (canal dos agentes, porta 5050)

Mensagens em **texto UTF-8, uma por linha, terminadas em `\n`**, no estilo dos comandos do SMTP
(C2 63–64). Campos separados por espaço. Uma linha tem no máximo **1024 bytes**.

O TCP entrega um **fluxo de bytes**, não mensagens separadas (C3 80, C2 101): um `recv()` pode trazer meia
linha ou várias linhas juntas. Por isso, o fim de cada mensagem é marcado pelo `\n`, e quem recebe
junta os pedaços até achar o `\n`.

### Comandos (agente → servidor)

| Comando | Formato | Exemplo |
|---|---|---|
| HELLO | `HELLO <agente_id> <chave>` | `HELLO agente-01 chave-01` |
| MEDICAO | `MEDICAO <alvo> <estado> <tcp_ms> <http_ms>` | `MEDICAO gaia.cs.umass.edu:80 UP 182.40 190.75` |
| PING | `PING <qualquer texto>` | `PING 1730123456.789` |
| BYE | `BYE` | `BYE` |

Campos da MEDICAO:
- `alvo`: `host:porta` do serviço medido.
- `estado`: `UP` (respondeu) ou `DOWN` (não respondeu em 3 s, recusou a conexão ou o DNS falhou).
- `tcp_ms` e `http_ms`: tempos em milissegundos, ou `-` quando não foram medidos.
  Um alvo `UP` sempre tem `tcp_ms`; um alvo `DOWN` usa `-` nos dois.

Exemplos:
```
MEDICAO gaia.cs.umass.edu:80 UP 182.40 190.75     (alvo HTTP)
MEDICAO aprender.unb.br:443 UP 4.12 -             (só conexão TCP)
MEDICAO 192.168.0.20:9000 DOWN - -                (fora do ar)
```

### Respostas (servidor → agente)

Toda resposta segue o formato `<código> <nome> [detalhe]`, no estilo das respostas do HTTP e do
SMTP (C2 29–30, C2 63). Cada comando recebe exatamente uma resposta.

| Código | Nome | Quando |
|---|---|---|
| 200 | `OK` | comando aceito. Na MEDICAO, o detalhe é o número da medição gravada |
| 200 | `PONG` | resposta ao PING; repete o texto recebido (usado para medir RTT da aplicação) |
| 400 | `FORMATO_INVALIDO` | campos faltando, alvo sem porta, estado diferente de UP/DOWN, tempo não numérico |
| 400 | `COMANDO_DESCONHECIDO` | comando que não existe no protocolo |
| 401 | `NAO_AUTENTICADO` | agente ou chave incorretos. O servidor fecha a conexão |
| 403 | `SEM_HELLO` | comando antes do HELLO |
| 403 | `HELLO_REPETIDO` | um segundo HELLO na mesma conexão |
| 403 | `JA_CONECTADO` | o mesmo agente já tem outra conexão aberta. O servidor fecha esta conexão |
| 413 | `LINHA_GRANDE` | linha com mais de 1024 bytes. O servidor fecha a conexão |
| 422 | `VALOR_INVALIDO` | UP sem tempo, DOWN com tempo, tempo fora de 0 a 60000 ms |

## 3. Sequência de operações

```
Agente                                       Servidor NetMon (porta 5050)
  |---- SYN, SYN-ACK, ACK (handshake TCP) ------->|
  |  HELLO agente-01 chave-01                     |
  |<---------------------- 200 OK bem-vindo agente-01
  |                                               |
  |  (mede gaia.cs.umass.edu:80: connect + GET)   |
  |  MEDICAO gaia.cs.umass.edu:80 UP 182.40 190.75|
  |<---------------------- 200 OK 17              |
  |  (mede 192.168.0.20:9000: recusou)            |
  |  MEDICAO 192.168.0.20:9000 DOWN - -           |
  |<---------------------- 200 OK 18              |  2ª vez seguida DOWN -> alerta
  |        ... espera 5 s, mede de novo ...       |
  |  BYE                                          |
  |<---------------------- 200 OK tchau           |
  |---- FIN / ACK (encerramento TCP) ------------->|
```

Regras de sequência:
- O primeiro comando deve ser `HELLO`. Antes dele, qualquer outro recebe `403 SEM_HELLO`.
- O agente espera a resposta de cada comando antes de mandar o próximo.
- Erros 400, 403 (exceto `JA_CONECTADO`) e 422 não fecham a conexão.

## 4. Desconexão e indisponibilidade

- **Programa do agente encerrado** sem `BYE` (ou derrubado): o sistema do agente fecha a conexão
  (FIN, C3 106), o `recv()` do servidor volta vazio, e o servidor gera o alerta "agente offline".
- **Máquina ou rede do agente caiu**: nenhum FIN chega. Com `settimeout(30)` (C2 113–116), depois de
  30 s sem mensagem o servidor fecha a conexão e gera o mesmo alerta. Por isso o agente aceita
  `--intervalo` de no máximo 20 s: assim ele nunca fica 30 s calado.
- **Agente reconectando antes de o servidor perceber a queda**: o HELLO recebe `403 JA_CONECTADO`,
  e o agente tenta de novo a cada 3 s até a conexão antiga expirar.
- **Servidor NetMon fora do ar**: o agente tenta reconectar a cada 3 s. As medições desse intervalo
  são perdidas; o histórico mostra a lacuna.
- **Serviço-alvo fora do ar**: o agente espera no máximo 3 s pela conexão e informa `DOWN`.
- **Saída normal**: o agente envia `BYE` (Ctrl+C). Não gera alerta.

## 5. Alertas

| Regra inicial | Condição | Medições seguidas | Nível |
|---|---|---|---|
| fora do ar | estado `DOWN` | 2 | crítico |
| conexão TCP lenta | `tcp_ms` > 200 ms | 3 | aviso |
| resposta HTTP lenta | `http_ms` > 500 ms | 3 | aviso |

O alerta só dispara depois de N medições seguidas, para que uma lentidão isolada não gere alerta.
Depois de disparar, a mesma regra só alerta de novo quando o serviço volta ao normal e piora outra vez.
Os limites podem ser mudados pelo painel (`PUT /api/regras/<id>`).

## 6. API HTTP do painel (porta 8765)

Respostas em JSON. O login devolve um **cookie** `sessao`, que o navegador reenvia em todas as
requisições seguintes (C2 32–35). Sem cookie válido, as rotas respondem `401`.

| Método e rota | O que faz | Respostas |
|---|---|---|
| `POST /api/login` | corpo `{"usuario", "senha"}`; cria a sessão | `200` + cookie · `400` · `401` |
| `POST /api/logout` | encerra a sessão | `200` |
| `GET /api/alvos` | última medição de cada alvo | `200` |
| `GET /api/agentes` | agentes e se estão conectados | `200` |
| `GET /api/medicoes` | histórico; filtros `alvo`, `desde` (só ids maiores), `limite` (até 1000) | `200` · `400` |
| `GET /api/alertas` | alertas; filtros `desde` e `limite` | `200` · `400` |
| `GET /api/regras` | regras de alerta | `200` |
| `PUT /api/regras/<id>` | altera uma regra; corpo `{"limiar", "consecutivas", "nivel"}` | `200` · `400` · `404` |
| `POST /api/carga` | recebe um corpo de N bytes e devolve N (Experimento B) | `200` |

O servidor usa **HTTP/1.1 com conexão persistente** (C2 25): o navegador reaproveita a mesma conexão
TCP nas consultas a cada 2 s, sem um handshake novo por consulta.

## 7. Logs

Uma linha por evento, com data e hora, no terminal do servidor e em `logs/servidor.log`:
```
2026-10-28 14:29:10.417  TCP  agente-01  MEDICAO 127.0.0.1:9 DOWN - - -> 200 OK 10
2026-10-28 14:29:10.419  ALERTA critico: 127.0.0.1:9 fora do ar (2 medições seguidas, agente agente-01)
2026-10-28 14:29:39.408  TCP  agente-03 desconectou (sem mensagens por 30 s)
2026-10-28 14:29:40.102  HTTP 127.0.0.1:51234 GET /api/alvos -> 200 (1.3 ms)
```
A chave do agente não é gravada no log (o HELLO aparece como `HELLO ***`).

## 8. Segurança e limitações

- O tráfego **não é criptografado** (TCP e HTTP sem TLS, C2 16). A senha do painel, a chave do agente
  e o cookie aparecem em texto claro no Wireshark. Para uso real, seria preciso TLS (HTTPS).
- Senhas e chaves ficam no banco como hash SHA-256, não em texto claro.
- O servidor NetMon é centralizado: se ele cair, os agentes param de registrar. É um ponto único de falha.
- As medições dependem da rede do agente no momento: Wi-Fi congestionado aumenta os tempos.
