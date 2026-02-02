from flask import Flask, request, abort
import json, random, os, re, threading, time
from difflib import SequenceMatcher

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, PushMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

# ================= إعدادات البوت =================
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

# 🔴 تأكد إن الايدي بتاعك هنا صح
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
words = load_json("words.json", ["تفاحة", "موز"])
race_data = load_json("race.json", ["سبحان الله"])
tf_data = load_json("truefalse.json", [{"q": "النار باردة", "a": "غلط"}])
f3alyat_list = load_json("f3alyat.json", ["صور خلفية جوالك"])
points = load_json("points.json", {})
admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)
group_settings = load_json("settings.json", {"mention_enabled_groups": []})
all_groups = load_json("all_groups.json", [])

GAMES_ENABLED = True 
active_games = {} 
tournament = {
    "state": "IDLE", "players": [], "names": {}, 
    "bracket": [], "winners": [], "current_match": None, "round_num": 1
}

# ================= قائمة الأذكار =================
dhikr_list = [
    "سبحان الله وبحمده، سبحان الله العظيم 🌿",
    "أستغفر الله العظيم وأتوب إليه 🤲",
    "لا حول ولا قوة إلا بالله العلي العظيم 💪",
    "اللهم صل وسلم على نبينا محمد ﷺ ❤️"
]

# ================= 🧠 الذكاء الاصطناعي (تم التعديل) =================
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
        # ✅ التعديل هنا: شيلنا شرط الطول عشان يقبل المنشن
        if u.startswith(c): return True 
        if len(c) > 3 and SequenceMatcher(None, u, c).ratio() > 0.85: return True
    return False

def is_correct_answer(user_ans, correct_ans):
    u = normalize(user_ans)
    c = normalize(correct_ans)
    return u == c or SequenceMatcher(None, u, c).ratio() > 0.7

# ================= ⏰ الأذكار =================
def send_dhikr_periodic():
    while True:
        time.sleep(5 * 60 * 60)
        dhikr = random.choice(dhikr_list)
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            for group_id in list(all_groups):
                try:
                    api.push_message(PushMessageRequest(to=group_id, messages=[TextMessage(text=f"📢 تذكير:\n{dhikr}")]))
                    time.sleep(1) 
                except: pass

dhikr_thread = threading.Thread(target=send_dhikr_periodic, daemon=True)
dhikr_thread.start()

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT READY (ADMIN FIX) 🔥"

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
    global tournament, GAMES_ENABLED, active_games, points, group_settings, admins, all_groups
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    
    if (room_id.startswith("C") or room_id.startswith("G")) and room_id not in all_groups:
        all_groups.append(room_id)
        save_json("all_groups.json", all_groups)

    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]
    
    user_name = "لاعب"
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: pass

        reply = None

        # 👑 ================= إدارة الأدمنز =================

        # 1. الآيدي
        if is_match(msg, ["ايدي", "id"]):
            reply = f"🆔 الآيدي الخاص بك:\n{user_id}"

        # 2. القائمة
        elif is_match(msg, ["الادمن", "المشرفين", "admins"]):
            txt = "👑 قائمة المشرفين:\n"
            for admin_id in admins:
                try:
                    name = api.get_profile(admin_id).display_name
                    role = " (مالك) 🌟" if admin_id == OWNER_ID else ""
                    txt += f"- {name}{role}\n"
                except:
                    txt += f"- مستخدم ({admin_id[:4]}..)\n"
            reply = txt

        # 3. رفع أدمن
        elif is_match(msg, ["رفع ادمن", "ترقية"]) and user_id == OWNER_ID:
            if mentionees:
                added_names = []
                for m_id in mentionees:
                    if m_id not in admins:
                        admins.append(m_id)
                        try: added_names.append(api.get_profile(m_id).display_name)
                        except: added_names.append("عضو")
                save_json("admins.json", admins)
                if added_names: reply = f"✅ تم ترقية: {', '.join(added_names)}"
                else: reply = "هم أدمن بالفعل!"
            else: reply = "❌ منشن الشخص!"

        # 4. تنزيل أدمن
        elif is_match(msg, ["تنزيل ادمن", "ازالة ادمن", "تنزيل"]) and user_id == OWNER_ID:
            if mentionees:
                removed_names = []
                for m_id in mentionees:
                    if m_id in admins and m_id != OWNER_ID:
                        admins.remove(m_id)
                        try: removed_names.append(api.get_profile(m_id).display_name)
                        except: removed_names.append("عضو")
                save_json("admins.json", admins)
                if removed_names: reply = f"🗑️ تم تنزيل: {', '.join(removed_names)}"
                else: reply = "ليسوا أدمن (أو بتحاول تنزل المالك)!"
            else: reply = "❌ منشن الشخص!"

        # 🕹️ التحكم والألعاب
        elif is_match(msg, ["قفل اللعب", "قفل"]):
            if user_id in admins:
                GAMES_ENABLED = False
                active_games.pop(room_id, None)
                reply = "🔒 تم القفل."
            else: reply = "❌ أنت مش أدمن."

        elif is_match(msg, ["فتح اللعب", "فتح"]):
            if user_id in admins:
                GAMES_ENABLED = True
                reply = "🔓 تم الفتح."
            else: reply = "❌ أنت مش أدمن."
            
        elif is_match(msg, ["تفعيل المنشن"]):
            if user_id in admins:
                if room_id not in group_settings["mention_enabled_groups"]:
                    group_settings["mention_enabled_groups"].append(room_id)
                    save_json("settings.json", group_settings)
                    reply = "🔔 تم تفعيل المنشن."
                else: reply = "مفعل."

        elif is_match(msg, ["قفل المنشن"]):
            if user_id in admins:
                if room_id in group_settings["mention_enabled_groups"]:
                    group_settings["mention_enabled_groups"].remove(room_id)
                    save_json("settings.json", group_settings)
                    reply = "🔕 تم قفل المنشن."
                else: reply = "مقفول."

        # البطولة
        elif is_match(msg, ["بطولة", "بطوله"]) and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}
            reply = "🏆 فتح التسجيل! اكتب ( سجلني )"

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

        elif is_match(msg, ["حذف", "stop"]):
            if room_id in active_games: del active_games[room_id]; reply = "🏳️ تم الحذف."
            else: reply = "مفيش لعبة."

        # تفاعل اللاعبين
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
                        w_name = tournament["names"][winner_id]
                        reply = f"🏁 الفائز: {w_name} 🎉\n"
                        if not tournament["bracket"]:
                            if len(tournament["winners"]) == 1:
                                reply += f"🏆 البطل: {tournament['names'][tournament['winners'][0]]}"
                                tournament["state"] = "IDLE"
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

        # الألعاب العادية
        elif GAMES_ENABLED and tournament["state"] != "MATCH_ACTIVE":
            if is_match(msg, [".h", "help", "menu", "الاوامر", "اوامر"]):
                reply = "🎮 الألعاب: سؤال، رتب، صح غلط، سباق، فعالية\n🏆 البطولة: سجلني، جاهز\n👮‍♂️ الادمن: رفع/تنزيل ادمن، بطولة"

            elif is_match(msg, ["سؤال", "اسئلة"]):
                q = random.choice(questions); active_games[room_id] = {"a": q["a"], "p": 2}; reply = f"🧠 سؤال: {q['q']}"
            elif is_match(msg, ["رتب", "ترتيب"]):
                w = random.choice(words); s = "".join(random.sample(w, len(w))); active_games[room_id] = {"a": w, "p": 2}; reply = f"✏️ رتب: {s}"
            elif is_match(msg, ["صح غلط"]):
                q = random.choice(tf_data); active_games[room_id] = {"a": q["a"], "p": 1}; reply = f"🤔 صح أم خطأ؟\n{q['q']}"
            elif is_match(msg, ["سباق", "سرعة"]):
                s = random.choice(race_data); active_games[room_id] = {"a": s, "p": 3}; reply = f"🏎️ اكتب بسرعة:\n{s}"
            elif is_match(msg, ["فعالية"]):
                if f3alyat_list: reply = f"✨ {random.choice(f3alyat_list)}"
            elif is_match(msg, ["توب"]):
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
                reply = "🏆 الأوائل:\n" + "\n".join([f"{i+1}. {api.get_profile(u).display_name if u else '..'} ({s})" for i, (u, s) in enumerate(top)]) if top else "مفيش نقاط."
            elif room_id in active_games:
                if is_correct_answer(msg, active_games[room_id]["a"]):
                    p = active_games[room_id]["p"]; points[user_id] = points.get(user_id, 0) + p; save_json("points.json", points); reply = f"✅ كفو! (+{p})"; del active_games[room_id]

        if not reply and mentionees and room_id in group_settings["mention_enabled_groups"]:
             if words: reply = f"{random.choice(words)} 🌚"

        if reply:
            api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply)]))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
