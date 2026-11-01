"""
core/system_scanner.py
System capability scanner — detects RAM, Ollama models, API keys, GPU, etc.
Reports what Neo can use and warns about constraints.
"""

import os
import json
import subprocess
import platform
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class SystemCapability:
    name: str
    available: bool
    details: str
    priority: str
    emoji: str


class NeoSystemScanner:
    """
    Scans the system for Neo's required and optional capabilities.
    Runs on startup and via `scan` command.
    """

    def __init__(self):
        self.capabilities: List[SystemCapability] = []
        self.ram_gb = 0.0
        self.ram_percent = 0.0
        self.os_name = platform.system()
        self.arch = platform.machine()
        self.scan_time = None

    def run_full_scan(self) -> Dict:
        """Run complete system scan and return report."""
        self.scan_time = datetime.now().isoformat()
        self.capabilities = []
        self._scan_ram()
        self._scan_ollama()
        self._scan_api_keys()
        self._scan_packages()
        self._scan_gpu()
        self._scan_disk()
        return self._build_report()

    def _scan_ram(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            self.ram_gb = mem.total / (1024 ** 3)
            self.ram_percent = mem.percent
            if self.ram_gb < 4:
                status = "⚠️ LOW RAM — Cloud-only mode strongly recommended"
                avail = False
            elif self.ram_gb < 8:
                status = "✅ Adequate — Small models only (qwen2.5:1.5b ~1.2GB)"
                avail = True
            elif self.ram_gb < 16:
                status = "✅ Good — Can run 7B models locally if needed"
                avail = True
            else:
                status = "✅ Excellent — Full local capability"
                avail = True
            self.capabilities.append(SystemCapability(
                name="RAM", available=avail,
                details=f"{self.ram_gb:.1f}GB total ({self.ram_percent}% used) — {status}",
                priority="critical", emoji="💾"
            ))
        except ImportError:
            self.capabilities.append(SystemCapability(
                name="RAM", available=True,
                details="psutil not installed — cannot detect RAM. Install: pip install psutil",
                priority="critical", emoji="💾"
            ))

    def _scan_ollama(self):
        models = []
        running = False
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                running = True
        except Exception:
            running = False
        if running:
            if models:
                has_fallback = any("qwen2.5:1.5b" in m for m in models)
                detail = f"Running — {len(models)} models: {', '.join(models[:5])}"
                if has_fallback:
                    detail += " | ✅ Fallback model ready"
                else:
                    detail += " | ⚠️ qwen2.5:1.5b not found — run: ollama pull qwen2.5:1.5b"
            else:
                detail = "Running but no models pulled. Run: ollama pull qwen2.5:1.5b"
        else:
            detail = "Not running. Start with: ollama serve"
        self.capabilities.append(SystemCapability(
            name="Ollama", available=running, details=detail,
            priority="recommended", emoji="🦙"
        ))

    def _scan_api_keys(self):
        keys = {
            "GROQ_API_KEY": ("Groq", "⚡ Free fast inference"),
            "OPENROUTER_API_KEY": ("OpenRouter", "🌐 Free model access (20 req/min)"),
            "TAVILY_API_KEY": ("Tavily", "🔍 Web search (1000 credits/mo)"),
            "MOONSHOT_API_KEY": ("Moonshot", "🌙 Alternative API"),
        }
        for env_key, (name, desc) in keys.items():
            value = os.getenv(env_key)
            if value:
                masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                detail = f"✅ Configured ({masked}) — {desc}"
                avail = True
            else:
                detail = f"❌ Not set — {desc}"
                avail = False
            self.capabilities.append(SystemCapability(
                name=name, available=avail, details=detail,
                priority="critical" if name in ["Groq", "OpenRouter"] else "recommended",
                emoji="🔑"
            ))

    def _scan_packages(self):
        packages = {
            "psutil": ("System monitoring", "recommended"),
            "numpy": ("Vector operations", "recommended"),
            "requests": ("HTTP client", "optional"),
            "faiss": ("Vector search (faiss-cpu)", "optional"),
            "sqlite3": ("Built-in database", "critical"),
        }
        for pkg, (desc, priority) in packages.items():
            try:
                if pkg == "sqlite3":
                    __import__(pkg)
                else:
                    __import__(pkg)
                detail = f"✅ Available — {desc}"
                avail = True
            except ImportError:
                detail = f"❌ Missing — {desc}. Install: pip install {pkg}"
                avail = False
            self.capabilities.append(SystemCapability(
                name=pkg, available=avail, details=detail,
                priority=priority, emoji="📦"
            ))

    def _scan_gpu(self):
        gpu_info = "No GPU detected"
        has_gpu = False
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                gpus = []
                for line in lines:
                    parts = line.split(", ")
                    if len(parts) >= 2:
                        gpus.append(f"{parts[0]} ({parts[1]})")
                if gpus:
                    gpu_info = f"NVIDIA: {', '.join(gpus)}"
                    has_gpu = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        if not has_gpu:
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showproductname"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and "GPU" in result.stdout:
                    gpu_info = "AMD GPU detected (ROCm)"
                    has_gpu = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        if not has_gpu and self.os_name == "Darwin":
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5
                )
                if "Metal" in result.stdout:
                    gpu_info = "Apple Silicon with Metal"
                    has_gpu = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        self.capabilities.append(SystemCapability(
            name="GPU", available=has_gpu,
            details=gpu_info + (" | Local inference will be fast" if has_gpu else " | CPU-only inference"),
            priority="optional", emoji="🎮"
        ))

    def _scan_disk(self):
        try:
            import psutil
            disk = psutil.disk_usage("/")
            free_gb = disk.free / (1024 ** 3)
            total_gb = disk.total / (1024 ** 3)
            percent = disk.percent
            if free_gb < 5:
                status = "⚠️ CRITICAL — Less than 5GB free"
                avail = False
            elif free_gb < 20:
                status = "⚠️ Low — Consider freeing space"
                avail = True
            else:
                status = "✅ Healthy"
                avail = True
            self.capabilities.append(SystemCapability(
                name="Disk", available=avail,
                details=f"{free_gb:.1f}GB free / {total_gb:.1f}GB total ({percent}% used) — {status}",
                priority="critical", emoji="💿"
            ))
        except ImportError:
            self.capabilities.append(SystemCapability(
                name="Disk", available=True,
                details="psutil not installed — cannot check disk",
                priority="critical", emoji="💿"
            ))

    def _build_report(self) -> Dict:
        critical = [c for c in self.capabilities if c.priority == "critical"]
        recommended = [c for c in self.capabilities if c.priority == "recommended"]
        optional = [c for c in self.capabilities if c.priority == "optional"]
        critical_ok = all(c.available for c in critical)
        recommended_ok = all(c.available for c in recommended)
        return {
            "scan_time": self.scan_time,
            "platform": f"{self.os_name} ({self.arch})",
            "ram_gb": self.ram_gb,
            "status": {
                "critical": "✅ PASS" if critical_ok else "❌ FAIL",
                "recommended": "✅ PASS" if recommended_ok else "⚠️ PARTIAL",
                "overall": "✅ Ready" if critical_ok else "❌ Needs setup"
            },
            "capabilities": {
                "critical": [asdict(c) for c in critical],
                "recommended": [asdict(c) for c in recommended],
                "optional": [asdict(c) for c in optional]
            },
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        recs = []
        has_groq = any(c.name == "Groq" and c.available for c in self.capabilities)
        has_openrouter = any(c.name == "OpenRouter" and c.available for c in self.capabilities)
        has_ollama = any(c.name == "Ollama" and c.available for c in self.capabilities)
        if not has_groq and not has_openrouter:
            recs.append("🚨 CRITICAL: No cloud API keys configured. Neo will be non-functional.")
            recs.append("   → Get free Groq key: https://console.groq.com/keys")
            recs.append("   → Get free OpenRouter key: https://openrouter.ai/keys")
        if not has_ollama and self.ram_gb < 8:
            recs.append("⚠️ No Ollama + low RAM. You need at least one cloud provider.")
        if self.ram_gb > 0 and self.ram_gb < 8:
            recs.append(f"💡 RAM: {self.ram_gb:.1f}GB detected. Keep only qwen2.5:1.5b local (~1.2GB).")
            recs.append("   → Route all quality work to Groq/OpenRouter free tiers.")
        if not any(c.name == "Tavily" and c.available for c in self.capabilities):
            recs.append("💡 Tavily not configured. Web research will be disabled.")
            recs.append("   → Get free key: https://tavily.com/ (1000 credits/month)")
        if not recs:
            recs.append("✅ All systems operational. Neo is ready.")
        return recs

    def print_report(self):
        """Print human-readable report to console."""
        report = self.run_full_scan()
        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════╗",
            "║              🔍 NEO SYSTEM CAPABILITY SCAN                   ║",
            f"║              {report['scan_time'][:19]}                       ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            f"Platform: {report['platform']}",
            f"Overall Status: {report['status']['overall']}",
            "",
            "── CRITICAL ──",
        ]
        for cap in report['capabilities']['critical']:
            status = "✅" if cap['available'] else "❌"
            lines.append(f"{cap['emoji']} {status} {cap['name']}: {cap['details']}")
        lines.append("")
        lines.append("── RECOMMENDED ──")
        for cap in report['capabilities']['recommended']:
            status = "✅" if cap['available'] else "❌"
            lines.append(f"{cap['emoji']} {status} {cap['name']}: {cap['details']}")
        lines.append("")
        lines.append("── OPTIONAL ──")
        for cap in report['capabilities']['optional']:
            status = "✅" if cap['available'] else "❌"
            lines.append(f"{cap['emoji']} {status} {cap['name']}: {cap['details']}")
        lines.append("")
        lines.append("── RECOMMENDATIONS ──")
        for rec in report['recommendations']:
            lines.append(rec)
        lines.append("")
        print("\n".join(lines))
        return report