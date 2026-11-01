# Neo Cameras — Frigate NVR integration

Frigate is an open-source NVR that runs local AI object detection on IP
camera streams. No cloud, no subscription, no signup. Neo talks to it via
its HTTP API and stores detections as observations you can see on `/map`.

## What you get

- Every camera you own becomes a pin on `/map`
- Person / vehicle / animal detections show up as orange dots
- Zone-based alerts (e.g. "person detected in driveway zone")
- Queryable history: `neo: any people at the gate yesterday?`

## Install Frigate (one docker-compose)

Create `~/frigate/docker-compose.yml`:

    services:
      frigate:
        image: ghcr.io/blakeblackshear/frigate:stable
        container_name: frigate
        restart: unless-stopped
        shm_size: "256mb"
        ports:
          - "5000:5000"
          - "8971:8971"
        volumes:
          - ./config:/config
          - ./storage:/media/frigate
          - type: tmpfs
            target: /tmp/cache
            tmpfs:
              size: 1000000000
        environment:
          FRIGATE_RTSP_PASSWORD: "changeme"

Then `docker compose up -d` in that folder.

## Minimal Frigate config

Create `~/frigate/config/config.yml`:

    mqtt:
      enabled: false

    cameras:
      driveway:
        ffmpeg:
          inputs:
            - path: rtsp://user:pass@192.168.1.100:554/stream1
              roles: [detect, record]
        detect:
          width: 1280
          height: 720
          fps: 5
        objects:
          track: [person, car, dog]
        zones:
          driveway_zone:
            coordinates: "0.1,0.1,0.5,0.1,0.5,0.9,0.1,0.9"
            filters:
              person:
                min_area: 5000

Restart Frigate after editing.

## Wire it into Neo

1. Add to `.env`:

        FRIGATE_URL=http://127.0.0.1:5000

2. Restart the launcher.

3. Add each Frigate camera to Neo's geo store:

        > cameras: add driveway rtsp://user:pass@192.168.1.100:554/stream1

   Or via the map: `/map` → **+ Add camera**.

## Test it

From the Neo prompt:

    > cameras: sync
    > cameras: status
    > cameras: list

Or via HTTP:

    curl http://127.0.0.1:8000/api/cameras/status
    curl -X POST http://127.0.0.1:8000/api/cameras/sync

Detections land in `observations` and appear on `/map` as orange dots.

## CPU vs GPU

On your 7.4 GB RAM / no-GPU box, Frigate can handle **1-2 cameras at 1-3 FPS**
with the default TensorRT/OpenVINO detector replaced by the CPU detector.
For 4+ cameras, one of these helps:

- Run Frigate on a cheap VPS ($5/mo) with cameras over VPN
- Add a Coral USB TPU ($60) — 10x faster inference
- Use Neo's cloud vision path (`/api/vision/cloud-detect`) on recorded frames
  instead of live detection — 1 frame every 5 seconds, free tier

## Privacy

Frigate is 100% local. No cloud roundtrip, no telemetry, no data leaving your
LAN. Neo's cloud vision path only fires if you explicitly call it.

## Troubleshooting

- **`frigate online=False`** — check `FRIGATE_URL` in `.env` and that the
  container is up (`docker ps | grep frigate`)
- **Cameras list empty on `/map`** — cameras need `lat`/`lng` to show as pins.
  Add them in the map UI or via `cameras: add <name> <rtsp> <lat> <lng>`
- **No detections syncing** — Frigate needs to have seen events first. Check
  `http://127.0.0.1:5000/api/events` in a browser.
