import ipaddress
import re
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from sistema_archivos import SistemaArchivos, SinEspacio, NoExiste, PermisoDenegado

ROL_OWNER = "OWNER"
ROL_ENRUTADOR = "ENRUTADOR"
_BASE64 = re.compile(r"[A-Za-z0-9+/=]+")


# ---------- Errores del protocolo ----------

class ErrorProtocolo(Exception):
    codigo = "ERR_FORMATO"

    def __init__(self, motivo: str = ""):
        super().__init__(motivo)
        self.motivo = motivo


class ErrFormato(ErrorProtocolo):
    codigo = "ERR_FORMATO"


class ErrSinHello(ErrorProtocolo):
    codigo = "ERR_SIN_HELLO"


class ErrPermiso(ErrorProtocolo):
    codigo = "ERR_PERMISO"


class ErrFirma(ErrorProtocolo):
    codigo = "ERR_FIRMA"


class ErrExpirado(ErrorProtocolo):
    codigo = "ERR_EXPIRADO"


class ErrNoExiste(ErrorProtocolo):
    codigo = "ERR_NO_EXISTE"


class ErrLleno(ErrorProtocolo):
    codigo = "ERR_LLENO"


# ---------- Contrato con el subsistema de certificados ----------

class CertificadoInvalido(Exception):
    """Lo lanza el Verificador si el certificado no es de confianza."""


@dataclass(frozen=True)
class Identidad:
    cn: str            # por ejemplo AS65003-17
    isla: int
    num_emisor: int
    not_after: int     # segundos Unix (UTC)


class Verificador(Protocol):
    def verificar_certificado(self, cert_b64: str) -> Identidad:
        """Valida la cadena contra el truststore y la vigencia del certificado.
        Lanza CertificadoInvalido si algo falla."""

    def verificar_firma(self, cert_b64: str, mensaje: bytes, firma_b64: str) -> bool:
        """RSA-2048 con SHA-256 usando la llave pública del certificado.
        Devuelve False ante cualquier entrada inválida, nunca lanza."""


# ---------- Estado ----------

class AlmacenCertificados:
    """Certificados de los emisores por NUM_EMISOR, en memoria (atiende CERT)."""

    def __init__(self):
        self._certs: dict[int, str] = {}
        self._mutex = threading.Lock()

    def guardar(self, num_emisor: int, cert_b64: str) -> None:
        with self._mutex:
            self._certs[num_emisor] = cert_b64

    def obtener(self, num_emisor: int) -> str | None:
        with self._mutex:
            return self._certs.get(num_emisor)


class SesionConexion:
    """Estado de una conexión. Se crea una por conexión y no se comparte entre hilos."""

    def __init__(self):
        self.rol: str | None = None
        self.id: str | None = None
        self.identidad: Identidad | None = None
        self.cert_b64: str | None = None
        self._nonce: str | None = None

    @property
    def hubo_hello(self) -> bool:
        return self.rol is not None

    def registrar_hello(self, rol: str, id_: str, identidad: Identidad | None = None,
                        cert_b64: str | None = None, nonce: str | None = None) -> None:
        self.rol = rol
        self.id = id_
        self.identidad = identidad
        self.cert_b64 = cert_b64
        self._nonce = nonce

    def consumir_nonce(self) -> str | None:
        nonce, self._nonce = self._nonce, None
        return nonce


@dataclass(frozen=True)
class _Roa:
    ip: str
    isla: str
    num_emisor: str
    emision: int
    vence: int
    firma: str


# ---------- Lógica de comandos ----------

class RepositorioROA:
    def __init__(self, fs: SistemaArchivos, verificador: Verificador,
                 almacen: AlmacenCertificados | None = None,
                 reloj: Callable[[], float] = time.time,
                 bitacora: Callable[[str], None] | None = None):
        self._fs = fs
        self._verificador = verificador
        self._almacen = almacen if almacen is not None else AlmacenCertificados()
        self._reloj = reloj
        self._bitacora = bitacora if bitacora is not None else (lambda mensaje: None)

    def procesar(self, linea: str, sesion: SesionConexion) -> list[str]:
        """Devuelve las líneas de respuesta, sin saltos de línea."""
        try:
            return self._despachar(linea, sesion)
        except ErrorProtocolo as e:
            self._bitacora(f"{e.codigo}: {e.motivo}")
            return [e.codigo]
        except SinEspacio:
            return [ErrLleno.codigo]
        except NoExiste:
            return [ErrNoExiste.codigo]
        except PermisoDenegado:
            return [ErrPermiso.codigo]

    def _despachar(self, linea: str, sesion: SesionConexion) -> list[str]:
        campos = linea.split("|")
        comando = campos[0]
        if comando == "HELLO":
            return self._hello(campos, sesion)
        manejadores = {
            "VERSION": self._version, "LIST": self._list, "GET": self._get,
            "CERT": self._cert, "PUT": self._put, "DELETE": self._delete,
        }
        if comando not in manejadores:
            raise ErrFormato("comando desconocido")
        if not sesion.hubo_hello:
            raise ErrSinHello()
        if comando in ("PUT", "DELETE") and sesion.rol != ROL_OWNER:
            raise ErrPermiso("el rol no puede modificar")
        return manejadores[comando](campos, sesion)

    # ----- Comandos -----

    def _hello(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        if sesion.hubo_hello:
            raise ErrFormato("HELLO repetido")
        if len(campos) < 3:
            raise ErrFormato("HELLO incompleto")
        rol, id_ = campos[1], campos[2]
        if rol == ROL_ENRUTADOR:
            if len(campos) != 3 or not id_:
                raise ErrFormato("HELLO de enrutador mal formado")
            sesion.registrar_hello(rol, id_)
            return [f"HELLO_OK|{rol}|-"]
        if rol == ROL_OWNER:
            if len(campos) != 4 or not id_.isascii() or not id_.isdigit():
                raise ErrFormato("HELLO de owner mal formado")
            cert_b64 = campos[3]
            if not _BASE64.fullmatch(cert_b64):
                raise ErrFormato("certificado no es base64")
            try:
                identidad = self._verificador.verificar_certificado(cert_b64)
            except CertificadoInvalido as e:
                raise ErrPermiso(f"certificado no confiable: {e}")
            if identidad.num_emisor != int(id_):
                raise ErrPermiso("el id del HELLO no coincide con el certificado")
            nonce = secrets.token_hex(16)
            sesion.registrar_hello(rol, id_, identidad, cert_b64, nonce)
            return [f"HELLO_OK|{rol}|{nonce}"]
        raise ErrFormato("rol desconocido")

    def _version(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        if len(campos) != 1:
            raise ErrFormato("VERSION no lleva argumentos")
        return [f"OK|{self._fs.generacion()}"]

    def _list(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        if len(campos) != 1:
            raise ErrFormato("LIST no lleva argumentos")
        generacion, roas = self._fs.listar_roas()
        return [f"OK|{generacion}|{len(roas)}"] + roas

    def _get(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        if len(campos) != 2:
            raise ErrFormato("GET lleva una IP")
        ip = self._validar_ip(campos[1])
        return [f"OK|{self._fs.leer_roa(ip)}"]

    def _cert(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        if len(campos) != 2 or not campos[1].isascii() or not campos[1].isdigit():
            raise ErrFormato("CERT lleva un número de emisor")
        cert_b64 = self._almacen.obtener(int(campos[1]))
        if cert_b64 is None:
            raise ErrNoExiste("no hay certificado para ese emisor")
        return [f"OK|{cert_b64}"]

    def _put(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        # PUT + 7 campos del ROA + firma de la petición
        if len(campos) != 9:
            raise ErrFormato("PUT lleva un ROA de 7 campos y una firma")
        roa_texto = "|".join(campos[1:8])
        self._verificar_peticion(sesion, f"PUT|{roa_texto}|", campos[8])
        roa = self._validar_roa(roa_texto, sesion)
        self._fs.guardar_roa(sesion.identidad.cn, roa.ip, roa_texto)
        return [f"OK|{self._fs.generacion()}"]

    def _delete(self, campos: list[str], sesion: SesionConexion) -> list[str]:
        if len(campos) != 3:
            raise ErrFormato("DELETE lleva una IP y una firma")
        ip = self._validar_ip(campos[1])
        self._verificar_peticion(sesion, f"DELETE|{ip}|", campos[2])
        self._fs.borrar_roa(sesion.identidad.cn, ip)
        return [f"OK|{self._fs.generacion()}"]

    # ----- Validaciones -----

    def _verificar_peticion(self, sesion: SesionConexion, prefijo: str,
                            firma_b64: str) -> None:
        """Comprueba la firma sobre prefijo + nonce. Prueba que el owner tiene
        la llave privada, y el nonce se consume para que no se pueda reenviar."""
        nonce = sesion.consumir_nonce()
        if nonce is None:
            raise ErrFirma("nonce ya consumido")
        if not _BASE64.fullmatch(firma_b64):
            raise ErrFormato("la firma no es base64")
        mensaje = f"{prefijo}{nonce}".encode("ascii")
        if not self._verificador.verificar_firma(sesion.cert_b64, mensaje, firma_b64):
            raise ErrFirma("la firma de la petición no verifica")
        # Con la posesión de la llave probada, el certificado queda disponible para CERT
        self._almacen.guardar(sesion.identidad.num_emisor, sesion.cert_b64)

    def _validar_roa(self, texto: str, sesion: SesionConexion) -> _Roa:
        campos = texto.split("|")
        if len(campos) != 7 or campos[0] != "ROA":
            raise ErrFormato("el ROA no tiene siete campos")
        _, ip, isla, num, emision, vence, firma = campos
        self._validar_ip(ip)
        for valor in (isla, num, emision, vence):
            if not valor.isascii() or not valor.isdigit():
                raise ErrFormato("campo numérico inválido en el ROA")
        if not _BASE64.fullmatch(firma):
            raise ErrFormato("la firma del ROA no es base64")

        identidad = sesion.identidad
        if int(num) != identidad.num_emisor:
            raise ErrPermiso("NUM_EMISOR distinto del HELLO")
        if f"AS{isla}-{num}" != identidad.cn:
            raise ErrPermiso("el CN del certificado no coincide con ISLA y NUM_EMISOR")

        ahora = int(self._reloj())
        if not (int(emision) <= ahora <= int(vence)):
            raise ErrExpirado("el ROA está fuera de su vigencia")
        if int(vence) > identidad.not_after:
            raise ErrExpirado("VENCE supera el notAfter del certificado")

        mensaje = "|".join(campos[:6]).encode("ascii")
        if not self._verificador.verificar_firma(sesion.cert_b64, mensaje, firma):
            raise ErrFirma("la firma del ROA no verifica")
        return _Roa(ip, isla, num, int(emision), int(vence), firma)

    @staticmethod
    def _validar_ip(texto: str) -> str:
        try:
            if str(ipaddress.IPv4Address(texto)) != texto:
                raise ValueError
        except ValueError:
            raise ErrFormato("IPv4 inválida")
        return texto