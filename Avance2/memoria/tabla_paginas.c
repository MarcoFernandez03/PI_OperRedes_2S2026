#include "tabla_paginas.h"
#include <stdlib.h>

TablaPaginas* tp_crear(uint32_t num_paginas) {
    TablaPaginas *tp = malloc(sizeof(TablaPaginas));
    if (!tp) return NULL;

    tp->entradas = calloc(num_paginas, sizeof(EntradaTabla));
    if (!tp->entradas) {
        free(tp);
        return NULL;
    }

    tp->num_paginas = num_paginas;
    // calloc ya deja valida = false (0) en cada entrada, pero lo dejamos explícito:
    for (uint32_t i = 0; i < num_paginas; i++) {
        tp->entradas[i].valida = false;
    }

    return tp;
}

void tp_destruir(TablaPaginas *tp) {
    if (!tp) return;
    free(tp->entradas);
    free(tp);
}

bool tp_traducir(TablaPaginas *tp, uint32_t pagina_virtual, uint32_t *pagina_fisica_out) {
    if (pagina_virtual >= tp->num_paginas) return false;
    if (!tp->entradas[pagina_virtual].valida) return false;

    *pagina_fisica_out = tp->entradas[pagina_virtual].pagina_fisica;
    return true;
}

void tp_mapear(TablaPaginas *tp, uint32_t pagina_virtual, uint32_t pagina_fisica) {
    if (pagina_virtual >= tp->num_paginas) return;  // fuera de rango, ignorar
    tp->entradas[pagina_virtual].pagina_fisica = pagina_fisica;
    tp->entradas[pagina_virtual].valida = true;
}