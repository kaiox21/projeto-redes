"""
Servidor de eco para o Experimento D (microteste TCP x UDP).

Devolve exatamente o que recebe, em duas portas:
  - 5051/TCP: como o TCPServer dos slides (C2 109), com uma thread por cliente (C2 113)
  - 5052/UDP: como o UDPServer dos slides (C2 105)
O microteste é separado do protocolo NetMon, que só usa TCP.

Uso:
    python3 experimentos/eco_servidor.py
"""
import threading
from socket import *

PORTA_TCP = 5051
PORTA_UDP = 5052


def atender_tcp(connectionSocket, addr):
    try:
        while True:
            dados = connectionSocket.recv(2048)
            if not dados:          # cliente fechou a conexão
                break
            connectionSocket.sendall(dados)
    except OSError:
        pass
    finally:
        connectionSocket.close()


def eco_tcp():
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    serverSocket.bind(("", PORTA_TCP))
    serverSocket.listen(10)
    while True:
        connectionSocket, addr = serverSocket.accept()
        threading.Thread(target=atender_tcp, args=(connectionSocket, addr), daemon=True).start()


def eco_udp():
    serverSocket = socket(AF_INET, SOCK_DGRAM)
    serverSocket.bind(("", PORTA_UDP))
    while True:
        mensagem, clientAddress = serverSocket.recvfrom(2048)
        serverSocket.sendto(mensagem, clientAddress)


if __name__ == "__main__":
    threading.Thread(target=eco_tcp, daemon=True).start()
    print("eco TCP na porta %d e eco UDP na porta %d (Ctrl+C para encerrar)" % (PORTA_TCP, PORTA_UDP), flush=True)
    try:
        eco_udp()
    except KeyboardInterrupt:
        pass
