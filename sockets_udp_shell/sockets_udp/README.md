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

## Integración con la syscall del kernel

`Kernel/send_sensor_data.c` implementa una syscall que crea un socket UDP
**en kernel**, envía un único datagrama, y cierra el socket
(`sock_create_kern` → `kernel_sendmsg` → `sock_release`, todo en la misma
llamada). Esto tiene dos implicaciones para la integración con `UDPSocket`:

1. **No hay `bind()` antes de enviar** → el puerto de origen es efímero y
   distinto en cada llamada.
2. **El socket se cierra apenas termina de enviar** → no hay forma de
   recibir una respuesta (el ACK) por ese mismo camino.

Por eso la integración separa emisión y recepción en dos canales
distintos del lado del Raspberry Pi:

- **Salida (DATA/FIN)** → por la syscall, vía `enviarPorSyscall()`
  (`include/SyscallTransport.h`).
- **Entrada (ACK)** → por un `UDPSocket` normal, bindeado a un **puerto
  fijo conocido de antemano** (`PUERTO_ACK_LOCAL` en los argumentos del
  programa). El servidor debe contestar el ACK a ese puerto fijo, no al
  puerto de origen que ve en `recvfrom()` (ese es el efímero de la
  syscall, ya cerrado). La IP sí puede tomarse de `recvfrom()`
  normalmente.

### Archivos nuevos

| Archivo | Rol |
|---|---|
| `include/SyscallTransport.h`, `src/SyscallTransport.cpp` | Wrapper de `syscall(NUMERO, ...)` para invocar `send_sensor_data` desde C++ |
| `examples/ejemplo_emisor_syscall.cpp` | Emisor: envía por la syscall, recibe ACK por `UDPSocket` en puerto fijo |
| `examples/ejemplo_receptor_syscall.cpp` | Receptor: contesta el ACK al puerto fijo del Pi, no al puerto de origen |

### ⚠️ Falta un dato: el número de syscall

`include/SyscallTransport.h` define:

```cpp
constexpr long NUMERO_SYSCALL_SEND_SENSOR_DATA = 471; // <-- CONFIRMAR
```

Ese `471` es una **estimación**, no un dato confirmado. El equipo dijo
que usa **kernel 6.18**, y desde el kernel 6.11 arm64 dejó de tener tabla
de syscalls propia: usa la misma tabla genérica que el resto de
arquitecturas modernas (`scripts/syscall.tbl`). Revisando esa tabla en el
árbol oficial de Linux, el último número asignado hasta la serie 6.18 es
`470` (`listns`); los números `471` (`rseq_slice_yield`) y `472`
(`fchroot`) son adiciones posteriores, todavía no presentes en 6.18. Si
agregaron `send_sensor_data` al final del archivo sin tocar nada más, lo
más probable es que haya quedado en el **471** — por eso ese es el valor
que trae el código. Aun así, hay que **confirmarlo** contra el archivo
real que editaron al compilar el kernel (buscar la línea con
`send_sensor_data`). Sin el número correcto, la llamada falla con
`ENOSYS` ("Function not implemented").

**Importante:** ese número es específico del kernel exacto que
compilaron. Probarlo en cualquier otra máquina (por ejemplo, una laptop
x86_64 con Linux estándar) no sirve para validar nada — podría incluso
coincidir por casualidad con una syscall real distinta ya existente ahí,
dando un error que no tiene nada que ver con el código (esto pasó al
probar el placeholder anterior, `451`, en un x86_64: coincide con
`cachestat`, y el kernel devolvió `EBADF` en vez de `ENOSYS`, porque
`cachestat` esperaba un descriptor de archivo como primer argumento). La
única prueba real es en el Raspberry Pi, con `Kernel/Image` booteado.

### Por qué se deshace el `htonl` antes de llamar a la syscall

`send_sensor_data` recibe `dest_ip` y hace `htonl(dest_ip)` internamente
(línea `addr.sin_addr.s_addr = htonl(dest_ip)` en el `.c`). Pero
`inet_pton()` en el lado de userspace ya entrega la IP en orden de red.
Si se le pasara ese valor tal cual a la syscall, el `htonl` del kernel lo
invertiría *de nuevo* y la IP llegaría corrupta. `enviarPorSyscall()` ya
resuelve esto internamente con `ntohl()` antes de la llamada — no hace
falta pensarlo al usar la función, pero vale la pena entender por qué
está ahí si algún día cambian algo de esa parte.

### Cómo probarlo en el Pi

Con el kernel personalizado ya booteado en el Raspberry Pi:

```bash
make   # genera los 4 binarios, incluyendo los _syscall

# En el servidor (Linux/Mac, kernel normal):
./ejemplo_receptor_syscall 30000 salida.txt 41000
#                          ^puerto DATA      ^debe coincidir con el
#                                             puerto_ack_local del Pi

# En el Raspberry Pi (con el kernel de Kernel/Image corriendo):
./ejemplo_emisor_syscall <IP_DEL_SERVIDOR> 30000 archivo_a_enviar.txt 41000
```

Si el número de syscall está bien, el flujo es idéntico al de
`ejemplo_emisor`/`ejemplo_receptor` (mismo protocolo, mismos logs), solo
que el envío pasa por el kernel en vez de por un socket de usuario. Si
falla con `ENOSYS`, el número en `SyscallTransport.h` no coincide con el
del kernel — revisar el paso anterior.

### De archivo a datos reales del sensor

Tanto `ejemplo_emisor.cpp` como `ejemplo_emisor_syscall.cpp` leen de un
archivo con `ifstream` a modo de prueba. Cuando se integre con
`Pruebas Sensor/sensor.cpp` (o `sensor.py`), ese `ifstream` se reemplaza
por lo que entregue el sensor — el resto del flujo (fragmentar, `seq`,
`enviarFragmentoConfirmado`) no cambia.

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
