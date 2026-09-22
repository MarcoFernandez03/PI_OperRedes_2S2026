#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "memoria_virtual.h"

int main(void) {
    MemoriaVirtual *mv = mv_crear(64, 32); // páginas de 64 bytes, 16 páginas -> valores de prueba
    assert(mv != NULL);

    mv_write_byte(mv, 10, 0xAB);
    assert(mv_read_byte(mv, 10) == 0xAB);

    // Escribir/leer varios bytes (ej. simulando una IP de 4 bytes)
    uint8_t ip[4] = {192, 168, 1, 1};
    mv_write_bytes(mv, 100, ip, 4);
    uint8_t ip_leida[4];
    mv_read_bytes(mv, 100, ip_leida, 4);
    assert(memcmp(ip, ip_leida, 4) == 0);

    // Forzar varios TLB misses/hits cruzando páginas
    for (int i = 0; i < 20; i++) {
        mv_write_byte(mv, i * 64, (uint8_t)i);
    }
    for (int i = 0; i < 20; i++) {
        assert(mv_read_byte(mv, i * 64) == (uint8_t)i);
    }

    mv_destruir(mv);
    printf("Todas las pruebas pasaron.\n");
    return 0;
}