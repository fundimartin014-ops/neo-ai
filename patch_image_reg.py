from pathlib import Path

# Register in api_server.py
p = Path("agents/api_server.py")
src = p.read_text(encoding="utf-8")
if "ImageAnalysisAgent" not in src:
    anchor = "    reg.register(DiseaseAlertAgent(bus=bus))"
    if anchor not in src:
        anchor = "    reg.register(SearchAgent(bus=bus))"
    if anchor not in src:
        print("anchor not found in api_server.py")
    else:
        src = src.replace(
            anchor,
            anchor + "\n    from agents.image_analysis_agent import ImageAnalysisAgent\n"
                     "    reg.register(ImageAnalysisAgent(bus=bus))",
            1,
        )
        p.write_text(src, encoding="utf-8")
        print("  - registered ImageAnalysisAgent")
else:
    print("  - ImageAnalysisAgent already registered")

# Add alias in executor
ex = Path("agents/executor_agent.py")
exsrc = ex.read_text(encoding="utf-8")
if '"image_analysis": "ImageAnalysisAgent"' not in exsrc:
    needle = '"disease": "DiseaseAlertAgent",'
    if needle in exsrc:
        exsrc = exsrc.replace(
            needle,
            needle + '\n    "image_analysis": "ImageAnalysisAgent",\n'
                     '    "analyze_image": "ImageAnalysisAgent",',
            1,
        )
        ex.write_text(exsrc, encoding="utf-8")
        print("  - added image_analysis alias in executor")

# Add to agents_skill ALIASES
sk = Path("skills/agents_skill.py")
sksrc = sk.read_text(encoding="utf-8")
if '"image_analysis":' not in sksrc:
    needle = '"disease":      "DiseaseAlertAgent",'
    if needle in sksrc:
        sksrc = sksrc.replace(
            needle,
            needle + '\n    "image_analysis": "ImageAnalysisAgent",\n'
                     '    "analyze_image": "ImageAnalysisAgent",',
            1,
        )
        sk.write_text(sksrc, encoding="utf-8")
        print("  - added image_analysis to agents_skill")