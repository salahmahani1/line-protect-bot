from flask import Flask, request, abort
import json, random, time

from linebot.v3.messaging import (
    MessagingApi, Configuration, ApiClient,
    ReplyMessageRequest, TextMessage
)

from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError


# =====================================
# 🔴 حط التوكن هنا فقط
# =====================================

CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"

# =====================================

app = Flask(__name__)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


# ================= LOAD FILES =================

def load_json(file):
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

questions_data = load_json("questions.json")
words_data = load_json("words.json")
race_data = load_json("race.json")
tf_data = load_json("truefalse.json")


# ================= QUEUE SYSTEM =================
# يمنع التكرار

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
last_message = {}

current_answer = None
current_word = None
race_text = None
tf_answer = None


# ================= HELPERS =================

def scramble(word):
    mixed = word
    while mixed == word:
        mixed = ''.join(random.sample(word, len(word)))
    return mixed


def anti_spam(user_id):
    now = time.time()

    if user_id in last_message:
        if now - last_message[user_id] < 1:
            return True

    last_message[user_id] = now
    return False


def add_points(user, amount=1):
    points[user] = points.get(user, 0) + amount


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
    msg = event.message.text.strip().lower()

    if anti_spam(user_id):
        return

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        reply = None

        # ================= MENU =================

        if msg in ["اوامر","menu","help"]:
            reply = """
🔥 GAME BOT 🔥

🧠 سؤال
⚡ مين الأسرع
🏁 سباق
✔️ صح ولا غلط
🏆 نقاطي
🥇 توب

اكتب اسم اللعبة بس 😄
"""

        # ================= QUESTIONS =================

        elif msg == "سؤال":

            if not questions_queue:
                questions_queue = create_queue(questions_data)

            q = questions_queue.pop()
            current_answer = q["a"].lower()

            reply = f"🧠 {q['q']}"

        elif current_answer and current_answer in msg:

            add_points(user_id, 2)
            reply = "🔥 إجابة صحيحة +2 نقاط"

            current_answer = None


        # ================= FAST WORD =================

        elif msg == "مين الأسرع":

            if not words_queue:
                words_queue = create_queue(words_data)

            word = words_queue.pop()
            current_word = word

            reply = f"⚡ رتب الكلمة:\n🔥 {scramble(word)}"

        elif current_word and msg == current_word:

            add_points(user_id, 2)
            reply = "🚀 أسرع لاعب +2 نقاط"

            current_word = None


        # ================= RACE =================

        elif msg == "سباق":

            if not race_queue:
                race_queue = create_queue(race_data)

            race_text = race_queue.pop().lower()

            reply = f"🏁 اكتب بسرعة:\n{race_text}"

        elif race_text and msg == race_text:

            add_points(user_id, 2)
            reply = "🔥 فاز بالسباق +2 نقاط"

            race_text = None


        # ================= TRUE / FALSE =================

        elif msg == "صح ولا غلط":

            if not tf_queue:
                tf_queue = create_queue(tf_data)

            q = tf_queue.pop()
            tf_answer = q["a"].lower()

            reply = f"🧠 {q['q']}"

        elif tf_answer and msg == tf_answer:

            add_points(user_id, 2)
            reply = "✔️ إجابة صح +2 نقاط"

            tf_answer = None


        # ================= POINTS =================

        elif msg == "نقاطي":
            reply = f"🏆 معاك {points.get(user_id,0)} نقطة"


        elif msg == "توب":

            if not points:
                reply = "لسه محدش لعب 😄"
            else:

                top = sorted(points.items(),
                             key=lambda x: x[1],
                             reverse=True)[:10]

                text = "🥇 أقوى اللاعبين:\n"

                for i,(u,s) in enumerate(top, start=1):
                    text += f"{i}- لاعب ({s})\n"

                reply = text


        # ================= SEND =================

        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


@app.route("/", methods=["GET"])
def home():
    return "BOT IS RUNNING 🔥"