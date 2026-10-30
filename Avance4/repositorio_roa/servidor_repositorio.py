import socket
import threading
import time
import traceback

from disco import Disco
from sistema_archivos import SistemaArchivos
from repositorio_roa import (RepositorioROA, SesionConexion, ErrorProtocolo,
                             ErrFormato, Verificador)

PUERTO = 9000
TIMEOUT = 10.0
MAX_LINEA = 16384        # bytes, el HELLO con certificado ronda los 2 KB
MAX_CONEXIONES = 64
RUTA_IMAGEN = "disco.bin"


def _bitacora(mensaje: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {mensaje}", flush=True)


class ServidorRepositorio:
    def __init__(self, repositorio: RepositorioROA, host: str = "",
                 puerto: int = PUERTO, timeout: float = TIMEOUT,
                 max_conexiones: int = MAX_CONEXIONES, bitacora=_bitacora):
        self._repo = repositorio
        self._host = host
        self._puerto = puerto
        self._timeout = timeout
        self._bitacora = bitacora
        self._cupo = threading.BoundedSemaphore(max_conexiones)
        self._detenido = threading.Event()
        self._socket: socket.socket | None = None
        self._hilo_aceptador: threading.Thread | None = None

    @property
    def puerto(self) -> int:
        """Puerto real de escucha. Útil en pruebas con puerto 0."""
        return self._socket.getsockname()[1] if self._socket else self._puerto

    def iniciar(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self._host, self._puerto))
        s.listen(30)
        s.settimeout(1.0)  # para revisar la bandera de cierre
        self._socket = s
        self._detenido.clear()
        self._hilo_aceptador = threading.Thread(target=self._aceptar, daemon=True)
        self._hilo_aceptador.start()
        self._bitacora(f"Repositorio escuchando en TCP {self.puerto}")

    def esperar(self) -> None:
        while not self._detenido.is_set():
            self._detenido.wait(0.5)

    def detener(self) -> None:
        self._detenido.set()
        if self._hilo_aceptador is not None:
            self._hilo_aceptador.join(timeout=3)
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._bitacora("Repositorio detenido")

    # ---------- Privados ----------

    def _aceptar(self) -> None:
        while not self._detenido.is_set():
            try:
                conn, addr = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self._cupo.acquire(blocking=False):
                self._bitacora(f"{addr[0]} rechazado, demasiadas conexiones")
                conn.close()
                continue
            threading.Thread(target=self._atender, args=(conn, addr),
                             daemon=True).start()

    def _atender(self, conn: socket.socket, addr) -> None:
        """HELLO, un comando y cierre."""
        lector = None
        try:
            conn.settimeout(self._timeout)
            lector = conn.makefile("rb")
            sesion = SesionConexion()
            for paso in ("HELLO", "comando"):
                linea = None
                respuesta = None
                try:
                    linea = self._leer_linea(lector)
                    if linea is None:
                        return
                    respuesta = self._repo.procesar(linea, sesion)
                except ErrorProtocolo as e:
                    respuesta = [e.codigo]
                self._enviar(conn, respuesta)
                self._bitacora(f"{addr[0]} {linea.split('|')[0] if linea else paso} -> {respuesta[0][:40]}")
                if respuesta[0].startswith("ERR"):
                    return
        except socket.timeout:
            self._bitacora(f"{addr[0]} timeout de lectura")
        except OSError as e:
            self._bitacora(f"{addr[0]} error de red: {e}")
        except Exception:
            self._bitacora(f"{addr[0]} error inesperado\n{traceback.format_exc()}")
        finally:
            if lector is not None:
                lector.close()
            conn.close()
            self._cupo.release()

    def _leer_linea(self, lector) -> str | None:
        """Lee hasta el salto de línea. Devuelve None si el cliente cerró."""
        datos = lector.readline(MAX_LINEA + 1)
        if not datos:
            return None
        if not datos.endswith(b"\n"):
            raise ErrFormato("línea demasiado larga o sin salto de línea")
        try:
            return datos.decode("ascii").rstrip("\r\n")
        except UnicodeDecodeError:
            raise ErrFormato("caracteres no ASCII")

    @staticmethod
    def _enviar(conn: socket.socket, lineas: list[str]) -> None:
        conn.sendall(("\n".join(lineas) + "\n").encode("ascii"))


# ---------- Arranque ----------

def _crear_verificador() -> Verificador:
    # Pendiente de la interfaz acordada con Gabriel (puntos a y b)
    raise NotImplementedError("Falta conectar el Verificador de certificados")


def arrancar(verificador: Verificador, ruta_imagen: str = RUTA_IMAGEN,
             puerto: int = PUERTO) -> None:
    disco = Disco()
    fs = SistemaArchivos(disco, ruta_imagen)
    if disco.cargar(ruta_imagen):
        fs.montar()
        _bitacora("Disco cargado y verificado")
    else:
        fs.formatear()
        _bitacora("Disco nuevo formateado")
    repositorio = RepositorioROA(fs, verificador, bitacora=_bitacora)
    servidor = ServidorRepositorio(repositorio, puerto=puerto)
    servidor.iniciar()
    try:
        servidor.esperar()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.detener()
        disco.guardar(ruta_imagen)


if __name__ == "__main__":
    arrancar(_crear_verificador())