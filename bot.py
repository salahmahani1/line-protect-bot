from flask import Flask, request, abort
import json, random, os, re, time
from datetime import datetime, timedelta
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

OWNER_ID = "U9ecd575f8df0e62798f4c8ecc9738d5d"

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= إدارة الملفات =================
def load_json(file, default_data):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return default_data

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except: pass

# تحميل ملفات البيانات
questions = load_json("questions.json", [])
words = load_json("words.json", [])
race_data = load_json("race.json", [])
tf_data = load_json("truefalse.json", [])
f3alyat_list = load_json("f3alyat.json", [])
points = load_json("points.json", {})
custom_replies = load_json("custom_replies.json", {})
bot_replies = load_json("replies.json", ["آمرني؟ 👀"])
mention_jokes = load_json("mentions.json", {"on_mention": ["نايم 😴"], "on_return": ["وصل 😂"]})
admins = load_json("admins.json", [OWNER_ID])

# ✅ ملفات الأنظمة الجديدة
economy = load_json("economy.json", {}) # للرواتب: {user_id: timestamp}
marriages = load_json("marriages.json", {}) # للزواج: {user_id: partner_id}

group_settings = load_json("settings.json", {"mention_enabled_groups": []})

# متغيرات النظام
GAMES_ENABLED = True 
active_games = {} 
learning_mode = {} 
pending_mentions = {}

# ================= دوال مساعدة =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def get_rank(p):
    if p < 500: return "🥉 نوب صاعد"
    if p < 2000: return "🥈 مقاتل محترف"
    if p < 5000: return "🥇 سفاح الجروب"
    return "💎 أسطورة البوت"

def is_match(user_input, commands_list):
    if isinstance(commands_list, str): commands_list = [commands_list]
    u = normalize(user_input)
    for cmd in commands_list:
        c = normalize(cmd)
        if u == c or u.startswith(c): return True
    return False

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT LEGENDARY v4 READY 🚀"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global points, economy, marriages, active_games, learning_mode, pending_mentions
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    
    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: user_name = "لاعب"

        reply = None

        # 🕵️‍♂️ المصيدة (أولوية)
        if room_id in pending_mentions and user_id in pending_mentions[room_id]:
            pending_mentions[room_id].remove(user_id)
            reply = random.choice(mention_jokes.get("on_return", ["أهو جه!"]))
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 💰 1. نظام الاقتصاد (راتب)
        if is_match(msg, ["راتب", "الراتب"]):
            now = time.time()
            last_time = economy.get(user_id, 0)
            if now - last_time > 86400: # 24 ساعة
                points[user_id] = points.get(user_id, 0) + 500
                economy[user_id] = now
                save_json("points.json", points)
                save_json("economy.json", economy)
                reply = f"💰 استلمت راتبك اليومي (500 نقطة)! رصيدك الحالي: {points[user_id]}"
            else:
                remaining = int(86400 - (now - last_time))
                h = remaining // 3600
                m = (remaining % 3600) // 60
                reply = f"⏳ باقي لك {h} ساعة و {m} دقيقة على راتبك القادم."

        # 🎭 2. نظام الزواج والطلاق
        elif is_match(msg, ["تزوج"]) and mentionees:
            partner_id = mentionees[0]
            if partner_id == user_id: reply = "عايز تتجوز نفسك؟ اخرج برة 😂"
            elif user_id in marriages: reply = "أنت متزوج أصلاً! خاف ربنا 😂"
            elif partner_id in marriages: reply = "هذا الشخص متزوج، ابحث عن غيره 💔"
            else:
                marriages[user_id] = partner_id
                marriages[partner_id] = user_id
                save_json("marriages.json", marriages)
                try: p_name = api.get_profile(partner_id).display_name
                except: p_name = "الشريك"
                reply = f"💍 مبروك! تم زواج {user_name} من {p_name} .. فين الكيك؟ 🍰"

        elif is_match(msg, ["زوجتي", "زوجي", "شريكي"]):
            if user_id in marriages:
                p_id = marriages[user_id]
                try: p_name = api.get_profile(p_id).display_name
                except: p_name = "مجهول"
                reply = f"❤️ شريك حياتك هو: {p_name}"
            else: reply = "أنت عازب يا مسكين 🦦"

        elif is_match(msg, ["طلاق"]):
            if user_id in marriages:
                p_id = marriages[user_id]
                del marriages[user_id]
                if p_id in marriages: del marriages[p_id]
                save_json("marriages.json", marriages)
                reply = "💔 تم الطلاق بنجاح.. اذهب فأنتم الطلقاء!"
            else: reply = "أنت مش متجوز عشان تطلق أصلاً! 😂"

        # 🪪 3. نظام البروفايلي
        elif is_match(msg, ["ملفي", "بروفايلي", "رصيدي"]):
            p = points.get(user_id, 0)
            rank = get_rank(p)
            status = "متزوج 💍" if user_id in marriages else "عازب 🦦"
            reply = f"🪪 **بطاقتك التعريفية**:\n\n👤 الاسم: {user_name}\n💰 النقاط: {p}\n🏆 الرتبة: {rank}\n❤️ الحالة: {status}\n🆔 ID: {user_id[:8]}.."

        # 🎮 باقي الألعاب والأوامر (نفس الكود السابق)
        elif is_match(msg, [".a", "الادمن"]):
            if user_id in admins: reply = "👮‍♂️ لوحة التحكم: سجل، تفعيل المنشن، بطولة، رفع ادمن."
            else: reply = "👑 قائمة الأدمن: (تظهر أسماء الأدمن هنا)"

        elif is_match(msg, ["سؤال"]):
            if questions:
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p": 2}
                reply = f"🧠 سؤال: {q['q']}"
        
        elif room_id in active_games and is_match(msg, active_games[room_id]["a"]):
            p = active_games[room_id]["p"]
            points[user_id] = points.get(user_id, 0) + p
            save_json("points.json", points)
            reply = f"✅ كفو {user_name}! (+{p} نقطة)"
            del active_games[room_id]

        # 🌝 الردود والمنشن
        if not reply:
            clean_msg = normalize(msg)
            if mentionees and room_id in group_settings["mention_enabled_groups"]:
                if room_id not in pending_mentions: pending_mentions[room_id] = []
                for m_id in mentionees:
                    if m_id != user_id: pending_mentions[room_id].append(m_id)
                reply = random.choice(mention_jokes.get("on_mention", ["..."]))
            elif clean_msg in ["بوت", "يا بوت"]: reply = "عيون البوت 👀"
            elif clean_msg in custom_replies: reply = custom_replies[clean_msg]

        if reply:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
