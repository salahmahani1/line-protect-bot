from flask import Flask, request, abort
import json, random, time, os, re
from difflib import SequenceMatcher

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# الإعدادات الأساسية
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= التخزين الذكي (دعم المجموعات) =================
# active_games سيعتمد على ID الغرفة لمنع التداخل
active_games = {}
points_db = "points.json"

def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_points(p):
    with open(points_db, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False)

points = load_json(points_db) if isinstance(load_json(points_db), dict) else {}

# تحميل ملفات الألعاب من الصورة
questions = load_json("questions.json")
words = load_json("words.json")
race_data = load_json("race.json")
tf_data = load_json("truefalse.json")

# ================= وظائف المساعدة =================

def normalize(text):
    text = text.lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text) # حذف التشكيل
    return text

def is_correct(user, answer):
    similarity = SequenceMatcher(None, normalize(user), normalize(answer)).ratio()
    return similarity > 0.85

# ================= منطق البوت =================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global points
    msg = event.message.text.strip()
    user_id = event.source.user_id
    # تحديد ID الغرفة (سواء جروب أو خاص) لضمان عدم تداخل الألعاب
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        reply = None

        # 1. نظام الردود الذكية والمرحة (AI Sim)
        if msg.startswith("قول "):
            words_to_say = msg.replace("قول ", "").strip()
            reply = f"📣 {words_to_say}"

        elif "@" in msg: # الرد عند المنشن
            fun_replies = ["ليه بتزعجه يا حبيب قلبي؟ 😂", "المنشن ممنوع بس مسموح عشانك 🌚", "سيبوه نايم يا جماعة! 😴"]
            reply = random.choice(fun_replies)

        elif msg in ["البوت", "يا بوت", "bot"]:
            greetings = ["عيون البوت؟ 👀", "لبيك شبيك البوت بين ايديك 🧞‍♂️", "نعم يا فنان؟ 🎨"]
            reply = random.choice(greetings)

        # 2. نظام الألعاب (منظم حسب الغرفة)
        if msg == "سؤال":
            q = random.choice(questions)
            active_games[room_id] = {"a": q["a"], "points": 2}
            reply = f"🧠 سؤال للعباقرة:\n\n{q['q']}"

        elif msg == "رتب":
            word = random.choice(words)
            scrambled = "".join(random.sample(word, len(word)))
            active_games[room_id] = {"a": word, "points": 2}
            reply = f"✏️ رتب الكلمة:\n\n {scrambled}"

        # التحقق من الإجابة (إذا كان هناك لعبة جارية في هذه الغرفة)
        elif room_id in active_games:
            game = active_games[room_id]
            if is_correct(msg, game["a"]):
                points[user_id] = points.get(user_id, 0) + game["points"]
                save_points(points)
                profile = api.get_profile(user_id)
                reply = f"✅ كفو يا {profile.display_name}! \nزاد رصيدك {game['points']} نقطة 🏆"
                del active_games[room_id]

        # 3. قائمة المساعدة والترتيب
        if msg in ["الأوامر", "menu", "help"]:
            reply = "🎮 قائمة المرح:\n- سؤال 🧠\n- رتب ✏️\n- توب 🏆\n- قول [نص] 📣\n\n* جرب منشن صديقك أو نادِ 'يا بوت' 😉"

        elif msg == "توب":
            top_users = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
            text = "🏆 لوحة الشرف:\n"
            for i, (uid, score) in enumerate(top_users, 1):
                try:
                    name = api.get_profile(uid).display_name
                    text += f"{i}. {name} -> {score} ن\n"
                except: continue
            reply = text

        # إرسال الرد
        if reply:
            api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            ))

# تشغيل السيرفر
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
