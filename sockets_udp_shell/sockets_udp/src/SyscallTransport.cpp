#include "SyscallTransport.h"
#include "SocketException.h"

#include <sys/syscall.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <cstring>
#include <cerrno>

void enviarPorSyscall(const void* datos, std::size_t len,
                       const std::string& host, unsigned short puerto)
{
    in_addr direccion{};
    if (::inet_pton(AF_INET, host.c_str(), &direccion) != 1)
    {
        throw SocketException("IP destino inválida para la syscall: " + host);
    }

    // inet_pton ya deja s_addr en orden de red (big-endian). La syscall,
    // del lado del kernel, hace htonl(dest_ip) internamente, así que si le
    // pasáramos el valor de inet_pton tal cual, se aplicaría la conversión
    // dos veces y la IP llegaría corrupta. Por eso se deshace con ntohl()
    // antes de pasarlo: el kernel espera el valor en orden de HOST.
    uint32_t ipOrdenHost = ntohl(direccion.s_addr);

    long resultado = ::syscall(NUMERO_SYSCALL_SEND_SENSOR_DATA,
                                datos, len, ipOrdenHost, puerto);

    if (resultado < 0)
    {
        std::string detalle = std::strerror(errno);
        if (errno == ENOSYS)
        {
            detalle += " (revisar NUMERO_SYSCALL_SEND_SENSOR_DATA en SyscallTransport.h; "
                       "probablemente no coincide con el número real del kernel, "
                       "o no se está corriendo el kernel personalizado)";
        }
        throw SocketException("Fallo en syscall send_sensor_data: " + detalle);
    }
}
