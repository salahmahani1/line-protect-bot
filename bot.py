from flask import Flask, request, abort
import random
import json
import os
import time

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
# Storage
# -------------------

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

# -------------------
# Performance Systems
# -------------------

user_cache = {}
last_message = {}

# -------------------
# Games Data
# -------------------

number_to_guess = None
current_answer = None
current_word = None

questions = [
    {"q": "مين غنى تملي معاك؟", "a": "عمرو دياب"},
    {"q": "عاصمة فرنسا؟", "a": "باريس"},
]

fast_words = ["كمبيوتر", "موبايل", "بوت", "برمجة"]

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
    except Exception as e:
        print("Webhook Crash:", e)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    try:
        user_message = event.message.text.strip().lower()
        user_id = event.source.user_id

        # 🚫 Anti Spam
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
                            event.source.group_id,
                            user_id
                        )
                    else:
                        profile = line_bot_api.get_profile(user_id)

                    username = profile.display_name
                    user_cache[user_id] = username

                except:
                    username = "Player 😄"

            reply = None

            # -------------------
            # MENU
            # -------------------

            if user_message in ["اوامر", "menu", "help"]:
                reply = """
🎮 اوامر البوت 🎮

🎯 لعبة رقم
🧠 سؤال
⚡ مين الأسرع
✂️ حجر / ورقة / مقص
🏆 نقاطي
🥇 توب
"""

            # -------------------
            # Guess Number
            # -------------------

            global number_to_guess

            if user_message == "لعبة رقم":
                number_to_guess = random.randint(1, 10)
                reply = "🎯 خمنت رقم من 1 لـ10!"

            elif user_message.isdigit() and number_to_guess:
                if int(user_message) == number_to_guess:
                    add_point(user_id)
                    reply = f"🔥 مبروك {username} +1 نقطة"
                    number_to_guess = None
                else:
                    reply = "❌ غلط"

            # -------------------
            # Question
            # -------------------

            global current_answer

            if user_message == "سؤال":
                q = random.choice(questions)
                current_answer = q["a"].lower()
                reply = q["q"]

            elif current_answer and user_message == current_answer:
                add_point(user_id)
                reply = f"🔥 صح يا {username}"
                current_answer = None

            # -------------------
            # Fast Word
            # -------------------

            global current_word

            if user_message == "مين الأسرع":
                current_word = random.choice(fast_words)
                scrambled = ''.join(random.sample(current_word, len(current_word)))
                reply = f"⚡ رتب الكلمة:\n{scrambled}"

            elif current_word and user_message == current_word:
                add_point(user_id)
                reply = f"🚀 {username} كسب!"
                current_word = None

            # -------------------
            # Rock Paper Scissors
            # -------------------

            if user_message in ["حجر", "ورقة", "مقص"]:

                choices = ["حجر", "ورقة", "مقص"]
                bot_choice = random.choice(choices)

                if user_message == bot_choice:
                    reply = f"🤝 تعادل! اخترت {bot_choice}"

                elif (
                    (user_message == "حجر" and bot_choice == "مقص") or
                    (user_message == "ورقة" and bot_choice == "حجر") or
                    (user_message == "مقص" and bot_choice == "ورقة")
                ):
                    add_point(user_id)
                    reply = f"🔥 كسبت! اخترت {bot_choice}"

                else:
                    reply = f"😈 خسرت! اخترت {bot_choice}"

            # -------------------
            # Points
            # -------------------

            if user_message == "نقاطي":
                score = points.get(user_id, 0)
                reply = f"🏆 معاك {score} نقطة"

            if user_message == "توب":

                if not points:
                    reply = "لسه محدش لعب 😄"

                else:
                    top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:10]

                    text = "🥇 التوب:\n"

                    for i, (uid, score) in enumerate(top, start=1):
                        name = user_cache.get(uid, "Player")
                        text += f"{i}- {name} ({score})\n"

                    reply = text

            # -------------------
            # Safe Reply
            # -------------------

            if reply:
                try:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply)]
                        )
                    )
                except Exception as e:
                    print("Reply Error:", e)

    except Exception as e:
        print("🔥 BOT CRASH:", e)


@app.route("/", methods=["GET"])
def home():
    return "Bot is running!"