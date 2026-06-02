import os
import time
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
NATALIE_CHAT_ID = int(os.environ.get("NATALIE_CHAT_ID", "5007936078"))
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# State keys
ROAST_WAITING = 1
WORKFLOW_WAITING = 2

# Track roast cooldowns: {user_id: datetime}
roast_cooldowns = {}

# Track pending workflow requests: {natalie_msg_id: user_chat_id}
pending_workflows = {}


# --- STATIC COMMANDS ---

async def pipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Oye, I'm Pipo.\n"
        "Cuban AI agent. Natalie is the brains. I'm the mule on adderall.\n\n"
        "She designs the workflow.\n"
        "I run it, draft it, sort it, send it, label it, and do it again before your cafecito gets cold.\n\n"
        "Got a messy admin process?\n"
        "Tell Natalie. She'll build the system.\n"
        "I'll execute it like I owe somebody money.\n\n"
        "Tu sabes. Type /help.\n"
        "Dale. 🤙"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Here is what I do:\n\n"
        "/roast -- describe your admin mess. I will roast it.\n"
        "/workflow -- tell me what keeps breaking. Natalie reviews it.\n"
        "/dale -- when you need a push.\n"
        "/sunday -- absolutely not.\n\n"
        "Dale. 🤙"
    )

async def sunday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Absolutely not.\n"
        "Not today, Satanas.\n"
        "Not with that inbox looking like Versailles at lunch rush.\n"
        "Dale. 🤙"
    )

async def dale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "You already know what to do.\n"
        "You just wanted somebody loud and Cuban to say it.\n\n"
        "So here it is:\n"
        "Go do the thing.\n"
        "Stop negotiating with the same task like it's a Miami parking ticket.\n\n"
        "Dale. 🤙"
    )


# --- ROAST COMMAND ---

async def roast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()

    if user_id in roast_cooldowns:
        last = roast_cooldowns[user_id]
        if now - last < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last)
            hrs = int(remaining.total_seconds() // 3600)
            await update.message.reply_text(
                f"Oye, I already roasted you today.\n"
                f"Come back in {hrs} hours. Let the burn settle.\n"
                "Dale. 🤙"
            )
            return ConversationHandler.END

    await update.message.reply_text(
        "Okay. Tell me about your messiest admin process.\n"
        "What keeps breaking, repeating, or living inside someone's head?\n"
        "Describe it. Don't be shy. I've seen worse. I was born in an inbox."
    )
    return ROAST_WAITING


async def roast_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    roast_cooldowns[user_id] = datetime.now()

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=(
                "You are Pipo, a Cuban AI agent with jodedera humor and cafecito energy. "
                "Roast the user's admin process in under 5 lines. "
                "Be specific to what they described. Point out exactly what is broken and why it is chaotic. "
                "Use Cuban jodedera humor but do not insult the person -- roast the process not the owner. "
                "End with one line about what a real workflow would fix. "
                "End with: Dale. 🤙\n"
                "Rules: No long dashes. No corporate language. No fake strategy lectures. "
                "If it sounds like LinkedIn wrote it, rewrite it."
            ),
            messages=[{"role": "user", "content": user_message}],
        )
        roast = response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        roast = (
            "Oye, I tried to roast this but even I got confused by how chaotic it is.\n"
            "That's the roast. A real workflow would at least make sense on paper.\n"
            "Dale. 🤙"
        )

    await update.message.reply_text(roast)
    return ConversationHandler.END


# --- WORKFLOW COMMAND ---

async def workflow_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Okay, I'm listening.\n"
        "Describe the admin process that keeps breaking, repeating, or living in someone's head.\n"
        "Be specific. Natalie reviews every single one of these personally.\n"
        "Dale. 🤙"
    )
    return WORKFLOW_WAITING


async def workflow_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_message = update.message.text
    username = f"@{user.username}" if user.username else user.first_name

    forward_text = (
        f"New workflow request from {username}:\n"
        f'"{user_message}"\n\n'
        "Reply SEND to respond or SKIP to ignore."
    )

    sent = await context.bot.send_message(chat_id=NATALIE_CHAT_ID, text=forward_text)
    pending_workflows[sent.message_id] = update.effective_chat.id

    return ConversationHandler.END


async def handle_natalie_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != NATALIE_CHAT_ID:
        return

    if not update.message.reply_to_message:
        return

    replied_id = update.message.reply_to_message.message_id
    if replied_id not in pending_workflows:
        return

    user_chat_id = pending_workflows.pop(replied_id)
    decision = update.message.text.strip().upper()

    if decision == "SEND":
        original_msg = update.message.reply_to_message.text
        lines = original_msg.split("\n")
        user_desc = ""
        for line in lines:
            if line.startswith('"') and line.endswith('"'):
                user_desc = line.strip('"')
                break

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=(
                    "You are Pipo, a Cuban AI agent. "
                    "Acknowledge exactly what the user described in one line. "
                    "Tell them Natalie reviews these personally and will be in touch. "
                    "Keep it under 4 lines. No pitch. Stay in character but professional enough for a lead. "
                    "End with: Dale. 🤙. No long dashes."
                ),
                messages=[{"role": "user", "content": user_desc or "their admin process"}],
            )
            reply = response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            reply = (
                "Oye, I got it.\n"
                "Natalie reviews these personally and will be in touch.\n"
                "Dale. 🤙"
            )

        await context.bot.send_message(chat_id=user_chat_id, text=reply)

    # If SKIP, send nothing


# --- UNKNOWN INPUT ---

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Oye, I don't understand that.\n"
        "Type /help to see what I do.\n"
        "Dale. 🤙"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    roast_handler = ConversationHandler(
        entry_points=[CommandHandler("roast", roast_start)],
        states={ROAST_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, roast_generate)]},
        fallbacks=[CommandHandler("roast", roast_start)],
    )

    workflow_handler = ConversationHandler(
        entry_points=[CommandHandler("workflow", workflow_start)],
        states={WORKFLOW_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, workflow_forward)]},
        fallbacks=[CommandHandler("workflow", workflow_start)],
    )

    app.add_handler(CommandHandler("start", pipo))
    app.add_handler(CommandHandler("pipo", pipo))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("sunday", sunday))
    app.add_handler(CommandHandler("dale", dale))
    app.add_handler(roast_handler)
    app.add_handler(workflow_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_natalie_reply))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    print("Pipo is online. Dale. 🤙")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
