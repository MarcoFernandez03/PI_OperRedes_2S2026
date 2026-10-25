import base64
import os
import subprocess
import time
from datetime import datetime, timezone

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

DIAS_CA = 1825
DIAS_NODO = 365

#_openssl evita repetir el subprocess.run en cada comando. Recibe solo los argumentos y le antepone "openssl".
def _openssl(args):
    try:
        return subprocess.run(["openssl"] + args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"openssl {args[0]} falló:\n{e.stderr}") from e

# La función generar_ca genera una nueva autoridad certificadora (CA) para un equipo específico.
def generar_ca(equipo, directorio, cnf="ca-ext.cnf"):
    os.makedirs(directorio, exist_ok=True)
    key = os.path.join(directorio, f"ca-{equipo}.key")
    crt = os.path.join(directorio, f"ca-{equipo}.crt")

    if os.path.exists(key) or os.path.exists(crt):
        raise FileExistsError(f"Ya existe una CA para {equipo}")

    _openssl(["genpkey", "-algorithm", "RSA",
              "-pkeyopt", "rsa_keygen_bits:2048", "-out", key])
    os.chmod(key, 0o600)

    _openssl(["req", "-new", "-x509", "-key", key,
              "-config", cnf, "-extensions", "v3_ca",
              "-subj", f"/CN=CA-{equipo}/O={equipo}/C=CR",
              "-sha256", "-days", str(DIAS_CA), "-out", crt])

    _openssl(["verify", "-CAfile", crt, crt])
    return key, crt

def generar_nodo(equipo, isla, num_emisor, directorio, cnf="nodo-ext.cnf"):
    cn = f"AS{isla}-{num_emisor}"
    ca_key = os.path.join(directorio, f"ca-{equipo}.key")
    ca_crt = os.path.join(directorio, f"ca-{equipo}.crt")
    key = os.path.join(directorio, f"{cn}.key")
    csr = os.path.join(directorio, f"{cn}.csr")
    crt = os.path.join(directorio, f"{cn}.crt")

    if os.path.exists(key) or os.path.exists(crt):
        raise FileExistsError(f"Ya existe el nodo {cn}")

    _openssl(["genpkey", "-algorithm", "RSA",
              "-pkeyopt", "rsa_keygen_bits:2048", "-out", key])
    os.chmod(key, 0o600)

    _openssl(["req", "-new", "-key", key,
              "-subj", f"/CN={cn}/O={equipo}/C=CR", "-out", csr])

    _openssl(["x509", "-req", "-in", csr, "-CA", ca_crt, "-CAkey", ca_key,
              "-CAcreateserial", "-days", str(DIAS_NODO), "-sha256",
              "-extfile", cnf, "-extensions", "v3_nodo", "-out", crt])

    _openssl(["verify", "-CAfile", ca_crt, crt])
    return key, crt

def cargar_truststore(ruta):
    with open(ruta, "rb") as f:
        return x509.load_pem_x509_certificates(f.read())

def cert_a_b64(cert):
    der = cert.public_bytes(serialization.Encoding.DER)
    return base64.b64encode(der).decode()

def cert_desde_b64(texto):
    return x509.load_der_x509_certificate(base64.b64decode(texto, validate=True))

def _ext_raiz_ok(raiz):
    try:
        bc = raiz.extensions.get_extension_for_class(x509.BasicConstraints)
        ku = raiz.extensions.get_extension_for_class(x509.KeyUsage)
    except x509.ExtensionNotFound:
        return False
    return (bc.critical and bc.value.ca and ku.critical
            and ku.value.key_cert_sign)


def _ext_nodo_ok(cert):
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage)
    except x509.ExtensionNotFound:
        return False
    return (bc.critical and not bc.value.ca and ku.critical
            and ku.value.digital_signature)

def validar_cadena(cert, raices, ahora=None):
    t = ahora if ahora is not None else time.time()
    ahora_dt = datetime.fromtimestamp(t, tz=timezone.utc)

    if not (cert.not_valid_before_utc <= ahora_dt <= cert.not_valid_after_utc):
        return False, "certificado del nodo fuera de vigencia"
    if not _ext_nodo_ok(cert):
        return False, "extensiones del certificado del nodo incorrectas"

    motivo = "emisor no está en el truststore"
    for raiz in raices:
        if raiz.subject != cert.issuer:
            continue
        if not (raiz.not_valid_before_utc <= ahora_dt <= raiz.not_valid_after_utc):
            motivo = "raíz fuera de vigencia"
            continue
        if not _ext_raiz_ok(raiz):
            motivo = "extensiones de la raíz incorrectas"
            continue
        try:
            raiz.public_key().verify(cert.signature, cert.tbs_certificate_bytes,
                                     padding.PKCS1v15(),
                                     cert.signature_hash_algorithm)
        except InvalidSignature:
            motivo = "la firma del certificado no verifica con la raíz"
            continue
        return True, "ok"
    return False, motivo