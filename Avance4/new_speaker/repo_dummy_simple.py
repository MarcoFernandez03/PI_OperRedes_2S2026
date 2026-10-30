#!/usr/bin/env python3
"""
Repositorio DUMMY minimo para probar el punto E. Sin criptografia, sin disco.
Acepta texto plano: NO hace falta que el cliente termine el mensaje con \n.
Cada conexion: HELLO + 1 comando + cierre.

Uso: python3 repo_dummy_simple.py [--port 9000] [--bump-every N]
"""
import argparse
import socket
import threading
import time

ROAS = [
    "ROA|10.1.0.5|65003|17|1791849600|1823385600|ZmlybWFfZmFsc2E=",
    "ROA|10.2.0.3|65010|42|1791850000|1823386000|ZmlybWFfZmFsc2E=",
]
CERT = "Q0VSVElGSUNBRE9fRFVNTVk="   # base64 de "CERTIFICADO_DUMMY"
version = 1


def ip_local():
    try:
        t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        t.connect(("8.8.8.8", 80))
        ip = t.getsockname()[0]
        t.close()
        return ip
    except OSError:
        return "127.0.0.1"


def manejar(conn, addr):
    conn.settimeout(10)
    pendientes = []

    def recibir():
        # Devuelve el siguiente mensaje, con o sin \n al final
        while not pendientes:
            data = conn.recv(4096)
            if not data:
                return None
            pendientes.extend(
                l.strip() for l in data.decode(errors="replace").splitlines() if l.strip()
            )
        msg = pendientes.pop(0)
        print(f"[{addr[0]}] -> {msg}")
        return msg

    def enviar(*lineas):
        conn.sendall(("\n".join(lineas) + "\n").encode())
        for l in lineas:
            print(f"  <- {l}")

    try:
        hello = recibir()
        if hello is None:
            return
        p = hello.split("|")
        if p[0] != "HELLO" or len(p) < 3:
            enviar("ERR_SIN_HELLO")
            return
        enviar(f"HELLO_OK|{p[1]}|{p[2]}") # Response with rile and id

        cmd = recibir()
        if cmd is None:
            return
        c = cmd.split("|")
        if c[0] == "VERSION":
            enviar(f"OK|{version}")
        elif c[0] == "LIST":
            enviar(f"OK|{version}|{len(ROAS)}", *ROAS)
        elif c[0] == "GET" and len(c) == 2:
            r = next((x for x in ROAS if x.split("|")[1] == c[1]), None)
            enviar(f"OK|{r}" if r else "ERR_NO_EXISTE")
        elif c[0] == "CERT" and len(c) == 2:
            enviar(f"OK|{CERT}")
        elif c[0] in ("PUT", "DELETE"):
            enviar("ERR_PERMISO")
        else:
            enviar("ERR_FORMATO")
    except (socket.timeout, OSError) as e:
        print(f"  error: {e}")
    finally:
        conn.close()


def main():
    global version
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--bump-every", type=int, default=0)
    a = ap.parse_args()

    if a.bump_every:
        def ciclo():
            global version
            while True:
                time.sleep(a.bump_every)
                version += 1
                print(f"*** version -> {version}")
        threading.Thread(target=ciclo, daemon=True).start()

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", a.port))
    s.listen(16)
    print(f"Repo dummy en {ip_local()}:{a.port}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=manejar, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()