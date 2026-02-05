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


CHANNEL_ACCESS_TOKEN = "/oJXvxwxxAnMPLH2/6LnLbO+7zohIRl4DBIhAKUUUx+T0zPHQBjPapfdCyHiL4CZDnzgMvVWaGLD2QYQmUI3u8F2Q1+ODUjMODVN0RMrv3atalk/5BoeivWmPpiY/+tNBe7KhXMUx+Rts0Fz1J6NDwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "b64fb5dc359d81c85cf875c1e617663f"
OWNER_ID = "U9ecd575f8df0e62798f4c8ecc9738d5d"


app = Flask(__name__)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== FILES =====
def load_json(file, default):
    if os.path.exists(file):
        with open(file,"r",encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file,data):
    with open(file,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False)

questions = load_json("questions.json",[{"q":"عاصمة مصر؟","a":"القاهرة"}])
words = load_json("words.json",["تفاحة"])
tf = load_json("truefalse.json",[{"q":"النار باردة","a":"غلط"}])
race = load_json("race.json",["سبحان الله"])

points = load_json("points.json",{})
admins = load_json("admins.json",[OWNER_ID])
settings = load_json("settings.json",{"mention":[]})

active_games = {}
GAMES_ENABLED = True

tournament = {"state":"OFF","players":[],"scores":{}}

# ===== SMART NORMALIZE =====
def normalize(text):
    text=str(text).lower().strip()

    rep={
        "أ":"ا","إ":"ا","آ":"ا",
        "ة":"ه","ى":"ي",
        "ؤ":"و","ئ":"ي"
    }

    for k,v in rep.items():
        text=text.replace(k,v)

    text=re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
    text=re.sub(r'[^\w\s.]','',text)
    text=re.sub(r'(?<=\w)\s+(?=\w)','',text)

    if text.startswith("ال") and len(text)>4:
        text=text[2:]

    return text


def similar(a,b):
    return SequenceMatcher(None,a,b).ratio()>0.65


def is_admin(user):
    return user in admins

def is_owner(user):
    return user == OWNER_ID


# ===== SERVER =====
@app.route("/",methods=['GET'])
def home():
    return "BOT RUNNING 🔥"

@app.route("/callback",methods=['POST'])
def callback():
    signature=request.headers['X-Line-Signature']
    body=request.get_data(as_text=True)

    try:
        handler.handle(body,signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


# ===== BOT =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle(event):

    global GAMES_ENABLED, tournament

    user=event.source.user_id
    room=getattr(event.source,'group_id',user)

    msg=normalize(event.message.text)
    cmd=msg.lstrip(".")

    with ApiClient(configuration) as api_client:
        api=MessagingApi(api_client)

        reply=None


# ================= OWNER =================
        if is_owner(user):

            if similar(cmd,"رفعادمن") and event.message.mention:
                for m in event.message.mention.mentionees:
                    if m.user_id not in admins:
                        admins.append(m.user_id)
                save_json("admins.json",admins)
                reply="✅ تم رفع الأدمن"

            elif similar(cmd,"تنزيلادمن") and event.message.mention:
                for m in event.message.mention.mentionees:
                    if m.user_id in admins:
                        admins.remove(m.user_id)
                save_json("admins.json",admins)
                reply="❌ تم تنزيل الأدمن"


# ================= ADMINS =================
        if is_admin(user):

            if similar(cmd,"قفل"):
                GAMES_ENABLED=False
                reply="🔒 تم قفل الألعاب"

            elif similar(cmd,"فتح"):
                GAMES_ENABLED=True
                reply="🔓 تم فتح الألعاب"

            elif similar(cmd,"حذف"):
                if room in active_games:
                    del active_games[room]
                    reply="🏳️ تم حذف اللعبة"
                else:
                    reply="مفيش لعبة شغالة"

            elif similar(cmd,"تشغيلمنشن"):
                if room not in settings["mention"]:
                    settings["mention"].append(room)
                    save_json("settings.json",settings)
                reply="✅ تم تشغيل المنشن"

            elif similar(cmd,"ايقافمنشن"):
                if room in settings["mention"]:
                    settings["mention"].remove(room)
                    save_json("settings.json",settings)
                reply="❌ تم إيقاف المنشن"

            elif similar(cmd,"بطوله"):
                tournament={"state":"ON","players":[],"scores":{}}
                reply="🏆 تم فتح التسجيل — اكتب (سجل)"

            elif similar(cmd,"ابدأ") and tournament["state"]=="ON":
                if len(tournament["players"])<2:
                    reply="لازم لاعبين على الأقل"
                else:
                    tournament["state"]="PLAY"
                    q=random.choice(questions)
                    active_games[room]={"a":q["a"],"tour":True}
                    reply=f"🏆 سؤال البطولة:\n{q['q']}"


# ================= TOURNAMENT =================
        if tournament["state"]=="ON":

            if similar(cmd,"سجل"):
                if user not in tournament["players"]:
                    tournament["players"].append(user)
                    tournament["scores"][user]=0
                    reply="🔥 تم تسجيلك في البطولة"


# ================= GAMES =================
        elif GAMES_ENABLED:

            if room in active_games:

                ans=normalize(active_games[room]["a"])

                if similar(msg,ans):
                    points[user]=points.get(user,0)+2
                    save_json("points.json",points)

                    reply="✅ إجابة صحيحة!"
                    del active_games[room]

            else:

                if similar(cmd,"سوال"):
                    q=random.choice(questions)
                    active_games[room]={"a":q["a"]}
                    reply=f"🧠 {q['q']}"

                elif similar(cmd,"رتب"):
                    w=random.choice(words)
                    mix="".join(random.sample(w,len(w)))
                    active_games[room]={"a":w}
                    reply=f"✏️ رتب:\n{mix}"

                elif similar(cmd,"صح"):
                    t=random.choice(tf)
                    active_games[room]={"a":t["a"]}
                    reply=f"🤔 {t['q']}"

                elif similar(cmd,"سباق"):
                    s=random.choice(race)
                    active_games[room]={"a":s}
                    reply=f"🏎️ اكتب بسرعة:\n{s}"

                elif similar(cmd,"توب"):
                    top=sorted(points.items(), key=lambda x:x[1], reverse=True)[:5]

                    text="🏆 التوب:\n"
                    for i,(u,p) in enumerate(top):
                        try:
                            name=api.get_profile(u).display_name
                        except:
                            name="لاعب"

                        text+=f"{i+1}- {name} ({p})\n"

                    reply=text


# ================= MENTION =================
        if not reply and room in settings["mention"]:
            if event.message.mention:
                reply=random.choice(words)


# ================= SEND =================
        if reply:
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)