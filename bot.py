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

# ================= إدارة الملفات (التخزين التلقائي) =================
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

# تحميل الداتا
questions = load_json("questions.json", [])
words = load_json("words.json", [])
points = load_json("points.json", {})
custom_replies = load_json("custom_replies.json", {})
admins = load_json("admins.json", [OWNER_ID])
economy = load_json("economy.json", {})
group_settings = load_json("settings.json", {"mention_groups": [], "games_locked_groups": []})

# متغيرات التشغيل
active_games = {} 
learning_mode = {} 
pending_mentions = {}
tournament = {"state": "IDLE", "players": [], "names": {}}

# ================= الذكاء والمطابقة =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text); text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    return text

def is_match(user_input, commands_list):
    u = normalize(user_input)
    if isinstance(commands_list, str): commands_list = [commands_list]
    for cmd in commands_list:
        c = normalize(cmd)
        if len(c) <= 3 and u == c: return True
        if u == c or u.startswith(c + " "): return True
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > 0.8: return True
    return False

# ================= السيرفر =================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global points, admins, custom_replies, group_settings, active_games, learning_mode
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    mentionees = [m.user_id for m in event.message.mention.mentionees] if event.message.mention else []

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: user_name = "لاعب"
        reply = None

        # 👑 1. أمر (.a) و (ايدي) - متاح للجميع
        if normalize(msg) == ".a":
            txt = "👑 **طاقم الإدارة:**\n"
            try: owner_name = api.get_profile(OWNER_ID).display_name
            except: owner_name = "المالك"
            txt += f"⭐ المالك: {owner_name}\n"
            txt += "──────────────\n"
            for a_id in admins:
                if a_id != OWNER_ID:
                    try: name = api.get_profile(a_id).display_name
                    except: name = "مشرف"
                    txt += f"👮‍♂️ {name}\n"
            reply = txt

        elif is_match(msg, ["ايدي", "الايدي", "id"]):
            reply = f"🆔 الـ ID الخاص بك هو:\n{user_id}"

        # 👮‍♂️ 2. أوامر التحكم للأدمن فقط
        elif user_id in admins:
            if is_match(msg, "رفع ادمن") and mentionees:
                new_admin = mentionees[0]
                if new_admin not in admins:
                    admins.append(new_admin); save_json("admins.json", admins)
                    reply = "✅ تم رفعه مشرف بنجاح."
            
            elif is_match(msg, "تنزيل ادمن") and mentionees:
                target = mentionees[0]
                if target != OWNER_ID and target in admins:
                    admins.remove(target); save_json("admins.json", admins)
                    reply = "🗑️ تم تنزيل المشرف."

            elif is_match(msg, ["الادمن", "لوحة", "لوحه"]):
                reply = "👮‍♂️ **لوحة التحكم:**\n• سجل/حذف (كلمة)\n• رفع/تنزيل ادمن @\n• فتح/قفل الالعاب\n• حذف اللعبة\n• ايدي (لمعرفة هويتك)"

            elif msg.startswith("سجل ") :
                kw = normalize(msg.replace("سجل ", "", 1).strip())
                if kw: learning_mode[user_id] = kw; reply = "✏️ أرسل الرد الآن..."

            elif is_match(msg, "حذف اللعبة"):
                if room_id in active_games:
                    del active_games[room_id]; reply = "🗑️ تم حذف اللعبة القائمة."

        # 💰 3. الراتب والبروفايل
        if not reply:
            if normalize(msg) == "راتب":
                now = time.time()
                if now - economy.get(user_id, 0) > 86400:
                    points[user_id] = points.get(user_id, 0) + 500; economy[user_id] = now
                    save_json("points.json", points); save_json("economy.json", economy)
                    reply = f"💰 {user_name}، مبروك الـ 500 نقطة!"
                else: reply = "⏳ الراتب كل 24 ساعة."
            
            elif is_match(msg, "ملفي"):
                p = points.get(user_id, 0)
                reply = f"🪪 **بروفايلك:**\n👤 الاسم: {user_name}\n💰 النقاط: {p}\n👮‍♂️ الرتبة: {'مالك' if user_id == OWNER_ID else ('مشرف' if user_id in admins else 'عضو')}"

        # 🎮 4. الألعاب
        if not reply and room_id not in group_settings["games_locked_groups"]:
            if normalize(msg) == "رتب" and words:
                w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 5}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, "سؤال") and questions:
                q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 5}; reply = f"🧠 سؤال: {q['q']}"
            
            elif room_id in active_games and SequenceMatcher(None, normalize(msg), normalize(active_games[room_id]["a"])).ratio() > 0.85:
                p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p
                save_json("points.json", points); reply = f"✅ صح يا {user_name}! (+{p})"; del active_games[room_id]

        # 🌝 5. الردود والمصيدة
        if not reply:
            clean = normalize(msg)
            if clean in custom_replies: reply = custom_replies[clean]
            elif clean in ["بوت", "يا بوت"]: reply = "عيون البوت! 👀"

        if reply: api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
