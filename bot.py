from flask import Flask, request
import random
import json
import re
from difflib import SequenceMatcher
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))
OWNER_ID = os.getenv("OWNER_ID")
admins = [OWNER_ID]

active_games = {}
games_enabled = True


# ================= LOAD JSON =================

def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default


questions = load_json("questions.json", [
    {"q": "ما هو أثقل حيوان؟", "a": "الحوت الأزرق"}
])

mentions_data = load_json("mentions.json", {
    "on_mention": ["نعم؟ 😎", "عايز ايه يا نجم؟"],
    "on_return": ["رجعت اهو 😏"]
})


# ================= SMART ARABIC =================

def normalize(text):
    text = str(text).lower()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي"
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    text = re.sub(r'[^\w\s]', '', text)
    text = " ".join(text.split())

    return text


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio() > 0.75


def is_admin(user):
    return user in admins


# ================= SERVER =================

@app.route("/", methods=['GET'])
def home():
    return "BOT IS RUNNING 🔥"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'


# ================= EVENTS =================

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_id = event.source.user_id
    room_id = getattr(event.source, "group_id", user_id)

    msg = normalize(event.message.text)

    reply = None

    # ========= OWNER COMMANDS =========

    if msg.startswith("رفع ادمن"):
        if user_id != OWNER_ID:
            reply = "❌ الأمر للمالك فقط"
        else:
            target = msg.replace("رفع ادمن", "").strip()
            admins.append(target)
            reply = "✅ تم رفع الأدمن"

    elif msg.startswith("تنزيل ادمن"):
        if user_id != OWNER_ID:
            reply = "❌ الأمر للمالك فقط"
        else:
            target = msg.replace("تنزيل ادمن", "").strip()
            if target in admins:
                admins.remove(target)
            reply = "✅ تم تنزيل الأدمن"

    # ========= ADMIN =========

    elif msg in ["قفل", "قفل اللعب"]:
        if not is_admin(user_id):
            reply = "❌ مش أدمن"
        else:
            global games_enabled
            games_enabled = False
            reply = "🔒 تم قفل الألعاب"

    elif msg in ["فتح", "فتح اللعب"]:
        if not is_admin(user_id):
            reply = "❌ مش أدمن"
        else:
            games_enabled = True
            reply = "🔓 تم فتح الألعاب"

    elif msg == "حذف":
        if room_id in active_games:
            del active_games[room_id]
            reply = "🗑 تم حذف اللعبة"
        else:
            reply = "مفيش لعبة شغالة 😅"

    # ========= GAMES =========

    elif msg in ["سؤال", "سوال"]:

        if not games_enabled:
            reply = "🚫 الألعاب مقفولة"
        elif room_id in active_games:
            reply = "⚠️ في لعبة شغالة بالفعل"
        else:
            q = random.choice(questions)
            active_games[room_id] = q
            reply = "🧠 سؤال:\n" + q["q"]

    # ========= CHECK ANSWER =========

    elif room_id in active_games:

        answer = normalize(active_games[room_id]["a"])

        if msg == answer or similar(msg, answer):
            del active_games[room_id]
            reply = "🎉 إجابة صحيحة!"

    # ========= MENTION =========

    elif "@bot" in msg or "بوت" in msg:
        reply = random.choice(mentions_data["on_mention"])

    # ========= DEFAULT =========

    if not reply:
        if random.random() < 0.03:
            reply = "انا صاحي اهو 👀"

    if reply:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )


if __name__ == "__main__":
    app.run()