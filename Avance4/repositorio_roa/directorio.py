import struct

from disco import BYTES_POR_BLOQUE

BYTES_POR_ENTRADA = 32
MAX_NOMBRE = 28
MAX_ENTRADAS = BYTES_POR_BLOQUE // BYTES_POR_ENTRADA

# 28 bytes de nombre y 4 del número de inodo
_FORMATO_ENTRADA = "<28sI"
assert struct.calcsize(_FORMATO_ENTRADA) == BYTES_POR_ENTRADA


class Directorio:
    def __init__(self):
        self._entradas: list[tuple[str, int] | None] = [None] * MAX_ENTRADAS

    @staticmethod
    def desde_bytes(datos: bytes) -> Directorio:
        if len(datos) != BYTES_POR_BLOQUE:
            raise ValueError(f"Un directorio ocupa exactamente {BYTES_POR_BLOQUE} bytes")
        directorio = Directorio()
        for i in range(MAX_ENTRADAS):
            nombre, num_inodo = struct.unpack_from(
                _FORMATO_ENTRADA, datos, i * BYTES_POR_ENTRADA)
            if num_inodo != 0:
                directorio._entradas[i] = (Directorio._decodificar_nombre(nombre), num_inodo)
        return directorio

    def serializar(self) -> bytes:
        datos = bytearray(BYTES_POR_BLOQUE)
        for i, entrada in enumerate(self._entradas):
            if entrada is not None:
                nombre, num_inodo = entrada
                struct.pack_into(_FORMATO_ENTRADA, datos, i * BYTES_POR_ENTRADA,
                                 Directorio._codificar_nombre(nombre), num_inodo)
        return bytes(datos)

    def buscar(self, nombre: str) -> int | None:
        i = self._indice_de(nombre)
        return None if i is None else self._entradas[i][1]

    def agregar(self, nombre: str, num_inodo: int) -> None:
        Directorio._codificar_nombre(nombre)
        if num_inodo < 1 or num_inodo > 0xFFFFFFFF:
            raise ValueError("El inodo 0 es la raíz y no puede aparecer en un directorio")
        if self._indice_de(nombre) is not None:
            raise ValueError(f"Ya existe una entrada llamada {nombre}")
        for i, entrada in enumerate(self._entradas):
            if entrada is None:
                self._entradas[i] = (nombre, num_inodo)
                return
        raise OverflowError("El directorio está lleno")

    def quitar(self, nombre: str) -> int:
        i = self._indice_de(nombre)
        if i is None:
            raise KeyError(nombre)
        num_inodo = self._entradas[i][1]
        self._entradas[i] = None
        return num_inodo

    def listar(self) -> list[tuple[str, int]]:
        return [e for e in self._entradas if e is not None]

    def esta_lleno(self) -> bool:
        return all(e is not None for e in self._entradas)

    def esta_vacio(self) -> bool:
        return all(e is None for e in self._entradas)

    def _indice_de(self, nombre: str) -> int | None:
        for i, entrada in enumerate(self._entradas):
            if entrada is not None and entrada[0] == nombre:
                return i
        return None

    @staticmethod
    def _codificar_nombre(nombre: str) -> bytes:
        datos = nombre.encode("ascii")
        if not datos or b"\x00" in datos:
            raise ValueError("El nombre no puede ser vacío ni contener ceros")
        if len(datos) > MAX_NOMBRE:
            raise ValueError(f"El nombre excede {MAX_NOMBRE} bytes")
        return datos

    @staticmethod
    def _decodificar_nombre(datos: bytes) -> str:
        return datos.rstrip(b"\x00").decode("ascii")