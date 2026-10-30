from disco import Disco, BYTES_POR_BLOQUE

class Bitmap:
    def __init__(self, disco: Disco, bloque: int, capacidad: int):
        if capacidad < 1 or capacidad > BYTES_POR_BLOQUE * 8:
            raise ValueError("Capacidad fuera de rango")
        self._disco = disco
        self._bloque = bloque
        self._capacidad = capacidad

    def reservar(self) -> int | None:
        """Reserva un indice en el bitmap y lo devuelve.
        
        
        Returns
            int: El índice reservado.
        
        Raises
            ValueError: Si no hay espacio disponible en el bitmap.
        """
        bitmap = bytearray(self._disco.leer_bloque(self._bloque))
        for i in range(self._capacidad):
            byte, mascara = self._posicion(i)
            if not bitmap[byte] & mascara:
                bitmap[byte] |= mascara
                self._disco.escribir_bloque(self._bloque, bitmap)
                return i
        return None

    def liberar(self, indice: int) -> None:
        """Libera un índice en el bitmap.
        
        Args
            indice (int): El índice a liberar.
        
        Raises
            ValueError: Si el índice está fuera de rango o ya está libre.
        """
        self._validar_indice(indice)
        byte, mascara = self._posicion(indice)
        bitmap = bytearray(self._disco.leer_bloque(self._bloque))
        if bitmap[byte] & mascara:
            bitmap[byte] &= 0xFF ^ mascara
            self._disco.escribir_bloque(self._bloque, bitmap)
        else:
            raise ValueError(f"El bit {indice} ya estaba libre")

    def marcar_ocupado(self, indice: int) -> None:
        """Marca un índice como ocupado en el bitmap.
        
        Args
            indice (int): El índice a marcar como ocupado.
        
        Raises
            ValueError: Si el índice está fuera de rango o ya está ocupado.
        """
        self._validar_indice(indice)
        byte, mascara = self._posicion(indice)
        bitmap = bytearray(self._disco.leer_bloque(self._bloque))
        if not bitmap[byte] & mascara:
            bitmap[byte] |= mascara
            self._disco.escribir_bloque(self._bloque, bitmap)
        else:
            raise ValueError(f"El bit {indice} ya estaba ocupado")

    def consultar_ocupado(self, indice: int) -> bool:
        """Consulta si un índice está ocupado en el bitmap.
        
        Args
            indice (int): El índice a consultar.
        
        Returns
            bool: True si el índice está ocupado, False si está libre.
        
        Raises
            ValueError: Si el índice está fuera de rango.
        """
        self._validar_indice(indice)
        byte, mascara = self._posicion(indice)
        bitmap = self._disco.leer_bloque(self._bloque)
        return bool(bitmap[byte] & mascara)

    def contar_libres(self) -> int:
        """Consulta la cantidad de índices libres en el bitmap.
        
        Returns
            int: La cantidad de índices libres.
        """
        bitmap = self._disco.leer_bloque(self._bloque)
        count = 0
        for i in range(self._capacidad):
            byte, mascara = self._posicion(i)
            if not bitmap[byte] & mascara:
                count += 1
        return count

    def liberar_todo(self) -> None:
        """Libera todos los índices en el bitmap.
        """
        self._disco.escribir_bloque(self._bloque, bytes(BYTES_POR_BLOQUE))

    def _posicion(self, i: int) -> tuple[int, int]:
        return i // 8, 1 << (i % 8)

    def _validar_indice(self, i: int) -> None:
        if i < 0 or i >= self._capacidad:
            raise ValueError("Índice fuera de rango")