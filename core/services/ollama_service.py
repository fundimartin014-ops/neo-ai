import aiohttp
from core.logger import log_info, log_error

OLLAMA_URL = "http://localhost:11434/api/generate"

async def ask_ollama(prompt, model="qwen2.5:1.5b"):

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    try:
        async with aiohttp.ClientSession() as session:

            async with session.post(
                OLLAMA_URL,
                json=payload
            ) as response:

                data = await response.json()

                log_info("Received response from Ollama")

                return data.get("response", "")

    except Exception as e:
        log_error(f"Ollama Error: {e}")
        return "Error connecting to Ollama."