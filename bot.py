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

# ================= الإعدادات الأساسية =================
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

OWNER_ID = "U9ecd575f8df0e62798f4c8ecc9738d5d"

app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= إدارة الذاكرة والتخزين التلقائي =================
def load_json(file, default):
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return default

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except: pass

# تحميل كافة الملفات (دماغ البوت)
questions = load_json("questions.json", [])
words = load_json("words.json", [])
race_data = load_json("race.json", [])
tf_data = load_json("truefalse.json", [])
f3alyat_list = load_json("f3alyat.json", [])
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

# ================= الذكاء الاصطناعي والمطابقة الذكية =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text); text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def is_match(user_input, commands_list, threshold=0.8):
    if isinstance(commands_list, str): commands_list = [commands_list]
    u = normalize(user_input)
    for cmd in commands_list:
        c = normalize(cmd)
        if len(c) <= 3 and u == c: return True # أولوية الأوامر الثابتة القصيرة
        if u == c or u.startswith(c + " "): return True
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > threshold: return True # ذكاء اصطناعي
    return False

# ================= السيرفر والتحكم =================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global points, active_games, admins, custom_replies, tournament, pending_mentions, group_settings
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    mentionees = [m.user_id for m in event.message.mention.mentionees] if event.message.mention else []
    
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: user_name = "لاعب"
        reply = None

        # 🕵️‍♂️ 1. المصيدة (تلقائية)
        if room_id in group_settings["mention_groups"] and room_id in pending_mentions and user_id in pending_mentions[room_id]:
            pending_mentions[room_id].remove(user_id)
            reply = random.choice(mention_jokes.get("on_return", ["وصل!"]))
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 🛑 2. وضع التعليم (سجل) للأدمن
        if user_id in learning_mode:
            kw = learning_mode[user_id]; custom_replies[kw] = msg
            save_json("custom_replies.json", custom_replies); del learning_mode[user_id]
            reply = f"✅ تم الحفظ يا {user_name}. لما حد يقول '{kw}' هرد عليه كدا."; api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 👮‍♂️ 3. أوامر الإدارة (مطابقة دقيقة)
        if msg.startswith("سجل ") and user_id in admins:
            kw = normalize(msg.replace("سجل ", "", 1).strip())
            if kw: learning_mode[user_id] = kw; reply = "✏️ قولي أرد بإيه؟ (نص/صورة)"
        
        elif is_match(msg, ["حذف اللعبة", "كنسل"]) and user_id in admins:
            if room_id in active_games: del active_games[room_id]; reply = "🗑️ تم حذف اللعبة القائمة."
            else: reply = "مافيش لعبة شغالة حالياً! 👀"

        elif is_match(msg, ["فتح الالعاب", "تشغيل الالعاب"]) and user_id in admins:
            if room_id in group_settings["games_locked_groups"]: group_settings["games_locked_groups"].remove(room_id); save_json("settings.json", group_settings); reply = "🔓 تم الفتح."

        elif is_match(msg, ["قفل الالعاب", "ايقاف الالعاب"]) and user_id in admins:
            if room_id not in group_settings["games_locked_groups"]: group_settings["games_locked_groups"].append(room_id); save_json("settings.json", group_settings); reply = "🔒 تم القفل."

        # 🏆 4. نظام البطولة (كامل)
        elif is_match(msg, ["بطولة", "بطوله"]) and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None}; reply = "🏆 اكتب ( سجلني )"
        
        # 💰 5. الاقتصاد (أمر ثابت)
        elif normalize(msg) == "راتب":
            now = time.time()
            if now - economy.get(user_id, 0) > 86400:
                points[user_id] = points.get(user_id, 0) + 500; economy[user_id] = now
                save_json("points.json", points); save_json("economy.json", economy); reply = f"💰 {user_name}، استلمت 500 نقطة!"
            else: reply = "⏳ الراتب مرة واحدة في اليوم."

        # 🎮 6. نظام الألعاب (ذكي وبدون تكرار)
        elif room_id not in group_settings["games_locked_groups"] and tournament["state"] == "IDLE":
            is_game = is_match(msg, ["سؤال", "رتب", "سباق", "صح غلط"])
            if is_game and room_id in active_games:
                reply = "⚠️ فيه لعبة شغالة! خلصوها الأول أو الأدمن يكتب 'كنسل'."
            elif normalize(msg) == "رتب" and words:
                w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 2}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, "سؤال") and questions:
                q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 2}; reply = f"🧠 سؤال: {q['q']}"
            
            # التحقق من الإجابة الصحيحة
            elif room_id in active_games and SequenceMatcher(None, normalize(msg), normalize(active_games[room_id]["a"])).ratio() > 0.85:
                p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p
                save_json("points.json", points); reply = f"✅ صح يا {user_name}! (+{p})"; del active_games[room_id]

        # 🌚 7. الردود العامة والمصيدة
        if not reply:
            clean = normalize(msg)
            if mentionees and room_id in group_settings["mention_groups"]:
                if room_id not in pending_mentions: pending_mentions[room_id] = []
                for m_id in mentionees:
                    if m_id != user_id: pending_mentions[room_id].append(m_id)
                reply = "..."
            elif is_match(msg, ["بوت", "يا بوت"]): reply = "آمرني؟ 👀"
            elif is_match(msg, "ملفي"):
                p = points.get(user_id, 0); reply = f"🪪 {user_name}\n💰 نقاطك: {p}"
            # ذكاء بشري في البحث عن ردود مسجلة
            else:
                for k, v in custom_replies.items():
                    if is_match(clean, k): reply = v; break

        if reply: api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
