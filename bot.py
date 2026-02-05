from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
import os
import random

from utils import load_json, save_json, normalize, similar

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))
OWNER_ID = os.getenv("OWNER_ID")

admins = load_json("admins.json",[OWNER_ID])
questions = load_json("questions.json",[])
truefalse = load_json("truefalse.json",[])
race = load_json("race.json",[])
mentions = load_json("mentions.json",{"on_mention":["نعم؟ 👀"]})

active_games = {}
GAMES_ENABLED = True


def is_admin(uid):
    return uid in admins or uid == OWNER_ID


@app.route("/",methods=['GET'])
def home():
    return "BOT RUNNING 🔥"


@app.route("/callback",methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    global GAMES_ENABLED

    user_id = event.source.user_id
    room_id = getattr(event.source,"group_id",user_id)

    msg_raw = event.message.text
    msg = normalize(msg_raw)

    reply = None

    print("MSG:",msg)

# ================= ADMIN =================

    if "رفع ادمن" in msg and user_id == OWNER_ID:
        if event.message.mention:
            for m in event.message.mention.mentionees:
                admins.append(m.user_id)
                save_json("admins.json",admins)
                reply = "✅ تم رفع الأدمن"

    elif "تنزيل ادمن" in msg and user_id == OWNER_ID:
        if event.message.mention:
            for m in event.message.mention.mentionees:
                admins.remove(m.user_id)
                save_json("admins.json",admins)
                reply = "✅ تم تنزيل الأدمن"


    elif "قفل" in msg and is_admin(user_id):
        GAMES_ENABLED = False
        active_games.pop(room_id,None)
        reply = "🔒 تم قفل الألعاب"


    elif "فتح" in msg and is_admin(user_id):
        GAMES_ENABLED = True
        reply = "🔓 تم فتح الألعاب"


    elif "حذف" in msg and is_admin(user_id):
        active_games.pop(room_id,None)
        reply = "🚫 تم حذف اللعبة"


# ================= MENTION =================

    elif "@bot" in msg:
        reply = random.choice(mentions["on_mention"])


# ================= GAMES =================

    elif "سوال" in msg and GAMES_ENABLED:

        q = random.choice(questions)

        active_games[room_id] = {
            "answer":normalize(q["a"])
        }

        reply = "🧠 "+q["q"]


    elif "صح غلط" in msg and GAMES_ENABLED:

        q = random.choice(truefalse)

        active_games[room_id] = {
            "answer":normalize(q["a"])
        }

        reply = "🤔 "+q["q"]


    elif "سباق" in msg and GAMES_ENABLED:

        word = random.choice(race)

        active_games[room_id] = {
            "answer":normalize(word)
        }

        reply = f"🏁 اكتب بسرعة:\n{word}"


# ================= CHECK ANSWER =================

    elif room_id in active_games:

        ans = active_games[room_id]["answer"]

        if msg == ans or similar(msg,ans):
            active_games.pop(room_id)
            reply = "🔥 إجابة صحيحة!"


# ================= AUTO REPLY =================

    if reply is None:
        reply = "اكتب ( سوال ) وابدأ اللعب 😎"


    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )


if __name__ == "__main__":
    app.run()