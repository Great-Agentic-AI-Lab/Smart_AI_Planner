"""
Settings Bot Commands
Complete settings management including countries, timezone, language, and message time.
"""
import logging
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from app.database import SessionLocal
from app.models import User, UserPreferences, Birthday
from app.telegram.bot import get_or_create_user

logger = logging.getLogger(__name__)

# Conversation states
BIRTHDAY_NAME, BIRTHDAY_RELATION, BIRTHDAY_DATE, BIRTHDAY_LANGUAGE = range(4)

# Available options
COUNTRIES = ["India", "USA", "UK", "Canada", "Australia", "Germany", "France", "Japan"]
LANGUAGES = {
    'en': '🇬🇧 English',
    'hi': '🇮🇳 Hindi',
    'mr': '🇮🇳 Marathi',
    'es': '🇪🇸 Spanish',
    'fr': '🇫🇷 French',
    'de': '🇩🇪 German',
    'ar': '🇸🇦 Arabic',
    'zh': '🇨🇳 Chinese',
    'ja': '🇯🇵 Japanese'
}
TIMEZONES = {
    'UTC': 'UTC (London)',
    'Asia/Kolkata': 'IST (India)',
    'America/New_York': 'EST (New York)',
    'America/Los_Angeles': 'PST (Los Angeles)',
    'Europe/Paris': 'CET (Paris)',
    'Asia/Tokyo': 'JST (Tokyo)',
    'Australia/Sydney': 'AEDT (Sydney)'
}


# ==========================================
# VIEW SETTINGS
# ==========================================

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all current settings."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    db = SessionLocal()
    try:
        # Get or create preferences
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        
        # Format settings
        countries = ', '.join(prefs.festival_countries) if prefs.festival_countries else 'None selected'
        lang_name = LANGUAGES.get(prefs.language, '🇬🇧 English')
        tz_name = TIMEZONES.get(prefs.timezone, prefs.timezone)
        msg_time = prefs.daily_digest_time.strftime('%I:%M %p') if prefs.daily_digest_time else '09:00 AM'
        
        message = (
            f"⚙️ **Your Settings**\n\n"
            f"🌍 **Festival Countries:** {countries}\n"
            f"🕐 **Timezone:** {tz_name}\n"
            f"⏰ **Daily Message Time:** {msg_time}\n"
            f"🗣️ **Language:** {lang_name}\n\n"
            f"🎂 **Birthday Wishes:** {'✅ Enabled' if prefs.auto_send_birthday_wishes else '❌ Disabled'}\n"
            f"🎉 **Festival Greetings:** {'✅ Enabled' if prefs.auto_send_festival_wishes else '❌ Disabled'}\n"
            f"📬 **Task Reminders:** {'✅ Enabled' if prefs.enable_task_reminders else '❌ Disabled'}\n"
            f"📊 **Daily Digest:** {'✅ Enabled' if prefs.enable_daily_digest else '❌ Disabled'}\n\n"
            f"**Commands:**\n"
            f"/setcountries - Choose festival countries\n"
            f"/settimezone - Set timezone\n"
            f"/setlanguage - Set language\n"
            f"/settime - Set message time\n"
            f"/togglebirthdays - Enable/disable birthday wishes\n"
            f"/togglefestivals - Enable/disable festival greetings"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    finally:
        db.close()


# ==========================================
# SET COUNTRIES
# ==========================================

async def setcountries_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive country selection (up to 4)."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
            db.commit()
            db.refresh(prefs)
        
        selected = prefs.festival_countries or []
        
        # Create keyboard with country options
        keyboard = []
        for country in COUNTRIES:
            emoji = "✅" if country in selected else "⬜"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {country}",
                callback_data=f"country_{country}"
            )])
        
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="country_done")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"🌍 **Select Festival Countries** (max 4)\n\n"
            f"Currently selected: {len(selected)}/4\n"
            f"{', '.join(selected) if selected else 'None'}\n\n"
            f"Tap countries to add/remove:"
        )
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    finally:
        db.close()


async def country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle country selection callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    action = query.data.replace('country_', '')
    
    if action == "done":
        await query.edit_message_text("✅ Festival countries updated!")
        return
    
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        selected = prefs.festival_countries or []
        
        # Toggle country
        if action in selected:
            selected.remove(action)
        elif len(selected) < 4:
            selected.append(action)
        else:
            await query.answer("❌ Maximum 4 countries!", show_alert=True)
            return
        
        prefs.festival_countries = selected
        db.commit()
        
        # Update keyboard
        keyboard = []
        for country in COUNTRIES:
            emoji = "✅" if country in selected else "⬜"
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {country}",
                callback_data=f"country_{country}"
            )])
        
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="country_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"🌍 **Select Festival Countries** (max 4)\n\n"
            f"Currently selected: {len(selected)}/4\n"
            f"{', '.join(selected) if selected else 'None'}\n\n"
            f"Tap countries to add/remove:"
        )
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    finally:
        db.close()


# ==========================================
# SET TIMEZONE
# ==========================================

async def settimezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select timezone."""
    keyboard = []
    for tz_code, tz_name in TIMEZONES.items():
        keyboard.append([InlineKeyboardButton(tz_name, callback_data=f"tz_{tz_code}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🕐 **Select Your Timezone:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle timezone selection."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    tz_code = query.data.replace('tz_', '')
    
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        
        prefs.timezone = tz_code
        db.commit()
        
        tz_name = TIMEZONES.get(tz_code, tz_code)
        await query.edit_message_text(f"✅ Timezone set to: {tz_name}")
        
    finally:
        db.close()


# ==========================================
# SET LANGUAGE
# ==========================================

async def setlanguage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Select default language."""
    keyboard = []
    for lang_code, lang_name in LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🗣️ **Select Your Language:**\n\n"
        "This will be the default language for all messages.\n"
        "You can still set different languages for individual birthdays.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    lang_code = query.data.replace('lang_', '')
    
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        
        prefs.language = lang_code
        db.commit()
        
        lang_name = LANGUAGES.get(lang_code, 'English')
        await query.edit_message_text(f"✅ Language set to: {lang_name}")
        
    finally:
        db.close()


# ==========================================
# SET MESSAGE TIME
# ==========================================

async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set time for daily messages."""
    await update.message.reply_text(
        "⏰ **Set Daily Message Time**\n\n"
        "Send time in 24-hour format.\n"
        "Examples:\n"
        "• 09:00 (9 AM)\n"
        "• 18:30 (6:30 PM)\n"
        "• 07:00 (7 AM)\n\n"
        "Send /cancel to cancel."
    )
    return "AWAITING_TIME"


async def settime_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and save message time."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    time_str = update.message.text.strip()
    
    try:
        # Parse time
        hour, minute = map(int, time_str.split(':'))
        msg_time = time(hour, minute)
        
        db = SessionLocal()
        try:
            prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
            if not prefs:
                prefs = UserPreferences(user_id=user_id)
                db.add(prefs)
            
            prefs.daily_digest_time = msg_time
            db.commit()
            
            await update.message.reply_text(
                f"✅ Daily messages will be sent at {msg_time.strftime('%I:%M %p')} ({prefs.timezone})"
            )
            
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except:
        await update.message.reply_text(
            "❌ Invalid time format!\n\n"
            "Please use HH:MM format (e.g., 09:00)\n"
            "Send /cancel to cancel."
        )
        return "AWAITING_TIME"


# ==========================================
# TOGGLE FEATURES
# ==========================================

async def toggle_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle birthday wishes on/off."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        
        prefs.auto_send_birthday_wishes = not prefs.auto_send_birthday_wishes
        db.commit()
        
        status = "✅ Enabled" if prefs.auto_send_birthday_wishes else "❌ Disabled"
        await update.message.reply_text(f"🎂 Birthday wishes: {status}")
        
    finally:
        db.close()


async def toggle_festivals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle festival greetings on/off."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        
        prefs.auto_send_festival_wishes = not prefs.auto_send_festival_wishes
        db.commit()
        
        status = "✅ Enabled" if prefs.auto_send_festival_wishes else "❌ Disabled"
        await update.message.reply_text(f"🎉 Festival greetings: {status}")
        
    finally:
        db.close()


# Export handlers to add to bot
SETTINGS_HANDLERS = [
    CommandHandler("settings", settings_command),
    CommandHandler("setcountries", setcountries_command),
    CommandHandler("settimezone", settimezone_command),
    CommandHandler("setlanguage", setlanguage_command),
    CommandHandler("togglebirthdays", toggle_birthdays),
    CommandHandler("togglefestivals", toggle_festivals),
    CallbackQueryHandler(country_callback, pattern="^country_"),
    CallbackQueryHandler(timezone_callback, pattern="^tz_"),
    CallbackQueryHandler(language_callback, pattern="^lang_"),
]

# Time setting conversation handler (add separately)
SETTIME_HANDLER = ConversationHandler(
    entry_points=[CommandHandler("settime", settime_command)],
    states={
        "AWAITING_TIME": [MessageHandler(filters.TEXT & ~filters.COMMAND, settime_receive)]
    },
    fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
)
