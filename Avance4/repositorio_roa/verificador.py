import base64
import os
import re
import sys
import time

# Directorio hermano donde vive pki.py. Ajusta el nombre al real.
DIR_PKI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pki")
if DIR_PKI not in sys.path:
    sys.path.append(DIR_PKI)

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

import pki
from repositorio_roa import CertificadoInvalido, Identidad

RUTA_TRUSTSTORE = "out/trusted-roots.pem"
_CN = re.compile(r"AS(\d+)-(\d+)")


class VerificadorPKI:
    def __init__(self, ruta_truststore: str = RUTA_TRUSTSTORE, reloj=time.time):
        self._ruta_truststore = ruta_truststore
        self._reloj = reloj

    def verificar_certificado(self, cert_b64: str) -> Identidad:
        """Valida la cadena contra el truststore y la vigencia.
        Lanza CertificadoInvalido si algo falla."""
        try:
            cert = pki.cert_desde_b64(cert_b64)
        except ValueError:
            raise CertificadoInvalido("el certificado no se pudo leer")

        # Se relee en cada llamada para tomar las actualizaciones del truststore
        try:
            raices = pki.cargar_truststore(self._ruta_truststore)
        except (OSError, ValueError):
            raise CertificadoInvalido("el truststore no está disponible")

        ok, motivo = pki.validar_cadena(cert, raices, self._reloj())
        if not ok:
            raise CertificadoInvalido(motivo)

        atributos = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        coincidencia = _CN.fullmatch(atributos[0].value) if atributos else None
        if coincidencia is None:
            raise CertificadoInvalido("el CN no tiene el formato AS<isla>-<num>")

        return Identidad(
            cn=atributos[0].value,
            isla=int(coincidencia.group(1)),
            num_emisor=int(coincidencia.group(2)),
            not_after=int(cert.not_valid_after_utc.timestamp()),
        )

    def verificar_firma(self, cert_b64: str, mensaje: bytes, firma_b64: str) -> bool:
        """RSA con PKCS#1 v1.5 y SHA-256 usando la llave pública del
        certificado. Devuelve False ante cualquier entrada inválida."""
        try:
            llave = pki.cert_desde_b64(cert_b64).public_key()
            if not isinstance(llave, rsa.RSAPublicKey):
                return False
            firma = base64.b64decode(firma_b64, validate=True)
            llave.verify(firma, mensaje, padding.PKCS1v15(), hashes.SHA256())
            return True
        except (InvalidSignature, UnsupportedAlgorithm, ValueError, TypeError):
            return False