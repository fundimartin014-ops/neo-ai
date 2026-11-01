from pathlib import Path
p = Path("launcher.py")
src = p.read_text(encoding="utf-8")
if "TRANSFORMERS_VERBOSITY" in src:
    print("already silenced")
else:
    needle = "logging.basicConfig(level=logging.INFO"
    if needle in src:
        silencer = (
            'import os as _os_ml\n'
            '_os_ml.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")\n'
            '_os_ml.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")\n'
            '_os_ml.environ.setdefault("TOKENIZERS_PARALLELISM", "false")\n\n'
        )
        src = src.replace(needle, silencer + needle, 1)
        p.write_text(src, encoding="utf-8")
        print("Silenced transformers progress bars")
    else:
        print("logging anchor not found")