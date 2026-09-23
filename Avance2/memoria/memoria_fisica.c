#include "memoria_fisica.h"
#include <stdio.h>
#include <stdlib.h>

static uint8_t *ram = NULL;
static size_t tamano_ram = 0;

bool mf_init(size_t tamano_bytes) {
    // Si ya estaba inicializada, liberamos antes de volver a asignar
    if (ram != NULL) {
        mf_destroy();
    }

    if (tamano_bytes == 0) {
        fprintf(stderr, "[Memoria Física ERROR] El tamaño de la memoria no puede ser 0.\n");
        return false;
    }

    ram = (uint8_t *)calloc(tamano_bytes, sizeof(uint8_t));
    if (ram == NULL) {
        fprintf(stderr, "[Memoria Física ERROR] Fallo al asignar %zu bytes de RAM.\n", tamano_bytes);
        return false;
    }

    tamano_ram = tamano_bytes;
    return true;
}

void mf_destroy(void) {
    if (ram != NULL) {
        free(ram);
        ram = NULL;
    }
    tamano_ram = 0;
}

uint8_t mf_read_byte(uint32_t direccion_fisica) {
    if (ram == NULL) {
        fprintf(stderr, "[Memoria Física ERROR] Intento de lectura en memoria NO inicializada.\n");
        return 0x00;
    }

    if (direccion_fisica >= tamano_ram) {
        fprintf(stderr, "[Memoria Física ERROR] Lectura fuera de rango: 0x%X (Límite: 0x%ZX)\n",
                direccion_fisica, tamano_ram - 1);
        return 0x00;
    }

    return ram[direccion_fisica];
}

void mf_write_byte(uint32_t direccion_fisica, uint8_t valor) {
    if (ram == NULL) {
        fprintf(stderr, "[Memoria Física ERROR] Intento de escritura en memoria NO inicializada.\n");
        return;
    }

    if (direccion_fisica >= tamano_ram) {
        fprintf(stderr, "[Memoria Física ERROR] Escritura fuera de rango: 0x%X (Límite: 0x%ZX)\n",
                direccion_fisica, tamano_ram - 1);
        return;
    }

    ram[direccion_fisica] = valor;
}