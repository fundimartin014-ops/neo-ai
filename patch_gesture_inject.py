from pathlib import Path
p = Path("launcher.py")
src = p.read_text(encoding="utf-8")

if "gesture.js" in src:
    print("already injected")
    raise SystemExit(0)

old = '''                inject = '<script src="/static/quick_panel.js" defer></script>'
                if "quick_panel.js" not in html:
                    if "</body>" in html:
                        html = html.replace("</body>", inject + "\\n</body>", 1)
                    else:
                        html += inject'''

new = '''                inject = (
                    '<script src="/static/quick_panel.js" defer></script>\\n'
                    '<script src="/static/gesture.js" defer></script>'
                )
                if "quick_panel.js" not in html:
                    if "</body>" in html:
                        html = html.replace("</body>", inject + "\\n</body>", 1)
                    else:
                        html += inject'''

if old not in src:
    print("inject anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("gesture.js now injected into chat page")