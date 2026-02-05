import json
import re
from difflib import SequenceMatcher


def load_json(file, default):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 🔥 ذكاء عربي
def normalize(text):
    text = str(text).lower().strip()

    replacements = {
        "أ":"ا","إ":"ا","آ":"ا",
        "ة":"ه",
        "ؤ":"و",
        "ئ":"ي"
    }

    for k,v in replacements.items():
        text = text.replace(k,v)

    text = re.sub(r'[^\w\s]', '', text)
    text = " ".join(text.split())

    if text.startswith("ال") and len(text) > 4:
        text = text[2:]

    return text


def similar(a,b):
    return SequenceMatcher(None,a,b).ratio() > 0.75