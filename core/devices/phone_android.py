"""Android control via ADB over WiFi."""
from __future__ import annotations
import json, logging, re, shutil, subprocess, time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("devices.android")
CONFIG_PATH = Path("data") / "phone_config.json"
SCREENSHOT_DIR = Path("generated_images")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _load_cfg() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try: return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    return {}


def _save_cfg(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _adb_path():
    # 1. Try PATH first
    p = shutil.which("adb") or shutil.which("adb.exe")
    if p:
        return p
    # 2. Fall back to known install locations (works even if PATH is broken)
    candidates = [
        Path.home() / "Android" / "platform-tools" / "adb.exe",
        Path("C:/Android/platform-tools/adb.exe"),
        Path("C:/platform-tools/adb.exe"),
        Path("C:/Program Files/Android/platform-tools/adb.exe"),
    ]
    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            pass
    return None





def _run(args, timeout=20):
    adb = _adb_path()
    if not adb:
        return {"ok": False, "error": "adb not found in PATH"}
    try:
        p = subprocess.run([adb] + args, capture_output=True, timeout=timeout)
        return {"ok": p.returncode == 0,
                "stdout": (p.stdout or b"").decode("utf-8", errors="replace"),
                "stderr": (p.stderr or b"").decode("utf-8", errors="replace")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"adb timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


class AndroidPhone:
    def __init__(self):
        cfg = _load_cfg()
        self.cfg = cfg.setdefault("android", {})

    def is_available(self):
        return _adb_path() is not None

    def devices(self):
        r = _run(["devices", "-l"])
        if not r.get("ok"): return []
        devs = []
        for line in r["stdout"].splitlines()[1:]:
            line = line.strip()
            if not line: continue
            parts = line.split()
            if len(parts) >= 2:
                devs.append({"serial": parts[0], "state": parts[1]})
        return devs

    def pair(self, host_port, code):
        if not self.is_available():
            return "[phone] adb not in PATH"
        if ":" not in host_port:
            return "[phone] usage: phone: pair <ip>:<port> <code>"
        try:
            p = subprocess.run([_adb_path(), "pair", host_port, code],
                              capture_output=True, timeout=30, text=True)
            out = (p.stdout or "") + (p.stderr or "")
            if "Successfully paired" in out or p.returncode == 0:
                ip = host_port.split(":")[0]
                self.cfg["last_pair_ip"] = ip
                _save_cfg({"android": self.cfg})
                return f"[phone] paired {host_port}. Now: phone: connect {ip}:5555"
            return f"[phone] pair failed: {out.strip()[:200]}"
        except Exception as e:
            return f"[phone] pair error: {e}"

    def connect(self, host_port=""):
        if not self.is_available():
            return "[phone] adb not in PATH"
        if not host_port:
            ip = self.cfg.get("last_pair_ip")
            if not ip:
                return "[phone] no saved phone. Run: phone: pair <ip:port> <code>"
            host_port = f"{ip}:5555"
        r = _run(["connect", host_port], timeout=15)
        out = (r.get("stdout") or "") + (r.get("stderr") or "")
        if "connected" in out.lower():
            self.cfg["target"] = host_port
            _save_cfg({"android": self.cfg})
            return f"[phone] {out.strip()}"
        return f"[phone] connect failed: {out.strip()[:200]}"

    def disconnect(self):
        target = self.cfg.get("target")
        if not target:
            return "[phone] no target"
        _run(["disconnect", target], timeout=10)
        return "[phone] disconnected"

    def battery(self):
        r = _run(["shell", "dumpsys", "battery"])
        if not r.get("ok"):
            return f"[phone] battery failed: {r.get('error', r.get('stderr',''))[:120]}"
        info = {}
        for line in r["stdout"].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                info[k.strip()] = v.strip()
        level = info.get("level", "?")
        status = {"1":"unknown","2":"charging","3":"discharging",
                  "4":"not charging","5":"full"}.get(info.get("status",""), "")
        return f"[phone] battery {level}% — {status}"

    def tap(self, x, y):
        _run(["shell", "input", "tap", str(x), str(y)])
        return f"[phone] tap ({x},{y})"

    def swipe(self, x1, y1, x2, y2, ms=300):
        _run(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms)])
        return f"[phone] swipe ok"

    def type_text(self, text):
        _run(["shell", "input", "text", text.replace(" ", "%s")])
        return "[phone] typed"

    _KEYS = {"home":"KEYCODE_HOME","back":"KEYCODE_BACK","enter":"KEYCODE_ENTER",
             "power":"KEYCODE_POWER","wake":"KEYCODE_WAKEUP","sleep":"KEYCODE_SLEEP",
             "volume_up":"KEYCODE_VOLUME_UP","volume_down":"KEYCODE_VOLUME_DOWN",
             "camera":"KEYCODE_CAMERA","recents":"KEYCODE_APP_SWITCH"}

    def key(self, name):
        code = self._KEYS.get(name.lower().strip())
        if not code:
            return f"[phone] unknown key {name!r}"
        _run(["shell", "input", "keyevent", code])
        return f"[phone] key {name}"

    def screenshot(self):
        adb = _adb_path()
        if not adb: return "[phone] adb not in PATH"
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOT_DIR / f"phone_{ts}.png"
        try:
            with open(path, "wb") as f:
                p = subprocess.run([adb, "exec-out", "screencap", "-p"],
                                  stdout=f, stderr=subprocess.PIPE, timeout=20)
            if p.returncode != 0:
                return f"[phone] screenshot failed"
            return f"[phone] screenshot saved: {path} ({path.stat().st_size} bytes)"
        except Exception as e:
            return f"[phone] screenshot error: {e}"

    def open_url(self, url):
        _run(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])
        return f"[phone] opened {url[:80]}"

    def launch_app(self, package):
        r = _run(["shell", "monkey", "-p", package, "-c",
                  "android.intent.category.LAUNCHER", "1"])
        if "No activities" in (r.get("stdout") or ""):
            return f"[phone] app {package!r} not found"
        return f"[phone] launched {package}"

    def list_packages(self, filter_str=""):
        r = _run(["shell", "pm", "list", "packages"])
        if not r.get("ok"): return "[phone] list failed"
        pkgs = [ln.replace("package:", "").strip()
                for ln in r["stdout"].splitlines() if ln.startswith("package:")]
        if filter_str:
            pkgs = [p for p in pkgs if filter_str.lower() in p.lower()]
        return f"[phone] {len(pkgs)} packages:\n  " + "\n  ".join(pkgs[:40])

    def info(self):
        if not self.is_available():
            return "[phone] adb not in PATH"
        devs = self.devices()
        if not devs:
            return "[phone] no devices. Run: phone: connect <ip>:5555"
        out = [f"adb devices: {len(devs)}"]
        for d in devs:
            out.append(f"  {d['serial']}  {d['state']}")
        r = _run(["shell", "getprop", "ro.product.model"])
        if r.get("ok"): out.append(f"  model: {r['stdout'].strip()}")
        return "\n".join(out)


def handle(text):
    t = (text or "").strip()
    if not t or t == "status":
        p = AndroidPhone()
        if not p.is_available():
            return ("[phone] adb not in PATH.\n"
                    "  Install: https://dl.google.com/android/repository/platform-tools-latest-windows.zip")
        devs = p.devices()
        if not devs:
            return ("[phone] adb ok, no devices.\n"
                    "  pair:    phone: pair <ip>:<port> <code>\n"
                    "  connect: phone: connect <ip>:5555")
        return "\n".join(["adb devices:"] + [f"  {d['serial']}  {d['state']}" for d in devs])

    p = AndroidPhone()
    parts = t.split(maxsplit=1)
    cmd, rest = parts[0].lower(), (parts[1] if len(parts) > 1 else "")

    if cmd == "pair":
        pp = rest.split()
        if len(pp) != 2: return "usage: phone: pair <ip>:<port> <code>"
        return p.pair(pp[0], pp[1])
    if cmd == "connect":   return p.connect(rest.strip())
    if cmd == "disconnect": return p.disconnect()
    if cmd == "battery":   return p.battery()
    if cmd == "screenshot": return p.screenshot()
    if cmd == "tap":
        n = re.findall(r"-?\d+", rest)
        if len(n) != 2: return "usage: phone: tap <x> <y>"
        return p.tap(int(n[0]), int(n[1]))
    if cmd == "swipe":
        n = re.findall(r"-?\d+", rest)
        if len(n) < 4: return "usage: phone: swipe <x1> <y1> <x2> <y2> [ms]"
        return p.swipe(int(n[0]), int(n[1]), int(n[2]), int(n[3]),
                       int(n[4]) if len(n) > 4 else 300)
    if cmd == "type":  return p.type_text(rest)
    if cmd == "key":   return p.key(rest)
    if cmd == "open":  return p.open_url(rest.strip())
    if cmd == "app":   return p.launch_app(rest.strip())
    if cmd == "apps":  return p.list_packages(rest.strip())
    if cmd == "info":  return p.info()
    return (f"[phone] unknown subcommand {cmd!r}. Try:\n"
            "  status | pair | connect | disconnect | info | battery | screenshot\n"
            "  tap | swipe | type | key | open | app | apps")
