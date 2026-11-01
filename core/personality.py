# core/personality.py
PERSONALITY_TEMPLATES = {
    "mentor": "You are a patient teacher. Break complex topics into steps. Ask guiding questions.",
    "analyst": "You are precise and data-driven. Cite sources. Use structured formatting.",
    "creative": "You think laterally. Use analogies and unconventional connections.",
    # ...
}

def build_system_prompt(personality, mode, available_tools):
    base = "You are Neo, a cognitive AI assistant..."
    persona = PERSONALITY_TEMPLATES[personality]
    tool_context = format_tools(available_tools)
    mode_context = f"Current mode: {mode}"
    
    return f"{base}\n{persona}\n{mode_context}\n{tool_context}"