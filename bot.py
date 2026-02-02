from flask import Flask, request, abort
import random

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = "4L0G8N8l1VWWYIMyOjeHwUgE33s7PK8Ew8rqrZV+UvfhNktNyEZsOvGWJ/CgHfOjWF6pqE6hKCdT9K0cVDZAr8rACRgMorBes/H5hqoV4oVzTPi4U0n3J+iea8t3/SlbpbL0ydIvyHstckOxy7DROwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "7bbf30cb8c46fc2cd23711c9ab8155c7"

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# -------------------
# Game Data
# -------------------

number_to_guess = None

questions = [
    {"q": "مين غنى تملي معاك؟\n1️⃣ تامر حسني\n2️⃣ عمرو دياب\n3️⃣ حماقي", "a": "2"},
    {"q": "عاصمة فرنسا ايه؟\n1️⃣ روما\n2️⃣ باريس\n3️⃣ مدريد", "a": "2"},
]

fast_words = ["كمبيوتر", "موبايل", "بوت", "برمجة", "ذكاء"]

current_question = None
current_answer = None

current_word = None


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
    global current_question, current_answer
    global current_word

    user_message = event.message.text.strip()

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        reply = None

        # 🎯 خمن الرقم
        if user_message == "لعبة رقم":
            number_to_guess = random.randint(1, 10)
            reply = "🎯 خمنت رقم من 1 لـ10... اكتب الرقم!"

        elif user_message.isdigit() and number_to_guess:
            if int(user_message) == number_to_guess:
                reply = f"🔥 مبروك! الرقم كان {number_to_guess}"
                number_to_guess = None
            else:
                reply = "❌ غلط.. حاول تاني"

        # 🧠 سؤال سريع
        elif user_message == "سؤال":
            q = random.choice(questions)
            current_question = q["q"]
            current_answer = q["a"]
            reply = "🧠 سؤال سريع!\n\n" + current_question

        elif current_answer and user_message == current_answer:
            reply = "🔥 إجابة صحيحة! انت جامد 😏"
            current_answer = None

        # ⚡ مين الأسرع
        elif user_message == "مين الأسرع":
            current_word = random.choice(fast_words)
            scrambled = ''.join(random.sample(current_word, len(current_word)))
            reply = f"⚡ رتب الكلمة دي بسرعة:\n{scrambled}"

        elif current_word and user_message == current_word:
            reply = "🚀 انت الأسرع! كسبت التحدي"
            current_word = None

        # 😈 اختيار عضو
        elif user_message == "اختار":
            if event.source.type == "group":
                user_id = event.source.user_id

                profile = line_bot_api.get_profile(user_id)

                reply = f"😈 البوت اختار: {profile.display_name}\nقولنا سر عنك 😆"
            else:
                reply = "اللعبة دي للجروبات بس 😁"

        if reply:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


if __name__ == "__main__":
    app.run()