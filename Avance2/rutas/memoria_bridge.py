
"""
Envoltorio en ctypes sobre memoria/libmemoria.so (el módulo de memoria
virtual + TLB + tabla de páginas en C). Este archivo es la ÚNICA parte
del código Python que sabe que la memoria está implementada en C; el
resto del código de rutas (tabla_rutas.py, escuchar_nodo_router.py)
solo ve una clase Python normal.

Requiere haber compilado la librería primero:
    cd memoria && make lib
"""

import ctypes
import os

# Ruta a libmemoria.so, relativa a este archivo (rutas/ vive junto a memoria/).
_RUTA_LIB = os.path.join(os.path.dirname(__file__), "..", "memoria", "libmemoria.so")


class MemoriaVirtual:
    """
    Espejo en Python de la struct opaca MemoriaVirtual* de memoria_virtual.h.
    Cada llamada a read_bytes/write_bytes pasa por mv_read_byte/mv_write_byte
    en C, que a su vez resuelven la dirección vía TLB -> tabla de páginas
    -> asignación de página física bajo demanda, exactamente como lo exige
    el enunciado. Python no reimplementa nada de esa lógica.

    Nota sobre ruta_lib: en el proyecto real, cada router corre en su
    propio proceso Python (una Raspberry Pi = un proceso), así que cada
    uno carga su propia copia de la librería en su propia memoria de
    proceso, sin ningún problema. El parámetro ruta_lib solo hace falta
    para pruebas que simulan varios routers dentro del MISMO proceso
    Python: ctypes reutiliza la misma librería cargada si la ruta es
    idéntica (dlopen no duplica por contenido, solo por ruta), así que
    todas las instancias terminarían compartiendo la misma RAM física
    simulada (el arreglo static de memoria_fisica.c) y pisándose entre
    sí. Para esos casos de prueba, cada instancia debe apuntar a una
    copia del .so con un nombre de archivo distinto.
    """

    def __init__(self, tam_pagina: int, num_paginas: int, ruta_lib: str = _RUTA_LIB):
        if not os.path.exists(ruta_lib):
            raise FileNotFoundError(
                f"No se encontró {ruta_lib}. Hay que compilar la librería primero: "
                f"cd memoria && make lib"
            )

        self._lib = ctypes.CDLL(ruta_lib)

        # Firmas de las funciones C (evita que ctypes asuma int de 32 bits
        # por defecto para argumentos/retornos que en realidad son punteros
        # o uint32_t; sin esto, en algunas plataformas los punteros a
        # MemoriaVirtual* se truncan y todo revienta con corrupción silenciosa).
        self._lib.mv_crear.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self._lib.mv_crear.restype = ctypes.c_void_p

        self._lib.mv_destruir.argtypes = [ctypes.c_void_p]
        self._lib.mv_destruir.restype = None

        self._lib.mv_read_bytes.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32
        ]
        self._lib.mv_read_bytes.restype = None

        self._lib.mv_write_bytes.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32
        ]
        self._lib.mv_write_bytes.restype = None

        self._mv = self._lib.mv_crear(tam_pagina, num_paginas)
        if not self._mv:
            raise MemoryError("mv_crear() devolvió NULL")

        self.tam_pagina = tam_pagina
        self.num_paginas = num_paginas

    def read_bytes(self, direccion_virtual: int, cantidad: int) -> bytes:
        buffer = ctypes.create_string_buffer(cantidad)
        self._lib.mv_read_bytes(self._mv, direccion_virtual, buffer, cantidad)
        return buffer.raw

    def write_bytes(self, direccion_virtual: int, datos: bytes) -> None:
        self._lib.mv_write_bytes(self._mv, direccion_virtual, datos, len(datos))

    def cerrar(self) -> None:
        if getattr(self, "_mv", None):
            self._lib.mv_destruir(self._mv)
            self._mv = None

    def __del__(self):
        # Best-effort: libera la memoria en C si el objeto Python se recolecta
        # sin haber llamado cerrar() explícitamente.
        try:
            self.cerrar()
        except Exception:
            pass