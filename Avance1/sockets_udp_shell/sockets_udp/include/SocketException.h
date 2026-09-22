#ifndef SOCKET_EXCEPTION_H
#define SOCKET_EXCEPTION_H

#include <string>

// Exception used to report socket-layer errors.
class SocketException
{
public:
    explicit SocketException(std::string mensaje) : m_mensaje(std::move(mensaje)) {}

    const std::string& description() const { return m_mensaje; }

private:
    std::string m_mensaje;
};

#endif // SOCKET_EXCEPTION_H
