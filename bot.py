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

# ================= تحميل البيانات =================
questions = load_json("questions.json", [])
if not questions: questions = [{"q": "عاصمة مصر؟", "a": "القاهرة"}]

words = load_json("words.json", ["تفاحة", "موز"])
race_data = load_json("race.json", ["سبحان الله"])
tf_data = load_json("truefalse.json", [{"q": "النار باردة", "a": "غلط"}])
f3alyat_list = load_json("f3alyat.json", ["صور شاشتك"])
points = load_json("points.json", {})

# الردود والمصيدة
custom_replies = load_json("custom_replies.json", {})
bot_replies = load_json("replies.json", ["آمرني؟ 👀", "هلا والله"])
mention_jokes = load_json("mentions.json", {
    "on_mention": ["تلاقيه نايم 😴"],
    "on_return": ["أهو جه أهو 😂"]
})

admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)

group_settings = load_json("settings.json", {"mention_enabled_groups": []})

# متغيرات النظام
GAMES_ENABLED = True 
RPS_ENABLED = True 
active_games = {} 
learning_mode = {} 
pending_mentions = {} # قائمة المصيدة

tournament = {
    "state": "IDLE", "players": [], "names": {}, 
    "bracket": [], "winners": [], "current_match": None, "round_num": 1
}

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
        if u == c: return True
        if u.startswith(c) and len(c) > 3: return True 
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > 0.85: return True
    return False

def is_correct_answer(user_ans, correct_ans):
    u = normalize(user_ans)
    c = normalize(correct_ans)
    return u == c or SequenceMatcher(None, u, c).ratio() > 0.75

# ================= 🪨 حجر ورقة مقص =================
def play_rps(user_choice):
    choices = ["حجر", "ورقة", "مقص"]
    bot_choice = random.choice(choices)
    emojis = {"حجر": "🪨", "ورقة": "📄", "مقص": "✂️"}
    
    uc = normalize(user_choice)
    if "حجر" in uc: user_clean = "حجر"
    elif "ورق" in uc: user_clean = "ورقة"
    elif "مقص" in uc: user_clean = "مقص"
    else: return None, None

    if user_clean == bot_choice: res, win = "تعادل! 🤝", False
    elif (user_clean == "حجر" and bot_choice == "مقص") or \
         (user_clean == "ورقة" and bot_choice == "حجر") or \
         (user_clean == "مقص" and bot_choice == "ورقة"):
        res, win = "أنت فزت! 🎉", True
    else: res, win = "أنا فزت! 😜", False
        
    return f"أنت: {emojis[user_clean]}\nأنا: {emojis[bot_choice]}\n\n{res}", win

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT READY (.a Added) 🚀"

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
    global tournament, GAMES_ENABLED, RPS_ENABLED, active_games, points, admins, custom_replies, learning_mode, group_settings, pending_mentions
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    
    # 🕵️‍♂️ فحص المصيدة (هل الشخص ده كان معمول له منشن؟)
    user_was_mentioned = False
    if room_id in group_settings["mention_enabled_groups"]:
        if room_id in pending_mentions:
            if user_id in pending_mentions[room_id]:
                user_was_mentioned = True
                pending_mentions[room_id].remove(user_id)
                if not pending_mentions[room_id]: del pending_mentions[room_id]

    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]

    user_name = "لاعب"
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: pass

        reply = None

        # 🛑 1. رد المصيدة (أولوية قصوى)
        if user_was_mentioned:
            if "on_return" in mention_jokes and mention_jokes["on_return"]:
                reply = random.choice(mention_jokes["on_return"])
                api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
                return

        # 🛑 2. وضع التعليم
        if user_id in learning_mode:
            keyword = learning_mode[user_id]
            custom_replies[keyword] = msg 
            save_json("custom_replies.json", custom_replies)
            del learning_mode[user_id]
            reply = f"✅ تم حفظ الرد: {keyword}"
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 👑 3. أوامر الإدارة (تم إضافة .a هنا)
        if is_match(msg, ["ايدي", "id"]): reply = f"🆔 ID: {user_id}"
        
        # ✅ الأمر .a والادمن
        elif is_match(msg, ["الادمن", "المشرفين", "admins", ".a"]):
            if user_id in admins:
                # لو أدمن -> نعرض لوحة التحكم
                txt = "👮‍♂️ **لوحة التحكم**:\n• سجل/حذف (الكلمة)\n• تفعيل/قفل المنشن (للمصيدة)\n• بطولة/ألعاب\n• رفع/تنزيل ادمن"
                reply = txt
            else:
                # لو عضو عادي -> نعرض أسماء المشرفين عشان يعرفهم
                admin_names = ""
                for admin_id in admins:
                    try: admin_names += f"- {api.get_profile(admin_id).display_name}\n"
                    except: admin_names += f"- {admin_id[:4]}..\n"
                reply = f"👑 **قائمة المشرفين:**\n{admin_names}"

        elif is_match(msg, ["رفع ادمن"]) and user_id == OWNER_ID:
            if mentionees:
                for m_id in mentionees:
                    if m_id not in admins: admins.append(m_id)
                save_json("admins.json", admins); reply = "✅ تم الترقية."
        elif is_match(msg, ["تنزيل ادمن"]) and user_id == OWNER_ID:
            if mentionees:
                for m_id in mentionees:
                    if m_id in admins and m_id != OWNER_ID: admins.remove(m_id)
                save_json("admins.json", admins); reply = "🗑️ تم التنزيل."

        elif is_match(msg, ["تفعيل المنشن"]):
            if user_id in admins:
                if room_id not in group_settings["mention_enabled_groups"]:
                    group_settings["mention_enabled_groups"].append(room_id)
                    save_json("settings.json", group_settings)
                    reply = "🔔 تم تفعيل المصيدة 😂"
                else: reply = "مفعلة."
        elif is_match(msg, ["قفل المنشن"]):
            if user_id in admins:
                if room_id in group_settings["mention_enabled_groups"]:
                    group_settings["mention_enabled_groups"].remove(room_id)
                    save_json("settings.json", group_settings)
                    reply = "🔕 تم القفل."

        elif msg.startswith("سجل ") and user_id in admins:
            kw = normalize(msg.replace("سجل ", "", 1).strip())
            if kw: learning_mode[user_id] = kw; reply = "✏️ ارسل الرد الآن..."
        elif msg.startswith("حذف ") and user_id in admins:
            kw = normalize(msg.replace("حذف ", "", 1).strip())
            if kw in custom_replies: del custom_replies[kw]; save_json("custom_replies.json", custom_replies); reply = "🗑️ تم الحذف."

        elif msg.startswith("قول "): reply = msg.replace("قول ", "", 1)

        elif is_match(msg, ["قفل اللعب"]) and user_id in admins: GAMES_ENABLED = False; active_games.pop(room_id, None); reply = "🔒 تم القفل."
        elif is_match(msg, ["فتح اللعب"]) and user_id in admins: GAMES_ENABLED = True; reply = "🔓 تم الفتح."
        elif is_match(msg, ["حذف", "stop"]): 
             if room_id in active_games: del active_games[room_id]; reply = "🏳️ تم الحذف."

        # 🏆 4. البطولة
        elif is_match(msg, ["بطولة"]) and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}
            reply = "🏆 التسجيل: اكتب ( سجلني )"
        elif is_match(msg, ["سجلني"]) and tournament["state"] == "REGISTER":
            if user_id not in tournament["players"]: tournament["players"].append(user_id); tournament["names"][user_id] = user_name; reply = "✅ تم."
        elif is_match(msg, ["ابدأ البطولة"]) and user_id in admins:
            if len(tournament["players"]) >= 2:
                pool = tournament["players"][:]; random.shuffle(pool); bracket = []; 
                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                if pool: tournament["winners"].append(pool[0])
                tournament["bracket"] = bracket; tournament["state"] = "MATCH_WAITING"; p1, p2 = bracket[0]
                reply = f"📣 {tournament['names'][p1]} 🆚 {tournament['names'][p2]}\nاكتبوا ( جاهز )"
        elif is_match(msg, ["جاهز"]) and tournament["state"] == "MATCH_WAITING":
             if tournament["bracket"]:
                 p1, p2 = tournament["bracket"][0]
                 if user_id in [p1, p2] or user_id in admins:
                     tournament["state"] = "MATCH_ACTIVE"; q = random.choice(questions)
                     tournament["current_match"] = {"p1": p1, "p2": p2, "s1": 0, "s2": 0, "q_count": 1, "q_data": q}
                     reply = f"🔔 س1: {q['q']}"
        elif tournament["state"] == "MATCH_ACTIVE" and tournament["current_match"]:
            match = tournament["current_match"]
            if user_id in [match["p1"], match["p2"]]:
                if is_correct_answer(msg, match["q_data"]["a"]):
                    if user_id == match["p1"]: match["s1"] += 1
                    else: match["s2"] += 1
                    if match["q_count"] >= 5: 
                        win = match["p1"] if match["s1"] >= match["s2"] else match["p2"]
                        tournament["winners"].append(win); tournament["bracket"].pop(0); tournament["state"] = "MATCH_WAITING"
                        reply = f"🏁 الفائز: {tournament['names'][win]} 🎉"
                        if not tournament["bracket"]: reply += "\nانتهى الدور! (ابدأ) للدور التالي"
                    else:
                        match["q_count"] += 1; match["q_data"] = random.choice(questions)
                        reply = f"✅ صح!\nس{match['q_count']}: {match['q_data']['q']}"

        # 🎮 5. الألعاب
        elif GAMES_ENABLED and tournament["state"] != "MATCH_ACTIVE":
            if is_match(msg, ["الاوامر"]): reply = "🎮 الألعاب: سؤال، رتب، صح غلط، سباق، توب"
            elif is_match(msg, ["سؤال"]): q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 2}; reply = f"🧠 سؤال: {q['q']}"
            elif is_match(msg, ["رتب"]): w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 2}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, ["توب"]): 
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
                reply = "🏆 التوب:\n" + "\n".join([f"{i+1}. {api.get_profile(u).display_name} ({s})" for i, (u, s) in enumerate(top)]) if top else ".."
            elif room_id in active_games and is_correct_answer(msg, active_games[room_id]["a"]):
                p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p; save_json("points.json", points); reply = f"✅ كفو! (+{p})"; del active_games[room_id]

        # 🌝 6. الردود والمنشن
        if not reply:
            clean_msg = normalize(msg)
            
            # أ. تسجيل الضحية في المصيدة (فقط إذا المنشن مفعل)
            if mentionees and room_id in group_settings["mention_enabled_groups"]:
                if room_id not in pending_mentions: pending_mentions[room_id] = []
                new_victims = False
                for m_id in mentionees:
                    if m_id != user_id:
                        pending_mentions[room_id].append(m_id)
                        new_victims = True
                if new_victims and "on_mention" in mention_jokes:
                    reply = random.choice(mention_jokes["on_mention"])

            # ب. الرد على "بوت"
            elif clean_msg in ["بوت", "يا بوت", "bot"]:
                reply = random.choice(bot_replies)
            
            # ج. الردود المخصصة
            elif clean_msg in custom_replies:
                reply = custom_replies[clean_msg]

        if reply:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
