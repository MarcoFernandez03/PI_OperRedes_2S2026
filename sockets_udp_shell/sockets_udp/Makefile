CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -Iinclude

SRC = src/UDPSocket.cpp src/Trama.cpp
SRC_SYSCALL = $(SRC) src/SyscallTransport.cpp

# ejemplo_emisor / ejemplo_receptor: prueba pura de sockets (sin syscall),
#   útil para validar la red entre el Pi y el servidor sin depender del
#   kernel personalizado.
# ejemplo_emisor_syscall / ejemplo_receptor_syscall: integración real con
#   la syscall del kernel. ejemplo_emisor_syscall SOLO corre en el
#   Raspberry Pi con el kernel personalizado (Kernel/Image) booteado.
all: ejemplo_receptor ejemplo_emisor ejemplo_receptor_syscall ejemplo_emisor_syscall

ejemplo_receptor: examples/ejemplo_receptor.cpp $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

ejemplo_emisor: examples/ejemplo_emisor.cpp $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

ejemplo_receptor_syscall: examples/ejemplo_receptor_syscall.cpp $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

ejemplo_emisor_syscall: examples/ejemplo_emisor_syscall.cpp $(SRC_SYSCALL)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f ejemplo_receptor ejemplo_emisor ejemplo_receptor_syscall ejemplo_emisor_syscall

.PHONY: all clean
