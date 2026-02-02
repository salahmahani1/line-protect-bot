from flask import Flask, request, abort
import json, random, time, os, re
from difflib import SequenceMatcher

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError


# 🔥 حط التوكن هنا فقط
CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"


app = Flask(__name__)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= LOAD =================

def load_json(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

questions = load_json("questions.json")
words = load_json("words.json")
race_data = load_json("race.json")
tf_data = load_json("truefalse.json")

# ================= QUEUE =================

def create_queue(data):
    temp = data.copy()
    random.shuffle(temp)
    return temp

questions_queue = create_queue(questions)
words_queue = create_queue(words)
race_queue = create_queue(race_data)
tf_queue = create_queue(tf_data)

# ================= STORAGE =================

points = {}
last_message = {}

current_answer = None
current_word = None
race_text = None
tf_answer = None

# ================= SMART FUNCTIONS =================

def normalize(text):
    text = text.lower().strip()

    # حذف "ال"
    if text.startswith("ال"):
        text = text[2:]

    # حذف التشكيل
    text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)

    # تحويل الحروف
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")

    # حذف الرموز
    text = re.sub(r'[^\w\s]', '', text)

    # حذف المسافات
    text = text.replace(" ", "")

    return text


# 🔥 ذكاء يقبل الأخطاء البسيطة
def is_correct(user, answer):

    user = normalize(user)
    answer = normalize(answer)

    similarity = SequenceMatcher(None, user, answer).ratio()

    return similarity > 0.80   # نسبة الذكاء


# ================= HELPERS =================

def get_user_name(api, user_id):
    try:
        profile = api.get_profile(user_id)
        return profile.display_name
    except:
        return "لاعب 😄"


def anti_spam(user_id):
    now = time.time()

    if user_id in last_message:
        if now - last_message[user_id] < 1:
            return True

    last_message[user_id] = now
    return False


def add_points(user, amount):
    points[user] = points.get(user, 0) + amount


def scramble(word):
    mixed = word
    while mixed == word:
        mixed = ''.join(random.sample(word, len(word)))
    return mixed


# ================= WEBHOOK =================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ================= BOT =================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    global current_answer, current_word, race_text, tf_answer
    global questions_queue, words_queue, race_queue, tf_queue

    user_id = event.source.user_id
    msg = event.message.text.strip()

    if anti_spam(user_id):
        return

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        reply = None

        # ========= MENU =========

        if msg in ["menu", "العاب", "help"]:
            reply = """
🎮 ألعاب البوت:

🧠 سؤال
✏️ رتب
⚡ سباق
✅ صح غلط
🏆 توب

اكتب اسم اللعبة 😈
"""

        # ========= سؤال =========

        elif msg == "سؤال":

            if not questions_queue:
                questions_queue = create_queue(questions)

            q = questions_queue.pop()

            current_answer = q["a"]

            reply = f"🧠 {q['q']}"

        elif current_answer and is_correct(msg, current_answer):

            name = get_user_name(api, user_id)

            add_points(user_id, 2)

            reply = f"🔥 {name} جاوب صح وكسب 2 نقطة!"

            current_answer = None


        # ========= رتب =========

        elif msg == "رتب":

            if not words_queue:
                words_queue = create_queue(words)

            current_word = words_queue.pop()

            reply = f"✏️ رتب الكلمة:\n{scramble(current_word)}"

        elif current_word and is_correct(msg, current_word):

            name = get_user_name(api, user_id)

            add_points(user_id, 2)

            reply = f"🔥 {name} رتبها صح!"

            current_word = None


        # ========= سباق =========

        elif msg == "سباق":

            if not race_queue:
                race_queue = create_queue(race_data)

            race_text = race_queue.pop()

            reply = f"⚡ اكتب بسرعة:\n{race_text}"

        elif race_text and is_correct(msg, race_text):

            name = get_user_name(api, user_id)

            add_points(user_id, 3)

            reply = f"🏎️ {name} كسب السباق!"

            race_text = None


        # ========= صح غلط =========

        elif msg == "صح غلط":

            if not tf_queue:
                tf_queue = create_queue(tf_data)

            q = tf_queue.pop()

            tf_answer = q["a"]

            reply = f"✅ صح أم غلط:\n{q['q']}"

        elif tf_answer and is_correct(msg, tf_answer):

            name = get_user_name(api, user_id)

            add_points(user_id, 1)

            reply = f"👏 {name} جاوب صح!"

            tf_answer = None


        # ========= التوب =========

        elif msg == "توب":

            if not points:
                reply = "لسه محدش لعب 😄"

            else:
                top = sorted(points.items(), key=lambda x: x[1], reverse=True)[:10]

                text = "🏆 أقوى اللاعبين:\n\n"

                for i, (uid, score) in enumerate(top, start=1):
                    name = get_user_name(api, uid)
                    text += f"{i}- {name} ({score}) نقطة\n"

                reply = text


        # ========= SEND =========

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


# ================= SERVER =================

@app.route("/", methods=["GET"])
def home():
    return "BOT IS RUNNING 🔥"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)