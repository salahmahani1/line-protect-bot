from flask import Flask, request, abort
import json
import os
import time
import random
from collections import defaultdict

from linebot.v3.messaging import (
    MessagingApi,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

from openai import OpenAI


import os
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
# ================= CONFIG =================

CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

# قائمة المالكين (أصحاب البوت)
OWNERS = [
    "U9ecd575f8df0e62798f4c8ecc9738d5d",
    "U3617621ee527f90ad2ee0231c8bf973f",
]

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def ai_reply(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
انت شاب مصري دمك خفيف.
بترد بطريقة طبيعية جداً مش robotic.
ردودك قصيرة (سطر او سطرين).
متقولش انك AI.
اهزر بس من غير ما تبقى بضان.
لو حد شتمك رد بثقة مش بعصبية.
"""
                },
                {"role": "user", "content": message}
            ],
            max_tokens=120
        )

        return response.choices[0].message.content

    except Exception as e:
        print("AI ERROR:", e)
        return "مخي هنج ثانية 😂 جرب تاني"
# ================= SAFE JSON =================

def load_json(file, default):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def save_json(file, data):
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, file)


admins = list(set(load_json("admins.json", []) + OWNERS))
save_json("admins.json", admins)

points = load_json("points.json", {})
economy = load_json("economy.json", {})
mentions = load_json("mentions.json", {"waiting": {}})

# ================= GAME DATA =================

words = load_json("words.json", ["قطة", "كلب", "تفاحة", "موز"])
questions = load_json("questions.json", [{"q": "عاصمة مصر؟", "a": "القاهرة"}])
tf_questions = load_json("truefalse.json", [{"q": "الأرض مسطحة؟", "a": "غلط"}])

active_games = {}

tournament = {
    "open": False,
    "players": [],
    "current": None,
    "scores": {},
    "answer": None
}

# ================= ANTI SPAM =================

cooldowns = defaultdict(float)

def spam_block(user):
    now = time.time()
    if now - cooldowns[user] < 1:
        return True
    cooldowns[user] = now
    return False


# ================= SERVER =================

@app.route("/")
def home():
    return "BOT ALIVE"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================= MESSAGE HANDLER =================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()

    if spam_block(user_id):
        return

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        try:
            name = api.get_profile(user_id).display_name
        except:
            name = "لاعب"

        reply = None

        # ================= GAMES =================

        if not reply:
            room_id = getattr(event.source, "group_id", user_id)

            # الإجابة على لعبة شغالة
            if room_id in active_games:
                game = active_games[room_id]

                if msg.lower() == game["answer"].lower():
                    pts = random.randint(10, 25)
                    points[user_id] = points.get(user_id, 0) + pts
                    save_json("points.json", points)

                    reply = f"🔥 {name} كسب {pts} نقطة!"
                    del active_games[room_id]

            # بدء لعبة جديدة
            elif msg == "سؤال":
                q = random.choice(questions)

                active_games[room_id] = {
                    "answer": q["a"]
                }

                reply = f"🧠 {q['q']}"

            elif msg == "رتب":
                w = random.choice(words)
                shuffled = ''.join(random.sample(w, len(w)))

                active_games[room_id] = {
                    "answer": w
                }

                reply = f"رتب الكلمة:\n{shuffled}"

            elif msg in ["صح غلط", "صح او غلط"]:
                q = random.choice(tf_questions)

                active_games[room_id] = {
                    "answer": q["a"]
                }

                reply = q["q"]

        # ================= TOURNAMENT =================

        if msg == "فتح بطولة" and user_id in admins:
            tournament["open"] = True
            tournament["players"] = []
            reply = "🔥 تم فتح التسجيل للبطولة!"

        elif msg == "تسجيل" and tournament["open"]:
            if user_id not in tournament["players"]:
                tournament["players"].append(user_id)
                reply = "✅ سجلت!"

        elif msg == "ابدأ البطولة" and user_id in admins:
            if len(tournament["players"]) < 2:
                reply = "لا يوجد لاعبين كفاية"
            else:
                p1, p2 = random.sample(tournament["players"], 2)

                q = random.choice(questions)

                tournament["current"] = [p1, p2]
                tournament["scores"] = {p1: 0, p2: 0}
                tournament["answer"] = q["a"]

                reply = f"🔥 مواجهة بدأت!\nالسؤال:\n{q['q']}"

        elif tournament["current"]:
            if user_id in tournament["current"]:
                if msg.lower() == tournament["answer"].lower():
                    tournament["scores"][user_id] += 1

                    if tournament["scores"][user_id] == 3:
                        points[user_id] = points.get(user_id, 0) + 1000
                        save_json("points.json", points)

                        reply = f"🏆 {name} كسب البطولة و اخد 1000 نقطة!"
                        tournament["current"] = None
                        tournament["open"] = False

                    else:
                        q = random.choice(questions)
                        tournament["answer"] = q["a"]

                        reply = f"صح!\nالسؤال الجديد:\n{q['q']}"

        elif msg == "الغاء البطولة" and user_id in admins:
            tournament["open"] = False
            tournament["current"] = None
            reply = "تم الغاء البطولة"

        # ================= OWNERS / ADMINS =================

        if msg == "الادمن":
            reply = f"عدد الادمنز: {len(admins)}"

        if msg.startswith("رفع") and user_id in OWNERS:
            if event.message.mention:
                target = event.message.mention.mentionees[0].user_id
                if target not in admins:
                    admins.append(target)
                    save_json("admins.json", admins)
                    reply = "✅ تم رفعه ادمن"

        if msg.startswith("تنزيل") and user_id in OWNERS:
            if event.message.mention:
                target = event.message.mention.mentionees[0].user_id
                if target in admins:
                    admins.remove(target)
                    save_json("admins.json", admins)
                    reply = "✅ تم تنزيل الادمن"

        # ================= ECONOMY =================

        if msg == "راتب":
            last = economy.get(user_id, 0)

            if time.time() - last > 86400:
                points[user_id] = points.get(user_id, 0) + 500
                economy[user_id] = time.time()

                save_json("points.json", points)
                save_json("economy.json", economy)

                reply = "💰 اخدت 500 نقطة"
            else:
                reply = "استنى بكرة 😄"

        if msg == "فلوسي":
            reply = f"معاك {points.get(user_id, 0)} نقطة"

        # ================= SMART MENTION =================

        mentions.setdefault("waiting", {})
        
        if event.message.mention:
            target = event.message.mention.mentionees[0].user_id
            mentions["waiting"][target] = True
            save_json("mentions.json", mentions)

            reply = "هبلغه لما يرجع 😏"

        if user_id in mentions["waiting"]:
            del mentions["waiting"][user_id]
            save_json("mentions.json", mentions)

            reply = random.choice([
                "👀 حد كان بيدور عليك",
                "تعالى يا نجم كانوا بيسألوا عليك 😂",
                "صح النوم 😏"
            ])
            try:
                pass
            except Exception as e:
                print("CRASH BLOCKED:", e)
    

    if reply:
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)