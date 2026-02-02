from flask import Flask, request, abort
import random, json, os, time
from deep_translator import GoogleTranslator

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = "QPrjs2oE0WkxeQqXZKUy8eDjfK4kY2iD3bg3iDaE09doEdXp9+C1203rzMyz+UWHDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3Z+GfADLEe2xv89bBYFqRg6ritVwXIPLFQBnWrM/7ITMAdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "7768432715f1e544354aa28f3b68ac0e"

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ==============================
# STORAGE
# ==============================

POINTS_FILE = "points.json"

if os.path.exists(POINTS_FILE):
    with open(POINTS_FILE, "r") as f:
        points = json.load(f)
else:
    points = {}

def save_points():
    with open(POINTS_FILE, "w") as f:
        json.dump(points, f)

def add_point(user_id, amount=1):
    points[user_id] = points.get(user_id, 0) + amount
    save_points()

# ==============================
# PERFORMANCE
# ==============================

user_cache = {}
last_message = {}
daily_salary = {}

# ==============================
# SMART REPLIES
# ==============================

smart_replies = {
    "السلام عليكم": "وعليكم السلام 😄🔥",
    "صباح الخير": "صباح الفل ☀️",
    "مساء الخير": "مساء العسل 😏",
    "بحبك": "وانا كمان 😂❤️"
}

# ==============================
# GAMES DATA
# ==============================

number_to_guess = None
current_answer = None
current_word = None

questions = [
    {"q": "مين غنى تملي معاك؟", "a": "عمرو دياب"},
    {"q": "عاصمة فرنسا؟", "a": "باريس"},
]

fast_words = [

"كمبيوتر","موبايل","شاشة","كيبورد","سماعة","تكنولوجيا","برمجة",
"ذكاء","روبوت","انترنت","متصفح","جوجل","يوتيوب","تطبيق",
"هاتف","بطارية","شاحن","كاميرا","ميكروفون","هارد","رام",

"سيارة","طائرة","قطار","سفينة","دراجة","محرك","سرعة",
"طريق","اشارة","وقود","فرامل","مقود",

"مدرسة","جامعة","مدرس","طالب","واجب","امتحان","قلم",
"كراسة","كتاب","مكتبة","فصل","سبورة",

"قهوة","شاي","عصير","بيتزا","برجر","مكرونة","شوربة",
"سلطة","شوكولاتة","بسكويت","فطار","غداء","عشاء",

"كرة","ملعب","هدف","حارس","مدافع","مهاجم","بطولة",
"كأس","مباراة","جمهور","مدرب",

"مطر","شمس","رياح","سحاب","صيف","شتاء","خريف","ربيع",
"بحر","نهر","جبل","صحراء",

"قطة","كلب","حصان","اسد","نمر","فيل","زرافة",
"قرد","ذئب","دب",

"شرطة","طبيب","مهندس","طيار","نجار","حداد","خباز",
"مزارع","جندي",

"موسيقى","اغنية","فيلم","مسلسل","مسرح","تمثيل",
"مخرج","ممثل","تصوير",

"نجاح","فشل","حلم","امل","قوة","صبر","ذكاء","شجاعة"

]
# ==============================
# WEBHOOK
# ==============================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print("Webhook Crash:", e)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    try:
        user_message = event.message.text.strip().lower()
        user_id = event.source.user_id

        # 🚫 Anti-Spam
        now = time.time()
        if user_id in last_message:
            if now - last_message[user_id] < 1:
                return
        last_message[user_id] = now

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # ⚡ Cached username
            if user_id in user_cache:
                username = user_cache[user_id]
            else:
                try:
                    if event.source.type == "group":
                        profile = line_bot_api.get_group_member_profile(
                            event.source.group_id, user_id
                        )
                    else:
                        profile = line_bot_api.get_profile(user_id)

                    username = profile.display_name
                    user_cache[user_id] = username
                except:
                    username = "Player 😄"

            reply = None

            # ==============================
            # MENU
            # ==============================

            if user_message in ["العاب","menu","help"]:
                reply = """
🔥 اوامر البوت 🔥

🎮 العاب:
لعبة ارقام
سوال
مين الاسرع
حجر / ورقة / مقص

💰 اقتصاد:
نقاطي
توب
راتب
لف
سرقة

🧠 أدوات:
احسب 5+5
ترجم hello

🗣️ قول كلام
"""

            # ==============================
            # SAY
            # ==============================

            elif user_message.startswith("قول "):
                text = event.message.text[4:]

                if "@all" in text.lower():
                    reply = "😈 مش هلعب اللعبة دي"
                else:
                    reply = text

            # ==============================
            # CALCULATOR
            # ==============================

            elif user_message.startswith("احسب"):
                try:
                    equation = event.message.text.replace("احسب","").strip()

                    allowed="0123456789+-*/(). "
                    if not all(c in allowed for c in equation):
                        reply="❌ عملية غير مسموحة"
                    else:
                        result=eval(equation)
                        reply=f"🧮 الناتج = {result}"

                except:
                    reply="اكتب كده:\nاحسب 5+5"

            # ==============================
            # TRANSLATE
            # ==============================

            elif user_message.startswith("ترجم"):
                try:
                    text=event.message.text.replace("ترجم","").strip()
                    translated=GoogleTranslator(source='auto', target='ar').translate(text)

                    reply=f"🌍 الترجمة:\n{translated}"

                except:
                    reply="اكتب:\nترجم hello"

            # ==============================
            # SMART REPLIES
            # ==============================

            elif user_message in smart_replies:
                reply = smart_replies[user_message]

            # ==============================
            # GUESS NUMBER
            # ==============================

            global number_to_guess

            if user_message == "لعبة ارقام":
                number_to_guess = random.randint(1,10)
                reply="🎯 خمنت رقم من 1 لـ10"

            elif user_message.isdigit() and number_to_guess:
                if int(user_message)==number_to_guess:
                    add_point(user_id)
                    reply=f"🔥 مبروك {username} +1 نقطة"
                    number_to_guess=None
                else:
                    reply="❌ غلط"

            # ==============================
            # QUESTION
            # ==============================

            global current_answer

            if user_message=="سوال":
                q=random.choice(questions)
                current_answer=q["a"].lower()
                reply=q["q"]

            elif current_answer and user_message==current_answer:
                add_point(user_id)
                reply=f"🔥 صح يا {username}"
                current_answer=None

            # ==============================
            # FAST WORD
            # ==============================

            global current_word

            if user_message=="مين الاسرع":
                current_word=random.choice(fast_words)
                scrambled = ''.join(random.sample(current_word.replace(" ",""), len(current_word.replace(" ",""))))
                reply=f"⚡ رتب الكلمة:\n{scrambled}"

            elif current_word and user_message==current_word:
                add_point(user_id)
                reply=f"🚀 {username} كسب!"
                current_word=None

            # ==============================
            # ROCK PAPER SCISSORS
            # ==============================

            if user_message in ["حجر","ورقة","مقص"]:
                choices=["حجر","ورقة","مقص"]
                bot=random.choice(choices)

                if user_message==bot:
                    reply=f"🤝 تعادل! اخترت {bot}"

                elif (
                    (user_message=="حجر" and bot=="مقص") or
                    (user_message=="ورقة" and bot=="حجر") or
                    (user_message=="مقص" and bot=="ورقة")
                ):
                    add_point(user_id)
                    reply=f"🔥 كسبت! اخترت {bot}"

                else:
                    reply=f"😈 خسرت! اخترت {bot}"

            # ==============================
            # ECONOMY
            # ==============================

            elif user_message=="نقاطي":
                reply=f"🏆 معاك {points.get(user_id,0)} نقطة"

            elif user_message=="توب":

                if not points:
                    reply="لسه محدش لعب 😄"
                else:
                    top=sorted(points.items(),key=lambda x:x[1],reverse=True)[:10]

                    text="🥇 التوب:\n"
                    for i,(uid,score) in enumerate(top,start=1):
                        name=user_cache.get(uid,"Player")
                        text+=f"{i}- {name} ({score})\n"

                    reply=text

            elif user_message=="راتب":

                if user_id in daily_salary and now-daily_salary[user_id]<86400:
                    reply="⏳ تعالا بكرة 😄"
                else:
                    salary=random.randint(5,15)
                    add_point(user_id,salary)
                    daily_salary[user_id]=now
                    reply=f"💰 قبضت {salary} نقطة!"

            elif user_message=="لف":

                prizes=[-3,-1,1,2,5,10]
                prize=random.choice(prizes)
                add_point(user_id,prize)

                if prize>0:
                    reply=f"🎰 كسبت {prize} نقاط!"
                else:
                    reply=f"💀 خسرت {abs(prize)}"

            elif user_message=="سرقة":

                success=random.choice([True,False])

                if success:
                    amount=random.randint(1,5)
                    add_point(user_id,amount)
                    reply=f"😈 سرقت {amount} نقاط!"
                else:
                    add_point(user_id,-2)
                    reply="🚔 اتمسكت! -2 نقاط"

            # ==============================
            # SAFE REPLY
            # ==============================

            if reply:
                try:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                except Exception as e:
                    print("Reply Error:",e)

    except Exception as e:
        print("🔥 BOT CRASH:",e)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"