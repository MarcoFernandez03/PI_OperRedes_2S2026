import base64
import ipaddress
import time

from pki import validar_cadena
from cryptography.x509.oid import NameOID

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

def _cn(cert):
    return cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value


def verificar_roa(linea, cert, raices, ahora=None):
    t = ahora if ahora is not None else time.time()

    try:
        roa = parsear_roa(linea)
    except ValueError as e:
        return False, f"formato inválido: {e}"

    if not (roa["emision"] <= t <= roa["vence"]):
        return False, "ROA fuera de su rango EMISION-VENCE"

    ok, motivo = validar_cadena(cert, raices, t)
    if not ok:
        return False, f"certificado no válido: {motivo}"

    esperado = f"AS{roa['isla']}-{roa['num_emisor']}"
    if _cn(cert) != esperado:
        return False, f"CN {_cn(cert)} no coincide con {esperado}"

    if roa["vence"] > cert.not_valid_after_utc.timestamp():
        return False, "VENCE es posterior al notAfter del certificado"

    if not verificar_firma(roa, cert):
        return False, "la firma no verifica"

    return True, "ok"
