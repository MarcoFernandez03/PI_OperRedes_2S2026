CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -Iinclude

SRC = src/UDPSocket.cpp src/Trama.cpp
SRC_SYSCALL = $(SRC) src/SyscallTransport.cpp

# ejemplo_emisor / ejemplo_receptor: regular UDP transport examples.
# ejemplo_emisor_syscall / ejemplo_receptor_syscall: custom-kernel examples.
#   The sender requires the custom kernel on the Raspberry Pi.
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
