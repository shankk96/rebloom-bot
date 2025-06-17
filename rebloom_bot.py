import logging
import os
import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters, CallbackQueryHandler,
                          ConversationHandler)
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_USERNAME = "@rebloom_available"
ADMIN_IDS = [84795049, 846376871]

PHOTO, DESCRIPTION, ADDRESS, PRICE, CONTACT, LOCATION = range(6)
EDIT_WAIT = 6

pending_applications = {}
editing_context = {}


def format_application(data):
    return (f"🌸 Новый букет #{data['id']}\n"
            f"Описание: {data['description']}\n"
            f"Адрес: {data['district']}\n"
            f"Цена: {data['price']} сум\n"
            f"Контакт: {data['contact']}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь фото букета 📸")
    return PHOTO


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("Опиши букет (состав, состояние):")
    return DESCRIPTION


async def description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Укажи адрес:")
    return ADDRESS


async def district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['district'] = update.message.text
    await update.message.reply_text("Укажи цену (в сумах):")
    return PRICE


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text
    await update.message.reply_text("Оставь контакт (номер или @username):")
    return CONTACT


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['contact'] = update.message.text
    keyboard = [[
        KeyboardButton("📍 Отправить геолокацию", request_location=True)
    ]]
    await update.message.reply_text(
        "📍 Нажми кнопку ниже, чтобы отправить местоположение (по желанию).",
        reply_markup=ReplyKeyboardMarkup(keyboard,
                                         one_time_keyboard=True,
                                         resize_keyboard=True))
    return LOCATION

    context.user_data['contact'] = update.message.text
    app_id = str(uuid.uuid4())[:8]
    context.user_data['id'] = app_id
    pending_applications[app_id] = context.user_data.copy()

    caption = format_application(context.user_data)
    keyboard = [[
        InlineKeyboardButton("✅ Опубликовать",
                             callback_data=f"approve:{app_id}"),
        InlineKeyboardButton("✏️ Редактировать",
                             callback_data=f"edit:{app_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{app_id}")
    ]]

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=context.user_data['photo'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logging.error(f"Ошибка при отправке админу: {e}")

    await update.message.reply_text("Спасибо! Заявка отправлена на модерацию.")
    return ConversationHandler.END


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, app_id = query.data.split(":")
    app = pending_applications.get(app_id)

    if not app:
        await query.edit_message_caption(caption="❌ Заявка не найдена.")
        return

    if action == "approve":
        caption = format_application(app)
        await context.bot.send_photo(chat_id=CHANNEL_USERNAME,
                                     photo=app['photo'],
                                     caption=caption)
        await query.edit_message_caption(
            caption="✅ Заявка опубликована в канале.")
    elif action == "reject":
        await query.edit_message_caption(caption="❌ Заявка отклонена.")
    elif action == "edit":
        editing_context[update.effective_user.id] = app_id
        await query.message.reply_text(
            """✏ Введите отредактированную заявку в формате:

Описание: ...
Адрес: ...
Цена: ...
Контакт: ...""")
        return EDIT_WAIT


async def handle_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    app_id = editing_context.get(user_id)
    if not app_id or app_id not in pending_applications:
        await update.message.reply_text("❌ Заявка не найдена.")
        return ConversationHandler.END

    app = pending_applications[app_id]
    text = update.message.text
    for line in text.strip().splitlines():
        if line.startswith("Описание:"):
            app['description'] = line.split("Описание:")[1].strip()
        elif line.startswith("Адрес:"):
            app['district'] = line.split("Адрес:")[1].strip()
        elif line.startswith("Цена:"):
            app['price'] = line.split("Цена:")[1].replace("сум", "").strip()
        elif line.startswith("Контакт:"):
            app['contact'] = line.split("Контакт:")[1].strip()

    caption = format_application(app)
    keyboard = [[
        InlineKeyboardButton("✅ Опубликовать",
                             callback_data=f"approve:{app_id}"),
        InlineKeyboardButton("✏️ Редактировать",
                             callback_data=f"edit:{app_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{app_id}")
    ]]
    await update.message.reply_photo(
        photo=app['photo'],
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END


async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        context.user_data['location'] = {
            'lat': update.message.location.latitude,
            'lon': update.message.location.longitude
        }
    else:
        context.user_data['location'] = None

    app_id = str(uuid.uuid4())[:8]
    context.user_data['id'] = app_id
    pending_applications[app_id] = context.user_data.copy()

    caption = format_application(context.user_data)
    keyboard = [[
        InlineKeyboardButton("✅ Опубликовать",
                             callback_data=f"approve:{app_id}"),
        InlineKeyboardButton("✏️ Редактировать",
                             callback_data=f"edit:{app_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{app_id}")
    ]]

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=context.user_data['photo'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard))
            if context.user_data['location']:
                await context.bot.send_location(
                    chat_id=admin_id,
                    latitude=context.user_data['location']['lat'],
                    longitude=context.user_data['location']['lon'])
        except Exception as e:
            logging.error(f"Ошибка при отправке админу: {e}")

    await update.message.reply_text("Спасибо! Заявка отправлена на модерацию.",
                                    reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Заявка отменена.")
    return ConversationHandler.END


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    form = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            DESCRIPTION:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, description)],
            ADDRESS:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, district)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, price)],
            CONTACT:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
            LOCATION: [MessageHandler(filters.LOCATION, location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_callback)],
        states={
            EDIT_WAIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               handle_edit_text)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(form)
    app.add_handler(edit)
    app.run_polling()


if __name__ == "__main__":
    main()
