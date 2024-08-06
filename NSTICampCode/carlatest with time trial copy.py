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
    def __init__(self, server_ip, server_port, resolution, vehicle_type, spawn_location, spawn_rotation, initial_weather, throttle_sensitivity, steering_sensitivity, countdown_duration, max_speed_limit, violation_penalties, enable_debug_menu_on_startup):
        pygame.init()
        self.client = carla.Client(server_ip, server_port)
        self.client.set_timeout(10.0)
        self.world = self.client.load_world('Town03')  # Load Town 3
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
        self.debug_menu_visible = enable_debug_menu_on_startup  # Initialize the debug menu visibility flag
        self.trial_run_active = False  # Trial run state
        self.trial_countdown = False  # Countdown state
        self.countdown_start_time = 0  # Countdown start time
        self.trial_running = False  # Trial running state
        self.trial_timer_start = 0  # Timer start time
        self.trial_timer = 0  # Timer value
        self.max_speed = 0  # Max speed during trial
        self.average_speed = 0  # Average speed during trial
        self.violation_durations = []  # List to track violation durations
        self.current_violation_start = 0  # Current violation start time
        self.go_text_display_time = 0  # Time to keep "GO" text on screen
        self.results_displayed = False  # Flag to indicate results are displayed
        self.speed_sum = 0  # To calculate average speed
        self.speed_sample_count = 0  # Number of speed samples taken
        self.final_duration = 0  # Store final duration

        # Configuration parameters
        self.resolution = resolution
        self.vehicle_type = vehicle_type
        self.spawn_location = spawn_location
        self.spawn_rotation = spawn_rotation
        self.initial_weather = initial_weather
        self.throttle_sensitivity = throttle_sensitivity
        self.steering_sensitivity = steering_sensitivity
        self.countdown_duration = countdown_duration
        self.max_speed_limit = max_speed_limit
        self.violation_penalties = violation_penalties

        # Clear all vehicles at startup
        self.clear_all_vehicles()

        self.initialize_vehicle(self.vehicle_type)
        self.setup_display()
        self.setup_gamepad()
        self.clock = pygame.time.Clock()
        self.set_weather(self.initial_weather)

    def clear_all_vehicles(self):
        # Destroy all existing vehicles in the world
        for actor in self.world.get_actors():
            if 'vehicle' in actor.type_id:
                actor.destroy()

    def setup_display(self):
        self.display = pygame.display.set_mode(self.resolution, pygame.HWSURFACE | pygame.DOUBLEBUF)
        pygame.display.set_caption("CARLA Simulator")

    def setup_gamepad(self):
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.gamepad = pygame.joystick.Joystick(0)
            self.gamepad.init()
        else:
            self.gamepad = None

    def initialize_vehicle(self, vehicle_type):
        if self.vehicle is not None:
            self.vehicle.destroy()
        blueprint = self.blueprint_library.find(vehicle_type)
        retries = 5
        success = False
        for _ in range(retries):
            transform = self.find_valid_spawn_point(carla.Location(*self.spawn_location), carla.Rotation(*self.spawn_rotation))
            try:
                self.vehicle = self.world.spawn_actor(blueprint, transform)
                success = True
                break
            except RuntimeError as e:
                print(f"Spawn attempt failed due to collision at {transform.location}. Retrying...")
        if not success:
            # Try spawning at a random valid location
            print("All retries failed. Trying a random valid spawn point.")
            transform = random.choice(self.world.get_map().get_spawn_points())
            try:
                self.vehicle = self.world.spawn_actor(blueprint, transform)
            except RuntimeError as e:
                print(f"Random spawn attempt failed: {e}")
                raise RuntimeError("Failed to spawn vehicle after multiple attempts.")

        self.vehicle.set_autopilot(False)
        self.setup_camera()

    def find_valid_spawn_point(self, location, rotation):
        # Try to spawn at the specified location first
        transform = carla.Transform(location, rotation)
        if self.world.get_map().get_waypoint(location, project_to_road=True, lane_type=carla.LaneType.Driving) is not None:
            return transform
        # If the specified location is invalid, choose a random valid spawn point
        spawn_points = self.world.get_map().get_spawn_points()
        return random.choice(spawn_points)

    def setup_camera(self):
        if self.camera is not None:
            self.camera.destroy()
        camera_blueprint = self.blueprint_library.find('sensor.camera.rgb')
        camera_blueprint.set_attribute('image_size_x', str(self.resolution[0]))
        camera_blueprint.set_attribute('image_size_y', str(self.resolution[1]))
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
        if self.trial_run_active or self.trial_countdown or self.results_displayed:
            self.display_trial_run_screen()
        if self.trial_countdown:
            self.display_countdown()
        if self.trial_running:
            self.display_timer()
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

        if speed > self.max_speed_limit:
            if not self.speed_exceeded:
                self.speed_violation_count += 1
                self.speed_exceeded = True
                self.current_violation_start = time.time()
            violation_text = f"Speed Violation! Speed: {speed:.2f} mph"
            violation_surface = font.render(violation_text, True, (255, 0, 0))
            self.display.blit(violation_surface, (self.display.get_width() // 2 - violation_surface.get_width() // 2, self.display.get_height() // 2 - violation_surface.get_height() // 2))
        else:
            if self.speed_exceeded:
                self.speed_exceeded = False
                self.violation_durations.append(time.time() - self.current_violation_start)

        if self.trial_running:
            self.speed_sum += speed
            self.speed_sample_count += 1
            self.max_speed = max(self.max_speed, speed)

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

    def display_trial_run_screen(self):
        bg_surface = pygame.Surface(self.display.get_size())
        bg_surface.set_alpha(200)  # Semi-transparent background
        bg_surface.fill((0, 0, 0))
        self.display.blit(bg_surface, (0, 0))

        if self.trial_run_active:
            font = pygame.font.Font(None, 48)
            text_surface = font.render("Sunny Run: Press Space to Start", True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.display.get_width() // 2, self.display.get_height() // 2))
            self.display.blit(text_surface, text_rect)

        if self.trial_countdown:
            self.display_countdown()

        if self.trial_running and time.time() - self.go_text_display_time < 1:  # Show "Go!" for 1 second
            font = pygame.font.Font(None, 72)
            go_text_surface = font.render("Go!", True, (0, 255, 0))
            go_text_rect = go_text_surface.get_rect(center=(self.display.get_width() // 2, self.display.get_height() // 2 + 50))
            self.display.blit(go_text_surface, go_text_rect)

        if self.results_displayed:
            self.display_results()

    def display_countdown(self):
        countdown = int(self.countdown_duration - (time.time() - self.countdown_start_time))
        if countdown <= 0:
            self.trial_countdown = False
            self.trial_running = True
            self.trial_timer_start = time.time()
            self.max_speed = 0
            self.average_speed = 0
            self.speed_violation_count = 0
            self.violation_durations = []
            self.speed_sum = 0
            self.speed_sample_count = 0
            self.go_text_display_time = time.time()
            countdown_text = "Go!"
            color = (0, 255, 0)
            # Unlock controls when "Go" is displayed
            self.control.throttle = self.throttle_sensitivity
            self.control.steer = 0.0
            self.control.brake = 0.0
        else:
            countdown_text = str(countdown)
            color = (255, 255, 255)

        font = pygame.font.Font(None, 72)
        text_surface = font.render(countdown_text, True, color)
        text_rect = text_surface.get_rect(center=(self.display.get_width() // 2, self.display.get_height() // 2))
        self.display.blit(text_surface, text_rect)

    def display_timer(self):
        self.trial_timer = time.time() - self.trial_timer_start
        timer_str = f"Time: {self.trial_timer:.2f} s"
        font = pygame.font.Font(None, 36)
        text_surface = font.render(timer_str, True, (255, 255, 255))
        self.display.blit(text_surface, (10, 90))

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

    def set_weather(self, weather_index):
        self.world.set_weather(self.weather_presets[weather_index])
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

        if not self.trial_run_active and not self.trial_countdown and not self.trial_running and not self.results_displayed:
            if keys[pygame.K_w]:
                self.control.throttle = self.throttle_sensitivity
            if keys[pygame.K_s]:
                self.control.brake = 1.0
                light_state |= carla.VehicleLightState.Brake
            if keys[pygame.K_a]:
                self.control.steer = -self.steering_sensitivity
            if keys[pygame.K_d]:
                self.control.steer = self.steering_sensitivity
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
                self.set_weather(self.current_weather_index)
            if keys[pygame.K_m]:  # Toggle debug menu visibility
                self.debug_menu_visible = not self.debug_menu_visible
            if keys[pygame.K_1]:
                self.start_trial_run()

        elif self.trial_run_active:
            if keys[pygame.K_SPACE]:
                self.start_countdown()

        elif self.trial_countdown:
            # Prevent controls during countdown
            return

        elif self.trial_running:
            if keys[pygame.K_w]:
                self.control.throttle = self.throttle_sensitivity
            if keys[pygame.K_s]:
                self.control.brake = 1.0
                light_state |= carla.VehicleLightState.Brake
            if keys[pygame.K_a]:
                self.control.steer = -self.steering_sensitivity
            if keys[pygame.K_d]:
                self.control.steer = self.steering_sensitivity
            if keys[pygame.K_SPACE]:
                self.control.hand_brake = True
            else:
                self.control.hand_brake = False
            if keys[pygame.K_q]:
                self.control.reverse = not self.control.reverse
            if keys[pygame.K_t]:
                self.switch_camera_view()

        elif self.results_displayed:
            if keys[pygame.K_ESCAPE]:  # Close the results screen
                self.results_displayed = False
                self.trial_run_active = False  # Reset the trial run state

        if self.control.reverse:
            light_state |= carla.VehicleLightState.Reverse

        self.vehicle.apply_control(self.control)
        self.vehicle.set_light_state(carla.VehicleLightState(light_state))


    def gamepad_control(self, events):
        self.control.throttle = 0.0
        self.control.steer = 0.0
        self.control.brake = 0.0
        light_state = carla.VehicleLightState.NONE

        if self.trial_run_active or self.trial_countdown:
            return

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
            self.set_weather(self.current_weather_index)

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

    def start_trial_run(self):
        self.trial_run_active = True
        self.speed_violation_count = 0
        self.clear_vehicles()
        self.teleport_vehicle(carla.Location(x=246.28, y=-18.94, z=0.0))
        self.current_weather_index = 0  # Set to sunny
        self.set_weather(self.current_weather_index)

    def start_countdown(self):
        self.trial_run_active = False
        self.trial_countdown = True
        self.countdown_start_time = time.time()

    def stop_trial_run(self):
        self.trial_running = False
        self.results_displayed = True
        self.final_duration = time.time() - self.trial_timer_start  # Capture final duration
        self.calculate_results()
        self.display_results()  # Display results after stopping the timer

    def clear_vehicles(self):
        for actor in self.world.get_actors():
            if 'vehicle' in actor.type_id and actor.id != self.vehicle.id:
                actor.destroy()

    def teleport_vehicle(self, location):
        # Create a new transform with the specified location and desired orientation
        transform = carla.Transform(location, carla.Rotation(pitch=0.0, yaw=-84.0, roll=0.0))
        self.vehicle.set_transform(transform)
        self.control = carla.VehicleControl()
        self.vehicle.apply_control(self.control)

    def calculate_results(self):
        duration = self.final_duration
        average_speed = self.speed_sum / (self.speed_sample_count if self.speed_sample_count > 0 else 1)
        total_violations = len(self.violation_durations)
        average_violation_duration = (sum(self.violation_durations) / total_violations) if total_violations > 0 else 0
        print(f"Trial Run Results: Duration: {duration:.2f} s, Max Speed: {self.max_speed:.2f} mph, Average Speed: {average_speed:.2f} mph, Speed Violations: {self.speed_violation_count}, Average Violation Duration: {average_violation_duration:.2f} s")

    def display_results(self):
        duration = self.final_duration
        average_speed = self.speed_sum / (self.speed_sample_count if self.speed_sample_count > 0 else 1)
        total_violations = len(self.violation_durations)
        average_violation_duration = (sum(self.violation_durations) / total_violations) if total_violations > 0 else 0

        results = [
            f"Duration: {duration:.2f} s",
            f"Max Speed: {self.max_speed:.2f} mph",
            f"Average Speed: {average_speed:.2f} mph",
            f"Speed Violations: {self.speed_violation_count}",
            f"Average Violation Duration: {average_violation_duration:.2f} s"
        ]

        font = pygame.font.Font(None, 36)
        y_offset = 100
        for result in results:
            text_surface = font.render(result, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.display.get_width() // 2, y_offset))
            self.display.blit(text_surface, text_rect)
            y_offset += 50

        close_text = "Press ESC to close"
        close_surface = font.render(close_text, True, (255, 255, 255))
        close_rect = close_surface.get_rect(center=(self.display.get_width() // 2, y_offset + 50))
        self.display.blit(close_surface, close_rect)

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
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            pygame.quit()
            if self.vehicle is not None:
                self.vehicle.destroy()
            if self.camera is not None:
                self.camera.destroy()

def main():
    # Default settings
    server_ip = '127.0.0.1'  # IP address of the CARLA server
    server_port = 2000  # Port for the CARLA server
    resolution = (1280, 720)  # Screen resolution
    vehicle_type = 'vehicle.nissan.patrol_2021'  # Type of vehicle to spawn initially
    spawn_location = (246.28, -18.94, 0)  # Default spawn coordinates for the vehicle
    spawn_rotation = (0, -84, 0)  # Default spawn rotation for the vehicle (pitch, yaw, roll)
    initial_weather = 0  # Index of the initial weather preset (0 for sunny weather)
    throttle_sensitivity = .7  # Sensitivity of throttle controls
    steering_sensitivity = .7  # Sensitivity of steering controls
    countdown_duration = 5  # Duration of the countdown before the trial run starts
    max_speed_limit = 40  # Speed limit for violations (in mph)
    violation_penalties = 2  # Penalty duration for speed violations (in seconds)
    enable_debug_menu_on_startup = False  # Flag to enable/disable the debug menu on startup

    # Create an instance of the CarlaSimulator with the specified settings
    sim = CarlaSimulator(
        server_ip=server_ip,
        server_port=server_port,
        resolution=resolution,
        vehicle_type=vehicle_type,
        spawn_location=spawn_location,
        spawn_rotation=spawn_rotation,
        initial_weather=initial_weather,
        throttle_sensitivity=throttle_sensitivity,
        steering_sensitivity=steering_sensitivity,
        countdown_duration=countdown_duration,
        max_speed_limit=max_speed_limit,
        violation_penalties=violation_penalties,
        enable_debug_menu_on_startup=enable_debug_menu_on_startup
    )

    # Start the simulation
    sim.run()

if __name__ == '__main__':
    main()
