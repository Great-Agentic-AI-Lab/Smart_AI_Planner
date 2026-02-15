"""
Birthday Bot Commands
Add, list, and manage birthdays with per-person language preferences.
"""
import logging
from datetime import datetime
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
from app.models import Birthday
from app.telegram.bot import get_or_create_user

logger = logging.getLogger(__name__)

# Conversation states
BIRTHDAY_NAME, BIRTHDAY_RELATION, BIRTHDAY_DATE, BIRTHDAY_LANGUAGE = range(4)

# Language options (same as settings)
LANGUAGES = {
    'en': ' English',
    'hi': ' Hindi',
    'mr': ' Marathi',
    'es': ' Spanish',
    'fr': ' French',
    'de': ' German',
    'ar': ' Arabic',
    'zh': ' Chinese',
    'ja': ' Japanese'
}


# ADD BIRTHDAY
async def addbirthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start birthday addition flow."""
    await update.message.reply_text(
        " **Add Birthday**\n\n"
        "What's the person's name?\n\n"
        "Send /cancel to cancel."
    )
    return BIRTHDAY_NAME


async def addbirthday_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store name and ask for relation."""
    context.user_data['birthday_name'] = update.message.text.strip()
    
    # Relation options
    keyboard = [
        [InlineKeyboardButton("‍‍‍ Family", callback_data="rel_family")],
        [InlineKeyboardButton(" Friend", callback_data="rel_friend")],
        [InlineKeyboardButton(" Colleague", callback_data="rel_colleague")],
        [InlineKeyboardButton(" Partner", callback_data="rel_partner")],
        [InlineKeyboardButton(" Custom", callback_data="rel_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"What's your relation with {context.user_data['birthday_name']}?",
        reply_markup=reply_markup
    )
    return BIRTHDAY_RELATION


async def addbirthday_relation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle relation selection."""
    query = update.callback_query
    await query.answer()
    
    relation = query.data.replace('rel_', '')
    
    if relation == "custom":
        await query.edit_message_text("Please type the relation (e.g., cousin, teacher, neighbor):")
        return BIRTHDAY_RELATION
    
    context.user_data['birthday_relation'] = relation
    
    await query.edit_message_text(
        f" Relation: {relation.capitalize()}\n\n"
        f" When is {context.user_data['birthday_name']}'s birthday?\n\n"
        f"Format: DD-MM or DD/MM\n"
        f"Examples: 25-12, 15/08\n\n"
        f"Send /cancel to cancel."
    )
    return BIRTHDAY_DATE


async def addbirthday_relation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom relation text."""
    context.user_data['birthday_relation'] = update.message.text.strip()
    
    await update.message.reply_text(
        f" Relation: {context.user_data['birthday_relation']}\n\n"
        f" When is {context.user_data['birthday_name']}'s birthday?\n\n"
        f"Format: DD-MM or DD/MM\n"
        f"Examples: 25-12, 15/08\n\n"
        f"Send /cancel to cancel."
    )
    return BIRTHDAY_DATE


async def addbirthday_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store date and ask for language."""
    date_str = update.message.text.strip()
    
    # Parse date
    try:
        if '/' in date_str:
            day, month = map(int, date_str.split('/'))
        elif '-' in date_str:
            day, month = map(int, date_str.split('-'))
        else:
            raise ValueError("Invalid format")
        
        # Validate
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError("Invalid date")
        
        # Store as date (use current year as placeholder)
        birthday_date = datetime(2000, month, day).date()
        context.user_data['birthday_date'] = birthday_date
        
        # Ask for language
        keyboard = []
        for lang_code, lang_name in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"blang_{lang_code}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f" **Select Wish Language**\n\n"
            f"Which language should birthday wishes be in for {context.user_data['birthday_name']}?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return BIRTHDAY_LANGUAGE
        
    except Exception as e:
        await update.message.reply_text(
            " Invalid date format!\n\n"
            "Please use DD-MM or DD/MM\n"
            "Examples: 25-12, 15/08\n\n"
            "Send /cancel to cancel."
        )
        return BIRTHDAY_DATE


async def addbirthday_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save birthday with selected language."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    lang_code = query.data.replace('blang_', '')
    
    db = SessionLocal()
    try:
        # Create birthday
        birthday = Birthday(
            user_id=user_id,
            person_name=context.user_data['birthday_name'],
            relation=context.user_data['birthday_relation'],
            birthday_date=context.user_data['birthday_date'],
            wish_language=lang_code
        )
        db.add(birthday)
        db.commit()
        db.refresh(birthday)
        
        lang_name = LANGUAGES.get(lang_code, 'English')
        
        await query.edit_message_text(
            f" **Birthday Added!**\n\n"
            f" {birthday.person_name}\n"
            f" {birthday.relation.capitalize()}\n"
            f" {birthday.birthday_date.strftime('%B %d')}\n"
            f" Wishes in {lang_name}\n\n"
            f"You'll receive automatic wishes on their birthday! ",
            parse_mode='Markdown'
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Failed to add birthday: {e}")
        await query.edit_message_text(" Failed to save birthday. Please try again.")
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


async def addbirthday_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel birthday addition."""
    context.user_data.clear()
    await update.message.reply_text(" Birthday addition cancelled.")
    return ConversationHandler.END


# LIST BIRTHDAYS
async def listbirthdays_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all saved birthdays."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    db = SessionLocal()
    try:
        birthdays = db.query(Birthday).filter(Birthday.user_id == user_id).order_by(Birthday.birthday_date).all()
        
        if not birthdays:
            await update.message.reply_text(
                " No birthdays saved yet!\n\n"
                "Use /addbirthday to add one."
            )
            return
        
        # Group by upcoming
        upcoming = [b for b in birthdays if b.is_birthday_soon(30)]
        all_birthdays = birthdays
        
        message = " **Your Birthdays**\n\n"
        
        if upcoming:
            message += "** Upcoming (Next 30 Days):**\n"
            for b in upcoming:
                days = b.days_until_birthday()
                lang = b.get_language_name()
                message += (
                    f"• {b.person_name} ({b.relation})\n"
                    f"  {b.birthday_date.strftime('%B %d')} - {days} days away\n"
                    f"   {lang}\n\n"
                )
        
        message += f"\n** All Birthdays ({len(all_birthdays)}):**\n"
        for b in all_birthdays[:10]:  # Show first 10
            lang = b.get_language_name()
            message += f"• {b.person_name} ({b.relation}) - {b.birthday_date.strftime('%B %d')} -  {lang}\n"
        
        if len(all_birthdays) > 10:
            message += f"\n... and {len(all_birthdays) - 10} more"
        
        message += "\n\nUse /deletebirthday <name> to remove one."
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    finally:
        db.close()


# DELETE BIRTHDAY
async def deletebirthday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a birthday by name."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    if not context.args:
        await update.message.reply_text(
            " Please provide a name.\n\n"
            "Example: /deletebirthday John"
        )
        return
    
    name_to_delete = ' '.join(context.args)
    
    db = SessionLocal()
    try:
        birthday = db.query(Birthday).filter(
            Birthday.user_id == user_id,
            Birthday.person_name.ilike(f"%{name_to_delete}%")
        ).first()
        
        if not birthday:
            await update.message.reply_text(f" No birthday found for '{name_to_delete}'")
            return
        
        name = birthday.person_name
        db.delete(birthday)
        db.commit()
        
        await update.message.reply_text(f" Deleted birthday for {name}")
        
    finally:
        db.close()


# Export handlers
BIRTHDAY_CONV_HANDLER = ConversationHandler(
    entry_points=[CommandHandler("addbirthday", addbirthday_start)],
    states={
        BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbirthday_name)],
        BIRTHDAY_RELATION: [
            CallbackQueryHandler(addbirthday_relation_callback, pattern="^rel_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, addbirthday_relation_text)
        ],
        BIRTHDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbirthday_date)],
        BIRTHDAY_LANGUAGE: [CallbackQueryHandler(addbirthday_language, pattern="^blang_")]
    },
    fallbacks=[CommandHandler("cancel", addbirthday_cancel)]
)

BIRTHDAY_HANDLERS = [
    BIRTHDAY_CONV_HANDLER,
    CommandHandler("listbirthdays", listbirthdays_command),
    CommandHandler("deletebirthday", deletebirthday_command)
]
