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

# ================= إعدادات البوت =================
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

# 🔴 ضع الـ ID الخاص بك هنا
OWNER_ID = "U9ecd575f8df0e62798f4c8ecc9738d5d"

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= 🤣 قائمة الردود الساخرة (تعمل دائماً) =================
funny_replies = [
    "عايز ايه يا ابني؟ انا مش فاضيلك 😒",
    "يا ساتر.. كل شوية منشن منشن! 🤯",
    "المنشن بفلوس على فكرة 💸",
    "أنا نايم، تعال بكره 😴",
    "حد يقوله يسكت والنبي 😂",
    "نعم؟ لبيك شبيك البوت بين ايديك 🧞‍♂️",
    "مش هرد عليك عشان شكلك مش عاجبني 🌚",
    "يا ابني ركز في مستقبلك وسيب البوت 📖",
    "لا إله إلا الله.. عايز ايه؟ 😂",
    "بحبك بس ما تكررهاش تاني ❤️",
    "انت بتناديني ليه؟ انا شغال عندك؟ 🤨",
    "سمعتك من اول مرة والله 👂",
    "جروب كله رغي مفيش فايدة 🗣️",
    "طب قول 'يا عم البوت' طيب احترمني! 😎",
    "فاضي شوية نشرب قهوة في حتة بعيدة؟ ☕",
    "أيوة أنا البوت.. الامضاء: ذكاء اصطناعي زهقان 🤖"
]

# ================= إدارة الملفات =================
def load_json(file, default_data):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

questions = load_json("questions.json", [{"q": "عاصمة مصر؟", "a": "القاهرة"}])

# ✅ الآن يتم تحميل الكلمات من الملف words.json تلقائياً
words = load_json("words.json", ["تفاحة", "موز", "برتقال"]) 

race_data = load_json("race.json", ["سبحان الله"])
tf_data = load_json("truefalse.json", [{"q": "الشمس تدور حول الأرض", "a": "غلط"}])
points = load_json("points.json", {})
admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)

GAMES_ENABLED = True 
active_games = {} 

# ================= دوال مساعدة =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def is_correct(user_ans, correct_ans):
    return SequenceMatcher(None, normalize(user_ans), normalize(correct_ans)).ratio() > 0.85

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT IS READY 🔥"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ================= معالجة الرسائل =================
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global GAMES_ENABLED, active_games, admins, points
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    
    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        reply = None

        # 👑 1. التحكم
        if msg == "قفل اللعب" or msg == "قفل":
            if user_id in admins:
                GAMES_ENABLED = False
                active_games.pop(room_id, None)
                reply = "🔒 تم قفل الألعاب!"
            else:
                reply = "❌ أنت مش أدمن!"

        elif msg == "فتح اللعب" or msg == "فتح":
            if user_id in admins:
                GAMES_ENABLED = True
                reply = "🔓 تم فتح الألعاب!"
            else:
                reply = "❌ انتظر الأدمن."

        elif msg.startswith("رفع ادمن") and user_id == OWNER_ID:
            for new_admin in mentionees:
                if new_admin not in admins: admins.append(new_admin)
            save_json("admins.json", admins)
            reply = "✅ تم الترقية."

        elif msg.startswith("تنزيل ادمن") and user_id == OWNER_ID:
            for old_admin in mentionees:
                if old_admin in admins and old_admin != OWNER_ID: admins.remove(old_admin)
            save_json("admins.json", admins)
            reply = "🗑️ تم التنزيل."
            
        elif msg == "ايدي": reply = user_id

        elif msg == "حذف":
            if room_id in active_games:
                del active_games[room_id]
                reply = "🏳️ تم حذف اللعبة الحالية."
            else:
                reply = "مفيش لعبة شغالة أصلاً! 😂"

        # 📋 2. القائمة
        elif msg in ["العاب", "اوامر الالعاب", "help", "menu"]:
            reply = """🎮 قائمة الألعاب:
1️⃣ سؤال
2️⃣ رتب
3️⃣ صح غلط
4️⃣ سباق
            
🛑 للحذف اكتب: حذف
🏆 للنقاط اكتب: توب"""

        # 🤣 3. الردود الساخرة (تعمل دائماً)
        elif mentionees and not msg.startswith(("رفع", "تنزيل")):
             reply = random.choice(funny_replies)

        # 🎮 4. الألعاب (تعمل فقط لو مفتوحة)
        elif GAMES_ENABLED:
            
            if msg in ["سؤال", "رتب", "سباق", "صح غلط"] and room_id in active_games:
                reply = "⛔ كملوا اللعبة الأولى الأول! أو اكتبوا 'حذف'."
            
            elif msg == "سؤال":
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p": 2} 
                reply = f"🧠 سؤال: {q['q']}"

            elif msg == "صح غلط":
                q = random.choice(tf_data)
                active_games[room_id] = {"a": q["a"], "p": 1}
                reply = f"🤔 صح أم خطأ؟\n{q['q']}"

            elif msg == "رتب":
                w = random.choice(words) # يقرأ من ملف words.json
                scrambled = "".join(random.sample(w, len(w)))
                active_games[room_id] = {"a": w, "p": 2}
                reply = f"✏️ رتب: {scrambled}"

            elif msg == "سباق":
                s = random.choice(race_data)
                active_games[room_id] = {"a": s, "p": 3}
                reply = f"🏎️ اكتب بسرعة:\n{s}"

            elif msg == "توب":
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
                txt = "🏆 الأوائل:\n"
                for i, (u, s) in enumerate(top, 1):
                    try: name = api.get_profile(u).display_name
                    except: name = "بطل"
                    txt += f"{i}. {name} -> {s}\n"
                reply = txt

            elif msg.startswith("قول "):
                reply = msg.replace("قول ", "")

            elif room_id in active_games:
                game = active_games[room_id]
                if is_correct(msg, game["a"]):
                    points[user_id] = points.get(user_id, 0) + game["p"]
                    save_json("points.json", points)
                    try: name = api.get_profile(user_id).display_name
                    except: name = "بطل"
                    
                    reply = f"✅ كفو {name}! (+{game['p']} نقاط)\nيلا افتحوا لعبة جديدة 🔥"
                    del active_games[room_id]

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
