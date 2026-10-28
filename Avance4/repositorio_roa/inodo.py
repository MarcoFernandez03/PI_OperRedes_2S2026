import struct
import time

from bitmap import Bitmap
from disco import Disco, SECTORES_POR_BLOQUE, BYTES_POR_SECTOR

TIPO_LIBRE = 0
TIPO_ARCHIVO = 1
TIPO_DIRECTORIO = 2

PERM_DUENO_LEE = 1
PERM_DUENO_ESCRIBE = 2
PERM_OTROS_LEEN = 4
PERM_OTROS_ESCRIBEN = 8
PERM_PUBLICO_LECTURA = PERM_DUENO_LEE | PERM_DUENO_ESCRIBE | PERM_OTROS_LEEN

MAX_NOMBRE_PROPIETARIO = 16
NUM_DIRECTOS = 4

# numero, tipo, permisos, propietario, tamano, creacion, modificacion,
# 4 directos, indirecto, relleno hasta 128 bytes
_FORMATO = "<HBB16sIII4HH86x"
assert struct.calcsize(_FORMATO) == BYTES_POR_SECTOR


class Inodo:
    def __init__(self, numero: int, tipo: int, propietario: str = "",
                 permisos: int = 0, tamano: int = 0,
                 creacion: int | None = None, modificacion: int | None = None,
                 directos: list[int] | None = None, indirecto: int = 0):
        ahora = int(time.time())
        self.numero = numero
        self.tipo = tipo
        self.propietario = propietario
        self.permisos = permisos
        self.tamano = tamano
        self.creacion = ahora if creacion is None else creacion
        self.modificacion = ahora if modificacion is None else modificacion
        self.directos = list(directos) if directos else [0] * NUM_DIRECTOS
        self.indirecto = indirecto

    def serializar(self) -> bytes:
        return struct.pack(
            _FORMATO, self.numero, self.tipo, self.permisos,
            self._codificar_nombre(self.propietario),
            self.tamano, self.creacion, self.modificacion,
            *self.directos, self.indirecto,
        )

    def permite(self, solicitante: str | None, accion: str) -> bool:
        """accion es 'leer' o 'escribir'. Un enrutador entra con None."""
        if accion not in ("leer", "escribir"):
            raise ValueError("Acción desconocida")
        if solicitante is not None and solicitante == self.propietario:
            bit = PERM_DUENO_LEE if accion == "leer" else PERM_DUENO_ESCRIBE
        else:
            bit = PERM_OTROS_LEEN if accion == "leer" else PERM_OTROS_ESCRIBEN
        return bool(self.permisos & bit)

    def bloques_en_uso(self) -> list[int]:
        return [b for b in self.directos if b != 0]

    def asignar_bloques(self, bloques: list[int]) -> None:
        if len(bloques) > NUM_DIRECTOS:
            raise ValueError(f"Un inodo admite como máximo {NUM_DIRECTOS} bloques directos")
        self.directos = list(bloques) + [0] * (NUM_DIRECTOS - len(bloques))

    def tocar(self) -> None:
        self.modificacion = int(time.time())

    @staticmethod
    def desde_bytes(datos: bytes) -> "Inodo":
        (numero, tipo, permisos, nombre, tamano, creacion, modificacion,
         d0, d1, d2, d3, indirecto) = struct.unpack(_FORMATO, datos)
        if tipo not in (TIPO_LIBRE, TIPO_ARCHIVO, TIPO_DIRECTORIO):
            raise ValueError(f"Tipo de inodo desconocido: {tipo}")
        return Inodo(numero, tipo, Inodo._decodificar_nombre(nombre), permisos,
                     tamano, creacion, modificacion, [d0, d1, d2, d3], indirecto)

    @staticmethod
    def _codificar_nombre(nombre: str) -> bytes:
        datos = nombre.encode("ascii")
        if len(datos) > MAX_NOMBRE_PROPIETARIO:
            raise ValueError(f"El propietario excede {MAX_NOMBRE_PROPIETARIO} bytes")
        return datos

    @staticmethod
    def _decodificar_nombre(datos: bytes) -> str:
        return datos.rstrip(b"\x00").decode("ascii")


class TablaInodos:
    def __init__(self, disco: Disco, bitmap: Bitmap, bloque_inicio: int,
                 cantidad: int = 32):
        self._disco = disco
        self._bitmap = bitmap
        self._bloque_inicio = bloque_inicio
        self._cantidad = cantidad

    def leer(self, n: int) -> Inodo:
        inodo = Inodo.desde_bytes(self._disco.leer_sector(self._sector_de(n)))
        if inodo.tipo == TIPO_LIBRE:
            raise ValueError(f"El inodo {n} está libre")
        if inodo.numero != n:
            raise ValueError(f"Inodo corrupto en la posición {n}")
        return inodo

    def escribir(self, inodo: Inodo) -> None:
        self._disco.escribir_sector(self._sector_de(inodo.numero), inodo.serializar())

    def reservar(self, tipo: int, propietario: str, permisos: int) -> Inodo | None:
        if tipo not in (TIPO_ARCHIVO, TIPO_DIRECTORIO):
            raise ValueError("Solo se reservan inodos de archivo o directorio")
        n = self._bitmap.reservar()
        if n is None:
            return None
        inodo = Inodo(n, tipo, propietario, permisos)
        try:
            self.escribir(inodo)
        except Exception:
            self._bitmap.liberar(n)
            raise
        return inodo

    def liberar(self, n: int) -> None:
        self._disco.escribir_sector(self._sector_de(n), bytes(BYTES_POR_SECTOR))
        self._bitmap.liberar(n)

    def contar_libres(self) -> int:
        return self._bitmap.contar_libres()

    def crear_raiz(self) -> Inodo:
        raiz = self.reservar(TIPO_DIRECTORIO, "ROOT", PERM_PUBLICO_LECTURA)
        if raiz is None or raiz.numero != 0:
            raise RuntimeError("La raíz debe ser el inodo 0 de un disco recién formateado")
        return raiz

    def _sector_de(self, n: int) -> int:
        if n < 0 or n >= self._cantidad:
            raise ValueError("Número de inodo fuera de rango")
        return self._bloque_inicio * SECTORES_POR_BLOQUE + n