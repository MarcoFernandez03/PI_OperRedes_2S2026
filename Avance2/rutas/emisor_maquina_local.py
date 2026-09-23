# Enviar mensajes a la pi

import socket

PUERTO_TCP = 5006
PREFIJO_DATOS = "DATA|"

# Dirección IP del nodo enrutador
IP_ENRUTADOR = "192.168.100.16"

def enviar_datos(ip_destino: str, contenido: str):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((IP_ENRUTADOR, PUERTO_TCP))
        msg = f"{PREFIJO_DATOS}{ip_destino}|{contenido}"
        s.sendall(msg.encode())
        print(f"Enviado al enrutador: {msg}")
    finally:
        s.close()

# Ejemplo de uso
if __name__ == "__main__":
    enviar_datos("192.168.100.153", "Hola receptor, soy el emisor")
