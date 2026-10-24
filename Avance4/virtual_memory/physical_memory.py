class PhysicalMemory:
    def __init__(self, size: int):
        """Crea la memoria física como un bloque contiguo de bytes en cero.

        Args
            size: Tamaño total de la memoria en bytes. Debe ser mayor que cero.

        Raises
            ValueError: Si size es menor o igual a cero.
        """
        if size <= 0:
            raise ValueError("El tamaño de la memoria física debe ser mayor que cero.")
        self.memory: bytearray = bytearray(size)

    def read_bytes(self, address: int, length: int) -> bytes:
        """Lee bytes de la memoria física.

        Args
            address: Dirección absoluta dentro de la memoria.
            length: Número de bytes a leer.

        Returns
            Los valores de los bytes leídos, como un objeto bytes.

        Raises
            ValueError: Si la dirección o el rango de bytes a leer está fuera de los límites de la memoria física.
        """
        self._validate_range(address, length)
        return bytes(self.memory[address:address + length])

    def write_bytes(self, address: int, data: bytes) -> None:
        """Escribe bytes en la memoria física.

        Args
            address: Dirección absoluta donde se escriben los bytes.
            data: Bytes a escribir en la memoria física.

        Raises
            ValueError: Si la dirección o el rango de bytes a escribir está fuera de los límites de la memoria física.
        """
        self._validate_range(address, len(data))
        self.memory[address:address + len(data)] = data

    def _validate_range(self, address: int, length: int) -> None:
        if address < 0 or length < 0 or address + length > len(self.memory):
            raise ValueError("Rango fuera de los límites de la memoria física.")
