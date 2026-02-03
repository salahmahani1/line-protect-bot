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

# تحميل كافة البيانات لضمان عدم ضياع أي ميزة
questions = load_json("questions.json", [])
words = load_json("words.json", [])
race_data = load_json("race.json", [])
tf_data = load_json("truefalse.json", [])
points = load_json("points.json", {})
custom_replies = load_json("custom_replies.json", {})
bot_replies = load_json("replies.json", ["نعم؟ 👀"])
mention_jokes = load_json("mentions.json", {"on_mention": ["نايم 😴"], "on_return": ["وصل 😂"]})
admins = load_json("admins.json", [OWNER_ID])
marriages = load_json("marriages.json", {})
economy = load_json("economy.json", {})
group_settings = load_json("settings.json", {"mention_groups": [], "games_locked_groups": []})

# متغيرات التشغيل اللحظية
active_games = {} 
learning_mode = {} 
pending_mentions = {}
tournament = {"state": "IDLE", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None}

# ================= الذكاء الاصطناعي والمطابقة =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text); text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def is_match(user_input, commands_list):
    u = normalize(user_input)
    if isinstance(commands_list, str): commands_list = [commands_list]
    for cmd in commands_list:
        c = normalize(cmd)
        if len(c) <= 3 and u == c: return True # مطابقة تامة للأوامر القصيرة (رتب/راتب)
        if u == c or u.startswith(c + " "): return True
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > 0.8: return True
    return False

def get_rank(p):
    if p < 500: return "🥉 نوب صاعد"
    if p < 2000: return "🥈 مقاتل محترف"
    if p < 5000: return "🥇 سفاح الجروب"
    return "💎 أسطورة البوت"

# ================= السيرفر والردود =================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global points, admins, custom_replies, group_settings, active_games, learning_mode, tournament, pending_mentions
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    mentionees = [m.user_id for m in event.message.mention.mentionees] if event.message.mention else []

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: user_name = "لاعب"
        reply = None

        # 🕵️‍♂️ 1. المصيدة (المنشن والعودة)
        if room_id in group_settings["mention_groups"] and room_id in pending_mentions and user_id in pending_mentions[room_id]:
            pending_mentions[room_id].remove(user_id)
            reply = random.choice(mention_jokes.get("on_return", ["وصل!"]))
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 🛑 2. وضع التعليم (سجل) للأدمن
        if user_id in learning_mode:
            kw = learning_mode[user_id]; custom_replies[kw] = msg
            save_json("custom_replies.json", custom_replies); del learning_mode[user_id]
            reply = f"✅ تم حفظ الرد لـ: {kw}"; api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 👑 3. أوامر عامة (ايدي، .a)
        if normalize(msg) == ".a":
            txt = "👑 **طاقم الإدارة:**\n"
            for a_id in admins:
                try: name = api.get_profile(a_id).display_name
                except: name = "أدمن"
                role = "⭐ مالك" if a_id == OWNER_ID else "👮‍♂️ مشرف"
                txt += f"{role}: {name}\n"
            reply = txt
        elif is_match(msg, ["ايدي", "id"]):
            reply = f"🆔 الـ ID الخاص بك:\n{user_id}"

        # 👮‍♂️ 4. أوامر المشرفين (التحكم، الرفع، القفل)
        elif user_id in admins:
            if is_match(msg, "رفع ادمن") and mentionees:
                new_admin = mentionees[0]
                if new_admin not in admins:
                    admins.append(new_admin); save_json("admins.json", admins); reply = "✅ تم رفعه مشرف."
            elif is_match(msg, "تنزيل ادمن") and mentionees:
                target = mentionees[0]
                if target != OWNER_ID:
                    admins.remove(target); save_json("admins.json", admins); reply = "🗑️ تم تنزيل المشرف."
            
            elif is_match(msg, ["قفل الالعاب", "ايقاف الالعاب"]):
                if room_id not in group_settings["games_locked_groups"]:
                    group_settings["games_locked_groups"].append(room_id); save_json("settings.json", group_settings); reply = "🔒 تم قفل الألعاب."
            elif is_match(msg, ["فتح الالعاب", "تشغيل الالعاب"]):
                if room_id in group_settings["games_locked_groups"]:
                    group_settings["games_locked_groups"].remove(room_id); save_json("settings.json", group_settings); reply = "🔓 تم فتح الألعاب."
            
            elif is_match(msg, ["فتح المنشن", "تفعيل المنشن"]):
                if room_id not in group_settings["mention_groups"]:
                    group_settings["mention_groups"].append(room_id); save_json("settings.json", group_settings); reply = "🔔 تم تفعيل المصيدة."
            elif is_match(msg, ["قفل المنشن", "ايقاف المنشن"]):
                if room_id in group_settings["mention_groups"]:
                    group_settings["mention_groups"].remove(room_id); save_json("settings.json", group_settings); reply = "🔕 تم إيقاف المصيدة."

            elif msg.startswith("سجل "):
                kw = normalize(msg.replace("سجل ", "", 1).strip())
                if kw: learning_mode[user_id] = kw; reply = "✏️ أرسل الرد الآن..."
            elif is_match(msg, "حذف اللعبة"):
                if room_id in active_games: del active_games[room_id]; reply = "🗑️ تم كنسل اللعبة."
            elif msg.startswith("قول "):
                reply = msg.replace("قول ", "", 1).strip()

        # 🎮 5. نظام الألعاب والبطولة
        GAMES_ALLOWED = room_id not in group_settings.get("games_locked_groups", [])
        if not reply and GAMES_ALLOWED and tournament["state"] == "IDLE":
            if normalize(msg) == "رتب" and words:
                w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 5}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, "سؤال") and questions:
                q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 5}; reply = f"🧠 سؤال: {q['q']}"
            elif is_match(msg, "سباق") and race_data:
                s = random.choice(race_data); active_games[room_id] = {"a": s, "p": 10}; reply = f"🏎️ أسرع واحد يكتب: {s}"
            
            # التحقق من الإجابة (Fuzzy Match)
            elif room_id in active_games and SequenceMatcher(None, normalize(msg), normalize(active_games[room_id]["a"])).ratio() > 0.85:
                p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p
                save_json("points.json", points); reply = f"✅ صح يا {user_name}! (+{p})"; del active_games[room_id]

        # 💰 6. الاقتصاد والاجتماعيات
        if not reply:
            if normalize(msg) == "راتب":
                now = time.time()
                if now - economy.get(user_id, 0) > 86400:
                    points[user_id] = points.get(user_id, 0) + 500; economy[user_id] = now
                    save_json("points.json", points); save_json("economy.json", economy); reply = "💰 استلمت راتبك 500 نقطة!"
                else: reply = "⏳ الراتب كل 24 ساعة."
            elif is_match(msg, "ملفي"):
                p = points.get(user_id, 0); status = "متزوج 💍" if user_id in marriages else "عازب 🦦"
                reply = f"🪪 **بروفايلك:**\n👤 {user_name}\n💰 النقاط: {p}\n🏆 الرتبة: {get_rank(p)}\n❤️ الحالة: {status}"
            elif is_match(msg, "تزوج") and mentionees:
                p_id = mentionees[0]
                if p_id != user_id and user_id not in marriages and p_id not in marriages:
                    marriages[user_id] = p_id; marriages[p_id] = user_id; save_json("marriages.json", marriages); reply = "💍 مبروك الزواج!"
            
            # الردود التلقائية والمصيدة
            elif mentionees and room_id in group_settings["mention_groups"]:
                if room_id not in pending_mentions: pending_mentions[room_id] = []
                for m_id in mentionees:
                    if m_id != user_id: pending_mentions[room_id].append(m_id)
                reply = "نايم 😴"
            elif normalize(msg) in custom_replies: reply = custom_replies[normalize(msg)]
            elif is_match(msg, ["بوت", "يا بوت"]): reply = random.choice(bot_replies)

        if reply: api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
