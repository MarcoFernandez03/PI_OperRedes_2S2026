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

def verificar_firma(roa, cert):
    try:
        firma = base64.b64decode(roa["firma"], validate=True)
        cert.public_key().verify(firma, roa["mensaje"].encode(),
                                 padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError):
        return False

if __name__ == "__main__":
    linea = crear_roa("10.1.0.5", 65003, 17, "out/AS65003-17.key", 3600)
    print(linea)
    roa = parsear_roa(linea)
    with open("out/AS65003-17.crt", "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    print("firma ok:", verificar_firma(roa, cert))
    roa["mensaje"] = roa["mensaje"].replace("10.1.0.5", "10.1.0.6")
    print("alterado:", verificar_firma(roa, cert))