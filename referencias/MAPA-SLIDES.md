# Mapa: requisitos do Projeto 1 → slides da disciplina

Slides em `referencias/slides/` (Kurose & Ross, v9.0). Regra do projeto: **tudo o que for implementado
ou escrito no relatório precisa se apoiar em um slide desta lista.** O que não tiver slide sai do
projeto ou entra no relatório como biblioteca ou ferramenta declarada.

Notação: `C2 100–105` = Capítulo 2, slides 100 a 105.

## Implementação

| Requisito do enunciado | Onde está no NetMon | Slides |
|---|---|---|
| Processos, sockets, endereço = IP + porta | agente, servidor, alvos `host:porta` | C2 8–10 |
| Escolher TCP ou UDP e justificar | canal agente → servidor em TCP | C2 12–15 · C3 9, 27–28 |
| Cliente/servidor **TCP** em Python | `servidor_agentes()`, `sessao()` do agente | C2 106–109 |
| Vários clientes ao mesmo tempo, timeout | um socket por agente, `settimeout()` (threads: ver abaixo) | C3 23 · C2 113–116 |
| TCP é fluxo de bytes: juntar pedaços até o `\n` | laço do `recv(1024)` no servidor e no agente | C3 80 · C2 101 |
| Medir o tempo de conexão (≈ 1 RTT) | `medir()` cronometra o `connect()` | C2 24 · C3 99–104 |
| `GET` HTTP escrito à mão | `medir()` em alvos `http:` | C2 26–31 |
| Consulta DNS antes da medição | `gethostbyname()` em `medir()` | C2 67–78 |
| Operação HTTP (requisição, resposta, métodos, códigos) | API do painel | C2 19–30 |
| HTTP persistente | `protocol_version = "HTTP/1.1"` | C2 25 |
| Protocolo de aplicação próprio em texto | `docs/PROTOCOLO.md` | C2 26–30 (HTTP) · C2 63–64 (SMTP) |
| Autenticação simples e estado entre requisições | HELLO com chave · cookie de sessão | C2 32–35 |
| Proteção de dados (sem criptografia, TLS) | seção 8 do protocolo | C2 16 · C1 60–61 |

## Experimentos

| Experimento | Base teórica |
|---|---|
| A — RTT e tempo de resposta | C2 24 (definição de RTT) · C2 25 (HTTP persistente) · C3 84–86 (SampleRTT, EstimatedRTT, DevRTT) |
| B — Throughput | C1 56–58 (vazão, gargalo) · C3 153 (vazão do TCP) |
| C — Concorrência 1, 2, 5 clientes | C1 46–52 (atraso de fila) · C3 23 (4-tupla: um socket por cliente) |
| D — TCP × UDP | C2 100–109 (sockets UDP e TCP) · C3 27–38 (UDP) · C3 80–106 (TCP) |
| E — Atraso e perda simulados | C1 46–55 (atrasos e perda) · C3 89–91 (retransmissões) · C3 108–127 (congestionamento) |

## Análise no Wireshark

| O que o enunciado pede | Slides |
|---|---|
| Ferramenta e o que ela captura | C1 89 · C2 31 |
| IPs, portas, protocolos por camada, tamanhos | C1 70–76, 88 (camadas, encapsulamento) · C4 43 (datagrama IP) |
| Estabelecimento de conexão TCP | C3 99–104 (handshake de 3 vias) · C3 106 (encerramento) |
| Sequência de requisições/respostas | C3 80–83 (números de sequência e ACKs) · C2 26–30 (HTTP) |
| RTT e retransmissões | C3 84–91 |
| Multiplexação e comunicação fim a fim | C3 11–25 |

## Fora dos slides (declarar no relatório como biblioteca ou ferramenta)

- `threading`: os slides só citam "multithreading" como forma de esperar vários sockets (C2 113);
  o uso de uma thread por cliente e da trava (`Lock`) é recurso do Python.

- `http.server` (servidor HTTP da biblioteca padrão), `sqlite3` (banco),
  `json` (formato das respostas da API), `hashlib` (hash das senhas).
- `fetch` no JavaScript do painel.
- `matplotlib`: só para gerar os gráficos dos experimentos.
- Algoritmo de Nagle (RFC 896): só no experimento extra opcional de `docs/EXPERIMENTOS.md`, junto com o ACK atrasado (C3 88).
- `tc`/`netem` (Linux) ou `dnctl`/`pfctl` (macOS): ferramentas para simular atraso e perda (Experimento E).
