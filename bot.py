from flask import Flask, request, abort
import json, random, os, re, time
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

# تحميل البيانات
points = load_json("points.json", {})
custom_replies = load_json("custom_replies.json", {})
bot_replies = load_json("replies.json", ["آمرني؟ 👀"])
mention_jokes = load_json("mentions.json", {"on_mention": ["نايم 😴"], "on_return": ["وصل 😂"]})
admins = load_json("admins.json", [OWNER_ID])
marriages = load_json("marriages.json", {})
economy = load_json("economy.json", {})
group_settings = load_json("settings.json", {"mention_enabled_groups": []})

# متغيرات الألعاب
questions = load_json("questions.json", [])
active_games = {}
pending_mentions = {}

# ================= دوال مساعدة =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def is_match(user_input, commands_list):
    if isinstance(commands_list, str): commands_list = [commands_list]
    u = normalize(user_input)
    for cmd in commands_list:
        c = normalize(cmd)
        if u == c or u.startswith(c): return True
    return False

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT READY (.a Modified) 🚀"

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
    global points, marriages, economy, active_games, admins, custom_replies
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: user_name = "لاعب"

        reply = None

        # 👑 1. الأمر المطلوب (.a) لعرض المالك والمشرفين فقط
        if normalize(msg) == ".a":
            txt = "👑 **المالك والمشرفين:**\n"
            # عرض المالك
            try: owner_name = api.get_profile(OWNER_ID).display_name
            except: owner_name = "المالك"
            txt += f"⭐ المالك: {owner_name}\n"
            txt += "──────────────\n"
            # عرض باقي الأدمن
            for admin_id in admins:
                if admin_id != OWNER_ID:
                    try: a_name = api.get_profile(admin_id).display_name
                    except: a_name = f"أدمن ({admin_id[:5]}..)"
                    txt += f"👮‍♂️ {a_name}\n"
            reply = txt

        # 👮‍♂️ 2. أوامر لوحة التحكم للأدمن فقط
        elif is_match(msg, ["الادمن", "المشرفين", "لوحه", "لوحة"]):
            if user_id in admins:
                reply = "👮‍♂️ **لوحة التحكم:**\n• سجل/حذف (كلمة)\n• رفع/تنزيل ادمن @\n• بطولة/ألعاب\n• تفعيل/قفل المنشن"
            else:
                reply = "❌ هذه اللوحة للمشرفين فقط. اكتب .a لرؤية من هم المشرفون."

        # 💰 3. الراتب
        elif is_match(msg, ["راتب", "الراتب"]):
            now = time.time()
            if now - economy.get(user_id, 0) > 86400:
                points[user_id] = points.get(user_id, 0) + 500
                economy[user_id] = now
                save_json("points.json", points); save_json("economy.json", economy)
                reply = f"💰 تم استلام 500 نقطة! رصيدك: {points[user_id]}"
            else: reply = "⏳ راتبك لسه ما جه، ارجع لاحقاً."

        # 🪪 4. ملفي
        elif is_match(msg, ["ملفي", "بروفايلي"]):
            reply = f"🪪 **بروفايلك:**\n👤 الاسم: {user_name}\n💰 الرصيد: {points.get(user_id, 0)}"

        # 🎮 5. الألعاب (سؤال)
        elif is_match(msg, ["سؤال"]):
            if questions:
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p": 5}
                reply = f"🧠 سؤال: {q['q']}"

        # التحقق من الإجابة
        elif room_id in active_games and is_match(msg, active_games[room_id]["a"]):
            p = active_games[room_id]["p"]
            points[user_id] = points.get(user_id, 0) + p
            save_json("points.json", points)
            reply = f"✅ كفو {user_name}! (+{p} نقطة)"; del active_games[room_id]

        # 🌝 6. الردود والمناداة
        if not reply:
            clean = normalize(msg)
            if clean in ["بوت", "يا بوت"]: reply = random.choice(bot_replies)
            elif clean in custom_replies: reply = custom_replies[clean]

        if reply:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
