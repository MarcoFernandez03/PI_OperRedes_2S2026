CC = gcc
CFLAGS = -Wall -Wextra -std=c11 -g
SRCS = memoria_fisica.c tabla_paginas.c tlb.c memoria_virtual.c
OBJS = $(SRCS:.c=.o)
TEST_SRC = test_memoria.c
TEST_BIN = test_memoria

.PHONY: all test clean

all: $(TEST_BIN)

$(TEST_BIN): $(OBJS) $(TEST_SRC:.c=.o)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

test: $(TEST_BIN)
	./$(TEST_BIN)

clean:
	rm -f $(OBJS) $(TEST_SRC:.c=.o) $(TEST_BIN)