#include "tlb.h"
#include <string.h>

void tlb_inicializar(TLB *tlb) {
    memset(tlb->entradas, 0, sizeof(tlb->entradas));
    for (int i = 0; i < TLB_TAMANO; i++) {
        tlb->entradas[i].valida = false;
    }
    tlb->contador_uso = 0;
}

bool tlb_buscar(TLB *tlb, uint32_t pagina_virtual, uint32_t *pagina_fisica_out) {
    for (int i = 0; i < TLB_TAMANO; i++) {
        if (tlb->entradas[i].valida && tlb->entradas[i].pagina_virtual == pagina_virtual) {
            tlb->contador_uso++;
            tlb->entradas[i].ultimo_uso = tlb->contador_uso;
            *pagina_fisica_out = tlb->entradas[i].pagina_fisica;
            return true;
        }
    }
    return false;
}

void tlb_insertar(TLB *tlb, uint32_t pagina_virtual, uint32_t pagina_fisica) {
    // 1. Buscar si ya existe una entrada para esta página virtual (actualizar en vez de duplicar)
    for (int i = 0; i < TLB_TAMANO; i++) {
        if (tlb->entradas[i].valida && tlb->entradas[i].pagina_virtual == pagina_virtual) {
            tlb->contador_uso++;
            tlb->entradas[i].pagina_fisica = pagina_fisica;
            tlb->entradas[i].ultimo_uso = tlb->contador_uso;
            return;
        }
    }

    // 2. Buscar un espacio libre (entrada no válida)
    int indice_destino = -1;
    for (int i = 0; i < TLB_TAMANO; i++) {
        if (!tlb->entradas[i].valida) {
            indice_destino = i;
            break;
        }
    }

    // 3. Si no hay espacio libre, elegir la entrada LRU (menor ultimo_uso)
    if (indice_destino == -1) {
        uint32_t menor_uso = tlb->entradas[0].ultimo_uso;
        indice_destino = 0;
        for (int i = 1; i < TLB_TAMANO; i++) {
            if (tlb->entradas[i].ultimo_uso < menor_uso) {
                menor_uso = tlb->entradas[i].ultimo_uso;
                indice_destino = i;
            }
        }
    }

    // 4. Insertar la nueva traducción
    tlb->contador_uso++;
    tlb->entradas[indice_destino].pagina_virtual = pagina_virtual;
    tlb->entradas[indice_destino].pagina_fisica = pagina_fisica;
    tlb->entradas[indice_destino].valida = true;
    tlb->entradas[indice_destino].ultimo_uso = tlb->contador_uso;
}