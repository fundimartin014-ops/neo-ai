from pathlib import Path
p = Path("launcher.py")
src = p.read_text(encoding="utf-8")
if "TRANSFORMERS_VERBOSITY" in src:
    print("already silenced")
else:
    needle = "import re\n"
    if needle not in src:
        print("anchor not found")
        raise SystemExit(1)
    silencer = (
        "import os as _os_ml\n"
        '_os_ml.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")\n'
        '_os_ml.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")\n'
        '_os_ml.environ.setdefault("TOKENIZERS_PARALLELISM", "false")\n'
        "import re\n"
    )
    src = src.replace(needle, silencer, 1)
    p.write_text(src, encoding="utf-8")
    print("Silenced sentence_transformers bat spam")