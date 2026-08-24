## Instalar libgpiod
```
sudo apt udpate
sudo apt install -y gpiod libgpiod-dev
```

## Consideraciones con sensores
Raspberry Pi solo admite ondas de entrada de máximo 3.3V, conectar una salida de 5V puede quemar el pin o le procesador, es necesario investigar sobre la salida de cada sensor. En caso de tener una salida de 5V es necesario añadir un divisor de voltaje, una resistencia de 1kΩ y otra de 2kΩ de la salida del sensor al pin de entrada.

### Código de color para 1kΩ
Café-negro-rojo-dorado

### Código de color para 2kΩ
Rojo-negro-rojo-dorado

## Compilación
Con g++
```
g++ -Wall -02 -std=c++17 *.cpp -lgpiodcxx -o ejecutable
```