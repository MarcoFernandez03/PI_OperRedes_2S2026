#ifndef SOCKET_EXCEPTION_H
#define SOCKET_EXCEPTION_H

#include <string>

// Excepción simple para errores de la capa de sockets.
// Se usa el mismo patrón que en el ejemplo TCP (Tougher): cualquier
// falla de una llamada al sistema (socket, bind, sendto, recvfrom...)
// se reporta lanzando esta excepción con un mensaje descriptivo
// (normalmente construido con errno / strerror).
class SocketException
{
public:
    explicit SocketException(std::string mensaje) : m_mensaje(std::move(mensaje)) {}

    const std::string& description() const { return m_mensaje; }

private:
    std::string m_mensaje;
};

#endif // SOCKET_EXCEPTION_H
