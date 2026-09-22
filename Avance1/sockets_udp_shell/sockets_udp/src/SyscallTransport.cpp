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

    // The kernel syscall expects the address in host byte order.
    uint32_t ipOrdenHost = ntohl(direccion.s_addr);

    long resultado = ::syscall(NUMERO_SYSCALL_SEND_SENSOR_DATA,
                                datos, len, ipOrdenHost, puerto);
    
    // Check for syscall errors.
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
