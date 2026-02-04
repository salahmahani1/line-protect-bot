from flask import Flask, request, abort
import json
import random
import os
import re
import time
from difflib import SequenceMatcher
from collections import defaultdict

from linebot.v3.messaging import (
    MessagingApi,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError


# ==============================================================================
#                                   CONFIG
# ==============================================================================

# التوكنز الخاصة بك
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

# قائمة المالكين (أصحاب البوت)
OWNERS = [
    "U9ecd575f8df0e62798f4c8ecc9738d5d",
    "U3617621ee527f90ad2ee0231c8bf973f",
]

# تعريف الاونر الرئيسي لتجنب الأخطاء
OWNER_ID = OWNERS[0]

app = Flask(__name__)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ==============================================================================
#                                SERVER CHECK
# ==============================================================================

# صفحة رئيسية لمنع Render من الدخول في وضع النوم
@app.route("/")
def home():
    return "Bot is alive and running successfully!"


# ==============================================================================
#                                FILE HANDLERS
# ==============================================================================

def load_json(file, default):
    """تحميل ملفات JSON بأمان مع قيمة افتراضية في حال عدم وجود الملف"""
    try:
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {file}: {e}")
    return default


def save_json(file, data):
    """حفظ البيانات في ملف JSON"""
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving {file}: {e}")


# ==============================================================================
#                                DATABASE INIT
# ==============================================================================

# تحميل البيانات أو إنشاء بيانات افتراضية
questions = load_json("questions.json", [
    {"q": "ما هي عاصمة السعودية؟", "a": "الرياض"},
    {"q": "ما هي عاصمة مصر؟", "a": "القاهرة"},
    {"q": "كم عدد ألوان قوس قزح؟", "a": "7"},
    {"q": "ما هو أسرع حيوان بري؟", "a": "الفهد"}
])

words = load_json("words.json", [
    "سيارة", "طيارة", "مدرسة", "جامعة", "تفاحة", "برتقال", 
    "كمبيوتر", "جوال", "مهندس", "طبيب", "سفينة"
])

tf_questions = load_json("truefalse.json", [
    {"q": "الشمس تدور حول الأرض؟", "a": "غلط"},
    {"q": "الماء يتكون من الهيدروجين والأكسجين؟", "a": "صح"},
    {"q": "عدد كواكب المجموعة الشمسية 9؟", "a": "غلط"}
])

points = load_json("points.json", {})
economy = load_json("economy.json", {})
marriages = load_json("marriages.json", {})
custom_replies = load_json("custom_replies.json", {})
settings = load_json("settings.json", {"games_locked": []})

# دمج المالكين مع الأدمنز
admins = list(set(load_json("admins.json", []) + OWNERS))
save_json("admins.json", admins)


# ==============================================================================
#                                RUNTIME VARS
# ==============================================================================

active_games = {}
cooldowns = defaultdict(float)
spam_guard = defaultdict(int)

# هيكل بيانات البطولة
tournament = {
    "open": False,          # هل التسجيل مفتوح؟
    "active": False,        # هل البطولة جارية الآن؟
    "players": [],          # قائمة اللاعبين المسجلين
    "round": [],            # قائمة المتأهلين للجولة القادمة
    "match": None,          # اللاعبين الحاليين [p1, p2]
    "scores": {},           # نتائج المواجهة الحالية {p1: 0, p2: 0}
    "current_answer": ""    # الإجابة الصحيحة للسؤال الحالي
}


# ==============================================================================
#                                HELPERS
# ==============================================================================

def normalize(text):
    """توحيد النصوص للمقارنة (إزالة الهمزات والتشكيل)"""
    if not text: return ""
    text = str(text).lower().strip()
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    return text


def match(msg, cmds):
    """التحقق من تطابق الرسالة مع الأمر"""
    msg = normalize(msg)

    if isinstance(cmds, str):
        cmds = [cmds]

    for c in cmds:
        c = normalize(c)

        # تطابق تام
        if msg == c:
            return True
        
        # تطابق جزئي ذكي (للتسامح مع الأخطاء الإملائية البسيطة)
        if len(c) > 3 and SequenceMatcher(None, msg, c).ratio() > 0.85:
            return True

    return False


# ==============================================================================
#                                HELP TEXTS
# ==============================================================================

GAMES_INFO = """🎮 قائمة الألعاب:

🔹 رتب:
رتب الحروف المبعثرة لتكوين كلمة صحيحة.

🔹 سؤال:
جاوب على سؤال ثقافي عام.

🔹 صح غلط:
جاوب بـ (صح) أو (غلط).

🔹 سباق:
أكتب الكلمة الظاهرة أسرع من غيرك.

🏆 جمع نقاط وادخل التوب!
"""

TOURNAMENT_INFO = """🏆 نظام البطولة:

1️⃣ يفتح الأدمن التسجيل وتكتب (تسجيل بطولة).
2️⃣ تبدأ البطولة بنظام خروج المغلوب.
3️⃣ كل مواجهة بين لاعبين، أول من يجيب 3 نقاط يفوز.
4️⃣ الفائز يتأهل للجولة التالية حتى يبقى بطل واحد.

🎁 الجائزة: 1000 نقطة للفائز!
"""

ADMIN_HELP = """🛠️ أوامر الإدارة:

📌 الألعاب:
• فتح الالعاب / قفل الالعاب

📌 الإضافات:
• اضف سؤال | س | ج
• اضف كلمة كلمة
• اضف رد | الكلمة | الرد
• حذف رد الكلمة

📌 البطولة:
• فتح تسجيل البطولة
• ابدأ البطولة
• الغاء البطولة

📌 النقاط:
• تصفير الكل
"""


# ==============================================================================
#                                SERVER HANDLER
# ==============================================================================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ==============================================================================
#                                MAIN LOGIC
# ==============================================================================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    msg = event.message.text.strip()
    user_id = event.source.user_id
    room_id = getattr(event.source, "group_id", user_id)

    now = time.time()

    # 🔥 Anti spam system (1 second delay)
    if now - cooldowns[user_id] < 1:
        return

    cooldowns[user_id] = now

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        # محاولة جلب اسم اللاعب
        try:
    name = api.get_profile(user_id).display_name
except:
    name = "لاعب"
        reply = None


        # ==============================================================================
        #                          1. ADMIN COMMANDS (الأدمن)
        # ==============================================================================
        
        if user_id in admins:

            # 🛠️ التحكم في قفل/فتح الألعاب
            if match(msg, ["فتح الالعاب", "تشغيل الالعاب"]):
                if room_id in settings["games_locked"]:
                    settings["games_locked"].remove(room_id)
                    save_json("settings.json", settings)
                reply = "🟢 تم فتح الألعاب، استمتعوا!"

            elif match(msg, ["قفل الالعاب", "ايقاف الالعاب"]):
                if room_id not in settings["games_locked"]:
                    settings["games_locked"].append(room_id)
                    save_json("settings.json", settings)
                reply = "🔴 تم قفل الألعاب مؤقتاً."

            # 🛠️ إضافة سؤال جديد
            elif msg.startswith("اضف سؤال"):
                # الصيغة: اضف سؤال | السؤال | الجواب
                parts = msg.split("|")
                if len(parts) == 3:
                    new_q = parts[1].strip()
                    new_a = parts[2].strip()
                    questions.append({"q": new_q, "a": new_a})
                    save_json("questions.json", questions)
                    reply = f"✅ تم إضافة السؤال: {new_q}"
                else:
                    reply = "❌ خطأ في الصيغة. استخدم:\nاضف سؤال | السؤال | الجواب"

            # 🛠️ إضافة كلمة جديدة
            elif msg.startswith("اضف كلمة"):
                new_word = msg.replace("اضف كلمة", "").strip()
                if new_word:
                    words.append(new_word)
                    save_json("words.json", words)
                    reply = f"✅ تم إضافة الكلمة: {new_word}"

            # 🛠️ إضافة رد تلقائي
            elif msg.startswith("اضف رد"):
                parts = msg.split("|")
                if len(parts) == 3:
                    trigger = normalize(parts[1])
                    response = parts[2].strip()
                    custom_replies[trigger] = response
                    save_json("custom_replies.json", custom_replies)
                    reply = f"✅ تم إضافة الرد على: {parts[1]}"
            
            # 🛠️ حذف رد تلقائي
            elif msg.startswith("حذف رد"):
                trigger = normalize(msg.replace("حذف رد", ""))
                if trigger in custom_replies:
                    del custom_replies[trigger]
                    save_json("custom_replies.json", custom_replies)
                    reply = f"🗑️ تم حذف الرد الخاص بـ: {trigger}"
                else:
                    reply = "❌ الرد غير موجود."

            # 🛠️ تصفير النقاط
            elif match(msg, "تصفير الكل"):
                points.clear()
                save_json("points.json", points)
                reply = "⚠️ تم تصفير نقاط جميع اللاعبين!"

            # 🛠️ التحكم في البطولة
            elif match(msg, "فتح تسجيل البطولة"):
                tournament["open"] = True
                tournament["active"] = False
                tournament["players"] = []
                reply = "🏆 تم فتح باب التسجيل للبطولة!\nاكتب (تسجيل بطولة) للمشاركة."

            elif match(msg, "ابدأ البطولة"):
                if len(tournament["players"]) < 2:
                    reply = "❌ لا يوجد عدد كافي من اللاعبين (يجب أن يكون 2 أو أكثر)."
                else:
                    tournament["active"] = True
                    tournament["open"] = False
                    
                    # خلط اللاعبين
                    random.shuffle(tournament["players"])
                    # نقلهم لقائمة الانتظار (Round)
                    tournament["round"] = tournament["players"].copy()

                    # سحب أول لاعبين
                    p1 = tournament["round"].pop()
                    p2 = tournament["round"].pop()

                    # اختيار سؤال عشوائي
                    q = random.choice(questions)
                    tournament["current_answer"] = normalize(q["a"])

                    tournament["match"] = [p1, p2]
                    tournament["scores"] = {p1: 0, p2: 0}
                    
                    # محاولة جلب الأسماء
                    try:
                        n1 = api.get_profile(p1).display_name
                        n2 = api.get_profile(p2).display_name
                    except:
                        n1 = "اللاعب 1"
                        n2 = "اللاعب 2"

                    reply = f"🔥 بدأت البطولة!\n⚔️ المواجهة الأولى:\n{n1} 🆚 {n2}\n\n🧠 السؤال: {q['q']}"

            elif match(msg, "الغاء البطولة"):
                tournament["active"] = False
                tournament["open"] = False
                tournament["players"] = []
                reply = "🚫 تم إلغاء البطولة الحالية."


        # ==============================================================================
        #                          2. PUBLIC COMMANDS (العامة)
        # ==============================================================================

        if match(msg, ["الاوامر", "help", "مساعدة"]):
            if user_id in admins:
                reply = ADMIN_HELP
            else:
                reply = """📜 الأوامر المتاحة:

🎮 الألعاب:
(رتب، سؤال، صح غلط، سباق)

🏆 البطولة والنقاط:
(تسجيل بطولة، توب، راتب)

⚙️ أخرى:
(ايدي، تفاصيل الالعاب، تفاصيل البطولة)
"""

        elif match(msg, "تفاصيل الالعاب"):
            reply = GAMES_INFO

        elif match(msg, "تفاصيل البطولة"):
            reply = TOURNAMENT_INFO

        # 💰 الراتب اليومي
        elif match(msg, "راتب"):
            last = economy.get(user_id, 0)
            if now - last > 86400: # 24 ساعة
                points[user_id] = points.get(user_id, 0) + 500
                economy[user_id] = now
                save_json("points.json", points)
                save_json("economy.json", economy)
                reply = "💰 تم إيداع 500 نقطة في رصيدك!\nتعال بكرة عشان تاخذ غيرها."
            else:
                remaining = int((86400 - (now - last)) / 3600)
                reply = f"⏳ تو الناس! باقي لك {remaining} ساعة على الراتب."

        # 📊 التوب (أفضل 10)
        elif match(msg, "توب"):
            top = sorted(points.items(), key=lambda x:x[1], reverse=True)[:10]
            text = "🏆 قائمة المتصدرين:\n"
            for i, (uid, p) in enumerate(top, 1):
                try:
                    n = api.get_profile(uid).display_name
                except:
                    n = "لاعب"
                text += f"{i}. {n} | 💎 {p}\n"
            reply = text

        elif match(msg, ["ايدي", "id"]):
            reply = f"🆔 الـ ID الخاص بك:\n{user_id}"

        # 💍 زواج (للمتعة فقط)
        elif match(msg, "تزوج"):
            marriages[user_id] = True
            save_json("marriages.json", marriages)
            reply = "💍 مبروك! صرت متزوج رسمي (افتراضياً طبعاً 😂)"


        # ==============================================================================
        #                          3. TOURNAMENT ENGINE (البطولة)
        # ==============================================================================
        
        # التسجيل
        if tournament["open"] and match(msg, "تسجيل بطولة"):
            if user_id not in tournament["players"]:
                tournament["players"].append(user_id)
                reply = f"✅ تم تسجيلك يا {name} بنجاح!"
            else:
                reply = "⚠️ أنت مسجل بالفعل، انتظر البدء."

        # منطق المواجهات (الأولوية القصوى للإجابات)
        if tournament["active"] and tournament["match"]:
            p1, p2 = tournament["match"]

            # التأكد أن الرسالة من أحد المتنافسين
            if user_id in [p1, p2]:
                
                # التحقق من الإجابة
                if normalize(msg) == tournament["current_answer"]:
                    
                    tournament["scores"][user_id] += 1
                    current_pt = tournament["scores"][user_id]

                    # شرط الفوز بالجولة (3 نقاط)
                    if current_pt >= 3:
                        winner = user_id
                        
                        # إعادة الفائز لقائمة الانتظار (في المقدمة)
                        tournament["round"].insert(0, winner)

                        # هل يوجد لاعبين كافيين لمواجهة جديدة؟
                        if len(tournament["round"]) >= 2:
                            
                            # إعداد المواجهة التالية
                            np1 = tournament["round"].pop()
                            np2 = tournament["round"].pop()
                            
                            # اختيار سؤال جديد
                            nq = random.choice(questions)
                            tournament["current_answer"] = normalize(nq["a"])
                            
                            tournament["match"] = [np1, np2]
                            tournament["scores"] = {np1: 0, np2: 0}

                            try:
                                nn1 = api.get_profile(np1).display_name
                                nn2 = api.get_profile(np2).display_name
                            except:
                                nn1, nn2 = "1", "2"
                            
                            reply = f"🎉 الفائز في الجولة: {name}!\n\n🔥 المواجهة التالية:\n{nn1} 🆚 {nn2}\n🧠 السؤال: {nq['q']}"
                        
                        else:
                            # انتهت البطولة (بقي فائز واحد)
                            tournament["active"] = False
                            
                            # مكافأة الفائز
                            points[winner] = points.get(winner, 0) + 1000
                            save_json("points.json", points)
                            
                            try:
                                champ_name = api.get_profile(winner).display_name
                            except:
                                champ_name = "البطل"

                            reply = f"🎉 مبروك للفائز بالجولة: {name}!\n\n👑👑👑 بطل البطولة هو: {champ_name} 👑👑👑\n💰 تم إضافة 1000 نقطة لرصيدك!"

                    else:
                        # الإجابة صحيحة لكن لم يفز بعد -> سؤال جديد
                        nq = random.choice(questions)
                        tournament["current_answer"] = normalize(nq["a"])
                        
                        scores_txt = f"{tournament['scores'][p1]} - {tournament['scores'][p2]}"
                        reply = f"✅ إجابة صحيحة يا {name}!\nالنتيجة: ({scores_txt})\n\n🧠 السؤال التالي: {nq['q']}"


        # ==============================================================================
        #                          4. GAMES ENGINE (الألعاب العادية)
        # ==============================================================================

        if not reply and not tournament["active"]:

            # تخطي إذا كانت الألعاب مقفلة
            if room_id in settings["games_locked"]:
                pass # لا تفعل شيء إذا كانت مقفلة

            # 🅰️ التحقق من إجابة لعبة قائمة
            elif room_id in active_games:
                
                game = active_games[room_id]
                answer = normalize(game["answer"])

                if normalize(msg) == answer:
                    
                    earned = game["points"]
                    points[user_id] = points.get(user_id, 0) + earned
                    save_json("points.json", points)

                    reply = f"🎉 كفو عليك يا {name}!\nالجواب صح: {game['answer']}\n💰 كسبت {earned} نقطة."
                    
                    # إنهاء اللعبة الحالية
                    del active_games[room_id]

            # 🅱️ بدء ألعاب جديدة
            else:

                # --- لعبة رتب ---
                if match(msg, "رتب") and words:
                    word = random.choice(words)
                    # خلط الحروف
                    scrambled = ''.join(random.sample(word, len(word)))
                    
                    active_games[room_id] = {
                        "answer": word,
                        "points": 10,
                        "type": "scramble"
                    }
                    reply = f"🔤 رتب الحروف التالية:\n{scrambled}"

                # --- لعبة سؤال ---
                elif match(msg, "سؤال") and questions:
                    q = random.choice(questions)
                    
                    active_games[room_id] = {
                        "answer": q["a"],
                        "points": 15,
                        "type": "question"
                    }
                    reply = f"🧠 سؤال ثقافي:\n{q['q']}"

                # --- لعبة صح أو غلط ---
                elif match(msg, ["صح غلط", "صح وغلط"]) and tf_questions:
                    q = random.choice(tf_questions)
                    
                    active_games[room_id] = {
                        "answer": q["a"],
                        "points": 7,
                        "type": "tf"
                    }
                    reply = f"❓ صح أم خطأ؟\n{q['q']}"

                # --- لعبة سباق ---
                elif match(msg, "سباق") and words:
                    w = random.choice(words)
                    
                    active_games[room_id] = {
                        "answer": w,
                        "points": 20,
                        "type": "race"
                    }
                    reply = f"🏎️ أسرع واحد يكتب:\n{w}"
                
                # --- لعبة عكس ---
                elif match(msg, "عكس") and words:
                    w = random.choice(words)
                    # عكس الكلمة للعرض
                    reversed_w = w[::-1]
                    
                    active_games[room_id] = {
                        "answer": w,
                        "points": 15,
                        "type": "reverse"
                    }
                    reply = f"🔄 اعكس الكلمة لترجع صحيحة:\n{reversed_w}"


        # ==============================================================================
        #                          5. CUSTOM REPLIES (الردود التلقائية)
        # ==============================================================================

        if not reply:
            normalized_msg = normalize(msg)
            if normalized_msg in custom_replies:
                reply = custom_replies[normalized_msg]


        # ==============================================================================
        #                          6. SEND RESPONSE (إرسال الرد)
        # ==============================================================================

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )

if __name__ == "__main__":
    # تشغيل السيرفر على البورت 5000
    app.run(host="0.0.0.0", port=5000)
