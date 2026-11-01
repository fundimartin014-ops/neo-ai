# Supported dialects: Swahili, Kikuyu, Luo, Kalenjin
LOCAL_LANG = {
    "en": {"show dashboard": "Show dashboard", "switch farm": "Switch to farm"},
    "sw": {"show dashboard": "Onyesha dashibodi", "switch farm": "Badilisha shamba"},
    "ki": {"show dashboard": "Onyesha dashibodi", "switch farm": "Hindura shamba"},
    "lu": {"show dashboard": "Dhiere dashibodi", "switch farm": "Pindua shamba"}
}

# Current language selection
current_lang = "en"

def set_language(lang_code):
    global current_lang
    if lang_code in LOCAL_LANG:
        current_lang = lang_code
        return f"Language set to {lang_code}"
    return f"Language {lang_code} not supported"

def translate_command(cmd):
    # Translate input command to English internal command
    for en_cmd, local_cmd in LOCAL_LANG.get(current_lang, {}).items():
        if cmd.lower() == local_cmd.lower():
            return en_cmd
    return cmd  # default to input if no translation
