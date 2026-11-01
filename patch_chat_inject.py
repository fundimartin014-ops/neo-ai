from pathlib import Path

p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

if "quick_panel.js" in src:
    print("already patched")
    raise SystemExit(0)

# 1) Add a static route for /static
needle = '''        @self.app.route("/farm")'''
if needle not in src:
    print("/farm route not found — run the previous patch first")
    raise SystemExit(1)

static_route = '''        @self.app.route("/static/<path:fname>")
        def _static(fname):
            from flask import send_from_directory
            return send_from_directory(str(PROJECT_ROOT / "static"), fname)

'''
src = src.replace(needle, static_route + needle, 1)

# 2) Inject the script tag into the index() render
old_index = '''            if ui_path.exists():
                with open(ui_path, "r", encoding="utf-8") as f:
                    return f.read(), 200, {"Content-Type": "text/html"}'''

new_index = '''            if ui_path.exists():
                with open(ui_path, "r", encoding="utf-8") as f:
                    html = f.read()
                inject = '<script src="/static/quick_panel.js" defer></script>'
                if "quick_panel.js" not in html:
                    if "</body>" in html:
                        html = html.replace("</body>", inject + "\\n</body>", 1)
                    else:
                        html += inject
                return html, 200, {"Content-Type": "text/html"}'''

if old_index not in src:
    print("index() render anchor not found")
    raise SystemExit(1)
src = src.replace(old_index, new_index, 1)

p.write_text(src, encoding="utf-8")
print("launcher injects quick_panel.js into chat page")