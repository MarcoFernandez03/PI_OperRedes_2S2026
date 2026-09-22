// Código para un botón
#include <gpiod.hpp>
#include <iostream>



int main(){
    return 0;
}

/*
Este código debería ser genérico para cualquier sensor de salida digital
solo es necesario cambiar las configuraciones necesarias marcadas en los comentarios.
*/
void digitalInput(){
    // Abre el chip de comunicación gpio del microcontrolador
    auto chip = gpiod::chip::open("/dev/gpiochip4");
    // Offset dentro del chip gpio, en español, el numero de pin gpio al
    // que el sensor está conectado, no número de pin fisico, de GPIO
    unsigned int offset = 23;

    // Configuraciones de la línea de comúnicación, o sea como se comunica
    // la placa con el pin
    gpiod::line_settings settings;
    settings.set_direction(gpiod::line::direction::INPUT); // INPUT o OUTPUT, que trabajo tiene el pin
    settings.set_edge_detection(gpiod::line::edge::BOTH_EDGES); // BOTH_EDGES, RISING_EDGE, FALLING_EDGE, cual de los flancos se quieren capturar del sensor

    // Habilitar resistencia pull-up (esto para la pi 4)
    settings.set_bias(gpiod::line::bias::PULL_UP); // PULL_UP, PULL_DOWN, DISABLE, dependiendo del sensor
    
    // Configurar la linea
    gpiod::line_config line_cfg;
    line_cfg.add_line_settings(offset, settings);

    // Abrir la línea pedida
    gpiod::request_config req_cfg;
    req_cfg.set_consumer("pi4_sensor");

    auto request = chip.request_lines(req_cfg, line_cfg);
    // Buffer para los datos, evita perdida de ellos, ordena de forma cronologica y con timestamps
    // 32 es el número de eventos que se desean guardar en el buffer
    gpiod::edge_event_buffer buffer(32);

    // Respuesta a los eventos
    while(true){
        // bloqueo de espera de eventos en 10 segundos
        if(request.wait_edge_events(std::chrono::seconds(10))){
           auto num = request.read_edge_events(buffer); // devuelve la cantidad de eventos en el buffer
            for (unsigned int i = 0; i < num; i++) {
                const auto& event = buffer[i];
                // si hubiera problemas de compilación cambiar por event.event_type()
                if(event.type() == gpiod::edge_event::event_type::RISING_EDGE){
                    // resultado para flanco superior
                } else {
                    // resultado para flanco inferior
                }
            }
        }
    }

}