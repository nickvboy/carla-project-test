import carla
import pygame
import random
import re
import numpy as np
import time
import sys

def find_weather_presets():
    rgx = re.compile('.+?WeatherParameters\.(.+)')
    presets = [getattr(carla.WeatherParameters, x) for x in dir(carla.WeatherParameters) if rgx.match(x)]
    return presets

class CarlaSimulator:
    def __init__(self):
        pygame.init()
        self.client = carla.Client('localhost', 2000)
        self.client.set_timeout(10.0)
        self.world = self.client.get_world()
        self.blueprint_library = self.world.get_blueprint_library()
        self.vehicle = None
        self.camera = None
        self.weather_presets = [
            self.create_sunny_weather(),
            self.create_rainy_weather(),
            self.create_foggy_weather()
        ]
        self.weather_messages = ["Sunny Weather", "Rainy Weather", "Foggy Weather"]
        self.current_weather_index = 0
        self.camera_transform = carla.Transform(carla.Location(x=-5, z=3), carla.Rotation(pitch=-20))
        self.vehicle_blueprints = self.blueprint_library.filter('vehicle.*.*')
        self.control = carla.VehicleControl()
        self.speed_violation_count = 0
        self.speed_exceeded = False
        self.weather_message_display_time = 0
        self.debug_menu_visible = False  # Initialize the debug menu visibility flag
        self.initialize_vehicle('vehicle.nissan.patrol_2021')
        self.setup_display()
        self.setup_gamepad()
        self.clock = pygame.time.Clock()
        self.set_weather()

    def setup_display(self):
        self.display = pygame.display.set_mode((800, 600), pygame.HWSURFACE | pygame.DOUBLEBUF)
        pygame.display.set_caption("CARLA Simulator")

    def setup_gamepad(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.gamepad = pygame.joystick.Joystick(0)
            self.gamepad.init()
        else:
            self.gamepad = None

    def initialize_vehicle(self, vehicle_type):
        spawn_points = self.world.get_map().get_spawn_points()
        if self.vehicle is not None:
            self.vehicle.destroy()
        blueprint = self.blueprint_library.find(vehicle_type)
        transform = random.choice(spawn_points)
        self.vehicle = self.world.spawn_actor(blueprint, transform)
        self.vehicle.set_autopilot(False)
        self.setup_camera()

    def setup_camera(self):
        if self.camera is not None:
            self.camera.destroy()
        camera_blueprint = self.blueprint_library.find('sensor.camera.rgb')
        camera_blueprint.set_attribute('image_size_x', '800')
        camera_blueprint.set_attribute('image_size_y', '600')
        camera_blueprint.set_attribute('fov', '90')
        self.camera = self.world.spawn_actor(camera_blueprint, self.camera_transform, attach_to=self.vehicle)
        self.camera.listen(lambda image: self.process_image(image))

    def process_image(self, image):
        image.convert(carla.ColorConverter.Raw)
        array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
        array = np.reshape(array, (image.height, image.width, 4))
        array = array[:, :, :3]  # Keep only RGB channels, discard alpha channel
        array = array[:, :, ::-1]  # Convert BGRA to RGB
        surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
        self.display.blit(surface, (0, 0))
        self.display_speed()
        self.display_weather_message()
        if self.debug_menu_visible:
            self.display_debug_menu()
        pygame.display.flip()

    def get_speed(self):
        velocity = self.vehicle.get_velocity()
        speed_mps = (velocity.x**2 + velocity.y**2 + velocity.z**2)**0.5  # Speed in m/s
        speed_mph = speed_mps * 2.23694  # Convert to mph
        return speed_mph

    def display_speed(self):
        speed = self.get_speed()
        speed_str = f"Speed: {speed:.2f} mph"
        font = pygame.font.Font(None, 36)
        text_surface = font.render(speed_str, True, (255, 255, 255))
        self.display.blit(text_surface, (10, 10))

        violation_str = f"Speed Violations: {self.speed_violation_count}"
        violation_surface = font.render(violation_str, True, (255, 255, 255))
        self.display.blit(violation_surface, (10, 50))

        if speed > 40:
            if not self.speed_exceeded:
                self.speed_violation_count += 1
                self.speed_exceeded = True
            violation_text = f"Speed Violation! Speed: {speed:.2f} mph"
            violation_surface = font.render(violation_text, True, (255, 0, 0))
            self.display.blit(violation_surface, (self.display.get_width() // 2 - violation_surface.get_width() // 2, self.display.get_height() // 2 - violation_surface.get_height() // 2))
        else:
            self.speed_exceeded = False

    def display_weather_message(self):
        if time.time() - self.weather_message_display_time < 2:  # Show message for 2 seconds
            font = pygame.font.Font(None, 36)
            message = self.weather_messages[self.current_weather_index]
            text_surface = font.render(f"Changed to {message}", True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.display.get_width() // 2, self.display.get_height() - 50))
            pygame.draw.rect(self.display, (0, 0, 0), text_rect.inflate(20, 20))
            self.display.blit(text_surface, text_rect)

    def display_debug_menu(self):
        vehicle_transform = self.vehicle.get_transform()
        location = vehicle_transform.location
        debug_info = [
            f"Location: ({location.x:.2f}, {location.y:.2f}, {location.z:.2f})",
            f"Rotation: (Pitch: {vehicle_transform.rotation.pitch:.2f}, Yaw: {vehicle_transform.rotation.yaw:.2f}, Roll: {vehicle_transform.rotation.roll:.2f})"
        ]

        font = pygame.font.Font(None, 24)
        bg_surface = pygame.Surface((400, 100))
        bg_surface.set_alpha(128)  # Set transparency to 128 (out of 255)
        bg_surface.fill((0, 0, 0))  # Black background
        self.display.blit(bg_surface, (10, 100))

        y_offset = 110
        for info in debug_info:
            text_surface = font.render(info, True, (255, 255, 255))
            self.display.blit(text_surface, (20, y_offset))
            y_offset += 30

    def create_sunny_weather(self):
        sunny_weather = carla.WeatherParameters(
            cloudiness=0.0,
            precipitation=0.0,
            fog_density=0.0,
            wetness=0.0,
            sun_altitude_angle=75.0
        )
        return sunny_weather

    def create_rainy_weather(self):
        rainy_weather = carla.WeatherParameters(
            cloudiness=80.0,
            precipitation=100.0,
            fog_density=0.0,
            wetness=80.0,
            sun_altitude_angle=-15.0
        )
        return rainy_weather

    def create_foggy_weather(self):
        foggy_weather = carla.WeatherParameters(
            cloudiness=80.0,
            precipitation=0.0,
            fog_density=100.0,
            fog_distance=0.0,
            wetness=0.0,
            sun_altitude_angle=-15.0
        )
        return foggy_weather

    def set_weather(self):
        self.world.set_weather(self.weather_presets[self.current_weather_index])
        self.weather_message_display_time = time.time()

    def input_router(self):
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                self.keyboard_control(events)
                return
            elif event.type == pygame.JOYAXISMOTION or event.type == pygame.JOYBUTTONDOWN or event.type == pygame.JOYBUTTONUP:
                self.gamepad_control(events)
                return

    def keyboard_control(self, events):
        keys = pygame.key.get_pressed()
        self.control.throttle = 0.0
        self.control.steer = 0.0
        self.control.brake = 0.0
        light_state = carla.VehicleLightState.NONE

        if keys[pygame.K_w]:
            self.control.throttle = 1.0
        if keys[pygame.K_s]:
            self.control.brake = 1.0
            light_state |= carla.VehicleLightState.Brake
        if keys[pygame.K_a]:
            self.control.steer = -1.0
        if keys[pygame.K_d]:
            self.control.steer = 1.0
        if keys[pygame.K_r]:
            self.change_vehicle()
        if keys[pygame.K_SPACE]:
            self.control.hand_brake = True
        else:
            self.control.hand_brake = False
        if keys[pygame.K_t]:
            self.switch_camera_view()
        if keys[pygame.K_q]:
            self.control.reverse = not self.control.reverse
        if keys[pygame.K_c]:
            self.current_weather_index = (self.current_weather_index + 1) % len(self.weather_presets)
            self.set_weather()
        if keys[pygame.K_d]:  # Toggle debug menu visibility
            self.debug_menu_visible = not self.debug_menu_visible

        if self.control.reverse:
            light_state |= carla.VehicleLightState.Reverse

        self.vehicle.apply_control(self.control)
        self.vehicle.set_light_state(carla.VehicleLightState(light_state))

    def gamepad_control(self, events):
        self.control.throttle = 0.0
        self.control.steer = 0.0
        self.control.brake = 0.0
        light_state = carla.VehicleLightState.NONE

        # Axes mapping for a typical gamepad
        left_x = self.gamepad.get_axis(0)
        right_trigger = self.gamepad.get_axis(5)
        left_trigger = self.gamepad.get_axis(4)
        a_button = self.gamepad.get_button(0)
        b_button = self.gamepad.get_button(1)
        x_button = self.gamepad.get_button(2)
        y_button = self.gamepad.get_button(3)
        c_button = self.gamepad.get_button(2)  # Mapping a button for weather change (example: 'X' button)

        # Steering
        self.control.steer = left_x

        # Throttle and Brake
        if right_trigger > -0.5:
            self.control.throttle = (right_trigger + 1) / 2
        if left_trigger > -0.5:
            self.control.brake = (left_trigger + 1) / 2
            light_state |= carla.VehicleLightState.Brake

        # Gear shifting (A for forward, B for reverse)
        if a_button:
            self.control.reverse = False
        if b_button:
            self.control.reverse = True

        # Hand brake (X button)
        self.control.hand_brake = x_button

        # Change camera view (Y button)
        if y_button:
            self.switch_camera_view()

        # Change weather (X button)
        if c_button:
            self.current_weather_index = (self.current_weather_index + 1) % len(self.weather_presets)
            self.set_weather()

        if self.control.reverse:
            light_state |= carla.VehicleLightState.Reverse

        self.vehicle.apply_control(self.control)
        self.vehicle.set_light_state(carla.VehicleLightState(light_state))

    def switch_camera_view(self):
        if self.camera_transform == carla.Transform(carla.Location(x=-5, z=3), carla.Rotation(pitch=-20)):
            self.camera_transform = carla.Transform(carla.Location(x=0, z=3), carla.Rotation(pitch=-20))
        else:
            self.camera_transform = carla.Transform(carla.Location(x=-5, z=3), carla.Rotation(pitch=-20))
        self.setup_camera()

    def change_vehicle(self):
        random_vehicle = random.choice(self.vehicle_blueprints).id
        self.initialize_vehicle(random_vehicle)

    def run(self):
        try:
            while True:
                self.world.tick()
                self.clock.tick_busy_loop(60)
                self.input_router()
                self.display_speed()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
        finally:
            pygame.quit()
            if self.vehicle is not None:
                self.vehicle.destroy()
            if self.camera is not None:
                self.camera.destroy()

if __name__ == '__main__':
    sim = CarlaSimulator()
    sim.run()
