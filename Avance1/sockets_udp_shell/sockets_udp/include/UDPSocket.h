#ifndef UDP_SOCKET_H
#define UDP_SOCKET_H

#include <string>
#include <cstddef>
#include <cstdint>
#include <netinet/in.h>
#include "SocketException.h"

// ---------------------------------------------------------------------------
// UDPSocket
// ---------------------------------------------------------------------------
// C++ wrapper for a UDP datagram socket.
//
// UDP has no connection or accept step; one object can send and receive.
//
// Protocol framing and retransmission are implemented in a separate layer.
//
// This keeps the transport independent from the protocol.
// ---------------------------------------------------------------------------
class UDPSocket
{
public:
    // Creates the UDP socket. Throws SocketException on failure.
    UDPSocket();

    // Closes the descriptor if it is still open.
    ~UDPSocket();

    // A socket owns a unique descriptor and cannot be copied.
    UDPSocket(const UDPSocket&) = delete;
    UDPSocket& operator=(const UDPSocket&) = delete;

    // Allows ownership transfer.
    UDPSocket(UDPSocket&& otro) noexcept;
    UDPSocket& operator=(UDPSocket&& otro) noexcept;

    // ---- Configuration ------------------------------------------------

    // Binds the socket to a local port. "0.0.0.0" listens on all interfaces.
    void bind(unsigned short puerto, const std::string& ip_local = "0.0.0.0");

    // Sets the receive timeout. Expiration raises SocketTimeoutException.
    void setTimeout(int segundos, int microsegundos = 0);

    // Sets the default destination used by send().
    void setDestino(const std::string& host, unsigned short puerto);

    // ---- Sending ---------------------------------------------------------

    // Sends len bytes to the destination configured with setDestino().
    int send(const void* datos, std::size_t len) const;

    // Sends len bytes to a specific host and port.
    int sendTo(const void* datos, std::size_t len,
               const std::string& host, unsigned short puerto) const;

    // ---- Receiving --------------------------------------------------------

    // Receives up to maxLen bytes and optionally returns the sender address.
    // A configured timeout raises SocketTimeoutException.
    int receiveFrom(void* buffer, std::size_t maxLen,
                     std::string* ipOrigen = nullptr,
                     unsigned short* puertoOrigen = nullptr) const;

    // Closes the socket explicitly.
    void close();

    int descriptor() const { return m_fd; }

private:
    int m_fd;
    sockaddr_in m_destino{};
    bool m_tieneDestino;
};

// Exception raised when the receive timeout expires.
class SocketTimeoutException : public SocketException
{
public:
    SocketTimeoutException() : SocketException("Timeout esperando datos") {}
};

#endif // UDP_SOCKET_H
