from flask import Flask, request, abort
import random
import json
import os

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = "QPrjs2oE0WkxeQqXZKUy8eDjfK4kY2iD3bg3iDaE09doEdXp9+C1203rzMyz+UWHDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3Z+GfADLEe2xv89bBYFqRg6ritVwXIPLFQBnWrM/7ITMAdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "7768432715f1e544354aa28f3b68ac0e"

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# -------------------
# Load Points
# -------------------

if os.path.exists("points.json"):
    with open("points.json", "r") as f:
        points = json.load(f)
else:
    points = {}

def save_points():
    with open("points.json", "w") as f:
        json.dump(points, f)

def add_point(user_id):
    if user_id not in points:
        points[user_id] = 0
    points[user_id] += 1
    save_points()


# -------------------
# Games Data
# -------------------

number_to_guess = None
current_answer = None
current_word = None

questions = [
    {"q": "مين غنى تملي معاك؟", "a": "عمرو دياب"},
    {"q": "عاصمة فرنسا ايه؟", "a": "باريس"},
    {"q": "أكبر كوكب في المجموعة الشمسية؟", "a": "المشتري"},
]

fast_words = ["كمبيوتر", "موبايل", "برمجة", "بوت", "تكنولوجيا"]


# -------------------
# Webhook
# -------------------

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
    global number_to_guess
    global current_answer
    global current_word

    user_message = event.message.text.strip().lower()
    user_id = event.source.user_id

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        profile = line_bot_api.get_profile(user_id)
        username = profile.display_name

        reply = None

        # 🎯 خمن الرقم
        if user_message == "لعبة رقم":
            number_to_guess = random.randint(1, 10)
            reply = "🎯 خمنت رقم من 1 لـ10... اكتب الرقم!"

        elif user_message.isdigit() and number_to_guess:
            if int(user_message) == number_to_guess:
                add_point(user_id)
                reply = f"🔥 مبروك {username}!\nكسبت نقطة 👑"
                number_to_guess = None
            else:
                reply = "❌ غلط.. حاول تاني"

        # 🧠 سؤال بدون اختيارات
        elif user_message == "سؤال":
            q = random.choice(questions)
            current_answer = q["a"].lower()
            reply = f"🧠 سؤال سريع!\n\n{q['q']}"

        elif current_answer and user_message == current_answer:
            add_point(user_id)
            reply = f"🔥 إجابة صحيحة يا {username}!\n+1 نقطة 👑"
            current_answer = None

        # ⚡ مين الأسرع
        elif user_message == "مين الأسرع":
            current_word = random.choice(fast_words)
            scrambled = ''.join(random.sample(current_word, len(current_word)))
            reply = f"⚡ رتب الكلمة دي بسرعة:\n{scrambled}"

        elif current_word and user_message == current_word:
            add_point(user_id)
            reply = f"🚀 انت الأسرع يا {username}!\n+1 نقطة 👑"
            current_word = None

        # 😈 اختيار عضو
        elif user_message == "اختار":
            reply = f"😈 البوت اختار: {username}\nقولنا سر عنك 😂"

        # 🏆 عرض النقاط
        elif user_message == "نقاطي":
            score = points.get(user_id, 0)
            reply = f"🏆 يا {username} عندك {score} نقطة!"

        # 🥇 التوب
        elif user_message == "توب":
            if not points:
                reply = "لسه محدش لعب 😅"
            else:
                top_users = sorted(points.items(), key=lambda x: x[1], reverse=True)[:10]

                text = "🏆 توب 10 لاعيبة:\n\n"

                for i, (uid, score) in enumerate(top_users, start=1):
                    try:
                        p = line_bot_api.get_profile(uid)
                        name = p.display_name
                    except:
                        name = "Unknown"

                    text += f"{i}- {name} ({score})\n"

                reply = text
                
        # 📜 عرض الأوامر
        elif user_message in ["اوامر", "help", "menu"]:
            reply = """
🎮 ════ اوامر العاب البوت ════ 🎮

🎯 لعبة رقم
البوت يخمن رقم من 1 لـ10 وانت تحاول تعرفه.

🧠 سؤال
البوت يسألك سؤال واللي يجاوب الأول يكسب.

⚡ مين الأسرع
يرمي كلمة ملخبطة وأسرع واحد يرتبها ياخد نقطة.

😈 اختار
البوت يختار عضو عشوائي للهزار 😂

🏆 نقاطي
تعرف معاك كام نقطة.

🥇 توب
تشوف أقوى لاعيبة في الجروب.

🔥 اكتب الأمر زي ما هو بدون رموز!
"""

        if reply:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


if __name__ == "__main__":
    app.run()