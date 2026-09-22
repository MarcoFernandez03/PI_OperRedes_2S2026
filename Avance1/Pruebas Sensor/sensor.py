from gpiozero import MotionSensor # gpiozero contains different imports for sensors
from datetime import datetime


def write_to_file():
  with open("motion_log.txt", "a") as file:
    file.write("Motion detected!" + " " + datetime.now().strftime("%d.%b %Y %H:%M:%S") + "\n")
    # To send the file from C++ the output file should be renamed or deleted to manage new lecture without redundancy of old
    # readings from the sensor, pytho creates a new file if it doesn't find the file

# Program "main"
pir = MotionSensor(4) # GPIO pin, not physical pin number
while True:
  print("Searching for motion")
  pir.wait_for_motion() # waiting for motion signal
  print("Motion detected!")
  write_to_file()
  pir.wait_for_no_motion() # wait for pin voltage to drop down to 0V
