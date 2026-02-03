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
questions = load_json("questions.json", [])

active_games = {}
pending_mentions = {}
learning_mode = {}

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
def home(): return "BOT READY (V5 - THE FINAL BOSS) 🚀"

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
    global points, marriages, economy, active_games, admins, custom_replies, learning_mode, group_settings, pending_mentions
    
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
            reply = random.choice(mention_jokes.get("on_return", ["وصل!"]))
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 🛑 وضع التعليم
        if user_id in learning_mode:
            kw = learning_mode[user_id]
            custom_replies[kw] = msg
            save_json("custom_replies.json", custom_replies)
            del learning_mode[user_id]
            reply = f"✅ تم حفظ الرد لـ: {kw}"
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 👑 1. الأمر (.a) لعرض المالك والمشرفين
        if normalize(msg) == ".a":
            txt = "👑 **المالك والمشرفين:**\n"
            try: owner_name = api.get_profile(OWNER_ID).display_name
            except: owner_name = "المالك"
            txt += f"⭐ المالك: {owner_name}\n──────────────\n"
            for admin_id in admins:
                if admin_id != OWNER_ID:
                    try: a_name = api.get_profile(admin_id).display_name
                    except: a_name = f"أدمن ({admin_id[:5]})"
                    txt += f"👮‍♂️ {a_name}\n"
            reply = txt

        # 🚀 2. تطوير رفع وتنزيل الأدمن (مع التأكيد الذكي)
        elif is_match(msg, ["رفع ادمن"]) and user_id == OWNER_ID:
            if mentionees:
                responses = []
                for m_id in mentionees:
                    if m_id in admins:
                        responses.append("هو ادمن بالفعل! ✅")
                    else:
                        admins.append(m_id)
                        responses.append("تم الترقية بنجاح! 👮‍♂️")
                save_json("admins.json", admins)
                reply = "\n".join(responses)
            else: reply = "❌ منشن الشخص اللي عاوز ترفعه."

        elif is_match(msg, ["تنزيل ادمن"]) and user_id == OWNER_ID:
            if mentionees:
                responses = []
                for m_id in mentionees:
                    if m_id in admins and m_id != OWNER_ID:
                        admins.remove(m_id)
                        responses.append("تم التنزيل بنجاح! 🗑️")
                    else:
                        responses.append("العضو ده مش ادمن أصلاً! 🤔")
                save_json("admins.json", admins)
                reply = "\n".join(responses)

        # 💰 3. نظام الراتب
        elif is_match(msg, ["راتب", "الراتب"]):
            now = time.time()
            if now - economy.get(user_id, 0) > 86400:
                points[user_id] = points.get(user_id, 0) + 500
                economy[user_id] = now
                save_json("points.json", points); save_json("economy.json", economy)
                reply = f"💰 استلمت راتبك (500 نقطة)! رصيدك: {points[user_id]}"
            else: reply = "⏳ راتبك لسه ما جه، ارجع لاحقاً."

        # 💍 4. نظام الزواج
        elif is_match(msg, ["تزوج"]) and mentionees:
            partner_id = mentionees[0]
            if partner_id == user_id: reply = "عايز تتجوز نفسك؟ اخرج برة 😂"
            elif user_id in marriages: reply = "أنت متزوج أصلاً! خاف ربنا 😂"
            elif partner_id in marriages: reply = "هذا الشخص متزوج، ابحث عن غيره 💔"
            else:
                marriages[user_id] = partner_id; marriages[partner_id] = user_id
                save_json("marriages.json", marriages)
                reply = f"💍 مبروك الزواج! تم الربط بنجاح ✨"

        elif is_match(msg, ["طلاق"]):
            if user_id in marriages:
                p_id = marriages[user_id]
                marriages.pop(user_id, None); marriages.pop(p_id, None)
                save_json("marriages.json", marriages)
                reply = "💔 تم الطلاق.. الله يعوض عليك."
            else: reply = "أنت عازب أصلاً! 😂"

        # 🪪 5. نظام ملفي (البروفايل)
        elif is_match(msg, ["ملفي", "بروفايلي"]):
            p = points.get(user_id, 0)
            status = "متزوج 💍" if user_id in marriages else "عازب 🦦"
            reply = f"🪪 **بروفايلك:**\n👤 الاسم: {user_name}\n💰 الرصيد: {p}\n🏆 الرتبة: {get_rank(p)}\n❤️ الحالة: {status}"

        # 👮‍♂️ 6. لوحة التحكم
        elif is_match(msg, ["لوحة", "لوحه", "الادمن"]):
            if user_id in admins:
                reply = "👮‍♂️ **لوحة التحكم:**\n• سجل/حذف (كلمة)\n• رفع/تنزيل ادمن @\n• تفعيل/قفل المنشن\n• قفل/فتح اللعب"
            else: reply = "❌ للمشرفين فقط."

        # 🎮 7. الألعاب (سؤال)
        elif is_match(msg, ["سؤال"]):
            if questions:
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p": 5}
                reply = f"🧠 سؤال: {q['q']}"

        elif room_id in active_games and is_match(msg, active_games[room_id]["a"]):
            p = active_games[room_id]["p"]
            points[user_id] = points.get(user_id, 0) + p
            save_json("points.json", points)
            reply = f"✅ كفو {user_name}! (+{p} نقطة)"; del active_games[room_id]

        # 🌝 8. الردود والمصيدة
        if not reply:
            clean = normalize(msg)
            if mentionees and room_id in group_settings["mention_enabled_groups"]:
                if room_id not in pending_mentions: pending_mentions[room_id] = []
                for m_id in mentionees:
                    if m_id != user_id: pending_mentions[room_id].append(m_id)
                reply = random.choice(mention_jokes.get("on_mention", ["..."]))
            elif clean in ["بوت", "يا بوت"]: reply = random.choice(bot_replies)
            elif clean in custom_replies: reply = custom_replies[clean]

        if reply:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
