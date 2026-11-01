from dotenv import load_dotenv
load_dotenv()  # reads .env from cwd

import os, requests

key = os.getenv("OPENROUTER_API_KEY", "").strip()
if not key:
    print("OPENROUTER_API_KEY not set (checked .env)")
    raise SystemExit(1)

r = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {key}"},
    timeout=15,
)
if r.status_code != 200:
    print(f"HTTP {r.status_code}: {r.text[:200]}")
    raise SystemExit(1)

ids = [m["id"] for m in r.json().get("data", []) if ":free" in m["id"]]
print(f"Found {len(ids)} free models:")
for i in ids[:40]:
    print(f"  {i}")