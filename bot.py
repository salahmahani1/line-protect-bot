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

# 🔴 ضع الآيدي الخاص بك هنا لتكون المالك
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
questions = load_json("questions.json", [{"q": "عاصمة مصر؟", "a": "القاهرة"}])
if not questions: questions = [{"q": "عاصمة السعودية؟", "a": "الرياض"}]

words = load_json("words.json", ["تفاحة", "موز", "برتقال", "سيارة"])
race_data = load_json("race.json", ["سبحان الله", "الحمد لله"])
tf_data = load_json("truefalse.json", [{"q": "النار باردة", "a": "غلط"}])
f3alyat_list = load_json("f3alyat.json", ["صور خلفية جوالك", "آخر صورة في الاستوديو"])
points = load_json("points.json", {})
# تحميل الردود من الملف
bot_replies = load_json("replies.json", ["هلا والله", "بخير", "منور"]) 

# المشرفين والجروبات
admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)

group_settings = load_json("settings.json", {"mention_enabled_groups": []})

# متغيرات النظام
GAMES_ENABLED = True 
RPS_ENABLED = True 
active_games = {} 
tournament = {
    "state": "IDLE", "players": [], "names": {}, 
    "bracket": [], "winners": [], "current_match": None, "round_num": 1
}

# ================= 🧠 الذكاء الاصطناعي والدوال المساعدة =================
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
        if u.startswith(c): return True 
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > 0.85: return True
    return False

def is_correct_answer(user_ans, correct_ans):
    u = normalize(user_ans)
    c = normalize(correct_ans)
    return u == c or SequenceMatcher(None, u, c).ratio() > 0.7

# ================= 🪨 منطق حجر ورقة مقص =================
def play_rps(user_choice):
    choices = ["حجر", "ورقة", "مقص"]
    bot_choice = random.choice(choices)
    emojis = {"حجر": "🪨", "ورقة": "📄", "مقص": "✂️"}
    
    uc = normalize(user_choice)
    if "حجر" in uc: user_clean = "حجر"
    elif "ورق" in uc: user_clean = "ورقة"
    elif "مقص" in uc: user_clean = "مقص"
    else: return None, None

    if user_clean == bot_choice:
        res, win = "تعادل! 🤝", False
    elif (user_clean == "حجر" and bot_choice == "مقص") or \
         (user_clean == "ورقة" and bot_choice == "حجر") or \
         (user_clean == "مقص" and bot_choice == "ورقة"):
        res, win = "أنت فزت! 🎉", True
    else:
        res, win = "أنا فزت! 😜", False
        
    return f"أنت: {emojis[user_clean]}\nأنا: {emojis[bot_choice]}\n\n{res}", win

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT READY (REPLY ONLY MODE) 🚀"

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
    global tournament, GAMES_ENABLED, RPS_ENABLED, active_games, points, group_settings, admins, bot_replies
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    
    # ✅ التحقق: هل الرسالة "رد" (Reply)؟
    is_reply_message = getattr(event.message, "quote_token", None) is not None

    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]
    
    user_name = "لاعب"
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: pass

        reply = None

        # 👑 1. إدارة المشرفين
        if is_match(msg, ["ايدي", "id"]):
            reply = f"🆔 الآيدي الخاص بك:\n{user_id}"

        elif is_match(msg, ["الادمن", "المشرفين", "admins"]):
            txt = "👑 قائمة المشرفين:\n"
            for admin_id in admins:
                try:
                    name = api.get_profile(admin_id).display_name
                    role = " (مالك) 🌟" if admin_id == OWNER_ID else ""
                    txt += f"- {name}{role}\n"
                except: txt += f"- مستخدم ({admin_id[:4]}..)\n"
            reply = txt

        elif is_match(msg, ["رفع ادمن", "ترقية"]) and user_id == OWNER_ID:
            if mentionees:
                added_names = []
                for m_id in mentionees:
                    if m_id not in admins:
                        admins.append(m_id)
                        try: added_names.append(api.get_profile(m_id).display_name)
                        except: added_names.append("عضو")
                save_json("admins.json", admins)
                reply = f"✅ تم ترقية: {', '.join(added_names)}" if added_names else "هم أدمن بالفعل!"
            else: reply = "❌ منشن الشخص!"

        elif is_match(msg, ["تنزيل ادمن", "ازالة ادمن"]) and user_id == OWNER_ID:
            if mentionees:
                removed_names = []
                for m_id in mentionees:
                    if m_id in admins and m_id != OWNER_ID:
                        admins.remove(m_id)
                        try: removed_names.append(api.get_profile(m_id).display_name)
                        except: removed_names.append("عضو")
                save_json("admins.json", admins)
                reply = f"🗑️ تم تنزيل: {', '.join(removed_names)}" if removed_names else "خطأ!"
            else: reply = "❌ منشن الشخص!"

        # 🗣️ 2. أمر قول
        elif msg.startswith("قول "):
            reply = msg.replace("قول ", "", 1)

        # 🛠️ 3. التحكم (أدمن)
        elif is_match(msg, ["قفل اللعب", "قفل الالعاب"]):
            if user_id in admins: GAMES_ENABLED = False; active_games.pop(room_id, None); reply = "🔒 تم قفل الألعاب (ماعدا حجر)."
            else: reply = "❌ أنت مش أدمن."

        elif is_match(msg, ["فتح اللعب", "فتح الالعاب"]):
            if user_id in admins: GAMES_ENABLED = True; reply = "🔓 تم فتح الألعاب."
            else: reply = "❌ أنت مش أدمن."

        elif is_match(msg, ["قفل حجر"]):
            if user_id in admins: RPS_ENABLED = False; reply = "🔒 تم قفل حجر ورقة مقص."
            else: reply = "❌ أنت مش أدمن."
            
        elif is_match(msg, ["فتح حجر"]):
            if user_id in admins: RPS_ENABLED = True; reply = "🔓 تم تشغيل حجر ورقة مقص."
            else: reply = "❌ أنت مش أدمن."

        elif is_match(msg, ["تفعيل المنشن"]):
            if user_id in admins:
                if room_id not in group_settings["mention_enabled_groups"]:
                    group_settings["mention_enabled_groups"].append(room_id); save_json("settings.json", group_settings); reply = "🔔 تم تفعيل المنشن."
                else: reply = "مفعل."

        elif is_match(msg, ["قفل المنشن"]):
            if user_id in admins:
                if room_id in group_settings["mention_enabled_groups"]:
                    group_settings["mention_enabled_groups"].remove(room_id); save_json("settings.json", group_settings); reply = "🔕 تم القفل."
                else: reply = "مقفول."

        elif is_match(msg, ["حذف", "stop"]):
            if room_id in active_games: del active_games[room_id]; reply = "🏳️ تم الحذف."
            else: reply = "مفيش لعبة."

        # 🏆 4. البطولة
        elif is_match(msg, ["بطولة", "بطوله"]) and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}
            reply = "🏆 فتح التسجيل! اكتب ( سجلني ) 🔥"

        elif is_match(msg, ["ابدأ البطولة", "ابدا"]) and user_id in admins:
            if len(tournament["players"]) < 2: reply = "❌ العدد قليل."
            else:
                pool = tournament["players"].copy(); random.shuffle(pool); bracket = []
                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                if pool: tournament["winners"].append(pool[0])
                tournament["bracket"] = bracket; tournament["state"] = "MATCH_WAITING"
                p1, p2 = bracket[0]
                reply = f"📣 بدأت! {tournament['names'][p1]} 🆚 {tournament['names'][p2]}\nاكتبوا ( جاهز )"

        elif is_match(msg, ["الغاء البطولة", "كنسل"]) and user_id in admins:
            tournament["state"] = "IDLE"; reply = "⛔ تم الغاء البطولة."

        elif is_match(msg, ["سجلني", "سجل"]) and tournament["state"] == "REGISTER":
            if user_id not in tournament["players"]:
                tournament["players"].append(user_id); tournament["names"][user_id] = user_name
                reply = f"✅ تم تسجيلك يا {user_name}."
            else: reply = "أنت مسجل."

        elif is_match(msg, ["جاهز", "go"]) and tournament["state"] == "MATCH_WAITING":
            if tournament["bracket"]:
                p1, p2 = tournament["bracket"][0]
                if user_id in [p1, p2] or user_id in admins:
                    tournament["state"] = "MATCH_ACTIVE"
                    q = random.choice(questions)
                    tournament["current_match"] = {"p1": p1, "p2": p2, "s1": 0, "s2": 0, "q_count": 1, "q_data": q}
                    reply = f"🔔 س1: {q['q']}"

        elif tournament["state"] == "MATCH_ACTIVE" and tournament["current_match"]:
            match = tournament["current_match"]
            if user_id in [match["p1"], match["p2"]]:
                if is_correct_answer(msg, match["q_data"]["a"]):
                    if user_id == match["p1"]: match["s1"] += 1
                    else: match["s2"] += 1
                    if match["q_count"] >= 10:
                        s1, s2 = match["s1"], match["s2"]
                        winner_id = match["p1"] if s1 >= s2 else match["p2"]
                        tournament["winners"].append(winner_id); tournament["bracket"].pop(0)
                        tournament["state"] = "MATCH_WAITING"
                        reply = f"🏁 الفائز: {tournament['names'][winner_id]} 🎉\n"
                        if not tournament["bracket"]:
                            if len(tournament["winners"]) == 1:
                                reply += f"🏆 البطل: {tournament['names'][tournament['winners'][0]]}"; tournament["state"] = "IDLE"
                            else:
                                tournament["players"] = tournament["winners"]; tournament["winners"] = []
                                tournament["round_num"] += 1
                                pool = tournament["players"].copy(); random.shuffle(pool); bracket = []
                                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                                if pool: tournament["winners"].append(pool[0])
                                tournament["bracket"] = bracket
                                reply += "انتهى الدور! اكتبوا ( جاهز )"
                        else:
                            p1n, p2n = tournament["bracket"][0]
                            reply += f"التالي: {tournament['names'][p1n]} 🆚 {tournament['names'][p2n]}\nاكتبوا ( جاهز )"
                    else:
                        match["q_count"] += 1; match["q_data"] = random.choice(questions)
                        reply = f"✅ صح!\nس{match['q_count']}: {match['q_data']['q']}"

        # 🪨 5. حجر ورقة مقص
        elif is_match(msg, ["حجر", "ورقة", "ورقه", "مقص"]):
            if RPS_ENABLED:
                res, win = play_rps(msg)
                if res:
                    reply = res
                    if win: points[user_id] = points.get(user_id, 0) + 1; save_json("points.json", points)
            elif not GAMES_ENABLED and not RPS_ENABLED: pass
            else: pass

        # 🎮 6. الألعاب العامة
        elif GAMES_ENABLED and tournament["state"] != "MATCH_ACTIVE":
            if is_match(msg, [".h", "help", "menu", "الاوامر", "اوامر"]):
                reply = """🎮 الألعاب:
سؤال، رتب، صح غلط، سباق، فعالية، توب
🪨 حجر، ورقة، مقص
🏆 البطولة: سجلني، جاهز
🗣️ قول كذا
👮‍♂️ الادمن: رفع/تنزيل ادمن، بطولة، قفل/فتح"""

            elif is_match(msg, ["سؤال", "اسئلة"]):
                q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 2}; reply = f"🧠 سؤال: {q['q']}"
            elif is_match(msg, ["رتب", "ترتيب"]):
                w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 2}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, ["صح غلط"]):
                q = random.choice(tf_data); active_games[room_id] = {"a": q["a"], "p": 1}; reply = f"🤔 صح أم خطأ؟\n{q['q']}"
            elif is_match(msg, ["سباق", "سرعة"]):
                s = random.choice(race_data); active_games[room_id] = {"a": s, "p": 3}; reply = f"🏎️ اكتب بسرعة:\n{s}"
            elif is_match(msg, ["فعالية", "تحدي"]):
                if f3alyat_list: reply = f"✨ {random.choice(f3alyat_list)}"
            elif is_match(msg, ["توب", "نقاط"]):
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
                reply = "🏆 الأوائل:\n" + "\n".join([f"{i+1}. {api.get_profile(u).display_name if u else '..'} ({s})" for i, (u, s) in enumerate(top)]) if top else "مفيش نقاط."
            elif room_id in active_games:
                if is_correct_answer(msg, active_games[room_id]["a"]):
                    p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p; save_json("points.json", points); reply = f"✅ كفو! (+{p})"; del active_games[room_id]

        # 🌝 7. الردود التلقائية (من الملف)
        if not reply:
            # 🛑 الشرط الجديد: يرد فقط إذا كانت الرسالة "رد" (Reply) أو مناداة صريحة
            direct_triggers = ["بوت", "يا بوت", "bot"]
            
            if is_reply_message or is_match(msg, direct_triggers):
                if bot_replies:
                    reply = random.choice(bot_replies)
            
            # المنشن الساخر
            elif mentionees and room_id in group_settings["mention_enabled_groups"]:
                if words: reply = f"{random.choice(words)} 🌚"

        if reply:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
