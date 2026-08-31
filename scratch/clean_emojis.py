import re
import os

def clean_emojis(file_path):
    if not os.path.exists(file_path):
        return
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex matching emojis and symbols
    # Common emoji ranges: 
    # \U00010000-\U0010ffff
    # \u2600-\u27bf
    # \u2300-\u23ff
    # \u2b50-\u2b55
    # Specific ones: 🔬, 🚀, ⚠️, ❌, ✅, 📈, 📊, ⚡, ▶, 👆, ⟳, 💡, 🔥, 🎯, 🟢, 🔴, etc.
    
    # Custom replacements for cleaner UX
    replacements = {
        "🔬 ": "",
        "🔬": "",
        "🚀 ": "",
        "🚀": "",
        "⚠️ ": "",
        "⚠️": "",
        "❌ ": "",
        "❌": "",
        "✅ ": "",
        "✅": "",
        "📈 ": "",
        "📈": "",
        "📊 ": "",
        "📊": "",
        "⚡ ": "",
        "⚡": "",
        "▶ ": "",
        "▶": "",
        "👆 ": "",
        "👆": "",
        "⟳ ": "",
        "⟳": "",
        "💡 ": "",
        "💡": "",
        "🔥 ": "",
        "🔥": "",
        "🎯 ": "",
        "🎯": "",
        "🟢 ": "",
        "🟢": "",
        "🔴 ": "",
        "🔴": "",
        "⚙️ ": "",
        "⚙️": "",
        "🔒 ": "",
        "🔒": "",
        "🛡️ ": "",
        "🛡️": ""
    }

    new_content = content
    for k, v in replacements.items():
        new_content = new_content.replace(k, v)

    # General emoji stripper
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "]+", flags=re.UNICODE)

    new_content = emoji_pattern.sub(r'', new_content)

    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Cleaned emojis from {file_path}")
    else:
        print(f"No emojis found in {file_path}")

if __name__ == "__main__":
    for p in ["app.py", "usdjpy_research.py", "research_engine.py", "research_analytics.py", "backtester.py"]:
        clean_emojis(p)
