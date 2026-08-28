CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -Iinclude

SRC = src/UDPSocket.cpp src/Trama.cpp

all: ejemplo_receptor ejemplo_emisor

ejemplo_receptor: examples/ejemplo_receptor.cpp $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

ejemplo_emisor: examples/ejemplo_emisor.cpp $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f ejemplo_receptor ejemplo_emisor

.PHONY: all clean
