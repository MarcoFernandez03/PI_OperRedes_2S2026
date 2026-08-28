#include "UDPSocket.h"

#include <cstring>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <netdb.h>
#include <errno.h>

namespace
{
    // Convierte un mensaje de error de sistema (errno) en texto,
    // igual que hace SocketException::description() en el ejemplo TCP.
    std::string errorDeSistema(const std::string& contexto)
    {
        return contexto + ": " + std::strerror(errno);
    }
}

UDPSocket::UDPSocket() : m_fd(-1), m_tieneDestino(false)
{
    m_fd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (m_fd < 0)
    {
        throw SocketException(errorDeSistema("No se pudo crear el socket UDP"));
    }
}

UDPSocket::~UDPSocket()
{
    close();
}

UDPSocket::UDPSocket(UDPSocket&& otro) noexcept
    : m_fd(otro.m_fd), m_destino(otro.m_destino), m_tieneDestino(otro.m_tieneDestino)
{
    otro.m_fd = -1;
}

UDPSocket& UDPSocket::operator=(UDPSocket&& otro) noexcept
{
    if (this != &otro)
    {
        close();
        m_fd = otro.m_fd;
        m_destino = otro.m_destino;
        m_tieneDestino = otro.m_tieneDestino;
        otro.m_fd = -1;
    }
    return *this;
}

void UDPSocket::close()
{
    if (m_fd >= 0)
    {
        ::close(m_fd);
        m_fd = -1;
    }
}

void UDPSocket::bind(unsigned short puerto, const std::string& ip_local)
{
    sockaddr_in direccion{};
    direccion.sin_family = AF_INET;
    direccion.sin_port = htons(puerto);

    if (ip_local == "0.0.0.0")
    {
        direccion.sin_addr.s_addr = INADDR_ANY;
    }
    else if (::inet_pton(AF_INET, ip_local.c_str(), &direccion.sin_addr) != 1)
    {
        throw SocketException("Dirección IP local inválida: " + ip_local);
    }

    if (::bind(m_fd, reinterpret_cast<sockaddr*>(&direccion), sizeof(direccion)) < 0)
    {
        throw SocketException(errorDeSistema("No se pudo hacer bind al puerto " + std::to_string(puerto)));
    }
}

void UDPSocket::setTimeout(int segundos, int microsegundos)
{
    timeval tv{};
    tv.tv_sec = segundos;
    tv.tv_usec = microsegundos;

    if (::setsockopt(m_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) < 0)
    {
        throw SocketException(errorDeSistema("No se pudo configurar el timeout del socket"));
    }
}

void UDPSocket::setDestino(const std::string& host, unsigned short puerto)
{
    std::memset(&m_destino, 0, sizeof(m_destino));
    m_destino.sin_family = AF_INET;
    m_destino.sin_port = htons(puerto);

    // Primero se intenta como dirección IP literal; si falla, se resuelve
    // como nombre de host (por ejemplo "localhost" o un hostname de la red).
    if (::inet_pton(AF_INET, host.c_str(), &m_destino.sin_addr) != 1)
    {
        addrinfo hints{};
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_DGRAM;

        addrinfo* resultado = nullptr;
        int rc = ::getaddrinfo(host.c_str(), nullptr, &hints, &resultado);
        if (rc != 0 || resultado == nullptr)
        {
            throw SocketException("No se pudo resolver el host: " + host);
        }

        m_destino.sin_addr = reinterpret_cast<sockaddr_in*>(resultado->ai_addr)->sin_addr;
        ::freeaddrinfo(resultado);
    }

    m_tieneDestino = true;
}

int UDPSocket::send(const void* datos, std::size_t len) const
{
    if (!m_tieneDestino)
    {
        throw SocketException("send() llamado sin haber configurado un destino (usar setDestino() o sendTo())");
    }

    ssize_t enviados = ::sendto(m_fd, datos, len, 0,
                                 reinterpret_cast<const sockaddr*>(&m_destino), sizeof(m_destino));
    if (enviados < 0)
    {
        throw SocketException(errorDeSistema("Error enviando datagrama"));
    }
    return static_cast<int>(enviados);
}

int UDPSocket::sendTo(const void* datos, std::size_t len,
                       const std::string& host, unsigned short puerto) const
{
    sockaddr_in direccion{};
    direccion.sin_family = AF_INET;
    direccion.sin_port = htons(puerto);

    if (::inet_pton(AF_INET, host.c_str(), &direccion.sin_addr) != 1)
    {
        throw SocketException("Dirección IP destino inválida: " + host);
    }

    ssize_t enviados = ::sendto(m_fd, datos, len, 0,
                                 reinterpret_cast<const sockaddr*>(&direccion), sizeof(direccion));
    if (enviados < 0)
    {
        throw SocketException(errorDeSistema("Error enviando datagrama"));
    }
    return static_cast<int>(enviados);
}

int UDPSocket::receiveFrom(void* buffer, std::size_t maxLen,
                            std::string* ipOrigen, unsigned short* puertoOrigen) const
{
    sockaddr_in origen{};
    socklen_t tamOrigen = sizeof(origen);

    ssize_t recibidos = ::recvfrom(m_fd, buffer, maxLen, 0,
                                    reinterpret_cast<sockaddr*>(&origen), &tamOrigen);

    if (recibidos < 0)
    {
        // EAGAIN / EWOULDBLOCK es lo que devuelve recvfrom() cuando expira
        // el timeout fijado con setTimeout(). Se traduce a una excepción
        // específica para que la capa del protocolo distinga "no llegó
        // nada a tiempo" (debe retransmitir) de un error real de socket.
        if (errno == EAGAIN || errno == EWOULDBLOCK)
        {
            throw SocketTimeoutException();
        }
        throw SocketException(errorDeSistema("Error recibiendo datagrama"));
    }

    if (ipOrigen != nullptr)
    {
        char texto[INET_ADDRSTRLEN] = {0};
        ::inet_ntop(AF_INET, &origen.sin_addr, texto, sizeof(texto));
        *ipOrigen = texto;
    }
    if (puertoOrigen != nullptr)
    {
        *puertoOrigen = ntohs(origen.sin_port);
    }

    return static_cast<int>(recibidos);
}
