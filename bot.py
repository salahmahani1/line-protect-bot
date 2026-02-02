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
    except:
        pass # لو الملف خربان، استخدم الافتراضي
    return default_data

questions = load_json("questions.json", [{"q": "سؤال تجريبي", "a": "جواب"}])
if not questions: questions = [{"q": "سؤال تجريبي", "a": "جواب"}]

admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)

# ================= 🏆 متغيرات البطولة =================
tournament = {
    "state": "IDLE", # IDLE, REGISTER, MATCH_WAITING, MATCH_ACTIVE
    "players": [],
    "names": {},
    "bracket": [],
    "winners": [],
    "current_match": None,
    "round_num": 1
}

# ================= دوال مساعدة =================
def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    return text

def is_correct(user_ans, correct_ans):
    return SequenceMatcher(None, normalize(user_ans), normalize(correct_ans)).ratio() > 0.85

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "TOURNAMENT BOT IS ALIVE 🏆"

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
    global tournament
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    
    # محاولة جلب الاسم
    user_name = "لاعب"
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try:
            profile = api.get_profile(user_id)
            user_name = profile.display_name
        except: pass

        reply = None

        # 🛑 1. أوامر الأدمن (التحكم)
        if msg == "بطولة" and user_id in admins:
            tournament = {"state": "REGISTER", "players": [], "names": {}, "bracket": [], "winners": [], "current_match": None, "round_num": 1}
            reply = "🏆 تم فتح باب التسجيل للبطولة!\n\nاكتب ( سجلني ) للمشاركة 🔥"

        elif msg == "الغاء البطولة" and user_id in admins:
            tournament["state"] = "IDLE"
            reply = "⛔ تم إلغاء البطولة."

        elif msg == "ابدأ البطولة" and user_id in admins:
            if len(tournament["players"]) < 2:
                reply = "❌ العدد قليل! لازم 2 على الأقل."
            else:
                # القرعة
                pool = tournament["players"].copy()
                random.shuffle(pool)
                bracket = []
                while len(pool) >= 2:
                    bracket.append([pool.pop(), pool.pop()])
                if pool: tournament["winners"].append(pool[0]) # تأهل تلقائي (Bye)
                
                tournament["bracket"] = bracket
                tournament["state"] = "MATCH_WAITING"
                
                p1, p2 = bracket[0]
                n1 = tournament["names"][p1]
                n2 = tournament["names"][p2]
                reply = f"📣 تم غلق التسجيل!\nعدد اللاعبين: {len(tournament['players'])}\n\n🔥 المباراة الأولى:\n{n1} 🆚 {n2}\n\nاللاعبين فقط يكتبوا ( جاهز ) للبدء!"

        # 📝 2. تسجيل اللاعبين
        elif msg == "سجلني" and tournament["state"] == "REGISTER":
            if user_id not in tournament["players"]:
                tournament["players"].append(user_id)
                tournament["names"][user_id] = user_name
                reply = f"✅ تم تسجيلك يا {user_name}!"
            else:
                reply = "أنت مسجل بالفعل! 😉"

        # ⚔️ 3. إدارة المباراة
        elif msg == "جاهز" and tournament["state"] == "MATCH_WAITING":
            if tournament["bracket"]:
                p1, p2 = tournament["bracket"][0]
                if user_id in [p1, p2] or user_id in admins:
                    tournament["state"] = "MATCH_ACTIVE"
                    q = random.choice(questions)
                    tournament["current_match"] = {"p1": p1, "p2": p2, "s1": 0, "s2": 0, "q_count": 1, "q_data": q}
                    reply = f"🔔 السؤال 1:\n{q['q']}"

        # 🧠 4. استقبال الإجابات
        elif tournament["state"] == "MATCH_ACTIVE" and tournament["current_match"]:
            match = tournament["current_match"]
            if user_id in [match["p1"], match["p2"]]:
                if is_correct(msg, match["q_data"]["a"]):
                    # حساب النقاط
                    if user_id == match["p1"]: match["s1"] += 1
                    else: match["s2"] += 1
                    
                    winner_round_name = tournament["names"][user_id]
                    
                    # هل انتهت المباراة (10 أسئلة)؟
                    if match["q_count"] >= 10:
                        s1, s2 = match["s1"], match["s2"]
                        # تحديد الفائز
                        if s1 >= s2: winner_id, loser_id = match["p1"], match["p2"]
                        else: winner_id, loser_id = match["p2"], match["p1"]
                        
                        w_name = tournament["names"][winner_id]
                        reply = f"🏁 انتهت المباراة!\nالفائز: {w_name} 🎉\nالنتيجة: {s1}-{s2}\n\n"
                        
                        tournament["winners"].append(winner_id)
                        tournament["bracket"].pop(0)
                        tournament["state"] = "MATCH_WAITING"
                        
                        # هل انتهى الدور؟
                        if not tournament["bracket"]:
                            if len(tournament["winners"]) == 1:
                                reply += f"🏆🏆 بطل البطولة هو: {tournament['names'][tournament['winners'][0]]} 🏆🏆"
                                tournament["state"] = "IDLE"
                            else:
                                tournament["players"] = tournament["winners"]
                                tournament["winners"] = []
                                tournament["round_num"] += 1
                                # قرعة جديدة
                                pool = tournament["players"].copy()
                                random.shuffle(pool)
                                bracket = []
                                while len(pool) >= 2: bracket.append([pool.pop(), pool.pop()])
                                if pool: tournament["winners"].append(pool[0])
                                tournament["bracket"] = bracket
                                reply += f"🛑 انتهى الدور {tournament['round_num']-1}!\nالمتأهلين للدور القادم: {len(tournament['players'])}\nاكتبوا ( جاهز ) للمباراة القادمة."
                        else:
                            p1_next, p2_next = tournament["bracket"][0]
                            n1 = tournament["names"][p1_next]
                            n2 = tournament["names"][p2_next]
                            reply += f"المباراة التالية:\n{n1} 🆚 {n2}\nاكتبوا ( جاهز )!"
                    else:
                        # السؤال التالي
                        match["q_count"] += 1
                        q = random.choice(questions)
                        match["q_data"] = q
                        reply = f"✅ صح {winner_round_name}!\nالسؤال {match['q_count']}:\n{q['q']}"

        elif msg == "شرح":
             reply = "انظر الرسالة المثبتة من الأدمن."

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
