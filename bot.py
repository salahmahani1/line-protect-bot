from flask import Flask, request, abort
import os, json, random, time, threading

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("63T0fX0zrA89Mnwv2V4zhRJq2uvKwU5rUwaQNVAa/DYdqW1bYE3/cNXjM7i4skZSDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3Y96eQqxuceWPUlHWJCw8IdOP0IAWX0FlzD4uDQTL0W7wdB04t89/1O/w1cDnyilFU=")
CHANNEL_SECRET = os.getenv("b64fb5dc359d81c85cf875c1e617663f")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ================= LOAD DATA =================

def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

questions_data = load_json("questions.json")
words_data = load_json("words.json")
race_data = load_json("race.json")
tf_data = load_json("truefalse.json")


# ================= QUEUE SYSTEM =================

def create_queue(data):
    q = data.copy()
    random.shuffle(q)
    return q

questions_queue = create_queue(questions_data)
words_queue = create_queue(words_data)
race_queue = create_queue(race_data)
tf_queue = create_queue(tf_data)

# ================= STORAGE =================

points = {}

def add_point(user, amount=1):
    points[user] = points.get(user, 0) + amount

# ================= PERFORMANCE =================

user_cache = {}
last_message = {}

# ================= GAME STATE =================

current_answer = None
current_word = None
race_text = None
tf_answer = None
round_active = False


# ================= FAST WORD =================

def scramble(word):
    mixed = word
    while mixed == word:
        mixed = ''.join(random.sample(word, len(word)))
    return mixed


def next_word():
    global words_queue

    if not words_queue:
        words_queue = create_queue(words_data)

    return words_queue.pop()


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


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    global current_answer, current_word, race_text, tf_answer, round_active

    try:
        msg = event.message.text.strip().lower()
        user_id = event.source.user_id

        # 🚫 Anti Spam
        now = time.time()
        if user_id in last_message:
            if now - last_message[user_id] < 1:
                return
        last_message[user_id] = now

        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)

            username = user_cache.get(user_id, "Player")
            user_cache[user_id] = username

            reply = None

            # ================= MENU =================

            if msg in ["العاب","menu"]:
                reply = """
🔥 GAME BOT 🔥

🧠 سؤال
⚡ مين الأسرع
🏁 سباق
✔️ صح ولا غلط
🏆 نقاطي
🥇 توب
"""

            # ================= QUESTIONS =================

            elif msg == "سؤال":

                global questions_queue

                if not questions_queue:
                    questions_queue = create_queue(questions_data)

                q = questions_queue.pop()

                current_answer = q["a"].lower()

                reply = f"🧠 {q['q']}"

            elif current_answer and current_answer in msg:

                add_point(user_id,2)
                reply = "🔥 إجابة صحيحة!"

                current_answer = None


            # ================= FAST GAME =================

            elif msg == "مين الأسرع":

                word = next_word()
                current_word = word
                round_active = True

                scrambled = scramble(word)

                reply = f"⚡ رتب الكلمة:\n🔥 {scrambled}"

            elif round_active and msg == current_word:

                add_point(user_id,2)

                reply = "🚀 أسرع واحد!"

                current_word = None
                round_active = False


            # ================= RACE =================

            elif msg == "سباق":

                global race_queue

                if not race_queue:
                    race_queue = create_queue(race_data)

                race_text = race_queue.pop().lower()

                reply = f"🏁 اكتب:\n{race_text}"

            elif race_text and msg == race_text:

                add_point(user_id,2)
                reply = "🔥 فاز بالسباق!"

                race_text = None


            # ================= TRUE FALSE =================

            elif msg == "صح ولا غلط":

                global tf_queue

                if not tf_queue:
                    tf_queue = create_queue(tf_data)

                q = tf_queue.pop()

                tf_answer = q["a"].lower()

                reply = f"🧠 {q['q']}"

            elif tf_answer and msg == tf_answer:

                add_point(user_id,2)
                reply = "✔️ صح!"

                tf_answer = None


            # ================= POINTS =================

            elif msg == "نقاطي":
                reply = f"🏆 معاك {points.get(user_id,0)} نقطة"

            elif msg == "توب":

                if points:
                    top = sorted(points.items(),
                                 key=lambda x:x[1],
                                 reverse=True)[:10]

                    text="🥇 التوب:\n"

                    for i,(u,s) in enumerate(top,start=1):
                        text+=f"{i}- {user_cache.get(u,'Player')} ({s})\n"

                    reply=text


            # ================= SAFE REPLY =================

            if reply:
                api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply)]
                    )
                )

    except Exception as e:
        print("BOT ERROR:", e)


@app.route("/", methods=["GET"])
def home():
    return "BOT RUNNING 🔥"