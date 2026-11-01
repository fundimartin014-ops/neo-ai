from pathlib import Path
import json

# Real Colab notebook — Wan 2.1 Fast + ngrok tunnel
cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Neo Video Backend (Colab)\n",
            "\n",
            "Run Wan 2.1 Fast on Colab's free GPU and expose it as an HTTP API\n",
            "that Neo can call from `generate video of X`.\n",
            "\n",
            "**Before running:** get a free ngrok token from https://dashboard.ngrok.com/get-started/your-authtoken\n",
            "and paste it in cell 3."
        ]
    },
    {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [
            "# 1. Install dependencies (takes ~30s)\n",
            "!pip install -q fastapi uvicorn pyngrok gradio_client nest_asyncio pydantic"
        ]
    },
    {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [
            "# 2. Verify GPU is available\n",
            "!nvidia-smi --query-gpu=name,memory.total --format=csv"
        ]
    },
    {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [
            "# 3. Config — paste your ngrok token here\n",
            "NGROK_TOKEN = \"PASTE_YOUR_NGROK_TOKEN_HERE\"  # from dashboard.ngrok.com/get-started/your-authtoken\n",
            "\n",
            "# Which HF Space to use as the video generator. These run on the\n",
            "# space's own GPU, so your Colab GPU is only used as a proxy.\n",
            "# If the first Space is down, we fall through to the next.\n",
            "SPACES = [\n",
            "    (\"multimodalart/wan2-1-fast\", \"/generate_video\"),\n",
            "    (\"hysts/zeroscope-v2\",        \"/run\"),\n",
            "]"
        ]
    },
    {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [
            "# 4. Build the FastAPI server\n",
            "from fastapi import FastAPI, HTTPException\n",
            "from pydantic import BaseModel\n",
            "from gradio_client import Client\n",
            "import base64, os, time, threading, nest_asyncio, uvicorn\n",
            "\n",
            "nest_asyncio.apply()\n",
            "app = FastAPI()\n",
            "_clients = {}\n",
            "\n",
            "def get_client(space_id):\n",
            "    if space_id not in _clients:\n",
            "        _clients[space_id] = Client(space_id, verbose=False)\n",
            "    return _clients[space_id]\n",
            "\n",
            "class Req(BaseModel):\n",
            "    prompt: str\n",
            "    seconds: int = 4\n",
            "\n",
            "@app.get(\"/health\")\n",
            "def health():\n",
            "    return {\"ok\": True, \"spaces\": [s[0] for s in SPACES]}\n",
            "\n",
            "@app.post(\"/generate\")\n",
            "def generate(req: Req):\n",
            "    errors = []\n",
            "    for space, api_name in SPACES:\n",
            "        try:\n",
            "            c = get_client(space)\n",
            "            result = c.predict(req.prompt, api_name=api_name)\n",
            "            # result can be: local path (str), list, or dict with url\n",
            "            path = None\n",
            "            if isinstance(result, str) and os.path.exists(result):\n",
            "                path = result\n",
            "            elif isinstance(result, (list, tuple)) and result:\n",
            "                cand = result[0]\n",
            "                if isinstance(cand, str) and os.path.exists(cand):\n",
            "                    path = cand\n",
            "                elif isinstance(cand, dict) and cand.get(\"video\"):\n",
            "                    path = cand[\"video\"]\n",
            "            elif isinstance(result, dict) and result.get(\"video\"):\n",
            "                path = result[\"video\"]\n",
            "\n",
            "            if path and os.path.exists(path):\n",
            "                with open(path, \"rb\") as f:\n",
            "                    b64 = base64.b64encode(f.read()).decode()\n",
            "                return {\"ok\": True, \"video_b64\": b64,\n",
            "                        \"bytes\": os.path.getsize(path), \"space\": space}\n",
            "            errors.append(f\"{space}: unrecognized result {type(result)}\")\n",
            "        except Exception as e:\n",
            "            errors.append(f\"{space}: {type(e).__name__}: {str(e)[:120]}\")\n",
            "    raise HTTPException(500, {\"errors\": errors})\n",
            "\n",
            "print(\"[ok] FastAPI server built\")"
        ]
    },
    {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [
            "# 5. Start server + open ngrok tunnel\n",
            "from pyngrok import ngrok\n",
            "import threading, uvicorn, time\n",
            "\n",
            "if \"PASTE\" in NGROK_TOKEN:\n",
            "    raise SystemExit(\"Paste your ngrok token in cell 3 first. \"\n",
            "                     \"Free token: https://dashboard.ngrok.com/get-started/your-authtoken\")\n",
            "\n",
            "ngrok.set_auth_token(NGROK_TOKEN)\n",
            "\n",
            "# Kill any old tunnel\n",
            "for t in ngrok.get_tunnels():\n",
            "    ngrok.disconnect(t.public_url)\n",
            "\n",
            "def _run():\n",
            "    uvicorn.run(app, host=\"0.0.0.0\", port=8000, log_level=\"warning\")\n",
            "\n",
            "threading.Thread(target=_run, daemon=True).start()\n",
            "time.sleep(3)\n",
            "\n",
            "url = ngrok.connect(8000).public_url\n",
            "print()\n",
            "print(\"=\" * 64)\n",
            "print(\"  Colab video backend is live\")\n",
            "print(\"=\" * 64)\n",
            "print(f\"  Health:   {url}/health\")\n",
            "print(f\"  Generate: POST {url}/generate\")\n",
            "print()\n",
            "print(\"  Add this to Neo's .env, then restart the launcher:\")\n",
            "print(f\"      COLAB_VIDEO_URL={url}\")\n",
            "print(\"=\" * 64)\n",
            "print()\n",
            "print(\"Keep this Colab tab open while you use it.\")\n",
            "print(\"Free tier = ~4h GPU/day. Idle = disconnected after 90m.\")"
        ]
    },
    {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [
            "# 6. (Optional) test it from here\n",
            "import requests\n",
            "r = requests.post(url + \"/generate\", json={\"prompt\": \"a red apple\", \"seconds\": 4}, timeout=300)\n",
            "print(r.status_code)\n",
            "if r.ok:\n",
            "    print(\"bytes:\", r.json().get(\"bytes\"))\n",
            "else:\n",
            "    print(r.text[:300])"
        ]
    }
]

notebook = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "colab": {"provenance": [], "toc_visible": True},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "cells": cells,
}

out = Path("colab_video_server.ipynb")
out.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(f"[ok] wrote {out}")
print("[ok] now open https://colab.research.google.com/")
print("     File -> Upload notebook -> select colab_video_server.ipynb")