import base64
import ipaddress
import time

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

def cargar_llave(ruta):
    with open(ruta, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def crear_roa(ip, isla, num_emisor, ruta_llave, vigencia, ahora=None):
    ipaddress.IPv4Address(ip)
    emision = int(ahora if ahora is not None else time.time())
    vence = emision + vigencia
    mensaje = f"ROA|{ip}|{isla}|{num_emisor}|{emision}|{vence}"

    llave = cargar_llave(ruta_llave)
    firma = llave.sign(mensaje.encode(), padding.PKCS1v15(), hashes.SHA256())
    firma_b64 = base64.b64encode(firma).decode()

    return f"{mensaje}|{firma_b64}"

def parsear_roa(linea):
    partes = linea.rstrip("\n").split("|")
    if len(partes) != 7 or partes[0] != "ROA":
        raise ValueError("ROA debe tener 7 campos y empezar con 'ROA'")
    _, ip, isla, num_emisor, emision, vence, firma = partes
    ipaddress.IPv4Address(ip)
    return {
        "ip": ip,
        "isla": int(isla),
        "num_emisor": int(num_emisor),
        "emision": int(emision),
        "vence": int(vence),
        "firma": firma,
        "mensaje": "|".join(partes[:6]),
    }