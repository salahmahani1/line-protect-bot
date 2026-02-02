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

# 🔴🔴 هام جداً: ضع الايدي الخاص بك هنا لتكون المالك الأساسي
# (لن يستطيع أحد حذفك أو التحكم غيرك في البداية)
OWNER_ID = "U55fb450e06025fe8a329ed942e65de04" 

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= إدارة الملفات والبيانات =================
def load_json(file, default_data):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# تحميل البيانات
questions = load_json("questions.json", [{"q": "عاصمة مصر؟", "a": "القاهرة"}])
words = load_json("words.json", ["تفاحة"])
race_data = load_json("race.json", ["سبحان الله"])
tf_data = load_json("truefalse.json", [{"q": "الشمس تدور حول الأرض", "a": "غلط"}])
points = load_json("points.json", {})

# تحميل قائمة الأدمن (تلقائياً يضيف المالك)
admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)

# حالة الألعاب (مفتوحة أو مغلقة)
GAMES_ENABLED = True 
active_games = {}

# ================= أدوات مساعدة =================
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
    
    # التعامل مع المنشن (لاستخراج الايديهات)
    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        reply = None

        # ---------------------------------------------------------
        # 👑 1. أوامر التحكم (للأدمن والمالك فقط)
        # ---------------------------------------------------------
        
        # أمر قفل اللعب
        if msg == "قفل اللعب" or msg == "قفل":
            if user_id in admins:
                GAMES_ENABLED = False
                active_games.pop(room_id, None) # إلغاء اللعبة الحالية
                reply = "🔒 تم قفل الألعاب! (محدش يقدر يلعب غير بأمر الأدمن)"
            else:
                reply = "❌ أنت مش أدمن عشان تقفل اللعبة!"

        # أمر فتح اللعب
        elif msg == "فتح اللعب" or msg == "فتح":
            if user_id in admins:
                GAMES_ENABLED = True
                reply = "🔓 تم فتح الألعاب للجميع! انطلقوا 🔥"
            else:
                reply = "❌ انتظر الأدمن يفتح اللعب."

        # أمر رفع أدمن بالمنشن (للمالك فقط)
        elif msg.startswith("رفع ادمن") and user_id == OWNER_ID:
            if not mentionees:
                reply = "⚠️ لازم تعمل منشن للشخص مع الأمر (مثال: رفع ادمن @فلان)"
            else:
                count = 0
                for new_admin in mentionees:
                    if new_admin not in admins:
                        admins.append(new_admin)
                        count += 1
                save_json("admins.json", admins) # حفظ دائم
                reply = f"✅ تم ترقية {count} عضو لرتبة أدمن بنجاح!"

        # أمر تنزيل أدمن (حذف صلاحية)
        elif msg.startswith("تنزيل ادمن") and user_id == OWNER_ID:
            if not mentionees:
                reply = "⚠️ منشن الشخص عشان تحذفه من الإدارة."
            else:
                for old_admin in mentionees:
                    if old_admin in admins and old_admin != OWNER_ID:
                        admins.remove(old_admin)
                save_json("admins.json", admins)
                reply = "🗑️ تم سحب رتبة الأدمن."

        # أمر معرفة الايدي (عشان تضيف نفسك أول مرة)
        elif msg == "ايدي":
            reply = f"🆔 {user_id}"

        # ---------------------------------------------------------
        # 🎮 2. الألعاب (تعمل فقط لو GAMES_ENABLED = True)
        # ---------------------------------------------------------
        elif GAMES_ENABLED:
            
            # --- الردود العادية ---
            if msg.startswith("قول "):
                reply = msg.replace("قول ", "")

            # --- تشغيل الألعاب ---
            elif msg == "سؤال":
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p": 2} 
                reply = f"🧠 سؤال: {q['q']}"

            elif msg == "صح غلط":
                q = random.choice(tf_data)
                active_games[room_id] = {"a": q["a"], "p": 1}
                reply = f"🤔 صح أم خطأ؟\n{q['q']}"

            elif msg == "رتب":
                w = random.choice(words)
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
                    try:
                        p = api.get_profile(u)
                        name = p.display_name
                    except:
                        name = "لاعب"
                    txt += f"{i}. {name} -> {s}\n"
                reply = txt

            # --- التحقق من الإجابة ---
            elif room_id in active_games:
                game = active_games[room_id]
                if is_correct(msg, game["a"]):
                    points[user_id] = points.get(user_id, 0) + game["p"]
                    save_json("points.json", points)
                    
                    try: name = api.get_profile(user_id).display_name
                    except: name = "بطل"
                    
                    reply = f"✅ صح يا {name}! (+{game['p']} نقاط)"
                    del active_games[room_id]

        # ⛔ رسالة لو اللعب مقفول وحد حاول يلعب (اختياري)
        elif msg in ["سؤال", "رتب", "سباق", "صح غلط"] and not GAMES_ENABLED:
            # يمكنك تركها فارغة لعدم الرد، أو وضع رد يوضح أن اللعب مغلق
            reply = "⛔ الألعاب مغلقة حالياً من قبل الأدمن."

        # إرسال الرد
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
