from flask import Flask, request, abort
import json, random, os, re, time
from difflib import SequenceMatcher
from collections import defaultdict

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError


# ================== CONFIG ==================

CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

OWNERS = [
    "U9ecd575f8df0e62798f4c8ecc9738d5d",
    "U3617621ee527f90ad2ee0231c8bf973f",
]

app = Flask(__name__)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# 🔥 يمنع Render ينام
@app.route("/")
def home():
    return "Bot is alive!"


# ================== SAFE JSON ==================

def load_json(file, default):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except:
        pass


# ================== DATABASE ==================

questions = load_json("questions.json", [])
words = load_json("words.json", [])
tf_questions = load_json("truefalse.json", [])

points = load_json("points.json", {})
economy = load_json("economy.json", {})
marriages = load_json("marriages.json", {})
custom_replies = load_json("custom_replies.json", {})
mentions_data = load_json("mentions.json", {
    "on_mention": [],
    "on_return": []
})
settings = load_json("settings.json", {"games_locked": []})

admins = list(set(load_json("admins.json", []) + OWNERS))
save_json("admins.json", admins)


# ================== RUNTIME ==================

active_games = {}
pending_mentions = {}
cooldowns = defaultdict(float)
spam_guard = defaultdict(int)

tournament = {
    "open": False,
    "active": False,
    "players": [],
    "round": [],
    "match": None,
    "scores": {}
}


# ================== SMART MATCH ==================

def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    return text


def match(msg, cmds):
    msg = normalize(msg)

    if isinstance(cmds, str):
        cmds = [cmds]

    for c in cmds:
        c = normalize(c)

        if msg == c:
            return True

        if len(c) > 3 and SequenceMatcher(None, msg, c).ratio() > 0.85:
            return True

    return False


# ================== HELP TEXT ==================

GAMES_INFO = """
🎮 الألعاب المتاحة:

• رتب → رتب الحروف
• سؤال → سؤال ثقافة
• صح غلط → اختر الإجابة
• سباق → أسرع كتابة

🏆 للفوز خذ نقاط وادخل التوب!
"""

TOURNAMENT_INFO = """
🏆 نظام البطولة:

• تسجيل بطولة → دخول
• تبدأ مواجهات 1 ضد 1
• خروج المغلوب
• النهائي يحدد البطل 👑

الجائزة ضخمة 😈
"""


# ================== SERVER ==================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================== MAIN ==================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    msg = event.message.text.strip()
    mention = event.message.mention
    user_id = event.source.user_id
    room_id = getattr(event.source, "group_id", user_id)

    now = time.time()

    # 🔥 Anti spam
    if now - cooldowns[user_id] < 1:
        return

    cooldowns[user_id] = now

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        try:
            name = api.get_profile(user_id).display_name
        except:
            name = "لاعب"

        reply = None


        # ================== INFO ==================

        if match(msg, "الاوامر"):
            reply = """
📌 الأوامر:

🎮 تفاصيل الالعاب
🏆 تفاصيل البطولة
💰 راتب
📊 توب
"""

        elif match(msg, "تفاصيل الالعاب"):
            reply = GAMES_INFO

        elif match(msg, "تفاصيل البطولة"):
            reply = TOURNAMENT_INFO


# ================= ADMIN =================

if user_id in admins:

    if match(msg, ["رفع ادمن","اضافة ادمن"]):

        if event.message.mention:

            target = event.message.mention.mentionees[0].user_id

            if target not in admins:
                admins.append(target)
                save_json("admins.json", admins)

                reply = "✅ تم رفعه أدمن"

    elif match(msg, ["تنزيل ادمن","حذف ادمن"]):

        if event.message.mention:

            target = event.message.mention.mentionees[0].user_id

            if target in admins:
                admins.remove(target)
                save_json("admins.json", admins)

                reply = "🗑️ تم تنزيله من الادمن"

elif match(msg, ["الادمن","الاداريين"]):

    text = "👮 قائمة الأدمن:\n"

    for ad in admins:
        try:
            n = api.get_profile(ad).display_name
        except:
            n = "Admin"

        if ad in OWNERS:
            text += f"👑 {n}\n"
        else:
            text += f"🔹 {n}\n"

    reply = text

    if match(msg, ["فتح الالعاب","تشغيل الالعاب"]):
                if room_id in settings["games_locked"]:
                    settings["games_locked"].remove(room_id)
                    save_json("settings.json", settings)

                reply = "✅ تم فتح الألعاب"

            elif match(msg, ["قفل الالعاب","ايقاف الالعاب"]):
                settings["games_locked"].append(room_id)
                save_json("settings.json", settings)

                reply = "🔒 تم قفل الألعاب"


            # 🔥 فتح تسجيل البطولة
elif match(msg, "فتح تسجيل البطولة"):

                tournament["open"] = True
                tournament["players"] = []

                reply = "🔥 تم فتح التسجيل! اكتب (تسجيل بطولة)"


            elif match(msg, "ابدأ البطولة"):

                if len(tournament["players"]) < 2:
                    reply = "❌ لاعبين غير كافيين"

                else:
                    tournament["active"] = True
                    tournament["open"] = False
                    random.shuffle(tournament["players"])

                    tournament["round"] = tournament["players"].copy()

                    p1 = tournament["round"].pop()
                    p2 = tournament["round"].pop()

                    tournament["match"] = [p1, p2]
                    tournament["scores"] = {p1:0, p2:0}

                    reply = "🔥 بدأت البطولة!"


        # ================== REGISTER ==================

        elif tournament["open"] and match(msg, "تسجيل بطولة"):

            if user_id not in tournament["players"]:
                tournament["players"].append(user_id)
                reply = "✅ تم تسجيلك!"

            else:
                reply = "انت مسجل بالفعل 😄"


        # ================== ECONOMY ==================

        elif match(msg, "راتب"):

            last = economy.get(user_id, 0)

            if now - last > 86400:

                points[user_id] = points.get(user_id, 0) + 500
                economy[user_id] = now

                save_json("points.json", points)
                save_json("economy.json", economy)

                reply = "💰 استلمت 500 نقطة!"

            else:
                reply = "⏳ الراتب كل 24 ساعة"


        elif match(msg, "توب"):

            top = sorted(points.items(), key=lambda x:x[1], reverse=True)[:10]

            text = "🏆 توب اللاعبين:\n"

            for i,(uid,p) in enumerate(top,1):
                try:
                    n = api.get_profile(uid).display_name
                except:
                    n = "لاعب"

                text += f"{i}- {n} | {p}\n"

            reply = text


        elif match(msg, ["ايدي","id"]):
            reply = user_id


        # ================== SEND ==================

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )
# ================== SEND ==================
        # ================== TOURNAMENT FIGHTS ==================

        if tournament["active"] and tournament["match"]:

            p1, p2 = tournament["match"]

            if user_id in [p1, p2]:

                q = random.choice(questions)
                answer = normalize(q["a"])

                if normalize(msg) == answer:

                    tournament["scores"][user_id] += 1

                    # الفوز عند 3 نقاط
                    if tournament["scores"][user_id] == 3:

                        winner = user_id

                        tournament["round"].append(winner)

                        # باقي لاعيبة؟
                        if len(tournament["round"]) >= 2:

                            p1 = tournament["round"].pop()
                            p2 = tournament["round"].pop()

                            tournament["match"] = [p1, p2]
                            tournament["scores"] = {p1:0, p2:0}

                            reply = "🔥 مواجهة جديدة بدأت!"

                        else:
                            tournament["active"] = False

                            points[winner] = points.get(winner,0)+1000
                            save_json("points.json", points)

                            try:
                                champ = api.get_profile(winner).display_name
                            except:
                                champ = "البطل"

                            reply = f"👑 البطل هو {champ} !!! +1000 نقطة 🔥"

                    else:
                        reply = f"✅ نقطة لـ {name} ({tournament['scores'][user_id]}/3)"



        # ================== SMART MENTION ==================

        if mention and mention.mentionees:

            for m in mention.mentionees:

                if m.user_id != user_id:

                    pending_mentions[m.user_id] = True

                    try:
                        target_name = api.get_profile(m.user_id).display_name
                    except:
                        target_name = "الشخص"

                    if mentions_data["on_mention"]:
                        msg_text = random.choice(mentions_data["on_mention"])
                        reply = f"{target_name} 👀 {msg_text}"



        # 🔥 رجوع المتخفي
        if user_id in pending_mentions:

            del pending_mentions[user_id]

            try:
                name_back = api.get_profile(user_id).display_name
            except:
                name_back = "المتخفي"

            if mentions_data["on_return"]:
                msg_text = random.choice(mentions_data["on_return"])
                reply = f"{name_back} 😈 {msg_text}"

        # ================== GAME ENGINE ==================

        if not reply and not tournament["active"]:

            if room_id in settings["games_locked"]:
                return


            # 🔥 يمنع لعبتين
            if room_id in active_games:

                game = active_games[room_id]
                answer = normalize(game["answer"])

                if normalize(msg) == answer:

                    points[user_id] = points.get(user_id,0)+game["points"]
                    save_json("points.json", points)

                    reply = f"🎉 {name} كسب {game['points']} نقطة!"

                    del active_games[room_id]


            else:

                # ================== رتب ==================

                if match(msg, "رتب") and words:

                    word = random.choice(words)
                    scrambled = ''.join(random.sample(word, len(word)))

                    active_games[room_id] = {
                        "answer":word,
                        "points":10
                    }

                    reply = f"🔤 رتب الحروف:\n{scrambled}"


                # ================== سؤال ==================

                elif match(msg, "سؤال") and questions:

                    q = random.choice(questions)

                    active_games[room_id] = {
                        "answer":q["a"],
                        "points":15
                    }

                    reply = f"🧠 {q['q']}"


                # ================== صح غلط ==================

                elif match(msg, ["صح غلط","صح وغلط"]) and tf_questions:

                    q = random.choice(tf_questions)

                    active_games[room_id] = {
                        "answer":q["a"],
                        "points":7
                    }

                    reply = f"❓ {q['q']}\n(صح / غلط)"


                # ================== سباق ==================

                elif match(msg, "سباق") and words:

                    w = random.choice(words)

                    active_games[room_id] = {
                        "answer":w,
                        "points":20
                    }

                    reply = f"🏎️ اكتب بسرعة:\n{w}"



        # ================== MARRIAGE 😂 ==================

        elif match(msg, "تزوج"):

            marriages[user_id] = True
            save_json("marriages.json", marriages)

            reply = "💍 مبروك! بقيت متزوج رسمي 😂"



        # ================== CUSTOM REPLIES ==================

        elif normalize(msg) in custom_replies:
            reply = custom_replies[normalize(msg)]
            
                # ================== SEND ==================

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)