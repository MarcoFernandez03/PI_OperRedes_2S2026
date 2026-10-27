import os
from typing import Tuple

RUTA_ARCHIVO = "disco.bin" #Placeholder

PLATOS = 2
PISTAS_POR_PLATO = 16
SECTORES_POR_PISTA = 8
BYTES_POR_SECTOR = 128
SECTORES_POR_BLOQUE = 4
BYTES_POR_BLOQUE = BYTES_POR_SECTOR * SECTORES_POR_BLOQUE
TOTAL_SECTORES = PLATOS * PISTAS_POR_PLATO * SECTORES_POR_PISTA
TOTAL_BYTES = TOTAL_SECTORES * BYTES_POR_SECTOR

class Disco:
    def __init__(self):
        self.almacenamiento = bytearray(TOTAL_BYTES)
    
    def leer_sector(self, sector: int) -> bytes:
        """Lee un sector del disco. Devuelve exactamente BYTES_POR_SECTOR bytes.

        Args
            sector (int): El número de sector a leer.
        
        Returns
            bytes: Los datos del sector leído.

        Raises
            ValueError: Si el número de sector está fuera de rango.
        """
        self._validar_indice(sector)
        return bytes(self.almacenamiento[sector * BYTES_POR_SECTOR:(sector + 1) * BYTES_POR_SECTOR])
    
    def escribir_sector(self, sector: int, datos: bytes) -> None:
        """Escribe un sector del disco. Los datos deben tener exactamente BYTES_POR_SECTOR bytes.

        Args
            sector (int): El número de sector a escribir.
            datos (bytes): Los datos a escribir en el sector.

        Raises
            ValueError: Si el número de sector está fuera de rango o los datos no tienen la longitud correcta.
        """
        self._validar_indice(sector)
        if len(datos) != BYTES_POR_SECTOR:
            raise ValueError(f"Los datos deben tener exactamente {BYTES_POR_SECTOR} bytes")
        self.almacenamiento[sector * BYTES_POR_SECTOR:(sector + 1) * BYTES_POR_SECTOR] = datos
    
    def leer_bloque(self, bloque: int) -> bytes:
        """Lee un bloque del disco. Devuelve exactamente BYTES_POR_BLOQUE bytes.

        Args
            bloque (int): El número de bloque a leer.
        
        Returns
            bytes: Los datos del bloque leído.

        Raises
            ValueError: Si el número de bloque está fuera de rango.
        """
        self._validar_indice(bloque * SECTORES_POR_BLOQUE)
        return bytes(self.almacenamiento[bloque * BYTES_POR_BLOQUE:(bloque + 1) * BYTES_POR_BLOQUE])

    def escribir_bloque(self, bloque: int, datos: bytes) -> None:
        """Escribe un bloque del disco. Los datos deben tener como máximo BYTES_POR_BLOQUE bytes.

        Args
            bloque (int): El número de bloque a escribir.
            datos (bytes): Los datos a escribir en el bloque.
        
        Raises
            ValueError: Si el número de bloque está fuera de rango o los datos exceden la longitud máxima.
        """
        self._validar_indice(bloque * SECTORES_POR_BLOQUE)
        if len(datos) > BYTES_POR_BLOQUE:
            raise ValueError(f"Los datos no pueden exceder {BYTES_POR_BLOQUE} bytes")
        datos = datos.ljust(BYTES_POR_BLOQUE, b'\x00')
        self.almacenamiento[bloque * BYTES_POR_BLOQUE:(bloque + 1) * BYTES_POR_BLOQUE] = datos

    def guardar(self, ruta: str = RUTA_ARCHIVO) -> None:
        """Guarda el contenido del disco en un archivo. Se utiliza un archivo temporal para asegurar la integridad de los datos.

        Args
            ruta (str): La ruta del archivo donde se guardará el contenido del disco.
        
        Raises
            OSError: Si ocurre un error al escribir en el archivo.
        """
        temporal = ruta + ".tmp"
        with open(temporal, "wb") as file:
            file.write(self.almacenamiento)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporal, ruta)

    def cargar(self, ruta: str = RUTA_ARCHIVO) -> bool:
        """Carga el contenido del disco desde un archivo. Devuelve True si se cargó correctamente, False si el archivo no existe.

        Args
            ruta (str): La ruta del archivo desde donde se cargará el contenido del disco.

        Returns
            bool: True si se cargó correctamente, False si el archivo no existe.
        
        Raises
            ValueError: Si el archivo no coincide con el tamaño del disco.
            OSError: Si ocurre un error al leer el archivo.
        """
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
        except FileNotFoundError:
            return False
        if len(datos) != TOTAL_BYTES:
            raise ValueError("El archivo no coincide con el tamaño del disco")
        self.almacenamiento = bytearray(datos)
        return True
    
    def ubicar(self, indice: int) -> Tuple[int, int, int]:
        """Devuelve la ubicación del sector en términos de (sector, pista, plato).

        Args
            indice (int): El número de sector a ubicar.

        Returns
            Tuple[int, int, int]: Una tupla con (sector, pista, plato).

        Raises
            ValueError: Si el número de sector está fuera de rango.
        """
        self._validar_indice(indice)
        sector: int = indice % SECTORES_POR_PISTA
        pista: int = (indice // SECTORES_POR_PISTA) % PISTAS_POR_PLATO
        plato: int = indice // (SECTORES_POR_PISTA * PISTAS_POR_PLATO)
        return (sector, pista, plato)

    def _validar_indice(self, indice: int) -> None:
        if indice < 0 or indice >= TOTAL_SECTORES:
            raise ValueError("Índice fuera de rango")
    