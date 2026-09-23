#include "memoria_virtual.h"
#include "memoria_fisica.h"
#include "tabla_paginas.h"
#include "tlb.h"
#include <stdlib.h>
#include <stdio.h>

struct MemoriaVirtual {
    TLB tlb;
    TablaPaginas *tabla_paginas;
    uint32_t tam_pagina;
    uint32_t num_paginas;
    uint32_t siguiente_pagina_fisica_libre;  // asignación bajo demanda, simple e incremental
};

MemoriaVirtual* mv_crear(uint32_t tam_pagina, uint32_t num_paginas) {
    MemoriaVirtual *mv = malloc(sizeof(MemoriaVirtual));
    if (!mv) return NULL;

    size_t tam_total_bytes = (size_t)tam_pagina * (size_t)num_paginas;
    if (!mf_init(tam_total_bytes)) {
        free(mv);
        return NULL;
    }

    mv->tabla_paginas = tp_crear(num_paginas);
    if (!mv->tabla_paginas) {
        free(mv);
        return NULL;
    }

    tlb_inicializar(&mv->tlb);
    mv->tam_pagina = tam_pagina;
    mv->num_paginas = num_paginas;
    mv->siguiente_pagina_fisica_libre = 0;

    return mv;
}

void mv_destruir(MemoriaVirtual *mv) {
    if (!mv) return;
    tp_destruir(mv->tabla_paginas);
    mf_destroy();
    free(mv);
}

// Traduce una dirección virtual a física, mapeando la página si es la primera vez que se usa.
// TLB miss -> tabla de páginas miss -> se asigna una página física nueva (bajo demanda).
static uint32_t traducir(MemoriaVirtual *mv, uint32_t direccion_virtual, uint32_t *offset_out) {
    uint32_t pagina_virtual = direccion_virtual / mv->tam_pagina;
    uint32_t offset = direccion_virtual % mv->tam_pagina;
    uint32_t pagina_fisica;

    if (pagina_virtual >= mv->num_paginas) {
        fprintf(stderr,
                "ERROR: direccion virtual %u fuera de rango (pagina %u >= num_paginas %u)\n",
                direccion_virtual, pagina_virtual, mv->num_paginas);
        exit(1);
    }

    if (!tlb_buscar(&mv->tlb, pagina_virtual, &pagina_fisica)) {
        if (!tp_traducir(mv->tabla_paginas, pagina_virtual, &pagina_fisica)) {
            // Primer acceso a esta página virtual: asignarle la siguiente página física libre
            pagina_fisica = mv->siguiente_pagina_fisica_libre;
            mv->siguiente_pagina_fisica_libre++;
            tp_mapear(mv->tabla_paginas, pagina_virtual, pagina_fisica);
        }
        tlb_insertar(&mv->tlb, pagina_virtual, pagina_fisica);
    }

    *offset_out = offset;
    return pagina_fisica;
}

uint8_t mv_read_byte(MemoriaVirtual *mv, uint32_t direccion_virtual) {
    uint32_t offset;
    uint32_t pagina_fisica = traducir(mv, direccion_virtual, &offset);
    uint32_t direccion_fisica = pagina_fisica * mv->tam_pagina + offset;
    return mf_read_byte(direccion_fisica);
}

void mv_write_byte(MemoriaVirtual *mv, uint32_t direccion_virtual, uint8_t valor) {
    uint32_t offset;
    uint32_t pagina_fisica = traducir(mv, direccion_virtual, &offset);
    uint32_t direccion_fisica = pagina_fisica * mv->tam_pagina + offset;
    mf_write_byte(direccion_fisica, valor);
}

void mv_read_bytes(MemoriaVirtual *mv, uint32_t direccion_virtual, uint8_t *buffer, uint32_t cantidad) {
    for (uint32_t i = 0; i < cantidad; i++) {
        buffer[i] = mv_read_byte(mv, direccion_virtual + i);
    }
}

void mv_write_bytes(MemoriaVirtual *mv, uint32_t direccion_virtual, const uint8_t *buffer, uint32_t cantidad) {
    for (uint32_t i = 0; i < cantidad; i++) {
        mv_write_byte(mv, direccion_virtual + i, buffer[i]);
    }
}