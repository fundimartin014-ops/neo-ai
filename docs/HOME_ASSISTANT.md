# Neo Device Control — Alexa-class via Home Assistant + Rhasspy

Home Assistant (HA) is the open-source hub that talks to 2000+ device brands
(Zigbee, Z-Wave, WiFi, Bluetooth, Matter). Rhasspy is the open-source voice
assistant that runs entirely local — no Amazon, no Google.

Together they give you Alexa-class control with zero cloud dependency, and
Neo becomes the brain that decides what to do.

## Architecture

    [mic] -> Rhasspy (wake word + intent) -> Neo API -> Home Assistant -> devices
    [web UI] -> Neo chat "turn on garden lights" -> Home Assistant -> devices

## Install Home Assistant (one docker-compose)

Create `~/hass/docker-compose.yml`:

    services:
      homeassistant:
        image: ghcr.io/home-assistant/home-assistant:stable
        container_name: homeassistant
        restart: unless-stopped
        network_mode: host
        volumes:
          - ./config:/config
          - /etc/localtime:/etc/localtime:ro
        environment:
          TZ: Africa/Nairobi

Then `docker compose up -d`.

Open `http://127.0.0.1:8123`, create your user, and add your devices
(Settings → Devices → Add Integration).

## Get a long-lived access token

In HA: Profile → Long-Lived Access Tokens → Create Token.
Copy it — that's your `HA_TOKEN`.

## Wire into Neo

Add to `.env`:

    HOME_ASSISTANT_URL=http://127.0.0.1:8123
    HOME_ASSISTANT_TOKEN=eyJ0eXAiOiJKV1Qi...

Restart the launcher.

## Use it from Neo

    > home: turn on garden lights
    > home: turn off all lights
    > home: set living room temperature to 22
    > home: status                        (list all entities)
    > home: lights                        (list only lights)

Under the hood, Neo:

1. Reads the intent ("turn on" + "garden lights")
2. Looks up matching entities in Home Assistant
3. Calls `light.turn_on` / `switch.turn_on` / `climate.set_temperature`
4. Reports what happened

## Rhasspy voice (Alexa replacement)

For hands-free, install Rhasspy on the same box:

    docker run -d --name rhasspy \
      -p 12101:12101 \
      -v "$HOME/.config/rhasspy/profiles:/profiles" \
      --device /dev/snd:/dev/snd \
      rhasspy/rhasspy:2.5.11 \
      --user-profiles /profiles --profile en

Open `http://127.0.0.1:12101`, train a wake word, and point its **intent
handler** at Neo:

    POST http://127.0.0.1:8000/api/voice/intent
    {"text": "<recognized speech>"}

Neo replies via the same Rhasspy TTS pipeline.

## Privacy

Everything local. No Amazon, no Google, no cloud. Voice never leaves your LAN.

## Troubleshooting

- **`HA online=False`** — check the token hasn't expired
- **`entity not found`** — the friendly name in HA must match what you said.
  Neo does fuzzy matching, but exotic names may need aliases.
- **Rhasspy doesn't hear you** — check `/dev/snd` is exposed and mic isn't
  claimed by another app
