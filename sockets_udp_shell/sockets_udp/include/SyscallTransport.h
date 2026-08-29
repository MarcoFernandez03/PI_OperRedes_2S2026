#ifndef SYSCALL_TRANSPORT_H
#define SYSCALL_TRANSPORT_H

#include <cstddef>
#include <string>

// ---------------------------------------------------------------------------
// SyscallTransport
// ---------------------------------------------------------------------------
// Envoltorio sobre la syscall del kernel `send_sensor_data` (ver
// Kernel/send_sensor_data.c del repo). Reemplaza a UDPSocket::send()/sendTo()
// SOLO para el envío de fragmentos DATA/FIN desde el Raspberry Pi.
//
// Importante: esta syscall NO reemplaza a UDPSocket por completo. Solo sabe
// enviar (kernel_sendmsg y listo, sin bind, sin recibir). La recepción de
// ACKs sigue haciéndose con un UDPSocket normal, bindeado a un puerto fijo
// (ver README.md, sección "Integración con la syscall del kernel").
//
// La syscall vive en el kernel del Raspberry Pi, así que este código SOLO
// puede probarse en el Pi con el kernel personalizado (Kernel/Image)
// corriendo. En cualquier otra máquina, syscall() devuelve ENOSYS.
// ---------------------------------------------------------------------------

// Número de syscall asignado a `send_sensor_data` en la tabla del kernel
// personalizado.
//
// ESTIMACIÓN para kernel 6.18 (a verificar): en scripts/syscall.tbl del
// kernel oficial, el último número asignado hasta la serie 6.18 es 470
// (listns). Los números 471 (rseq_slice_yield) y 472 (fchroot) son
// adiciones posteriores a 6.18, no presentes todavía en esa versión. Si
// el equipo agregó `send_sensor_data` al final del archivo sin tocar
// nada más, lo más probable es que haya quedado en el 471.
//
// AUN ASÍ, HAY QUE CONFIRMARLO: revisar el propio scripts/syscall.tbl (o
// el archivo equivalente que hayan editado) del árbol fuente del kernel
// que compilaron, buscando la línea con send_sensor_data. Si el número
// real es otro, cambiarlo aquí.
constexpr long NUMERO_SYSCALL_SEND_SENSOR_DATA = 471; // Debemos confirmar que concuerde 
                                                      // contra el propio árbol del kernel

// Envía 'len' bytes a host:puerto usando la syscall send_sensor_data
// (en vez de un socket UDP normal). Lanza SocketException (definida en
// SocketException.h) si la syscall falla, incluyendo el caso en que el
// número de syscall esté mal (errno == ENOSYS -> "Function not implemented").
//
// Nota sobre orden de bytes: la syscall recibe dest_ip en orden de host y
// internamente le aplica htonl() (ver send_sensor_data.c línea "addr.sin_
// addr.s_addr = htonl(dest_ip)"). Por eso esta función NO debe pasar la IP
// tal como la da inet_pton() (que ya viene en orden de red) sino deshacer
// esa conversión con ntohl() antes de llamar a la syscall. Esto ya está
// resuelto dentro de la función; no hace falta pensarlo al usarla.
void enviarPorSyscall(const void* datos, std::size_t len,
                       const std::string& host, unsigned short puerto);

#endif // SYSCALL_TRANSPORT_H
