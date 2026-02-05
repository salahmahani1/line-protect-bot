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
PREFIX = "."
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

# متغيرات النظام
GAMES_ENABLED = True 
active_games = {} 

# متغيرات البطولة
tournament = {
    "state": "IDLE", 
    "players": [], "names": {}, "bracket": [], "winners": [], 
    "current_match": None, "round_num": 1
}

# ================= 🧠 الذكاء الاصطناعي (معالجة النصوص) =================
def normalize(text):
    # توحيد النصوص لزيادة دقة التطابق
    text = str(text).lower().strip()
    # توحيد الألف
    text = re.sub(r'[أإآ]', 'ا', text)
    # توحيد التاء المربوطة والهاء
    text = re.sub(r'ة', 'ه', text)
    # توحيد الياء والألف اللينة
    text = re.sub(r'ى', 'ي', text)
    # إزالة التشكيل (الفتحة والضمة والكسرة...)
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def is_correct(user_ans, correct_ans):
    u = normalize(user_ans)
    c = normalize(correct_ans)
    
    # 1. تطابق تام
    if u == c: return True
    
    # 2. السماح بالأخطاء الإملائية البسيطة (نسبة تشابه 70%)
    # هذا يسمح بـ "القاهر" بدلاً من "القاهرة" أو "فرنسا" بدلاً من "فرنسه"
    if SequenceMatcher(None, u, c).ratio() > 0.7:
        return True
        
    return False

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "BOT IS READY (SMART MODE) 🧠🔥"

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
    global tournament, GAMES_ENABLED, active_games, points, group_settings, admins
    
    msg = event.message.text.strip()
    is_command = msg.startswith(".")
    cmd = msg[1:].strip() if is_command else msg
    user_id = event.source.user_id
    room_id = event.source.group_id if hasattr(event.source, 'group_id') else user_id
    # تجاهل الكلام العادي فقط لو مش لعبة
    if not is_command and msg not in ["سؤال", "رتب", "سباق", "صح غلط"] and room_id not in active_games:
        return
    
    mentionees = []
    if event.message.mention:
        mentionees = [m.user_id for m in event.message.mention.mentionees]
    
    user_name = "لاعب"
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try: user_name = api.get_profile(user_id).display_name
        except: pass

        reply = None

        # 👑 1. التحكم والإدارة
        if is_command in ["قفل اللعب", "قفل"]:
            if user_id in admins:
                GAMES_ENABLED = False
                active_games.pop(room_id, None)
                reply = "🔒 تم قفل الألعاب."
            else: reply = "❌ أنت مش أدمن."

        elif is_command and cmd in ["فتح اللعب", "فتح"]:
            if user_id in admins:
                GAMES_ENABLED = True
                reply = "🔓 تم فتح الألعاب."
            else: reply = "❌ أنت مش أدمن."
            
        elif is_command and cmd == "تفعيل المنشن" and user_id in admins:
            if room_id not in group_settings["mention_enabled_groups"]:
                group_settings["mention_enabled_groups"].append(room_id)
                save_json("settings.json", group_settings)
                reply = "🔔 تم تفعيل المنشن."
            else: reply = "مفعل بالفعل."

        elif is_command and cmd == "قفل المنشن" and user_id in admins:
            if room_id in group_settings["mention_enabled_groups"]:
                group_settings["mention_enabled_groups"].remove(room_id)
                save_json("settings.json", group_settings)
                reply = "🔕 تم قفل المنشن."
            else: reply = "مقفول بالفعل."

        # أوامر البطولة
        elif is_command and cmd == "بطولة" and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}
            reply = "🏆 تم فتح باب التسجيل للبطولة!\nاكتب ( سجلني ) للمشاركة 🔥"

        elif is_command and cmd == "ابدأ البطولة" and user_id in admins:
            if len(tournament["players"]) < 2:
                reply = "❌ العدد قليل (لازم 2+)."
            else:
                pool = tournament["players"].copy()
                random.shuffle(pool)
                bracket = []
                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                if pool: tournament["winners"].append(pool[0])
                tournament["bracket"] = bracket
                tournament["state"] = "MATCH_WAITING"
                p1, p2 = bracket[0]
                n1, n2 = tournament["names"][p1], tournament["names"][p2]
                reply = f"📣 بدأت البطولة!\nالمباراة الأولى:\n{n1} 🆚 {n2}\nاكتبوا ( جاهز ) للبدء."

        elif is_command and cmd == "الغاء البطولة" and user_id in admins:
            tournament["state"] = "IDLE"
            reply = "⛔ تم الغاء البطولة."

        elif msg == "حذف":
            if room_id in active_games:
                del active_games[room_id]
                reply = "🏳️ تم حذف اللعبة."
            else: reply = "مفيش لعبة."

        # 🏆 2. تفاعل البطولة
        elif msg == "سجلني" and tournament["state"] == "REGISTER":
            if user_id not in tournament["players"]:
                tournament["players"].append(user_id)
                tournament["names"][user_id] = user_name
                reply = f"✅ تم تسجيلك يا {user_name}."
            else: reply = "أنت مسجل بالفعل."

        elif msg == "جاهز" and tournament["state"] == "MATCH_WAITING":
            if tournament["bracket"]:
                p1, p2 = tournament["bracket"][0]
                if user_id in [p1, p2] or user_id in admins:
                    tournament["state"] = "MATCH_ACTIVE"
                    q = random.choice(questions)
                    tournament["current_match"] = {"p1": p1, "p2": p2, "s1": 0, "s2": 0, "q_count": 1, "q_data": q}
                    reply = f"🔔 السؤال 1:\n{q['q']}"

        elif tournament["state"] == "MATCH_ACTIVE" and tournament["current_match"]:
            match = tournament["current_match"]
            if user_id in [match["p1"], match["p2"]]:
                # استخدام دالة التصحيح الذكية
                if is_correct(msg, match["q_data"]["a"]):
                    if user_id == match["p1"]: match["s1"] += 1
                    else: match["s2"] += 1
                    
                    if match["q_count"] >= 10: # نهاية المباراة
                        s1, s2 = match["s1"], match["s2"]
                        winner_id = match["p1"] if s1 >= s2 else match["p2"]
                        w_name = tournament["names"][winner_id]
                        reply = f"🏁 الفائز: {w_name} ({s1}-{s2}) 🎉\n"
                        tournament["winners"].append(winner_id)
                        tournament["bracket"].pop(0)
                        tournament["state"] = "MATCH_WAITING"
                        if not tournament["bracket"]: 
                            if len(tournament["winners"]) == 1:
                                reply += f"🏆 بطل البطولة: {tournament['names'][tournament['winners'][0]]} 🏆"
                                tournament["state"] = "IDLE"
                            else:
                                tournament["players"] = tournament["winners"]
                                tournament["winners"] = []
                                tournament["round_num"] += 1
                                pool = tournament["players"].copy()
                                random.shuffle(pool)
                                bracket = []
                                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                                if pool: tournament["winners"].append(pool[0])
                                tournament["bracket"] = bracket
                                reply += "انتهى الدور! اكتبوا ( جاهز ) للمباراة القادمة."
                        else:
                            p1n, p2n = tournament["bracket"][0]
                            reply += f"التالي: {tournament['names'][p1n]} 🆚 {tournament['names'][p2n]}\nاكتبوا ( جاهز )."
                    else:
                        match["q_count"] += 1
                        match["q_data"] = random.choice(questions)
                        reply = f"✅ صح!\nالسؤال {match['q_count']}:\n{match['q_data']['q']}"

        # 🎮 3. الألعاب العادية
        elif GAMES_ENABLED and tournament["state"] != "MATCH_ACTIVE":
            
            if msg in ["help", "قائمة", "menu"] or (is_command and cmd == "h"):
                reply = "🎮 الأوامر:\nسؤال، رتب، صح غلط، سباق، فعالية، توب\n\n🏆 البطولة:\nسجلني، جاهز\n\n👮‍♂️ (للأدمن): بطولة، ابدأ، قفل/فتح، تفعيل/قفل المنشن"

            elif msg in ["سؤال", "رتب", "سباق", "صح غلط"] and room_id in active_games:
                reply = "⛔ فيه لعبة شغالة! كملوها أو اكتبوا 'حذف'."

            elif msg == "سوال":
                q = random.choice(questions)
                active_games[room_id] = {"a": q["a"], "p": 2}
                reply = f"🧠 سؤال: {q['q']}"
            
            elif msg == "رتب":
                w = random.choice(words)
                s = "".join(random.sample(w, len(w)))
                active_games[room_id] = {"a": w, "p": 2}
                reply = f"✏️ رتب: {s}"

            elif msg == "صح غلط":
                q = random.choice(tf_data)
                active_games[room_id] = {"a": q["a"], "p": 1}
                reply = f"🤔 صح أم خطأ؟\n{q['q']}"

            elif msg == "سباق":
                s = random.choice(race_data)
                active_games[room_id] = {"a": s, "p": 3}
                reply = f"🏎️ اكتب بسرعة:\n{s}"
            
            elif msg == "فعالية":
                if f3alyat_list: reply = f"✨ {random.choice(f3alyat_list)}"
                else: reply = "مفيش فعاليات."

            elif msg == "توب":
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:5]
                reply = "🏆 الأوائل:\n" + "\n".join([f"{i+1}. {api.get_profile(u).display_name if u else 'غير معروف'} ({s})" for i, (u, s) in enumerate(top)]) if top else "مفيش نقاط."

            # التحقق من إجابة الألعاب (باستخدام الدالة الذكية)
            elif room_id in active_games:
                if is_correct(msg, active_games[room_id]["a"]):
                    p = active_games[room_id]["p"]
                    points[user_id] = points.get(user_id, 0) + p
                    save_json("points.json", points)
                    reply = f"✅ كفو! (+{p} نقاط)"
                    del active_games[room_id]

        # 🌝 4. المنشن (إذا مفعل)
        if not reply and mentionees and room_id in group_settings["mention_enabled_groups"]:
             if words: reply = f"{random.choice(words)} 🌚"

        # إرسال الرد
        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
