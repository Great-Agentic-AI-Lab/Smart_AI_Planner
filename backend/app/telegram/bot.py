"""
Telegram Bot - COMPLETE VERSION
Includes: Tasks, Edit, Complete, Postpone, Settings, Birthdays, All Features
"""

import logging
import re
from datetime import datetime, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from app.config import settings
from app.database import SessionLocal
from app.models import Task, User, UserPreferences, Birthday, TaskStatusEnum, PriorityEnum
from app.agents import get_task_planner
from app.vectordb.task_hooks import on_task_created, on_task_completed, on_task_deleted

logger = logging.getLogger(__name__)
bot_application: Application = None

# Conversation states
TASK_TITLE, TASK_DESCRIPTION, TASK_DUE_DATE = range(3)
EDIT_CHOICE, EDIT_TITLE, EDIT_DESCRIPTION, EDIT_DUE_DATE = range(3, 7)
BIRTHDAY_NAME, BIRTHDAY_RELATION, BIRTHDAY_DATE, BIRTHDAY_LANGUAGE = range(7, 11)
AWAITING_TIME = 11

# Constants
COUNTRIES = ["India", "USA", "UK", "Canada", "Australia", "Germany", "France", "Japan"]
LANGUAGES = {
    'en': ' English', 'hi': ' Hindi', 'mr': ' Marathi',
    'es': ' Spanish', 'fr': ' French', 'de': ' German',
    'ar': ' Arabic', 'zh': ' Chinese', 'ja': ' Japanese'
}
TIMEZONES = {
    'UTC': 'UTC (London)', 'Asia/Kolkata': 'IST (India)',
    'America/New_York': 'EST (New York)', 'America/Los_Angeles': 'PST (Los Angeles)',
    'Europe/Paris': 'CET (Paris)', 'Asia/Tokyo': 'JST (Tokyo)',
    'Australia/Sydney': 'AEDT (Sydney)'
}


def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None) -> int:
    """Get or create user and return user_id."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name, last_active=datetime.utcnow())
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user: {telegram_id}")
        else:
            user.last_active = datetime.utcnow()
            if username: user.username = username
            if first_name: user.first_name = first_name
            db.commit()
            db.refresh(user)
        return user.id
    finally:
        db.close()


def parse_due_date(text: str):
    """Parse natural language due dates."""
    text = text.lower().strip()
    now = datetime.utcnow()
    if "tomorrow" in text: return now + timedelta(days=1)
    if "today" in text: return now
    match = re.search(r'in (\d+) days?', text)
    if match: return now + timedelta(days=int(match.group(1)))
    if "next week" in text: return now + timedelta(weeks=1)
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try: return datetime.strptime(text, fmt)
        except: continue
    return None


def check_duplicate_task(user_id: int, title: str):
    """Check if similar task exists."""
    db = SessionLocal()
    try:
        return db.query(Task).filter(Task.user_id == user_id, Task.title.ilike(f"%{title}%"), Task.status == TaskStatusEnum.PENDING).first()
    finally:
        db.close()


# START & HELP
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)
    message = (
        f" Welcome {user.first_name} to Smart Personal Planner!\n\n"
        " AI-Powered Task Management\n\n"
        " **Tasks:**\n/addtask /listtasks /edittask /complete /postpone /deletetask\n\n"
        " **Celebrations:**\n/addbirthday /listbirthdays\n\n"
        " **Settings:**\n/settings /setcountries /setlanguage /settimezone\n\n"
        " **AI:**\n/suggest\n\n"
        "Say: 'Add task: Buy groceries tomorrow'"
    )
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        " **All Commands**\n\n"
        "**Tasks:** /addtask /listtasks /edittask /complete /postpone /deletetask /suggest\n"
        "**Birthdays:** /addbirthday /listbirthdays /deletebirthday\n"
        "**Settings:** /settings /setcountries /setlanguage /settimezone /settime\n"
        "**Toggles:** /togglebirthdays /togglefestivals"
    )
    await update.message.reply_text(message, parse_mode='Markdown')


# TASK CREATION
async def addtask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(" What's the task?")
    return TASK_TITLE


async def addtask_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_title'] = update.message.text
    await update.message.reply_text("Description? (or /skip)")
    return TASK_DESCRIPTION


async def addtask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "/skip":
        context.user_data['task_description'] = update.message.text
    await update.message.reply_text(" Due date? (tomorrow, 2026-02-20, in 3 days, or /skip)")
    return TASK_DUE_DATE


async def addtask_due_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    due_date = None
    if update.message.text != "/skip":
        due_date = parse_due_date(update.message.text)
    
    title = context.user_data.get('task_title')
    description = context.user_data.get('task_description')
    
    duplicate = check_duplicate_task(user_id, title)
    if duplicate:
        await update.message.reply_text(f" Similar task exists: #{duplicate.id} {duplicate.title}\n\nCreating anyway...")
    
    analyzing_msg = await update.message.reply_text(" Analyzing with AI...")
    
    db = SessionLocal()
    try:
        task = Task(user_id=user_id, title=title, description=description, due_date=due_date, status=TaskStatusEnum.PENDING)
        db.add(task)
        db.commit()
        db.refresh(task)
        
        try:
            agent = get_task_planner()
            result = await agent.execute(title=title, description=description, due_date=due_date)
            if result['success']:
                task.priority = PriorityEnum[result['priority'].upper()]
                task.priority_score = result['priority_score']
                task.estimated_effort_minutes = result['estimated_effort_minutes']
                db.commit()
                db.refresh(task)
                
                #  NEW: Store embedding in Pinecone
                try:
                    await on_task_created(task)
                except Exception as e:
                    logger.warning(f" Embedding storage failed: {e}")
                
                await analyzing_msg.delete()
                priority_emoji = {'high': '', 'medium': '🟡', 'low': '🟢'}
                await update.message.reply_text(
                    f" Task Created!\n\n {title}\n{priority_emoji.get(result['priority'], '')} Priority: {result['priority'].upper()}\n"
                    f" Score: {result['priority_score']}/100\n Est: {result['estimated_effort_minutes']}min\n"
                    f" Due: {due_date.strftime('%d %b %Y') if due_date else 'No deadline'}\n\n {result['reasoning']}"
                )
            else:
                await analyzing_msg.delete()
                await update.message.reply_text(f" Task created: {title}\n AI failed.")
        except Exception as e:
            logger.error(f"AI error: {e}")
            await analyzing_msg.delete()
            await update.message.reply_text(f" Task created: {title}\n AI unavailable.")
    finally:
        db.close()
    
    context.user_data.clear()
    return ConversationHandler.END


async def addtask_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(" Cancelled.")
    return ConversationHandler.END


# TASK OPERATIONS
async def listtasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.user_id == user_id, Task.status == TaskStatusEnum.PENDING).order_by(Task.priority_score.desc()).limit(20).all()
        if not tasks:
            await update.message.reply_text(" No pending tasks!")
            return
        message = " **Your Tasks**\n\n"
        priority_emoji = {PriorityEnum.HIGH: '', PriorityEnum.MEDIUM: '🟡', PriorityEnum.LOW: '🟢'}
        for task in tasks:
            emoji = priority_emoji.get(task.priority, '')
            due_text = f"Due: {task.due_date.strftime('%d %b')}" if task.due_date else "No deadline"
            message += f"{emoji} #{task.id} {task.title}\n   {task.priority.value.upper()} ({task.priority_score}) | {due_text}\n\n"
        await update.message.reply_text(message + " /edittask /complete /postpone /deletetask", parse_mode='Markdown')
    finally:
        db.close()


async def complete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text(" Usage: /complete <ID>")
            return
    except:
        await update.message.reply_text(" Invalid ID")
        return
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f" Task #{task_id} not found")
            return
        task.status = TaskStatusEnum.COMPLETED
        task.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(task)
        
        #  NEW: Update embedding with completion info
        try:
            await on_task_completed(task)
        except Exception as e:
            logger.warning(f" Embedding update failed: {e}")
        
        await update.message.reply_text(f" Completed: {task.title}\n\n Great job!")
    finally:
        db.close()


async def postpone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text(" Usage: /postpone <ID>")
            return
    except:
        await update.message.reply_text(" Invalid ID")
        return
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f" Task #{task_id} not found")
            return
        if not task.due_date:
            task.due_date = datetime.utcnow() + timedelta(days=1)
        else:
            task.due_date = task.due_date + timedelta(days=1)
        task.postponed_count += 1
        db.commit()
        await update.message.reply_text(f" Postponed: {task.title}\n\nNew due: {task.due_date.strftime('%d %b %Y')}\nPostponed {task.postponed_count} time(s)")
    finally:
        db.close()


async def deletetask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text(" Usage: /deletetask <ID>")
            return
    except:
        await update.message.reply_text(" Invalid ID")
        return
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f" Task #{task_id} not found")
            return
        title = task.title
        task_id_to_delete = task.id
        db.delete(task)
        db.commit()
        
        # NEW: Delete embedding from Pinecone
        try:
            await on_task_deleted(task_id_to_delete)
        except Exception as e:
            logger.warning(f" Embedding deletion failed: {e}")
        
        await update.message.reply_text(f" Deleted: {title}")
    finally:
        db.close()


async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.user_id == user_id, Task.status == TaskStatusEnum.PENDING).order_by(Task.priority_score.desc()).first()
        if not task:
            await update.message.reply_text(" No pending tasks!")
            return
        priority_emoji = {PriorityEnum.HIGH: '', PriorityEnum.MEDIUM: '🟡', PriorityEnum.LOW: '🟢'}
        emoji = priority_emoji.get(task.priority, '')
        await update.message.reply_text(f" **AI Recommendation**\n\nWork on this next:\n\n{emoji} {task.title}\n\n {task.priority_score}/100 |  {task.estimated_effort_minutes or '?'}min\n\nReady? /complete {task.id} when done!", parse_mode='Markdown')
    finally:
        db.close()


# ==========================================
# SETTINGS
# ==========================================

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        countries = ', '.join(prefs.festival_countries) if prefs.festival_countries else 'None'
        lang = LANGUAGES.get(prefs.language, ' English')
        tz = TIMEZONES.get(prefs.timezone, prefs.timezone)
        msg_time = prefs.daily_digest_time.strftime('%I:%M %p') if prefs.daily_digest_time else '09:00 AM'
        message = (
            f" **Settings**\n\n Countries: {countries}\n Timezone: {tz}\n Message Time: {msg_time}\n Language: {lang}\n\n"
            f" Birthdays: {'' if prefs.auto_send_birthday_wishes else ''}\n"
            f" Festivals: {'' if prefs.auto_send_festival_wishes else ''}\n\n"
            f"/setcountries /settimezone /setlanguage /settime /togglebirthdays /togglefestivals"
        )
        await update.message.reply_text(message, parse_mode='Markdown')
    finally:
        db.close()


async def setcountries_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        keyboard = []
        for country in COUNTRIES:
            emoji = "" if country in selected else "⬜"
            keyboard.append([InlineKeyboardButton(f"{emoji} {country}", callback_data=f"country_{country}")])
        keyboard.append([InlineKeyboardButton(" Done", callback_data="country_done")])
        await update.message.reply_text(f" **Select Countries** (max 4)\n\nSelected: {len(selected)}/4\n{', '.join(selected) if selected else 'None'}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db.close()


async def country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    action = query.data.replace('country_', '')
    if action == "done":
        await query.edit_message_text(" Countries updated!")
        return
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        selected = prefs.festival_countries or []
        if action in selected:
            selected.remove(action)
        elif len(selected) < 4:
            selected.append(action)
        else:
            await query.answer(" Max 4 countries!", show_alert=True)
            return
        prefs.festival_countries = selected
        db.commit()
        keyboard = []
        for country in COUNTRIES:
            emoji = "" if country in selected else "⬜"
            keyboard.append([InlineKeyboardButton(f"{emoji} {country}", callback_data=f"country_{country}")])
        keyboard.append([InlineKeyboardButton(" Done", callback_data="country_done")])
        await query.edit_message_text(f" **Select Countries** (max 4)\n\nSelected: {len(selected)}/4\n{', '.join(selected) if selected else 'None'}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db.close()


async def settimezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=f"tz_{code}")] for code, name in TIMEZONES.items()]
    await update.message.reply_text(" **Select Timezone:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.edit_message_text(f" Timezone: {TIMEZONES.get(tz_code)}")
    finally:
        db.close()


async def setlanguage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=f"lang_{code}")] for code, name in LANGUAGES.items()]
    await update.message.reply_text(" **Select Language:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await query.edit_message_text(f" Language: {LANGUAGES.get(lang_code)}")
    finally:
        db.close()


async def toggle_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        prefs.auto_send_birthday_wishes = not prefs.auto_send_birthday_wishes
        db.commit()
        await update.message.reply_text(f" Birthday wishes: {' Enabled' if prefs.auto_send_birthday_wishes else ' Disabled'}")
    finally:
        db.close()


async def settime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " **Set Daily Message Time**\n\n"
        "Send time in 24-hour format.\n"
        "Examples: 09:00, 18:30, 07:00\n\n"
        "Send /cancel to cancel.",
        parse_mode='Markdown'
    )
    return AWAITING_TIME


async def settime_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    time_str = update.message.text.strip()
    try:
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
            await update.message.reply_text(f" Daily messages at {msg_time.strftime('%I:%M %p')}")
        finally:
            db.close()
        return ConversationHandler.END
    except:
        await update.message.reply_text(" Invalid! Use HH:MM (e.g., 09:00)")
        return AWAITING_TIME


async def toggle_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        prefs.auto_send_birthday_wishes = not prefs.auto_send_birthday_wishes
        db.commit()
        await update.message.reply_text(f" Birthday wishes: {' Enabled' if prefs.auto_send_birthday_wishes else ' Disabled'}")
    finally:
        db.close()


async def toggle_festivals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    db = SessionLocal()
    try:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.add(prefs)
        prefs.auto_send_festival_wishes = not prefs.auto_send_festival_wishes
        db.commit()
        await update.message.reply_text(f" Festival greetings: {' Enabled' if prefs.auto_send_festival_wishes else ' Disabled'}")
    finally:
        db.close()


# BIRTHDAYS
async def addbirthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(" **Add Birthday**\n\nWhat's the person's name?")
    return BIRTHDAY_NAME


async def addbirthday_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['birthday_name'] = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("‍‍‍ Family", callback_data="rel_family")],
        [InlineKeyboardButton(" Friend", callback_data="rel_friend")],
        [InlineKeyboardButton(" Colleague", callback_data="rel_colleague")],
        [InlineKeyboardButton(" Partner", callback_data="rel_partner")],
        [InlineKeyboardButton(" Custom", callback_data="rel_custom")]
    ]
    await update.message.reply_text(f"What's your relation with {context.user_data['birthday_name']}?", reply_markup=InlineKeyboardMarkup(keyboard))
    return BIRTHDAY_RELATION


async def addbirthday_relation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    relation = query.data.replace('rel_', '')
    if relation == "custom":
        await query.edit_message_text("Type the relation:")
        return BIRTHDAY_RELATION
    context.user_data['birthday_relation'] = relation
    await query.edit_message_text(f" Relation: {relation}\n\n Birthday? (DD-MM or DD/MM)")
    return BIRTHDAY_DATE


async def addbirthday_relation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['birthday_relation'] = update.message.text.strip()
    await update.message.reply_text(f" Relation: {context.user_data['birthday_relation']}\n\n Birthday? (DD-MM or DD/MM)")
    return BIRTHDAY_DATE


async def addbirthday_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    try:
        if '/' in date_str:
            day, month = map(int, date_str.split('/'))
        else:
            day, month = map(int, date_str.split('-'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        context.user_data['birthday_date'] = datetime(2000, month, day).date()
        keyboard = [[InlineKeyboardButton(name, callback_data=f"blang_{code}")] for code, name in LANGUAGES.items()]
        await update.message.reply_text(f" **Wish Language** for {context.user_data['birthday_name']}?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return BIRTHDAY_LANGUAGE
    except:
        await update.message.reply_text(" Invalid! Use DD-MM or DD/MM")
        return BIRTHDAY_DATE


async def addbirthday_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    lang_code = query.data.replace('blang_', '')
    db = SessionLocal()
    try:
        birthday = Birthday(
            user_id=user_id,
            person_name=context.user_data['birthday_name'],
            relation=context.user_data['birthday_relation'],
            birthday_date=context.user_data['birthday_date'],
            wish_language=lang_code
        )
        db.add(birthday)
        db.commit()
        await query.edit_message_text(f" **Birthday Added!**\n\n {birthday.person_name}\n {birthday.relation}\n {birthday.birthday_date.strftime('%B %d')}\n {LANGUAGES.get(lang_code)}", parse_mode='Markdown')
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Failed: {e}")
        await query.edit_message_text(" Failed to save")
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        db.close()


async def addbirthday_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(" Cancelled")
    return ConversationHandler.END


async def listbirthdays_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    db = SessionLocal()
    try:
        birthdays = db.query(Birthday).filter(Birthday.user_id == user_id).order_by(Birthday.birthday_date).all()
        if not birthdays:
            await update.message.reply_text(" No birthdays saved!\n\nUse /addbirthday")
            return
        upcoming = [b for b in birthdays if b.is_birthday_soon(30)]
        message = " **Birthdays**\n\n"
        if upcoming:
            message += "** Upcoming (30 days):**\n"
            for b in upcoming:
                message += f"• {b.person_name} ({b.relation}) - {b.birthday_date.strftime('%B %d')} - {b.days_until_birthday()} days -  {b.get_language_name()}\n\n"
        message += f"\n** All ({len(birthdays)}):**\n"
        for b in birthdays[:10]:
            message += f"• {b.person_name} ({b.relation}) - {b.birthday_date.strftime('%B %d')} -  {b.get_language_name()}\n"
        if len(birthdays) > 10:
            message += f"\n...and {len(birthdays)-10} more"
        await update.message.reply_text(message, parse_mode='Markdown')
    finally:
        db.close()


async def deletebirthday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    if not context.args:
        await update.message.reply_text(" Usage: /deletebirthday <name>")
        return
    name = ' '.join(context.args)
    db = SessionLocal()
    try:
        birthday = db.query(Birthday).filter(Birthday.user_id == user_id, Birthday.person_name.ilike(f"%{name}%")).first()
        if not birthday:
            await update.message.reply_text(f" Not found: {name}")
            return
        db.delete(birthday)
        db.commit()
        await update.message.reply_text(f" Deleted: {birthday.person_name}")
    finally:
        db.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.lower()
    if any(p in message for p in ['add task', 'create task', 'new task']):
        for trigger in ['add task:', 'create task:', 'new task:']:
            if trigger in message:
                context.user_data['task_title'] = message.split(trigger, 1)[1].strip()
                await update.message.reply_text(f" Creating: {context.user_data['task_title']}\n\nDescription? (or /skip)")
                return TASK_DESCRIPTION
    await update.message.reply_text("Try:\n/addtask /listtasks /suggest\nOr: 'Add task: <task name>'")



# BOT STARTUP
async def start_bot():
    global bot_application
    if not settings.telegram_bot_token:
        logger.warning(" No token")
        return
    try:
        bot_application = Application.builder().token(settings.telegram_bot_token).build()
        
        # Task conversation
        addtask_conv = ConversationHandler(
            entry_points=[CommandHandler("addtask", addtask_start)],
            states={
                TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_title)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_description), CommandHandler("skip", addtask_description)],
                TASK_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_due_date), CommandHandler("skip", addtask_due_date)],
            },
            fallbacks=[CommandHandler("cancel", addtask_cancel)]
        )
        
        # Birthday conversation
        addbirthday_conv = ConversationHandler(
            entry_points=[CommandHandler("addbirthday", addbirthday_start)],
            states={
                BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbirthday_name)],
                BIRTHDAY_RELATION: [CallbackQueryHandler(addbirthday_relation_callback, pattern="^rel_"), MessageHandler(filters.TEXT & ~filters.COMMAND, addbirthday_relation_text)],
                BIRTHDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addbirthday_date)],
                BIRTHDAY_LANGUAGE: [CallbackQueryHandler(addbirthday_language, pattern="^blang_")]
            },
            fallbacks=[CommandHandler("cancel", addbirthday_cancel)]
        )
        
        # Settime conversation
        settime_conv = ConversationHandler(
            entry_points=[CommandHandler("settime", settime_command)],
            states={
                AWAITING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, settime_receive)]
            },
            fallbacks=[CommandHandler("cancel", addtask_cancel)]
        )
        
        # Register all handlers
        bot_application.add_handler(addtask_conv)
        bot_application.add_handler(addbirthday_conv)
        bot_application.add_handler(settime_conv)
        bot_application.add_handler(CommandHandler("start", start_command))
        bot_application.add_handler(CommandHandler("help", help_command))
        bot_application.add_handler(CommandHandler("listtasks", listtasks_command))
        bot_application.add_handler(CommandHandler("suggest", suggest_command))
        bot_application.add_handler(CommandHandler("complete", complete_command))
        bot_application.add_handler(CommandHandler("postpone", postpone_command))
        bot_application.add_handler(CommandHandler("deletetask", deletetask_command))
        bot_application.add_handler(CommandHandler("settings", settings_command))
        bot_application.add_handler(CommandHandler("setcountries", setcountries_command))
        bot_application.add_handler(CommandHandler("settimezone", settimezone_command))
        bot_application.add_handler(CommandHandler("setlanguage", setlanguage_command))
        bot_application.add_handler(CommandHandler("togglebirthdays", toggle_birthdays))
        bot_application.add_handler(CommandHandler("togglefestivals", toggle_festivals))
        bot_application.add_handler(CommandHandler("listbirthdays", listbirthdays_command))
        bot_application.add_handler(CommandHandler("deletebirthday", deletebirthday_command))
        bot_application.add_handler(CallbackQueryHandler(country_callback, pattern="^country_"))
        bot_application.add_handler(CallbackQueryHandler(timezone_callback, pattern="^tz_"))
        bot_application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
        bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Starting bot...")
        await bot_application.initialize()
        await bot_application.start()
        await bot_application.updater.start_polling()
        logger.info(" Bot started!")
    except Exception as e:
        logger.error(f" Failed: {e}")
        raise


async def stop_bot():
    global bot_application
    if bot_application:
        try:
            if bot_application.updater and bot_application.updater.running:
                await bot_application.updater.stop()
            await bot_application.stop()
            await bot_application.shutdown()
            logger.info(" Bot stopped")
        except Exception as e:
            logger.error(f"Error: {e}")
