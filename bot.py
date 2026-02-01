from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import *

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = "4L0G8N8l1VWWYIMyOjeHwUgE33s7PK8Ew8rqrZV+UvfhNktNyEZsOvGWJ/CgHfOjWF6pqE6hKCdT9K0cVDZAr8rACRgMorBes/H5hqoV4oVzTPi4U0n3J+iea8t3/SlbpbL0ydIvyHstckOxy7DROwdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "7bbf30cb8c46fc2cd23711c9ab8155c7"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

###################################
# 👑 الاونرز
###################################
owners = {"U55fb450e06025fe8a329ed942e65de04"}

###################################
# 🛡️ الادمنز
###################################
admins = set()

###################################
# 🚫 المحظورين
###################################
banned = set()

###################################
# 📊 نظام المراقبة
###################################
monitor_mode = False
attendance = set()


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    handler.handle(body, signature)
    return 'OK'


###################################
# 🔥 الاوامر
###################################

@handler.add(MessageEvent, message=TextMessage)
def commands(event):

    global monitor_mode

    user_id = event.source.user_id
    text = event.message.text.lower()
    group_id = getattr(event.source, "group_id", None)

    if not group_id:
        return


    ###################################
    # ✅ فحص البوت
    ###################################
    if text in ["ping", "alive", "status"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🔥 البوت شغال 100%")
        )
        return


    ###################################
    # منع @all
    ###################################
    if "@all" in text and user_id not in admins and user_id not in owners:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("🚫 ممنوع استخدام @all")
        )
        return


    ###################################
    # رفع ادمن
    ###################################
    if text.startswith("رفع ادمن") and user_id in owners:

        if event.message.mention:
            for m in event.message.mention.mentionees:
                admins.add(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم رفع ادمن")
        )
        return


    ###################################
    # تنزيل ادمن
    ###################################
    if text.startswith("تنزيل ادمن") and user_id in owners:

        if event.message.mention:
            for m in event.message.mention.mentionees:
                admins.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("❌ تم تنزيل الادمن")
        )
        return


    ###################################
    # رفع اونر
    ###################################
    if text.startswith("رفع اونر") and user_id in owners:

        if event.message.mention:
            for m in event.message.mention.mentionees:
                owners.add(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("👑 تم رفع Owner")
        )
        return


    ###################################
    # طرد
    ###################################
    if text.startswith("طرد") and (user_id in owners or user_id in admins):

        if event.message.mention:
            for m in event.message.mention.mentionees:

                if m.user_id in owners:
                    continue

                line_bot_api.kickout_from_group(group_id, [m.user_id])

        return


    ###################################
    # حظر
    ###################################
    if text.startswith("حظر") and (user_id in owners or user_id in admins):

        if event.message.mention:
            for m in event.message.mention.mentionees:

                banned.add(m.user_id)

                line_bot_api.kickout_from_group(group_id, [m.user_id])

        return


    ###################################
    # فك الحظر
    ###################################
    if text.startswith("فك حظر") and user_id in owners:

        if event.message.mention:
            for m in event.message.mention.mentionees:
                banned.discard(m.user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage("✅ تم فك الحظر")
        )
        return


    ###################################
    # 🔥 تشغيل المراقبة
    ###################################
    if text == "تشغيل المراقبة" and user_id in owners:

        monitor_mode = True
        attendance.clear()

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                "🔥 تم تشغيل المراقبة!\n\n"
                "اكتب (تم) علشان تسجل حضورك 😈"
            )
        )
        return


    ###################################
    # 🔥 ايقاف المراقبة
    ###################################
    if text == "ايقاف المراقبة" and user_id in owners:

        monitor_mode = False

        if attendance:
            report = "📊 الحاضرين:\n\n" + "\n".join(attendance)
        else:
            report = "محدش سجل حضور 😅"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(report)
        )
        return


    ###################################
    # تسجيل الحضور
    ###################################
    if monitor_mode and text == "تم":

        profile = line_bot_api.get_profile(user_id)
        attendance.add(profile.display_name)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(f"✅ {profile.display_name} حاضر!")
        )
        return


###################################
# 🚫 منع دخول المحظورين
###################################

@handler.add(MemberJoinedEvent)
def anti_banned(event):

    group_id = event.source.group_id

    for member in event.joined.members:

        if member.user_id in banned:
            try:
                line_bot_api.kickout_from_group(group_id, [member.user_id])
            except:
                pass


###################################
# 🔒 قفل QR
###################################

@handler.add(JoinEvent)
def lock_qr(event):

    try:
        line_bot_api.update_group(
            group_id=event.source.group_id,
            prevent_join_by_ticket=True
        )
    except:
        pass


if __name__ == "__main__":
    app.run(port=5000)
