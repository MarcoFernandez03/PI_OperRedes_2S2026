#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "memoria_virtual.h"

int main(void) {
    MemoriaVirtual *mv = mv_crear(8, 24); // valores reales confirmados: 8 bytes/página, 24 páginas
    assert(mv != NULL);

    mv_write_byte(mv, 5, 0xAB);
    assert(mv_read_byte(mv, 5) == 0xAB);

    // Escribir/leer varios bytes (ej. simulando una IP de 4 bytes) dentro de una misma página
    uint8_t ip[4] = {192, 168, 1, 1};
    mv_write_bytes(mv, 16, ip, 4);
    uint8_t ip_leida[4];
    mv_read_bytes(mv, 16, ip_leida, 4);
    assert(memcmp(ip, ip_leida, 4) == 0);

    // Forzar varios TLB misses/hits cruzando las 24 páginas disponibles (8 * 24 = 192 bytes en total)
    for (int i = 0; i < 24; i++) {
        mv_write_byte(mv, i * 8, (uint8_t)i);
    }
    for (int i = 0; i < 24; i++) {
        assert(mv_read_byte(mv, i * 8) == (uint8_t)i);
    }

    mv_destruir(mv);
    printf("Todas las pruebas pasaron.\n");
    return 0;
}