"""
Telegram bot for task and event management.
COMPLETE VERSION: Create, Read, Update, Delete + AI Features
"""

import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from app.config import settings
from app.database import SessionLocal
from app.models import Task, User, TaskStatusEnum, PriorityEnum
from app.agents import get_task_planner

logger = logging.getLogger(__name__)
bot_application: Application = None

# Conversation states
TASK_TITLE, TASK_DESCRIPTION, TASK_DUE_DATE = range(3)
EDIT_CHOICE, EDIT_TITLE, EDIT_DESCRIPTION, EDIT_DUE_DATE = range(3, 7)


def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None) -> int:
    """Get or create user and return user_id."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_active=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user: {telegram_id}")
        else:
            user.last_active = datetime.utcnow()
            if username:
                user.username = username
            if first_name:
                user.first_name = first_name
            db.commit()
            db.refresh(user)
        
        user_id = user.id
        return user_id
    finally:
        db.close()


def parse_due_date(text: str) -> datetime | None:
    """Parse natural language due dates."""
    text = text.lower().strip()
    now = datetime.utcnow()

    if "tomorrow" in text:
        return now + timedelta(days=1)
    if "today" in text:
        return now
    match = re.search(r'in (\d+) days?', text)
    if match:
        return now + timedelta(days=int(match.group(1)))
    if "next week" in text:
        return now + timedelta(weeks=1)

    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def check_duplicate_task(user_id: int, title: str) -> Task | None:
    """Check if similar task exists."""
    db = SessionLocal()
    try:
        duplicate = db.query(Task).filter(
            Task.user_id == user_id,
            Task.title.ilike(f"%{title}%"),
            Task.status == TaskStatusEnum.PENDING
        ).first()
        return duplicate
    finally:
        db.close()


# ============================================
# CREATE TASK HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)
    message = (
        f"👋 Welcome {user.first_name} to Smart Personal Planner!\n\n"
        "🤖 AI-Powered Task Management\n\n"
        "📝 Create & Manage:\n"
        "/addtask - Add new task with AI priority\n"
        "/listtasks - View all tasks\n"
        "/edittask <ID> - Edit a task\n"
        "/complete <ID> - Mark as done\n"
        "/postpone <ID> - Push deadline +1 day\n"
        "/deletetask <ID> - Delete task\n\n"
        "🤖 AI Features:\n"
        "/suggest - Get AI recommendation\n\n"
        "💡 Natural language:\n"
        "\"Add task: Buy groceries tomorrow\""
    )
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide help."""
    message = (
        "📚 Smart Personal Planner - Commands\n\n"
        "➕ Create:\n"
        "/addtask - Interactive task creation\n\n"
        "📋 View:\n"
        "/listtasks - See all pending tasks\n\n"
        "✏️ Edit:\n"
        "/edittask <ID> - Modify task\n"
        "/complete <ID> - Mark done\n"
        "/postpone <ID> - Delay +1 day\n\n"
        "🗑️ Delete:\n"
        "/deletetask <ID> - Remove task\n\n"
        "🤖 AI:\n"
        "/suggest - Recommendation\n\n"
        "Examples:\n"
        "• Add task: Submit report Friday\n"
        "• /edittask 5\n"
        "• /complete 3"
    )
    await update.message.reply_text(message)


async def addtask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start task creation."""
    await update.message.reply_text("📝 What's the task?\n\nExample: Submit project report")
    return TASK_TITLE


async def addtask_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store task title."""
    context.user_data['task_title'] = update.message.text
    await update.message.reply_text("Any description or details?\n(Send /skip to skip)")
    return TASK_DESCRIPTION


async def addtask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store task description."""
    if update.message.text != "/skip":
        context.user_data['task_description'] = update.message.text
    await update.message.reply_text(
        "📅 When is it due?\n\n"
        "Examples: tomorrow, 2026-02-20, in 3 days, next week\n\n"
        "(Send /skip for no deadline)"
    )
    return TASK_DUE_DATE


async def addtask_due_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create task with AI prioritization."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    due_date = None
    if update.message.text != "/skip":
        due_date = parse_due_date(update.message.text)
        if not due_date:
            await update.message.reply_text("⚠️ Couldn't parse date. Using no deadline.")

    title = context.user_data.get('task_title')
    description = context.user_data.get('task_description')

    # Check duplicate
    duplicate = check_duplicate_task(user_id, title)
    if duplicate:
        await update.message.reply_text(
            f"⚠️ Similar task exists:\n"
            f"#{duplicate.id}: {duplicate.title}\n\n"
            f"Creating anyway..."
        )

    analyzing_msg = await update.message.reply_text("🤖 Creating task and analyzing with AI...")

    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            due_date=due_date,
            status=TaskStatusEnum.PENDING
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # AI prioritization
        try:
            agent = get_task_planner()
            result = await agent.execute(title=title, description=description, due_date=due_date)
            
            if result['success']:
                task.priority = PriorityEnum[result['priority'].upper()]
                task.priority_score = result['priority_score']
                task.estimated_effort_minutes = result['estimated_effort_minutes']
                db.commit()
                
                await analyzing_msg.delete()
                
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
                success_message = (
                    f"✅ Task Created!\n\n"
                    f"📋 {title}\n"
                    f"{priority_emoji.get(result['priority'], '⚪')} Priority: {result['priority'].upper()}\n"
                    f"📊 AI Score: {result['priority_score']}/100\n"
                    f"⏱️ Estimated: {result['estimated_effort_minutes']} min\n"
                    f"📅 Due: {due_date.strftime('%d %b %Y') if due_date else 'No deadline'}\n\n"
                    f"🤖 AI Reasoning:\n{result['reasoning']}\n\n"
                    f"Use /listtasks to see all tasks!"
                )
                await update.message.reply_text(success_message)
            else:
                await analyzing_msg.delete()
                await update.message.reply_text(f"✅ Task created: {title}\n\n⚠️ AI failed. Default priority.")
        
        except Exception as e:
            logger.error(f"AI error: {e}")
            await analyzing_msg.delete()
            await update.message.reply_text(f"✅ Task created: {title}\n\n⚠️ AI unavailable.")

    finally:
        db.close()
    
    context.user_data.clear()
    return ConversationHandler.END


async def addtask_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel task creation."""
    context.user_data.clear()
    await update.message.reply_text("❌ Task creation cancelled.")
    return ConversationHandler.END


# ============================================
# EDIT TASK HANDLERS (NEW!)
# ============================================

async def edittask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start task editing."""
    user = update.effective_user
    user_id = get_or_create_user(user.id)

    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text(
                "❌ Please provide task ID\n\n"
                "Example: /edittask 5\n\n"
                "Use /listtasks to see IDs"
            )
            return ConversationHandler.END
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid task ID.")
        return ConversationHandler.END

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
            return ConversationHandler.END
        
        # Store task_id for later
        context.user_data['edit_task_id'] = task_id
        
        message = (
            f"✏️ Editing Task #{task_id}\n\n"
            f"Current:\n"
            f"📋 Title: {task.title}\n"
            f"📝 Description: {task.description or 'None'}\n"
            f"📅 Due: {task.due_date.strftime('%d %b %Y') if task.due_date else 'No deadline'}\n\n"
            f"What do you want to edit?\n\n"
            f"1️⃣ Title\n"
            f"2️⃣ Description\n"
            f"3️⃣ Due Date\n"
            f"4️⃣ All (start over)\n\n"
            f"Reply with number (1-4) or /cancel"
        )
        await update.message.reply_text(message)
        return EDIT_CHOICE
        
    finally:
        db.close()


async def edittask_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit choice."""
    choice = update.message.text.strip()
    
    if choice == "1":
        await update.message.reply_text("📝 Enter new title:")
        return EDIT_TITLE
    elif choice == "2":
        await update.message.reply_text("📝 Enter new description (or /skip):")
        return EDIT_DESCRIPTION
    elif choice == "3":
        await update.message.reply_text("📅 Enter new due date (or /skip):")
        return EDIT_DUE_DATE
    elif choice == "4":
        await update.message.reply_text("📝 Enter new title:")
        context.user_data['edit_all'] = True
        return EDIT_TITLE
    else:
        await update.message.reply_text("❌ Invalid choice. Use /edittask again.")
        return ConversationHandler.END


async def edittask_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update task title."""
    new_title = update.message.text
    task_id = context.user_data['edit_task_id']
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if task:
            task.title = new_title
            db.commit()
            
            if context.user_data.get('edit_all'):
                await update.message.reply_text("✅ Title updated!\n\n📝 Enter new description (or /skip):")
                return EDIT_DESCRIPTION
            else:
                await update.message.reply_text(f"✅ Title updated to: {new_title}")
                context.user_data.clear()
                return ConversationHandler.END
    finally:
        db.close()


async def edittask_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update task description."""
    task_id = context.user_data['edit_task_id']
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if task:
            if update.message.text != "/skip":
                task.description = update.message.text
                db.commit()
            
            if context.user_data.get('edit_all'):
                await update.message.reply_text("✅ Description updated!\n\n📅 Enter new due date (or /skip):")
                return EDIT_DUE_DATE
            else:
                await update.message.reply_text("✅ Description updated!")
                context.user_data.clear()
                return ConversationHandler.END
    finally:
        db.close()


async def edittask_due_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update task due date."""
    task_id = context.user_data['edit_task_id']
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if task:
            if update.message.text != "/skip":
                new_due_date = parse_due_date(update.message.text)
                if new_due_date:
                    task.due_date = new_due_date
                    db.commit()
                    await update.message.reply_text(f"✅ Due date updated to: {new_due_date.strftime('%d %b %Y')}")
                else:
                    await update.message.reply_text("⚠️ Couldn't parse date. Not updated.")
            else:
                await update.message.reply_text("✅ Edit complete!")
            
            context.user_data.clear()
            return ConversationHandler.END
    finally:
        db.close()


async def edittask_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel editing."""
    context.user_data.clear()
    await update.message.reply_text("❌ Edit cancelled.")
    return ConversationHandler.END


# ============================================
# COMPLETE & POSTPONE HANDLERS (NEW!)
# ============================================

async def complete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark task as completed."""
    user = update.effective_user
    user_id = get_or_create_user(user.id)

    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text("❌ Usage: /complete <ID>")
            return
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid task ID.")
        return

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
            return
        
        task.status = TaskStatusEnum.COMPLETED
        task.completed_at = datetime.utcnow()
        db.commit()
        
        await update.message.reply_text(f"✅ Completed: {task.title}\n\n🎉 Great job!")
        
    finally:
        db.close()


async def postpone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Postpone task by 1 day."""
    user = update.effective_user
    user_id = get_or_create_user(user.id)

    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text("❌ Usage: /postpone <ID>")
            return
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid task ID.")
        return

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
            return
        
        if not task.due_date:
            # No due date, set to tomorrow
            task.due_date = datetime.utcnow() + timedelta(days=1)
        else:
            # Push existing due date +1 day
            task.due_date = task.due_date + timedelta(days=1)
        
        task.postponed_count += 1
        db.commit()
        
        await update.message.reply_text(
            f"📅 Postponed: {task.title}\n\n"
            f"New due date: {task.due_date.strftime('%d %b %Y')}\n"
            f"Postponed {task.postponed_count} time(s)"
        )
        
    finally:
        db.close()


# ============================================
# LIST, SUGGEST, DELETE (EXISTING)
# ============================================

async def listtasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all pending tasks."""
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.username, user.first_name)
    
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(
            Task.user_id == user_id,
            Task.status == TaskStatusEnum.PENDING
        ).order_by(Task.priority_score.desc()).limit(20).all()

        if not tasks:
            await update.message.reply_text("📭 No pending tasks!\n\nUse /addtask to add one.")
            return

        message = "📋 Your Tasks (sorted by AI priority)\n\n"
        
        priority_emoji = {
            PriorityEnum.HIGH: '🔴',
            PriorityEnum.MEDIUM: '🟡',
            PriorityEnum.LOW: '🟢'
        }
        
        for task in tasks:
            emoji = priority_emoji.get(task.priority, '⚪')
            due_text = f"Due: {task.due_date.strftime('%d %b')}" if task.due_date else "No deadline"
            effort_text = f"{task.estimated_effort_minutes}min" if task.estimated_effort_minutes else "?"
            
            message += (
                f"{emoji} #{task.id} {task.title}\n"
                f"   {task.priority.value.upper()} ({task.priority_score}) | "
                f"{due_text} | {effort_text}\n\n"
            )
        
        message += "💡 Commands:\n/edittask <ID> | /complete <ID> | /postpone <ID> | /deletetask <ID>"
        await update.message.reply_text(message)
        
    finally:
        db.close()


async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI suggests next task."""
    user = update.effective_user
    user_id = get_or_create_user(user.id)
    
    db = SessionLocal()
    try:
        task = db.query(Task).filter(
            Task.user_id == user_id,
            Task.status == TaskStatusEnum.PENDING
        ).order_by(Task.priority_score.desc()).first()
        
        if not task:
            await update.message.reply_text("🎉 No pending tasks!\n\nTake a break!")
            return
        
        priority_emoji = {
            PriorityEnum.HIGH: '🔴',
            PriorityEnum.MEDIUM: '🟡',
            PriorityEnum.LOW: '🟢'
        }
        
        emoji = priority_emoji.get(task.priority, '⚪')
        due_text = f"Due: {task.due_date.strftime('%d %b %Y')}" if task.due_date else "No deadline"
        
        suggestion = (
            f"💡 AI Recommendation\n\n"
            f"Work on this next:\n\n"
            f"{emoji} {task.title}\n\n"
            f"📊 Priority: {task.priority_score}/100\n"
            f"⏱️ Estimated: {task.estimated_effort_minutes or '?'} min\n"
            f"📅 {due_text}\n\n"
            f"Ready? /complete {task.id} when done! 💪"
        )
        await update.message.reply_text(suggestion)
        
    finally:
        db.close()


async def deletetask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a task."""
    user = update.effective_user
    user_id = get_or_create_user(user.id)

    try:
        task_id = int(context.args[0]) if context.args else None
        if not task_id:
            await update.message.reply_text("❌ Usage: /deletetask <ID>")
            return
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Invalid task ID.")
        return

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text(f"❌ Task #{task_id} not found.")
            return
        
        title = task.title
        db.delete(task)
        db.commit()
        await update.message.reply_text(f"🗑️ Deleted: {title}")
        
    finally:
        db.close()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle natural language."""
    message = update.message.text.lower()
    triggers = ['add task', 'create task', 'new task']
    
    if any(phrase in message for phrase in triggers):
        for trigger in ['add task:', 'create task:', 'new task:']:
            if trigger in message:
                task_text = message.split(trigger, 1)[1].strip()
                context.user_data['task_title'] = task_text
                await update.message.reply_text(f"📝 Creating: {task_text}\n\nAdd description? (or /skip)")
                return TASK_DESCRIPTION
    
    await update.message.reply_text(
        "Try:\n"
        "/addtask | /listtasks | /suggest\n"
        "Or: 'Add task: <task name>'"
    )


# ============================================
# BOT STARTUP/SHUTDOWN
# ============================================

async def start_bot():
    """Start Telegram bot."""
    global bot_application
    
    if not settings.telegram_bot_token:
        logger.warning("⚠️ No Telegram token.")
        return

    try:
        bot_application = Application.builder().token(settings.telegram_bot_token).build()

        # Add task conversation
        addtask_conv = ConversationHandler(
            entry_points=[CommandHandler("addtask", addtask_start)],
            states={
                TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_title)],
                TASK_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_description),
                    CommandHandler("skip", addtask_description)
                ],
                TASK_DUE_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, addtask_due_date),
                    CommandHandler("skip", addtask_due_date)
                ],
            },
            fallbacks=[CommandHandler("cancel", addtask_cancel)]
        )

        # Edit task conversation (NEW!)
        edittask_conv = ConversationHandler(
            entry_points=[CommandHandler("edittask", edittask_start)],
            states={
                EDIT_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edittask_choice)],
                EDIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edittask_title)],
                EDIT_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edittask_description),
                    CommandHandler("skip", edittask_description)
                ],
                EDIT_DUE_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edittask_due_date),
                    CommandHandler("skip", edittask_due_date)
                ],
            },
            fallbacks=[CommandHandler("cancel", edittask_cancel)]
        )

        # Register all handlers
        bot_application.add_handler(addtask_conv)
        bot_application.add_handler(edittask_conv)  # NEW!
        bot_application.add_handler(CommandHandler("start", start_command))
        bot_application.add_handler(CommandHandler("help", help_command))
        bot_application.add_handler(CommandHandler("listtasks", listtasks_command))
        bot_application.add_handler(CommandHandler("suggest", suggest_command))
        bot_application.add_handler(CommandHandler("complete", complete_command))  # NEW!
        bot_application.add_handler(CommandHandler("postpone", postpone_command))  # NEW!
        bot_application.add_handler(CommandHandler("deletetask", deletetask_command))
        bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Start polling
        logger.info("Starting Telegram bot in polling mode...")
        await bot_application.initialize()
        await bot_application.start()
        await bot_application.updater.start_polling()
        logger.info("✅ Telegram bot polling started!")
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise


async def stop_bot():
    """Stop Telegram bot."""
    global bot_application
    
    if bot_application:
        try:
            if bot_application.updater and bot_application.updater.running:
                await bot_application.updater.stop()
            await bot_application.stop()
            await bot_application.shutdown()
            logger.info("✅ Bot stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
