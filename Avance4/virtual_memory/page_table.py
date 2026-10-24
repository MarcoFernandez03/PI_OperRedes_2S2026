from typing import Optional

class PageTable:
    def __init__(self, num_pages: int):
        """Crea una tabla de páginas con un número especificado de páginas.

        Args
            num_pages: Número total de páginas virtuales. Debe ser mayor que cero.

        Raises
            ValueError: Si num_pages es menor o igual a cero.
        """
        if num_pages <= 0:
            raise ValueError("El número de páginas debe ser mayor que cero.")
        self.table: list[Optional[int]] = [None] * num_pages

    def look_up(self, virtual_page_number: int) -> Optional[int]:
        """Traduce una página virtual a su página física.

        Args
            virtual_page_number: Número de página virtual.

        Returns
            El número de página física, o None si la página está fuera
            de rango o no está mapeada (fallo de página).
        """
        if not 0 <= virtual_page_number < len(self.table):
            return None
        return self.table[virtual_page_number]

    def map(self, virtual_page_number: int, physical_frame_number: int) -> None:
        """Mapea una página virtual a una página física.

        Args
            virtual_page_number: Número de página virtual.
            physical_frame_number: Número de marco físico asociado.

        Raises
            IndexError: Si virtual_page_number está fuera de rango.
        """
        if not 0 <= virtual_page_number < len(self.table):
            raise IndexError("La página virtual está fuera de rango.")
        self.table[virtual_page_number] = physical_frame_number