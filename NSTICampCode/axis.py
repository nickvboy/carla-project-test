import pygame
import sys

class Gamepad:
    def __init__(self):
        pygame.init()
        self.joystick = None
        self.init_joystick()

    def init_joystick(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            print("No joystick detected.")
            sys.exit()
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        print(f"Initialized joystick: {self.joystick.get_name()}")

    def detect_axes_and_buttons(self):
        print("Press any axis or button on the gamepad to detect it.")
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.JOYAXISMOTION:
                    for i in range(self.joystick.get_numaxes()):
                        axis_value = self.joystick.get_axis(i)
                        if abs(axis_value) > 0.1:  # Adjust the threshold as needed
                            print(f"Axis {i+1} is being moved. Value: {axis_value}")
                if event.type == pygame.JOYBUTTONDOWN:
                    for i in range(self.joystick.get_numbuttons()):
                        if self.joystick.get_button(i):
                            print(f"Button {i+1} is pressed.")

if __name__ == "__main__":
    gamepad = Gamepad()
    gamepad.detect_axes_and_buttons()
