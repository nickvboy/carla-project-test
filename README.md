
# CARLA Simulator

This project is a CARLA Simulator that allows you to drive a vehicle in a simulated environment, experiment with different weather conditions, and participate in trial runs while monitoring speed and other parameters.

## Requirements

- Python 3.6 or higher
- CARLA Simulator 0.9.11 or higher
- Pygame
- NumPy

## Installation

### CARLA Simulator
Download and install CARLA Simulator from the official website.

### Python Dependencies
Install the required Python packages using pip:
```bash
pip install pygame numpy
```

## Usage

### Start the CARLA Server
Launch the CARLA server on your machine.
```bash
./CarlaUE4.sh
```

### Run the Simulator
Execute the Python script to start the CARLA Simulator.
```bash
python carla_simulator.py
```

### Start Time Trials
- Press 1 to activate the trial run screen.
- Press Space to start the countdown for the trial run.
- Once the countdown ends, the trial run begins and the timer starts.
- Press Space again to stop the trial run and display the results.

## Configuration

The simulator script `carla_simulator.py` contains default settings for various parameters. You can modify these parameters in the `main()` function of the script:

- `server_ip`: IP address of the CARLA server (default: 'localhost')
- `server_port`: Port for the CARLA server (default: 2000)
- `resolution`: Screen resolution (default: (1280, 720))
- `vehicle_type`: Type of vehicle to spawn initially (default: 'vehicle.nissan.patrol_2021')
- `spawn_location`: Default spawn coordinates for the vehicle (default: (246.28, -18.94, 0))
- `spawn_rotation`: Default spawn rotation for the vehicle (pitch, yaw, roll) (default: (0, -84, 0))
- `initial_weather`: Index of the initial weather preset (0 for sunny weather) (default: 0)
- `throttle_sensitivity`: Sensitivity of throttle controls (default: 1.0)
- `steering_sensitivity`: Sensitivity of steering controls (default: 1.0)
- `countdown_duration`: Duration of the countdown before the trial run starts (default: 5 seconds)
- `max_speed_limit`: Speed limit for violations (in mph) (default: 40)
- `violation_penalties`: Penalty duration for speed violations (in seconds) (default: 2 seconds)
- `enable_debug_menu_on_startup`: Flag to enable/disable the debug menu on startup (default: False)

## Controls

### Keyboard Controls:
- W: Throttle
- S: Brake
- A: Steer left
- D: Steer right
- R: Change vehicle
- Space: Hand brake / Start trial run / Stop trial run
- T: Switch camera view
- Q: Toggle reverse
- C: Change weather
- M: Toggle debug menu
- 1: Start trial run

### Gamepad Controls:
- Left stick (horizontal): Steering
- Right trigger: Throttle
- Left trigger: Brake
- A button: Forward gear
- B button: Reverse gear
- X button: Hand brake
- Y button: Change camera view
- X button (weather change)

## Features

- Weather Presets: Switch between sunny, rainy, and foggy weather.
- Speed Monitoring: Display current speed and monitor speed violations.
- Trial Runs: Start and participate in trial runs with countdown and result displays.
- Debug Menu: Toggle debug menu to view vehicle's location and rotation.
