from flask import Flask, request, abort
import json, random, os, re
from difflib import SequenceMatcher

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError


# ================= إعدادات =================
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"
OWNER_ID = "U9ecd575f8df0e62798f4c8ecc9738d5d"


PREFIX = "."


app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ================= ملفات =================
def load_json(file, default):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


questions = load_json("questions.json", [{"q":"عاصمة مصر؟","a":"القاهرة"}])
words = load_json("words.json", ["تفاحة"])
race_data = load_json("race.json", ["سبحان الله"])
tf_data = load_json("truefalse.json", [{"q":"النار باردة","a":"غلط"}])
points = load_json("points.json", {})
admins = load_json("admins.json", [OWNER_ID])


active_games = {}
GAMES_ENABLED = True


# ================= ذكاء عربي =================
def normalize(text):
    text = str(text).lower().strip()

    text = re.sub(r'[أإآا]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[^\w\s]', '', text)

    return text


def is_correct(user, answer):
    u = normalize(user)
    a = normalize(answer)

    if u == a:
        return True

    if SequenceMatcher(None, u, a).ratio() > 0.75:
        return True

    return False


def is_admin(user_id):
    return user_id in admins


# ================= سيرفر =================
@app.route("/", methods=['GET'])
def home():
    return "BOT IS RUNNING 🔥"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================= الرسائل =================
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    global GAMES_ENABLED

    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id

    is_command = msg.startswith(PREFIX)
    cmd = normalize(msg[len(PREFIX):]) if is_command else ""

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        reply = None

        # ================= أوامر الأدمن =================

        if is_command and "قفل" in cmd and is_admin(user_id):
            GAMES_ENABLED = False
            active_games.pop(room_id, None)
            reply = "🔒 تم قفل الألعاب."

        elif is_command and "فتح" in cmd and is_admin(user_id):
            GAMES_ENABLED = True
            reply = "🔓 تم فتح الألعاب."

        elif is_command and cmd == "h":
            reply = """🎮 الأوامر:

سؤال
رتب
سباق
صح غلط
توب

👮‍♂️ أوامر الأدمن:
.فتح
.قفل
"""

        # ================= الألعاب =================

        elif GAMES_ENABLED:

            if msg == "سؤال":
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p":2}
                reply = f"🧠 سؤال:\n{q['q']}"

            elif msg == "رتب":
                w = random.choice(words)
                mixed = "".join(random.sample(w, len(w)))
                active_games[room_id] = {"a": w, "p":2}
                reply = f"✏️ رتب:\n{mixed}"

            elif msg == "سباق":
                s = random.choice(race_data)
                active_games[room_id] = {"a": s, "p":3}
                reply = f"🏎️ اكتب بسرعة:\n{s}"

            elif msg == "صح غلط":
                q = random.choice(tf_data)
                active_games[room_id] = {"a": q["a"], "p":1}
                reply = f"🤔 {q['q']}"

            elif msg == "توب":

                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]

                if top:
                    text = "🏆 الأوائل:\n"
                    for i,(u,s) in enumerate(top):
                        try:
                            name = api.get_profile(u).display_name
                        except:
                            name = "لاعب"
                        text += f"{i+1}. {name} ({s})\n"

                    reply = text
                else:
                    reply = "لسه مفيش نقاط!"

            # ===== التحقق من الإجابات =====

            elif room_id in active_games:

                if is_correct(msg, active_games[room_id]["a"]):

                    p = active_games[room_id]["p"]
                    points[user_id] = points.get(user_id,0)+p
                    save_json("points.json", points)

                    reply = f"✅ صح! +{p} نقطة"
                    del active_games[room_id]


        # ================= إرسال =================

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)