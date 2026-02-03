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

# تحميل كافة البيانات
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
marriages = load_json("marriages.json", {})
economy = load_json("economy.json", {})
group_settings = load_json("settings.json", {"mention_groups": [], "games_locked_groups": []})

# متغيرات التشغيل
active_games = {} 
learning_mode = {} 
pending_mentions = {}
tournament = {"state": "IDLE", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}

# ================= دوال الذكاء الاصطناعي (Smart Matching) =================
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
        if u == c or u.startswith(c + " "): return True
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > 0.8: return True
    return False

def is_correct_answer(user_ans, correct_ans):
    u = normalize(user_ans)
    c = normalize(correct_ans)
    return u == c or SequenceMatcher(None, u, c).ratio() > 0.8

def get_rank(p):
    if p < 500: return "🥉 نوب صاعد"
    if p < 2000: return "🥈 مقاتل محترف"
    return "💎 أسطورة البوت"

def play_rps(user_choice):
    choices = ["حجر", "ورقة", "مقص"]
    bot_choice = random.choice(choices)
    emojis = {"حجر": "🪨", "ورقة": "📄", "مقص": "✂️"}
    uc = normalize(user_choice)
    user_clean = "حجر" if is_match(uc, ["حجر"]) else "ورقة" if is_match(uc, ["ورقه"]) else "مقص" if is_match(uc, ["مقص"]) else None
    if not user_clean: return None, None
    if user_clean == bot_choice: return f"أنت: {emojis[user_clean]}\nأنا: {emojis[bot_choice]}\n\nتعادل! 🤝", False
    if (user_clean == "حجر" and bot_choice == "مقص") or (user_clean == "ورقة" and bot_choice == "حجر") or (user_clean == "مقص" and bot_choice == "ورقة"):
        return f"أنت: {emojis[user_clean]}\nأنا: {emojis[bot_choice]}\n\nأنت فزت! 🎉", True
    return f"أنت: {emojis[user_clean]}\nأنا: {emojis[bot_choice]}\n\nأنا فزت! 😜", False

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT READY (ULTIMATE STABLE VERSION) ✅🚀"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    global points, marriages, economy, active_games, admins, custom_replies, tournament, pending_mentions, group_settings
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    mentionees = [m.user_id for m in event.message.mention.mentionees] if event.message.mention else []
    GAMES_ALLOWED = room_id not in group_settings.get("games_locked_groups", [])

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: user_name = "لاعب"
        reply = None

        # 🕵️‍♂️ المصيدة (لكل جروب)
        if room_id in group_settings.get("mention_groups", []) and room_id in pending_mentions and user_id in pending_mentions[room_id]:
            pending_mentions[room_id].remove(user_id)
            reply = random.choice(mention_jokes.get("on_return", ["أهو جه!"]))
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 🛑 وضع التعليم (سجل)
        if user_id in learning_mode:
            kw = learning_mode[user_id]; custom_replies[kw] = msg
            save_json("custom_replies.json", custom_replies); del learning_mode[user_id]
            reply = f"✅ تم حفظ الرد لـ: {kw}"; api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))
            return

        # 👮‍♂️ أوامر التعليم والتحكم (للأدمن فقط)
        if msg.startswith("سجل ") and user_id in admins:
            kw = normalize(msg.replace("سجل ", "", 1).strip())
            if kw: learning_mode[user_id] = kw; reply = "✏️ أرسل الرد الآن..."
        
        elif (msg.startswith("حذف ") or msg.startswith("مسح ")) and user_id in admins:
            kw = normalize(msg.replace("حذف ", "", 1).replace("مسح ", "", 1).strip())
            if kw in custom_replies: 
                del custom_replies[kw]; save_json("custom_replies.json", custom_replies); reply = f"🗑️ تم الحذف: {kw}"

        elif is_match(msg, ["فتح الالعاب", "تشغيل الالعاب"]) and user_id in admins:
            if room_id in group_settings["games_locked_groups"]: group_settings["games_locked_groups"].remove(room_id); save_json("settings.json", group_settings); reply = "🔓 تم الفتح."
        elif is_match(msg, ["قفل الالعاب", "ايقاف الالعاب"]) and user_id in admins:
            if room_id not in group_settings["games_locked_groups"]: group_settings["games_locked_groups"].append(room_id); save_json("settings.json", group_settings); reply = "🔒 تم القفل."

        elif is_match(msg, ["تشغيل المنشن", "فتح المنشن"]) and user_id in admins:
            if room_id not in group_settings["mention_groups"]: group_settings["mention_groups"].append(room_id); save_json("settings.json", group_settings); reply = "🔔 تم تفعيل المصيدة."
        elif is_match(msg, ["قفل المنشن", "ايقاف المنشن"]) and user_id in admins:
            if room_id in group_settings["mention_groups"]: group_settings["mention_groups"].remove(room_id); save_json("settings.json", group_settings); reply = "🔕 تم القفل."

        # 👑 الإدارة العامة
        elif normalize(msg) == ".a":
            txt = f"👑 المالك والمشرفين:\n⭐ المالك: Not Play\n──────────────\n"
            for admin_id in admins:
                if admin_id != OWNER_ID:
                    try: a_name = api.get_profile(admin_id).display_name
                    except: a_name = f"أدمن ({admin_id[:5]})"
                    txt += f"👮‍♂️ {a_name}\n"
            reply = txt

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

        elif is_match(msg, ["الادمن", "لوحة"]):
            if user_id in admins: reply = "👮‍♂️ سجل/حذف، فتح/قفل الالعاب، فتح/قفل المنشن، رفع/تنزيل ادمن، بطولة."

        elif msg.startswith("قول ") and user_id in admins:
            txt = msg.replace("قول ", "", 1).strip(); reply = txt if txt else None

        # 🏆 البطولة
        elif is_match(msg, ["بطولة", "بطوله"]) and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}; reply = "🏆 اكتب ( سجلني )"
        elif is_match(msg, ["سجلني", "سجل"]) and tournament["state"] == "REGISTER":
            if user_id not in tournament["players"]: tournament["players"].append(user_id); tournament["names"][user_id] = user_name; reply = "✅ تم تسجيلك."
        elif is_match(msg, ["ابدأ البطولة", "ابدا"]) and user_id in admins:
            if len(tournament["players"]) >= 2:
                pool = tournament["players"][:]; random.shuffle(pool); bracket = []
                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                if pool: tournament["winners"].append(pool[0])
                tournament["bracket"] = bracket; tournament["state"] = "MATCH_WAITING"; p1, p2 = bracket[0]
                reply = f"📣 {tournament['names'][p1]} 🆚 {tournament['names'][p2]}\n( جاهز ) للبدء."
        elif is_match(msg, ["جاهز"]) and tournament["state"] == "MATCH_WAITING":
            if tournament["bracket"]:
                p1, p2 = tournament["bracket"][0]
                if user_id in [p1, p2] or user_id in admins:
                    tournament["state"] = "MATCH_ACTIVE"; q = random.choice(questions)
                    tournament["current_match"] = {"p1": p1, "p2": p2, "s1": 0, "s2": 0, "q_count": 1, "q_data": q}; reply = f"🔔 س1: {q['q']}"
        elif tournament["state"] == "MATCH_ACTIVE" and tournament["current_match"]:
            match = tournament["current_match"]
            if user_id in [match["p1"], match["p2"]] and is_correct_answer(msg, match["q_data"]["a"]):
                if user_id == match["p1"]: match["s1"] += 1
                else: match["s2"] += 1
                if match["q_count"] >= 5:
                    win_id = match["p1"] if match["s1"] >= match["s2"] else match["p2"]
                    tournament["winners"].append(win_id); tournament["bracket"].pop(0); tournament["state"] = "MATCH_WAITING"; reply = f"🏁 الفائز: {tournament['names'][win_id]}! 🎉"
                    if not tournament["bracket"]:
                        if len(tournament["winners"]) == 1: reply += f"\n🏆 البطل: {tournament['names'][tournament['winners'][0]]}"; tournament["state"] = "IDLE"
                        else:
                            tournament["players"] = tournament["winners"]; tournament["winners"] = []; tournament["round_num"] += 1; pool = tournament["players"][:]; random.shuffle(pool); bracket = []
                            while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                            if pool: tournament["winners"].append(pool[0])
                            tournament["bracket"] = bracket; reply += "\nالدور التالي! ( جاهز )"
                else: match["q_count"] += 1; match["q_data"] = random.choice(questions); reply = f"✅ صح!\nس{match['q_count']}: {match['q_data']['q']}"

        # 💰 اقتصاد + زواج + بروفايل
        elif is_match(msg, ["راتب", "الراتب"]):
            now = time.time()
            if now - economy.get(user_id, 0) > 86400:
                points[user_id] = points.get(user_id, 0) + 500; economy[user_id] = now
                save_json("points.json", points); save_json("economy.json", economy); reply = f"💰 استلمت 500 نقطة! رصيدك: {points[user_id]}"
            else: reply = "⏳ الراتب كل 24 ساعة."
        elif is_match(msg, ["تزوج"]) and mentionees:
            p_id = mentionees[0]
            if p_id != user_id and user_id not in marriages and p_id not in marriages:
                marriages[user_id] = p_id; marriages[p_id] = user_id; save_json("marriages.json", marriages); reply = "💍 مبروك الزواج!"
        elif is_match(msg, ["طلاق"]):
             if user_id in marriages:
                p = marriages[user_id]; del marriages[user_id]
                if p in marriages: del marriages[p]
                save_json("marriages.json", marriages); reply = "💔 تم الطلاق."
        elif is_match(msg, ["ملفي", "بروفايلي"]):
            p = points.get(user_id, 0); status = "متزوج 💍" if user_id in marriages else "عازب 🦦"
            reply = f"🪪 {user_name}\n💰 {p} | 🏆 {get_rank(p)}\n❤️ {status}"

        # 🎮 الألعاب (تعمل لو GAMES_ALLOWED)
        elif GAMES_ALLOWED and tournament["state"] == "IDLE":
            if is_match(msg, ["سؤال"]):
                q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 2}; reply = f"🧠 سؤال: {q['q']}"
            elif is_match(msg, ["رتب"]):
                w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 2}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, ["صح غلط"]):
                q = random.choice(tf_data); active_games[room_id] = {"a": q["a"], "p": 1}; reply = f"🤔 صح أم خطأ؟\n{q['q']}"
            elif is_match(msg, ["سباق"]):
                s = random.choice(race_data); active_games[room_id] = {"a": s, "p": 3}; reply = f"🏎️ اكتب بسرعة:\n{s}"
            elif is_match(msg, ["فعالية"]):
                if f3alyat_list: reply = f"✨ {random.choice(f3alyat_list)}"
            elif is_match(msg, ["توب"]):
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
                reply = "🏆 التوب:\n" + "\n".join([f"{i+1}. {api.get_profile(u).display_name if u else '..'} ({s})" for i, (u, s) in enumerate(top)])
            elif is_match(msg, ["حجر", "ورقة", "مقص"]):
                res, win = play_rps(msg)
                if res:
                    reply = res
                    if win: points[user_id] = points.get(user_id, 0) + 1; save_json("points.json", points)
            elif room_id in active_games and is_correct_answer(msg, active_games[room_id]["a"]):
                p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p
                save_json("points.json", points); reply = f"✅ صح! (+{p})"; del active_games[room_id]

        # 🌝 الردود والمصيدة (المنشن)
        if not reply:
            clean = normalize(msg)
            if mentionees and room_id in group_settings.get("mention_groups", []):
                if room_id not in pending_mentions: pending_mentions[room_id] = []
                for m_id in mentionees:
                    if m_id != user_id: pending_mentions[room_id].append(m_id)
                reply = random.choice(mention_jokes.get("on_mention", ["..."]))
            elif is_match(msg, ["بوت", "يا بوت"]): reply = random.choice(bot_replies)
            else:
                for k, v in custom_replies.items():
                    if is_match(clean, k): reply = v; break

        if reply: api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
