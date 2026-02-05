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
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

questions = load_json("questions.json", [{"q": "سؤال تجريبي", "a": "جواب"}])
points = load_json("points.json", {})
admins = load_json("admins.json", [OWNER_ID])
if OWNER_ID not in admins: admins.append(OWNER_ID)

# ================= 🏆 نظام البطولة (Tournament System) =================
# الهيكل:
# state: 'IDLE' (خامل), 'REGISTER' (تسجيل), 'MATCH' (مباراة شغالة)
# players: قائمة اللاعبين المسجلين [id1, id2, ...]
# names: قاموس الأسماء {id: "Name"}
# bracket: قائمة المباريات في الدور الحالي [[id1, id2], [id3, id4]]
# winners: الفائزون الذين صعدوا للدور القادم
# current_match: المباراة الحالية {p1: id, p2: id, s1: 0, s2: 0, q_count: 0, q_data: None}

tournament = {
    "state": "IDLE",
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
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    return text

def is_correct(user_ans, correct_ans):
    return SequenceMatcher(None, normalize(user_ans), normalize(correct_ans)).ratio() > 0.85

def get_next_match_text():
    if not tournament["bracket"]:
        return None
    p1_id = tournament["bracket"][0][0]
    p2_id = tournament["bracket"][0][1]
    n1 = tournament["names"].get(p1_id, "لاعب 1")
    n2 = tournament["names"].get(p2_id, "لاعب 2")
    return f"🔥 المباراة القادمة:\n{n1} 🆚 {n2}\n\nجاهزين؟ اللي جاهز يكتب 'جاهز'!"

# ================= السيرفر =================
@app.route("/", methods=['GET'])
def home(): return "TOURNAMENT BOT READY 🏆"

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
    global tournament, points, admins
    
    msg = event.message.text.strip()
    user_id = event.source.user_id
    
    # اسم المستخدم (نحاول نجيبه)
    user_name = "بطل"
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        try:
            profile = api.get_profile(user_id)
            user_name = profile.display_name
        except: pass

        reply = None

        # ----------------------------------------------------
        # 🟢 1. إدارة البطولة (الأوامر الأساسية)
        # ----------------------------------------------------
        
        # فتح باب التسجيل (للأدمن)
        if msg == "بطولة" and user_id in admins:
            tournament = {
                "state": "REGISTER", "players": [], "names": {}, 
                "bracket": [], "winners": [], "current_match": None, "round_num": 1
            }
            reply = """🏆🏆 إعلان بطولــة كبــرى 🏆🏆

تم فتح باب التسجيل! 🔥
أي حد عاوز يشارك ويتحدى يكتب كلمة:
( سجلني )

العدد مفتوح.. ورونا مين الأذكى! 😎"""

        # تسجيل اللاعبين
        elif msg == "سجلني" and tournament["state"] == "REGISTER":
            if user_id not in tournament["players"]:
                tournament["players"].append(user_id)
                tournament["names"][user_id] = user_name
                count = len(tournament["players"])
                reply = f"✅ تم تسجيلك يا {user_name}!\nعدد المسجلين حتى الآن: {count}"
            else:
                reply = "أنت مسجل بالفعل يا نجم! 🌟"

        # بدء البطولة (للأدمن)
        elif msg == "ابدأ البطولة" and user_id in admins:
            if len(tournament["players"]) < 2:
                reply = "❌ العدد غير كافي! لازم على الأقل 2."
            else:
                # عمل القرعة
                players_pool = tournament["players"].copy()
                random.shuffle(players_pool)
                bracket = []
                
                # تقسيم كل اثنين مع بعض
                while len(players_pool) >= 2:
                    p1 = players_pool.pop()
                    p2 = players_pool.pop()
                    bracket.append([p1, p2])
                
                # لو فيه واحد زيادة يصعد تلقائي (Bye)
                if players_pool:
                    lucky_one = players_pool[0]
                    tournament["winners"].append(lucky_one)
                    
                tournament["bracket"] = bracket
                tournament["state"] = "MATCH_WAITING" # انتظار كلمة جاهز
                
                # تجهيز المباراة الأولى
                if bracket:
                    p1, p2 = bracket[0]
                    n1 = tournament["names"][p1]
                    n2 = tournament["names"][p2]
                    reply = f"""📣 تم غلق التسجيل!
عدد اللاعبين: {len(tournament["players"])}
عدد المباريات: {len(bracket)}

🔴 المباراة الأولى:
{n1} 🆚 {n2}

المطلوب: 10 أسئلة 🧠
الفائز يصعد، والخاسر يودعنا 👋

اكتبوا ( جاهز ) عشان نبدأ!"""
                else:
                     reply = "حدث خطأ في القرعة."

        # ----------------------------------------------------
        # 🔴 2. منطق المباراة (الأسئلة والنقاط)
        # ----------------------------------------------------

        # بدء المباراة الحالية بكلمة "جاهز"
        elif msg == "جاهز" and tournament["state"] == "MATCH_WAITING":
            if not tournament["bracket"]: return # مفيش مباريات
            
            p1, p2 = tournament["bracket"][0]
            
            # التأكد ان اللي كتب جاهز هو أحد اللاعبين أو الأدمن
            if user_id in [p1, p2] or user_id in admins:
                # إعداد المباراة
                tournament["state"] = "MATCH_ACTIVE"
                q = random.choice(questions)
                tournament["current_match"] = {
                    "p1": p1, "p2": p2,
                    "s1": 0, "s2": 0,
                    "q_count": 1,
                    "q_data": q
                }
                
                reply = f"""🔔 انطلقنا! السؤال 1 من 10:

{q['q']}

(الإجابة للاعبين فقط)"""

        # استلام الإجابات أثناء المباراة
        elif tournament["state"] == "MATCH_ACTIVE" and tournament["current_match"]:
            match = tournament["current_match"]
            
            # التحقق: هل المرسل هو أحد اللاعبين؟
            if user_id not in [match["p1"], match["p2"]]:
                pass # تجاهل الغرباء (أو ممكن ترد عليهم بس بلاش إزعاج)
            
            else:
                # التحقق من الإجابة
                if is_correct(msg, match["q_data"]["a"]):
                    # إضافة نقطة للفائز
                    winner_name = ""
                    if user_id == match["p1"]:
                        match["s1"] += 1
                        winner_name = tournament["names"][match["p1"]]
                    else:
                        match["s2"] += 1
                        winner_name = tournament["names"][match["p2"]]
                    
                    # هل انتهت الـ 10 أسئلة؟
                    if match["q_count"] >= 10:
                        # تحديد الفائز بالمباراة
                        final_p1 = match["p1"]
                        final_p2 = match["p2"]
                        score1 = match["s1"]
                        score2 = match["s2"]
                        
                        winner_id = None
                        loser_name = ""
                        
                        text_res = f"🏁 انتهت المباراة!\nالنتيجة:\n{tournament['names'][final_p1]}: {score1}\n{tournament['names'][final_p2]}: {score2}\n\n"
                        
                        if score1 > score2:
                            winner_id = final_p1
                            loser_name = tournament["names"][final_p2]
                        elif score2 > score1:
                            winner_id = final_p2
                            loser_name = tournament["names"][final_p1]
                        else:
                            # تعادل (عملة عشوائية لتحديد الفائز)
                            winner_id = random.choice([final_p1, final_p2])
                            text_res += "تعادل! القرعة اختارت الفائز...\n"
                        
                        w_name = tournament["names"][winner_id]
                        text_res += f"🎉 الفائز: {w_name} (تأهل للدور القادم)\n👋 هاردلك: {loser_name}"
                        
                        # تصعيد الفائز
                        tournament["winners"].append(winner_id)
                        tournament["bracket"].pop(0) # حذف المباراة المنتهية
                        tournament["current_match"] = None
                        tournament["state"] = "MATCH_WAITING"
                        
                        # هل انتهى الدور بالكامل؟
                        if not tournament["bracket"]:
                            # بدء دور جديد
                            if len(tournament["winners"]) == 1:
                                # يوجد بطل واحد فقط
                                champion = tournament["names"][tournament["winners"][0]]
                                tournament["state"] = "IDLE"
                                reply = f"{text_res}\n\n🏆🏆🏆 بطل البطولة هو: {champion} 🏆🏆🏆\nمبروووووك!"
                            else:
                                # تجهيز الدور التالي
                                tournament["players"] = tournament["winners"]
                                tournament["winners"] = []
                                tournament["round_num"] += 1
                                
                                # قرعة جديدة للدور الجديد
                                pool = tournament["players"].copy()
                                random.shuffle(pool)
                                new_bracket = []
                                while len(pool) >= 2:
                                    new_bracket.append([pool.pop(), pool.pop()])
                                if pool: tournament["winners"].append(pool[0]) # صعود تلقائي
                                
                                tournament["bracket"] = new_bracket
                                
                                reply = f"{text_res}\n\n🛑 انتهى الدور!\nالمتأهلين للدور {tournament['round_num']}: {len(tournament['players'])}\n\nانتظروا المباريات القادمة... اكتب (جاهز) للمباراة التالية."
                        else:
                            # لسه فيه مباريات في نفس الدور
                            next_m_txt = get_next_match_text()
                            reply = f"{text_res}\n\n{next_m_txt}"
                            
                    else:
                        # الانتقال للسؤال التالي (لسه ما كملنا 10)
                        match["q_count"] += 1
                        new_q = random.choice(questions)
                        match["q_data"] = new_q
                        
                        reply = f"✅ صح {winner_name}! (+1)\nالنتيجة: {match['s1']} - {match['s2']}\n\nالسؤال {match['q_count']}:\n{new_q['q']}"

        # ----------------------------------------------------
        # 🛠️ 3. أوامر المساعدة وإلغاء البطولة
        # ----------------------------------------------------
        elif msg == "الغاء البطولة" and user_id in admins:
            tournament["state"] = "IDLE"
            reply = "⛔ تم إلغاء البطولة وتصفير البيانات."

        elif msg == "حالة البطولة":
            s = tournament["state"]
            count = len(tournament["players"])
            reply = f"📊 الحالة: {s}\nالمشاركين: {count}\nالدور: {tournament['round_num']}"

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
