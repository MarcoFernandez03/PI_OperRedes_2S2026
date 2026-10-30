import struct
import threading

from bitmap import Bitmap
from candados import RegistroCandados
from directorio import Directorio
from disco import Disco, BYTES_POR_BLOQUE, BYTES_POR_SECTOR, TOTAL_BYTES
from inodo import (TablaInodos, TIPO_ARCHIVO, TIPO_DIRECTORIO,
                   PERM_PUBLICO_LECTURA, MAX_NOMBRE_PROPIETARIO)

# Distribución del disco en bloques
TOTAL_BLOQUES = TOTAL_BYTES // BYTES_POR_BLOQUE                              # 64
BLOQUE_SUPERBLOQUE = 0
BLOQUE_BITMAP_INODOS = 1
BLOQUE_BITMAP_DATOS = 2
BLOQUE_TABLA_INODOS = 3
BLOQUES_TABLA_INODOS = 8
NUM_INODOS = BLOQUES_TABLA_INODOS * (BYTES_POR_BLOQUE // BYTES_POR_SECTOR)   # 32
INICIO_DATOS = BLOQUE_TABLA_INODOS + BLOQUES_TABLA_INODOS                    # 11
NUM_BLOQUES_DATOS = TOTAL_BLOQUES - INICIO_DATOS                             # 53
RAIZ = 0


class ErrorSistemaArchivos(Exception):
    pass


class SinEspacio(ErrorSistemaArchivos):
    pass


class NoExiste(ErrorSistemaArchivos):
    pass


class PermisoDenegado(ErrorSistemaArchivos):
    pass


_FORMATO_SB = "<4sIIIIIIII"
_MAGIA = b"RFS1"


class Superbloque:
    def __init__(self, generacion: int = 0):
        self.generacion = generacion

    def serializar(self) -> bytes:
        return struct.pack(_FORMATO_SB, _MAGIA, BYTES_POR_BLOQUE, NUM_INODOS,
                           NUM_BLOQUES_DATOS, BLOQUE_BITMAP_INODOS,
                           BLOQUE_BITMAP_DATOS, BLOQUE_TABLA_INODOS,
                           INICIO_DATOS, self.generacion)

    @staticmethod
    def desde_bytes(datos: bytes) -> "Superbloque":
        campos = struct.unpack(_FORMATO_SB, datos[:struct.calcsize(_FORMATO_SB)])
        if campos[0] != _MAGIA:
            raise ValueError("El disco no tiene formato")
        esperado = (BYTES_POR_BLOQUE, NUM_INODOS, NUM_BLOQUES_DATOS,
                    BLOQUE_BITMAP_INODOS, BLOQUE_BITMAP_DATOS,
                    BLOQUE_TABLA_INODOS, INICIO_DATOS)
        if campos[1:8] != esperado:
            raise ValueError("La geometría del disco no coincide")
        return Superbloque(campos[8])


class SistemaArchivos:
    def __init__(self, disco: Disco, ruta_imagen: str | None = None):
        self._disco = disco
        self._ruta_imagen = ruta_imagen
        self._bitmap_inodos = Bitmap(disco, BLOQUE_BITMAP_INODOS, NUM_INODOS)
        self._bitmap_datos = Bitmap(disco, BLOQUE_BITMAP_DATOS, NUM_BLOQUES_DATOS)
        self._tabla = TablaInodos(disco, self._bitmap_inodos,
                                  BLOQUE_TABLA_INODOS, NUM_INODOS)
        self._dirs = RegistroCandados()
        self._inodos = RegistroCandados()
        self._mutex_meta = threading.Lock()   # superbloque y bitmaps
        self._escritor = threading.Lock()     # un solo escritor a la vez

    # ---------- Ciclo de vida ----------

    def formatear(self) -> None:
        with self._escritor:
            for bloque in range(TOTAL_BLOQUES):
                self._disco.escribir_bloque(bloque, b"")
            self._escribir_superbloque(Superbloque(0))
            inodo, bloque = self._reservar_inodo_y_bloque(TIPO_DIRECTORIO, "ROOT")
            if inodo.numero != RAIZ:
                raise RuntimeError("La raíz debe ser el inodo 0")
            self._disco.escribir_bloque(bloque, Directorio().serializar())
            inodo.asignar_bloques([bloque])
            inodo.tamano = BYTES_POR_BLOQUE
            self._tabla.escribir(inodo)
            self._persistir()

    def montar(self) -> None:
        self._leer_superbloque()
        if self._tabla.leer(RAIZ).tipo != TIPO_DIRECTORIO:
            raise ValueError("El inodo 0 no es un directorio")
        for n in range(NUM_INODOS):
            ocupado = self._bitmap_inodos.consultar_ocupado(n)
            try:
                self._tabla.leer(n)
                usado = True
            except ValueError:
                usado = False
            if ocupado != usado:
                raise ValueError(f"Inconsistencia entre bitmap y tabla en el inodo {n}")

    # ---------- Operaciones públicas ----------

    def guardar_roa(self, propietario: str, ip: str, roa: str) -> bool:
        """Crea o reemplaza el ROA de una IP. Devuelve False si el contenido
        era idéntico, en cuyo caso no cambia nada ni sube la generación."""
        datos = roa.encode("ascii")
        if not datos or len(datos) > BYTES_POR_BLOQUE:
            raise ValueError(f"El ROA debe medir entre 1 y {BYTES_POR_BLOQUE} bytes")
        self._validar_nombres(propietario, ip)
        with self._escritor:
            ubicacion = self._localizar(ip)
            if ubicacion is not None:
                self._exigir_escritura(ubicacion[1], propietario)
                if not self._reemplazar(ubicacion[1], datos):
                    return False
            else:
                self._crear(propietario, ip, datos)
            self._incrementar_generacion()
            self._persistir()
            return True

    def borrar_roa(self, propietario: str, ip: str) -> None:
        with self._escritor:
            ubicacion = self._localizar(ip)
            if ubicacion is None:
                raise NoExiste(ip)
            num_dir, num_archivo = ubicacion
            self._exigir_escritura(num_archivo, propietario)
            # Primero se quita la entrada para que nadie nuevo llegue al inodo
            with self._dirs.obtener(num_dir).escritura():
                directorio = self._leer_directorio(num_dir)
                directorio.quitar(ip)
                self._escribir_directorio(num_dir, directorio)
            # Esperar a los lectores que ya lo tenían abierto
            with self._inodos.obtener(num_archivo).escritura():
                inodo = self._tabla.leer(num_archivo)
                with self._mutex_meta:
                    for bloque in inodo.bloques_en_uso():
                        self._bitmap_datos.liberar(bloque - INICIO_DATOS)
                    self._tabla.liberar(num_archivo)
            self._incrementar_generacion()
            self._persistir()

    def leer_roa(self, ip: str) -> str:
        ubicacion = self._localizar(ip, adquirir_lectura=True)
        if ubicacion is None:
            raise NoExiste(ip)
        num_archivo = ubicacion[1]
        try:
            return self._leer_contenido(num_archivo)
        finally:
            self._inodos.obtener(num_archivo).liberar_lectura()

    def listar_roas(self) -> tuple[int, list[str]]:
        # La generación se lee primero, así el contenido nunca es más viejo que ella
        generacion = self.generacion()
        roas = []
        for _, num_dir in self._emisores():
            roas.extend(self._leer_roas_de(num_dir))
        return generacion, roas

    def generacion(self) -> int:
        with self._mutex_meta:
            return self._leer_superbloque().generacion

    def espacio_libre(self) -> tuple[int, int]:
        """Devuelve (inodos libres, bloques de datos libres)."""
        with self._mutex_meta:
            return (self._bitmap_inodos.contar_libres(),
                    self._bitmap_datos.contar_libres())

    # ---------- Creación y reemplazo ----------

    def _crear(self, propietario: str, ip: str, datos: bytes) -> None:
        num_dir = self._buscar_directorio_emisor(propietario)
        nuevo = num_dir is None
        necesarios = 2 if nuevo else 1
        inodos_libres, bloques_libres = self.espacio_libre()
        if inodos_libres < necesarios or bloques_libres < necesarios:
            raise SinEspacio("No quedan inodos o bloques")
        if self._directorio_lleno(RAIZ if nuevo else num_dir):
            raise SinEspacio("El directorio está lleno")
        if nuevo:
            num_dir = self._crear_directorio_emisor(propietario)
        self._crear_archivo(num_dir, propietario, ip, datos)

    def _crear_directorio_emisor(self, propietario: str) -> int:
        inodo, bloque = self._reservar_inodo_y_bloque(TIPO_DIRECTORIO, propietario)
        self._disco.escribir_bloque(bloque, Directorio().serializar())
        inodo.asignar_bloques([bloque])
        inodo.tamano = BYTES_POR_BLOQUE
        self._tabla.escribir(inodo)
        with self._dirs.obtener(RAIZ).escritura():
            raiz = self._leer_directorio(RAIZ)
            raiz.agregar(propietario, inodo.numero)
            self._escribir_directorio(RAIZ, raiz)
        return inodo.numero

    def _crear_archivo(self, num_dir: int, propietario: str, ip: str,
                       datos: bytes) -> None:
        inodo, bloque = self._reservar_inodo_y_bloque(TIPO_ARCHIVO, propietario)
        self._disco.escribir_bloque(bloque, datos)
        inodo.asignar_bloques([bloque])
        inodo.tamano = len(datos)
        self._tabla.escribir(inodo)
        # Publicar al final, con la entrada de directorio
        with self._dirs.obtener(num_dir).escritura():
            directorio = self._leer_directorio(num_dir)
            directorio.agregar(ip, inodo.numero)
            self._escribir_directorio(num_dir, directorio)

    def _reemplazar(self, num_archivo: int, datos: bytes) -> bool:
        with self._inodos.obtener(num_archivo).escritura():
            inodo = self._tabla.leer(num_archivo)
            bloque = inodo.directos[0]
            if self._disco.leer_bloque(bloque)[:inodo.tamano] == datos:
                return False
            self._disco.escribir_bloque(bloque, datos)
            inodo.tamano = len(datos)
            inodo.tocar()
            self._tabla.escribir(inodo)
        return True

    # ---------- Búsqueda y lectura ----------

    def _localizar(self, ip: str, adquirir_lectura: bool = False):
        """Devuelve (inodo del directorio, inodo del archivo) o None. Con
        adquirir_lectura toma el candado de lectura del archivo antes de
        soltar el del directorio, y quien llama debe liberarlo."""
        for _, num_dir in self._emisores():
            with self._dirs.obtener(num_dir).lectura():
                num_archivo = self._leer_directorio(num_dir).buscar(ip)
                if num_archivo is not None:
                    if adquirir_lectura:
                        self._inodos.obtener(num_archivo).adquirir_lectura()
                    return num_dir, num_archivo
        return None

    def _emisores(self) -> list[tuple[str, int]]:
        with self._dirs.obtener(RAIZ).lectura():
            return self._leer_directorio(RAIZ).listar()

    def _buscar_directorio_emisor(self, propietario: str) -> int | None:
        with self._dirs.obtener(RAIZ).lectura():
            return self._leer_directorio(RAIZ).buscar(propietario)

    def _leer_roas_de(self, num_dir: int) -> list[str]:
        with self._dirs.obtener(num_dir).lectura():
            entradas = self._leer_directorio(num_dir).listar()
            candados = [self._inodos.obtener(n) for _, n in entradas]
            for candado in candados:
                candado.adquirir_lectura()
        try:
            return [self._leer_contenido(n) for _, n in entradas]
        finally:
            for candado in candados:
                candado.liberar_lectura()

    def _leer_contenido(self, num_archivo: int) -> str:
        inodo = self._tabla.leer(num_archivo)
        datos = self._disco.leer_bloque(inodo.directos[0])[:inodo.tamano]
        return datos.decode("ascii")

    # ---------- Directorios ----------

    def _leer_directorio(self, num: int) -> Directorio:
        inodo = self._tabla.leer(num)
        return Directorio.desde_bytes(self._disco.leer_bloque(inodo.directos[0]))

    def _escribir_directorio(self, num: int, directorio: Directorio) -> None:
        inodo = self._tabla.leer(num)
        self._disco.escribir_bloque(inodo.directos[0], directorio.serializar())
        inodo.tocar()
        self._tabla.escribir(inodo)

    def _directorio_lleno(self, num: int) -> bool:
        with self._dirs.obtener(num).lectura():
            return self._leer_directorio(num).esta_lleno()

    # ---------- Metadatos y validaciones ----------

    def _reservar_inodo_y_bloque(self, tipo: int, propietario: str):
        with self._mutex_meta:
            inodo = self._tabla.reservar(tipo, propietario, PERM_PUBLICO_LECTURA)
            if inodo is None:
                raise SinEspacio("No quedan inodos")
            relativo = self._bitmap_datos.reservar()
            if relativo is None:
                self._tabla.liberar(inodo.numero)
                raise SinEspacio("No quedan bloques de datos")
        return inodo, INICIO_DATOS + relativo

    def _exigir_escritura(self, num_archivo: int, solicitante: str) -> None:
        if not self._tabla.leer(num_archivo).permite(solicitante, "escribir"):
            raise PermisoDenegado("El ROA pertenece a otro emisor")

    def _validar_nombres(self, propietario: str, ip: str) -> None:
        prueba = Directorio()
        prueba.agregar(propietario, 1)
        prueba.agregar(ip, 2)
        if len(propietario.encode("ascii")) > MAX_NOMBRE_PROPIETARIO:
            raise ValueError("El propietario excede el tamaño permitido")

    def _leer_superbloque(self) -> Superbloque:
        return Superbloque.desde_bytes(self._disco.leer_bloque(BLOQUE_SUPERBLOQUE))

    def _escribir_superbloque(self, superbloque: Superbloque) -> None:
        self._disco.escribir_bloque(BLOQUE_SUPERBLOQUE, superbloque.serializar())

    def _incrementar_generacion(self) -> None:
        with self._mutex_meta:
            superbloque = self._leer_superbloque()
            superbloque.generacion += 1
            self._escribir_superbloque(superbloque)

    def _persistir(self) -> None:
        if self._ruta_imagen is not None:
            self._disco.guardar(self._ruta_imagen)