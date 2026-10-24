from typing import Optional

ROUTE_SIZE = 8

def _bytes_to_ip(datos: bytes) -> str:
    return ".".join(str(b) for b in datos)

def _ip_to_bytes(ip: str) -> bytes:
    partes = ip.split(".")
    if len(partes) != 4:
        raise ValueError(f"IP inválida: {ip!r}")
    return bytes(int(p) for p in partes)

class RoutingTable:
    def __init__(self, vm: VirtualMemory):
        self._vm: VirtualMemory = vm
        self._table: list[int] = []

    def _find_slot(self, destination_ip: str) -> Optional[int]:
        for i in range(len(self._table)):
            destination, _ = self._read_slot(i)
            if destination == destination_ip:
                return i
        return None

    def _read_slot(self, index: int) -> tuple[str, str]:
        data = self._vm.read_bytes(self._table[index], ROUTE_SIZE)
        destination = _bytes_to_ip(data[0:4])
        next_hop = _bytes_to_ip(data[4:8])
        return destination, next_hop

    def _write_slot(self, index: int, destination_ip: str, next_hop_ip: str) -> None:
        data = _ip_to_bytes(destination_ip) + _ip_to_bytes(next_hop_ip)
        self._vm.write_bytes(self._table[index], data)

    def add_route(self, destination_ip: str, next_hop_ip: str) -> bool:
        """Agrega una ruta a la tabla de enrutamiento. Si la ruta ya existe, se actualiza.
        
        Args
            destination_ip (str): Direccion IP destino.
            next_hop_ip (str): Direccion IP de siguiente salto.
        
        Returns
            bool: True si la ruta fue agregada o actualizada exitosamente, False si no hay espacio disponible en la memoria virtual.
        """
        slot_index = self._find_slot(destination_ip)
        if slot_index is None:
            slot_address = self._vm.allocate(ROUTE_SIZE)
            if slot_address is None:
                return False
            self._table.append(slot_address)
            slot_index = len(self._table) - 1
        
        self._write_slot(slot_index, destination_ip, next_hop_ip)
        return True

    def remove_route(self, destination_ip: str) -> bool:
        """Elimina una ruta de la tabla de enrutamiento.
        
        Args
            destination_ip (str): Direccion IP destino.
        
        Returns
            bool: True si la ruta fue eliminada exitosamente, False si la ruta no existe.
        """
        slot_index = self._find_slot(destination_ip)
        if slot_index is not None:
            self._vm.free(self._table[slot_index])
            del self._table[slot_index]
            return True
        return False

    def get_next_hop(self, destination_ip: str) -> Optional[str]:
        """Obtiene la dirección IP del siguiente salto para una dirección IP de destino dada.
        
        Args
            destination_ip (str): Direccion IP destino.
        
        Returns
            Optional[str]: Direccion IP de siguiente salto si la ruta existe, None en caso contrario.
        """
        slot_index = self._find_slot(destination_ip)
        if slot_index is not None:
            _, next_hop = self._read_slot(slot_index)
            return next_hop
        return None