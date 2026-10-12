CC ?= gcc
CFLAGS ?= -O3 -fPIC -Wall -march=native
TARGET = libyuv2rgb.so

all: $(TARGET)

$(TARGET): yuv2rgb.c
	$(CC) $(CFLAGS) -shared $< -o $@

clean:
	rm -f $(TARGET)

.PHONY: all clean
