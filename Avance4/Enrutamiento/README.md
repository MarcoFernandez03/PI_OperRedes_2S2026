# Enrutamiento por vector de distancia (Punto F + integración)

Reemplaza al enrutador de `Avance2/rutas` (inundación por IP, sin costos) para la Etapa 3.

| Archivo | Qué hace |
|---|---|
| `vector_distancia.py` | El algoritmo (clase `Nodo`). Sin sockets ni memoria. |
| `tabla_rutas.py` | Guarda el resumen (destino, siguiente salto, costo) en la memoria virtual. |
| `nodo_router.py` | Sockets, hilos, ANNOUNCE cada 30 s, silencio, aviso de muerte, DATA con TTL. |
| `config_isla3.json` | Configuración de SHELL (isla 3): solo sus vecinos y costos. |

## Correr

    cd Avance2/memoria && make lib          # una vez: compila la memoria en C
    cd Avance4/enrutamiento
    python3 nodo_router.py config_isla3.json

## Pendiente / por acordar con los otros grupos
- Formato del ANNOUNCE (hoy: `ANNOUNCE|<isla>|<destino>:<costo>,...`; vive en `armar_announce`/`leer_announce`).
- Tolerancia de silencio (hoy 40 s, con ANNOUNCE cada 30 s) e `INF` (hoy 100).
- IPs de las VLAN de tránsito en `config_isla3.json` (supuestas a partir del ejemplo del enunciado).
- Contadores de TLB (aciertos/fallos) y fallos de página: la memoria todavía no los cuenta.
- Cómo viaja el destino final desde el cliente (Etapa 1, syscall) hasta el puerto 5006 del enrutador.