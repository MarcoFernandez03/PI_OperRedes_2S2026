#from gpiozero import MotionSensor # gpiozero permite importar distintos sensores
from datetime import datetime
from random import randrange # BORRAR CUANDO SE CUENTE CON EL SENSOR REAL



# Esto no hace falta cambiarlo, la escritura funciona como debería
def write_to_file():
  with open("motion_log.txt", "a") as file:
    file.write("Motion detected!" + " " + datetime.now().strftime("%d.%b %Y %H:%M:%S") + "\n")
    # Para enviar desde C este archivo debería renombrarse para llevar un control de lecturas nuevas y a enviar para no chocar
    # con el archivo que se sigue escribiendo, python crearía uno nuevo cada vez que ya no exista por estarse enviando


# Por estas cosas no me gusta python, como que esto es básicamente "main"?
while True:
  #pir = MotionSensor(4) # Recordar que esto es número de pin GPIO, no el número físico del pin
  #pir.wait_for_motion()
  if randrange(100) < 50:  # Simulación de detección de movimiento BORRAR CUANDO SE CUENTE CON EL SENSOR REAL
    print("Motion detected!")
    write_to_file()

# LOS COMENTARIOS SON EL CÓDIGO PARA EL SENSOR DE MOVIMIENTO REAL, EL RESTO ES SIMULACIÓN PARA PODER PROBARLO SIN EL SENSOR