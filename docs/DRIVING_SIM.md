# Neo Driving — Simulation first, hardware later

You asked for "driving AI level" perception: see obstacle → stop → reroute.
That capability exists today in research form (openpilot, Autoware, CARLA
challenge winners). It runs on a GPU. Your box has none.

**The honest path:** train and validate the perception + decision loop in
simulation on Google Colab (free GPU hours), export the weights, run
perception locally on CPU at low FPS as proof of concept. Real-world driving
needs a car, sensors, and a safety officer — that's a 1-3 year project, not
a weekend.

## What you can build now

1. **Perception on recorded video** — Neo watches a dashcam clip, detects
   pedestrians / cars / lanes, logs every detection
2. **Decision loop in CARLA** — spawn a car in the open-source driving
   simulator (Colab), let Neo's policy drive, watch it stop for obstacles
3. **Sim-to-real transfer prep** — export the trained policy, plan the
   hardware you'd need

## Colab path (free GPU)

Open https://colab.research.google.com and paste:

    !pip install carla==0.9.15
    !apt-get install -y xvfb
    !wget https://carla-releases.s3.eu-west-3.amazonaws.com/Linux/CARLA_0.9.15.tar.gz
    !tar -xzf CARLA_0.9.15.tar.gz

    # Start CARLA headless
    !xvfb-run ./CARLA_0.9.15/CarlaUE4.sh -RenderOffScreen &

    # Now the Python client can connect on localhost:2000

Then in a second cell:

    import carla
    client = carla.Client("localhost", 2000)
    world = client.get_world()
    bp = world.get_blueprint_library().filter("vehicle.*")[0]
    spawn = world.get_map().get_spawn_points()[0]
    vehicle = world.spawn_actor(bp, spawn)
    print("Vehicle spawned:", vehicle.id)

That's the full open-source driving stack running in ~2 minutes on a free
Colab GPU.

## The Neo bridge

`core/driving/sim_bridge.py` (already installed) exposes:

    from core.driving.sim_bridge import SimBridge
    bridge = SimBridge(carla_url="tcp://colab-host:2000")
    bridge.spawn_ego_vehicle()
    frame = bridge.get_camera_frame()           # 800x600 rgb array
    detections = bridge.detect_obstacles(frame) # uses Neo's cloud vision
    action = bridge.decide(detections)          # rule-based for now
    bridge.apply(action)                        # throttle/brake/steer

The decision loop starts rule-based (stop if person < 10m ahead) and can be
replaced with a trained PPO policy later.

## Connect Colab to your local Neo

In Colab:

    from google.colab import output
    output.serve_kernel_port_as_view(2000)

That gives you a public HTTPS URL for the CARLA port. Put it in `.env`:

    CARLA_URL=wss://<colab-url>.googleusercontent.com

Restart Neo. Then:

    > sim: spawn
    > sim: drive 30              (30 seconds of autonomous driving)
    > sim: frame                 (return a single frame as base64)
    > sim: stop

## Training a policy

Once perception works, training is a PPO loop:

    from stable_baselines3 import PPO
    from core.driving.gym_wrapper import CarlaEnv

    env = CarlaEnv(bridge)
    model = PPO("CnnPolicy", env, verbose=1)
    model.learn(total_timesteps=200_000)     # ~4h on free Colab GPU
    model.save("neo_driving_v1")

Then `sim: load neo_driving_v1` and let it drive.

## Safety reality

Even after this works in simulation:

- Real cars need CAN bus integration (openpilot's hardware: $1k+)
- Legal requirements: most countries need homologation
- Insurance: nobody insures experimental autonomy
- Testing: thousands of km under supervision before any solo operation

The simulation gets you 80% of the *software*. The remaining 20% is
hardware + law + money, not code.

## What runs on your current box

- Perception on pre-recorded video: **yes**, cloud vision backend, ~5 FPS
- Live camera feed object detection: **yes**, ~1-3 FPS on CPU
- CARLA simulator itself: **no**, needs GPU (use Colab)
- Trained policy inference on a frame: **yes**, ~2-5 FPS on CPU
- Real vehicle control: **no**, needs hardware
