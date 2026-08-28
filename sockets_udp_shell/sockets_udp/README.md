# Sockets UDP — Grupo SHELL

Módulo de sockets en C++ para el Trabajo 1 (Redes / Sistemas Operativos).
Implementa la capa de comunicación sobre `SOCK_DGRAM` que usará el protocolo
confiable definido por el equipo (fragmentación, `seq`, `ACK`, timeout,
retransmisión) para enviar datos del sensor desde el Raspberry Pi hacia la
computadora Linux/Mac que actúa como servidor.

## Separación sockets ↔ protocolo

Como se comentó en el equipo, el socket no debería depender del protocolo.
Por eso el código está dividido en dos capas independientes:

- **`UDPSocket`** (`include/UDPSocket.h`, `src/UDPSocket.cpp`): solo sabe
  mandar y recibir bytes por UDP, con timeout configurable. No conoce nada
  de `DATA`/`ACK`/`FIN` ni de números de secuencia.
- **`protocolo::Trama`** (`include/Trama.h`, `src/Trama.cpp`): solo sabe
  convertir los campos del encabezado (`tipo`, `seq`, `longitud`, `payload`)
  hacia/desde un buffer de bytes. No conoce nada de sockets.

La lógica de "esperar ACK, reintentar, detectar duplicados" (que es la
parte que decidan otros compañeros del equipo o que se ajuste en clase) usa
ambas piezas, pero vive aparte, en los programas de `examples/`.

## Estructura del proyecto

```
sockets_udp/
├── include/
│   ├── SocketException.h   # Excepción para errores de socket
│   ├── UDPSocket.h          # Wrapper del socket UDP
│   └── Trama.h              # Serialización de encabezados del protocolo
├── src/
│   ├── UDPSocket.cpp
│   └── Trama.cpp
├── examples/
│   ├── ejemplo_emisor.cpp    # Raspberry Pi: fragmenta y envía un archivo
│   └── ejemplo_receptor.cpp  # Servidor: recibe y reconstruye el archivo
├── Makefile
└── README.md
```

## API de `UDPSocket`

```cpp
UDPSocket socket;                          // crea el socket (o lanza SocketException)

// --- Lado receptor (servidor) ---
socket.bind(30000);                        // escucha en el puerto 30000, todas las interfaces
int n = socket.receiveFrom(buffer, tam, &ipOrigen, &puertoOrigen);

// --- Lado emisor (Raspberry Pi) ---
socket.setDestino("192.168.1.50", 30000);  // fija el destino una sola vez
socket.setTimeout(2);                      // timeout de 2s para receiveFrom()
socket.send(buffer, tam);                  // usa el destino fijado
// o, sin fijar destino:
socket.sendTo(buffer, tam, "192.168.1.50", 30000);

try {
    socket.receiveFrom(bufferAck, tam);
} catch (const SocketTimeoutException&) {
    // no llegó el ACK a tiempo -> retransmitir (MAX_REINTENTOS)
}
```

Todas las fallas de llamadas al sistema (`socket`, `bind`, `sendto`,
`recvfrom`, `setsockopt`) se reportan lanzando `SocketException`, igual que
en el ejemplo del PDF. El caso especial de "expiró el timeout" lanza
`SocketTimeoutException` (que hereda de `SocketException`), para que la
capa de protocolo pueda distinguirlo de un error real y decidir
retransmitir.

## Por qué las tramas se serializan a mano (`Trama.h`)

No se envía el `struct` de C++ directamente por el socket porque:

1. **Padding**: el compilador puede insertar bytes de relleno entre
   campos para alinearlos en memoria (por ejemplo entre el `uint8_t` y el
   `uint32_t`), así que `sizeof(struct)` puede no ser igual a la suma de
   los tamaños de los campos (1+4+2 = 7 bytes), y puede variar entre el
   Raspberry Pi (ARM) y el servidor (x86_64 / Mac).
2. **Orden de bytes (endianness)**: por convención de red los campos
   multi-byte (`seq`, `longitud`) se envían en *network byte order*
   (big-endian), usando `htonl`/`ntohl` y `htons`/`ntohs`. No hay que
   asumir que emisor y receptor tienen la misma arquitectura.

`protocolo::construirTramaDatos()` / `construirTramaAck()` arman el buffer
de bytes exacto a enviar; `parsearTramaDatos()` / `parsearTramaAck()` lo
interpretan del lado receptor, validando que la longitud declarada
coincida con los bytes realmente recibidos.

## Formato de las tramas (según el protocolo acordado)

```
DATA / FIN                         ACK
+--------+--------+----------+     +--------+--------+
| tipo   | seq    | longitud |     | tipo   | seq    |
| 1 byte | 4 bytes| 2 bytes  |     | 1 byte | 4 bytes|
+--------+--------+----------+     +--------+--------+
| payload (longitud bytes)   |
+-----------------------------+
```

- `tipo`: `0 = DATA`, `1 = ACK`, `2 = FIN`.
- `seq`: número de secuencia del fragmento.
- `longitud`: bytes de payload (no aplica en ACK).

## Ejemplos incluidos

Los dos programas en `examples/` implementan el flujo completo descrito en
el documento del protocolo (fragmentación, timeout, reintentos,
detección de duplicados) usando únicamente `UDPSocket` y `Trama`, a modo de
prueba de concepto y para dejar documentado cómo se integran ambas piezas.
En el proyecto final, el emisor tomaría los datos desde la syscall que
implementen para leer el sensor, en vez de leer un archivo — el resto del
flujo (fragmentar, enviar, esperar ACK) es igual.

### Compilar

```bash
make
```

Genera `ejemplo_receptor` y `ejemplo_emisor`.

### Probar (dos terminales, o dos máquinas en la misma red)

Terminal del servidor (Linux/Mac):
```bash
./ejemplo_receptor 30000 salida.txt
```

Terminal del cliente (Raspberry Pi, o localhost para probar):
```bash
./ejemplo_emisor <IP_DEL_SERVIDOR> 30000 archivo_a_enviar.txt
```

Al terminar, `salida.txt` debe ser idéntico al archivo original. Esto ya
se probó localmente (incluyendo un archivo de ~118 fragmentos) y el
resultado es byte a byte idéntico.

## Notas / pendientes para integrar con el resto del equipo

- `protocolo::MAX_PAYLOAD` (actualmente 1024 bytes) y `MAX_REINTENTOS`
  (actualmente 5) están como constantes fáciles de ajustar; falta acordar
  los valores finales con el equipo (el documento del protocolo especifica
  `TIMEOUT_SEG` entre 2 y 3 segundos, ya usado como valor por defecto).
- El emisor de ejemplo lee un archivo con `ifstream`; cuando esté lista la
  syscall del sensor, solo hay que reemplazar esa fuente de datos por lo
  que devuelva la syscall — el resto (fragmentar, `enviarFragmentoConfirmado`)
  no cambia.
- `UDPSocket` funciona igual en Linux (Raspberry Pi OS) y en macOS, ya que
  usa únicamente llamadas POSIX estándar (`socket`, `bind`, `sendto`,
  `recvfrom`, `setsockopt` con `SO_RCVTIMEO`).
