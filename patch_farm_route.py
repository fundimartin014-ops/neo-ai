from pathlib import Path

p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

if "/farm" in src and "farm.html" in src:
    print("already patched")
    raise SystemExit(0)

needle = '''        @self.app.route("/api/health")'''
if needle not in src:
    print("api/health anchor not found")
    raise SystemExit(1)

route = '''        @self.app.route("/farm")
        def farm_dashboard():
            from flask import send_from_directory
            fp = PROJECT_ROOT / "farm.html"
            if fp.exists():
                return send_from_directory(str(PROJECT_ROOT), "farm.html", mimetype="text/html")
            return "farm.html missing", 404

'''

src = src.replace(needle, route + needle, 1)
p.write_text(src, encoding="utf-8")
print("Added /farm route")