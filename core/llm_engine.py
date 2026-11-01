# core/llm_engine.py

import os
import time
import json
import shutil
import subprocess
import requests


class LocalLLM:

    def __init__(self, model="qwen2.5:1.5b"):

        self.model = model

        self.url = "http://localhost:11434/api/generate"
        self.tags_url = "http://localhost:11434/api/tags"

        self.available = False

        self.ollama_path = self.find_ollama()

        if self.ollama_path:
            self.ensure_ollama()
            self.ensure_model()
        else:
            print("[Neo] Ollama executable not found")

    # ============================================
    # FIND OLLAMA AUTOMATICALLY
    # ============================================
    def find_ollama(self):

        # PATH
        path = shutil.which("ollama")

        if path:
            return path

        # common windows paths
        possible = [

            r"C:\Users\fundi\AppData\Local\Programs\Ollama\ollama.exe",

            r"C:\Program Files\Ollama\ollama.exe"
        ]

        for p in possible:
            if os.path.exists(p):
                return p

        return None

    # ============================================
    # CHECK SERVER
    # ============================================
    def server_running(self):

        try:

            requests.get(self.tags_url, timeout=3)

            return True

        except:
            return False

    # ============================================
    # START SERVER
    # ============================================
    def ensure_ollama(self):

        # already running
        if self.server_running():

            self.available = True

            print("[Neo] Ollama already running")

            return

        print("[Neo] Starting Ollama server...")

        try:

            subprocess.Popen(

                [self.ollama_path, "serve"],

                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,

                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )

        except Exception as e:

            print("[Neo] Failed starting Ollama:", e)

            return

        # wait for server
        for _ in range(20):

            if self.server_running():

                self.available = True

                print("[Neo] Ollama started successfully")

                return

            time.sleep(1)

        print("[Neo] Ollama server timeout")

    # ============================================
    # AUTO INSTALL MODEL
    # ============================================
    def ensure_model(self):

        if not self.available:
            return

        try:

            r = requests.get(self.tags_url, timeout=10)

            models = r.json().get("models", [])

            installed = [
                m.get("name", "")
                for m in models
            ]

            if self.model in installed:

                print(f"[Neo] Model ready: {self.model}")

                return

            print(f"[Neo] Downloading model: {self.model}")

            subprocess.run(

                [self.ollama_path, "pull", self.model],

                check=True
            )

            print("[Neo] Model installed")

        except Exception as e:

            print("[Neo] Model install failed:", e)

    # ============================================
    # GENERATE
    # ============================================
    def generate(self, prompt):

        # fallback if ollama died
        if not self.server_running():

            print("[Neo] Ollama offline -> fallback mode")

            return self.offline_fallback(prompt)

        try:

            response = requests.post(

                self.url,

                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },

                timeout=120
            )

            response.raise_for_status()

            data = response.json()

            text = data.get("response", "").strip()

            # anti junk
            if not text:
                return self.offline_fallback(prompt)

            if len(text) < 3:
                return self.offline_fallback(prompt)

            return text

        except Exception as e:

            print("[LLM ERROR]", e)

            return self.offline_fallback(prompt)

    # ============================================
    # OFFLINE FALLBACK BRAIN
    # ============================================
    def offline_fallback(self, prompt):

        p = prompt.lower()

        facts = {

            "president of america":
                "Donald Trump is the current president of the United States.",

            "president of uganda":
                "Yoweri Kaguta Museveni is the current president of Uganda.",

            "president of kenya":
                "William Ruto is the current president of Kenya.",

            "what is ai":
                "Artificial intelligence is the simulation of human intelligence by machines."
        }

        for k, v in facts.items():

            if k in p:
                return v

        return "I cannot verify the answer right now because the LLM is offline."