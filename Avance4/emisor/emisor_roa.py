"""
emisor_roa.py - El nodo EMISOR (owner) de una isla. Tres pasos:

  1) pedir     -> el emisor genera su llave y una CSR (la llave privada NO sale de aqui)
  2) firmar    -> la CA firma la CSR y devuelve el certificado (.crt)
  3) publicar  -> el emisor firma un ROA por cada IP suya y lo manda al repositorio cada 60 s

Uso:
  python3 emisor_roa.py pedir    config_emisor.json                 (en la maquina del emisor)
  python3 emisor_roa.py firmar   AS3-301.csr ../pki/out SHELL       (en la maquina de la CA)
  python3 emisor_roa.py publicar config_emisor.json                 (en la maquina del emisor)

Aqui el AS es el numero de isla: el CN es AS<ISLA>-<NUM_EMISOR> (ej. AS3-301) y el ROA lleva ISLA=3.
El certificado identifica al emisor; lo que une cada IP con la isla es el ROA que el emisor firma con su llave.
"""
import base64
import json
import os
import socket
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "pki"))     # pki.py y roa.py viven en Avance4/pki

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

import pki
from roa import cargar_llave, crear_roa, parsear_roa

PREFIJO_DATOS = "DATA|"

def _rutas(cfg):
    cn = f"AS{cfg['isla']}-{cfg['num_emisor']}"
    carpeta = os.path.join(AQUI, cfg.get("carpeta_llaves", "llaves"))
    return cn, carpeta, os.path.join(carpeta, cn + ".key"), os.path.join(carpeta, cn + ".csr"), os.path.join(carpeta, cn + ".crt")


# ------------------------------------------------------------------ 1) pedir el certificado
def pedir(cfg):
    cn, carpeta, key, csr, _ = _rutas(cfg)
    os.makedirs(carpeta, exist_ok=True)
    if os.path.exists(key):
        raise OSError(f"Ya existe {key}: no se sobreescribe la llave.")
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    solicitud = (x509.CertificateSigningRequestBuilder()
                 .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn),
                                          x509.NameAttribute(NameOID.ORGANIZATION_NAME, cfg["equipo"]),
                                          x509.NameAttribute(NameOID.COUNTRY_NAME, "CR")]))
                 .sign(llave, hashes.SHA256()))
    with open(key, "wb") as f:
        f.write(llave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    os.chmod(key, 0o600)
    with open(csr, "wb") as f:
        f.write(solicitud.public_bytes(serialization.Encoding.PEM))
    print(f"Listo. Llave privada: {key} (no la compartas).")
    print(f"Mandale {csr} a la CA; ella devuelve {cn}.crt, que va en {os.path.dirname(key)}/")


# ------------------------------------------------------------------ 2) la CA firma (solo en la maquina de la CA)
def firmar(csr, directorio_ca, equipo):
    crt = pki.firmar_csr(equipo, csr, directorio_ca)
    print(f"Certificado emitido: {crt}  -> se lo devuelves al emisor.")


# ------------------------------------------------------------------ 3) publicar los ROA
def _put(cfg, cert_b64, llave, roa):
    """Una conexion por comando (como pide el diseno): HELLO + PUT firmado con el nonce. Devuelve la respuesta."""
    repo = cfg["repositorio"]
    with socket.create_connection((repo["ip"], repo.get("puerto", 9000)), timeout=10) as s:
        f = s.makefile("r")
        s.sendall(f"HELLO|OWNER|{cfg['num_emisor']}|{cert_b64}\n".encode())
        hello = f.readline().strip().split("|")
        if hello[0] != "HELLO_OK":
            return hello[0]
        firma = llave.sign(f"PUT|{roa}|{hello[2]}".encode(), padding.PKCS1v15(), hashes.SHA256())
        s.sendall(f"PUT|{roa}|{base64.b64encode(firma).decode()}\n".encode())
        return f.readline().strip()


def publicar(cfg, una_vez=False):
    cn, _, key, _, crt = _rutas(cfg)
    with open(crt, "rb") as f:
        cert_b64 = pki.cert_a_b64(x509.load_pem_x509_certificate(f.read()))
    llave = cargar_llave(key)
    roas = {}                                           # ip -> linea ROA ya firmada
    while True:
        for ip in cfg["ips"]:
            # Se reenvia SIEMPRE la misma linea firmada (asi el PUT identico no sube la version del repositorio);
            # solo se firma uno nuevo si no hay o le quedan menos de 5 minutos.
            if ip not in roas or parsear_roa(roas[ip])["vence"] - time.time() < 300:
                roas[ip] = crear_roa(ip, cfg["isla"], cfg["num_emisor"], key, cfg.get("vigencia", 3600))
            try:
                resp = _put(cfg, cert_b64, llave, roas[ip])
            except OSError as e:
                resp = f"sin conexion con el repositorio ({e})"
            print(f"[{time.strftime('%H:%M:%S')}] {cn} publica ROA de {ip} (isla {cfg['isla']}): {resp}", flush=True)
        if una_vez:
            return
        time.sleep(cfg.get("intervalo", 60))


def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] in ("pedir", "publicar"):
        cfg = json.load(open(a[1]))
        pedir(cfg) if a[0] == "pedir" else publicar(cfg, una_vez="--una-vez" in a)
    elif len(a) == 4 and a[0] == "firmar":
        firmar(a[1], a[2], a[3])
    else:
        print(__doc__)

    cn, _, _, csr, _ = _rutas(cfg)
    csr = pki.firmar_csr("SHELL", csr, "trust-anchors")

    hello_repo(cfg)

    while True:
        ip_destino = input("Ingrese la IP del receptor: ")
        contenido = input("Ingrese el contenido del mensaje: ")
        enviar_datos(cfg, ip_destino, contenido)

def enviar_datos(cfg, isla_destino: str, contenido: str):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((cfg["router"]["ip"], cfg["router"]["puerto"]))
        msg = f"{PREFIJO_DATOS}{cfg['isla']}|{isla_destino}|8|{contenido}"
        s.sendall(msg.encode())
        print(f"Enviado al enrutador: {msg}")
    finally:
        s.close()

def hello_repo(cfg):
    repo = cfg["repositorio"]
    _, roa_b64 = crear_roa(cfg["ips"][0], cfg["isla"], cfg["num_emisor"], os.path.join(AQUI, cfg.get("carpeta_llaves", "llaves"), f"AS{cfg['isla']}-{cfg['num_emisor']}.key"), cfg.get("vigencia", 3600)).split("|")
    with socket.create_connection((repo["ip"], repo.get("puerto", 9000)), timeout=10) as s:
        f = s.makefile("r")
        s.sendall(f"HELLO|OWNER|{cfg['num_emisor']}|{roa_b64}\n".encode())
        hello = f.readline().strip().split("|")
        if hello[0] != "HELLO_OK":
            print(f"Error en HELLO: {hello[0]}")
            return
        print(f"HELLO_OK recibido: {hello}")

if __name__ == "__main__":
    main()
