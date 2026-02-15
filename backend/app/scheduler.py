"""
Daily Scheduler
Runs daily checks for birthdays, festivals, and task reminders.
Uses APScheduler for scheduling.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from app.database import SessionLocal
from app.models import User, Birthday, Task, TaskStatusEnum
from app.agents import get_celebration_agent, get_notification_agent
from app.telegram.bot import send_message_to_user

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler = None


async def check_birthdays_and_send_wishes():
    """
    Daily job: Check for birthdays and send wishes.
    Runs at 9:00 AM UTC daily.
    """
    logger.info("🎂 Running daily birthday check...")
    
    db = SessionLocal()
    try:
        # Get all birthdays that are today
        birthdays_today = db.query(Birthday).all()
        
        celebration_agent = get_celebration_agent()
        wishes_sent = 0
        
        for birthday in birthdays_today:
            if birthday.is_birthday_today() and birthday.send_on_day:
                # Get user preferences
                user = db.query(User).filter(User.id == birthday.user_id).first()
                if not user or not hasattr(user, 'preferences'):
                    continue
                
                prefs = user.preferences
                if not prefs or not prefs.auto_send_birthday_wishes:
                    continue
                
                # Generate personalized wish
                wish_data = await celebration_agent.generate_birthday_wish(
                    name=birthday.person_name,
                    relation=birthday.relation,
                    age=birthday.age,
                    interests=birthday.interests
                )
                
                if wish_data['success']:
                    # Send via Telegram
                    message = f"🎂 **Birthday Reminder!**\n\n{wish_data['message']}"
                    
                    if user.telegram_id:
                        await send_message_to_user(user.telegram_id, message)
                        wishes_sent += 1
                        logger.info(f"✅ Sent birthday wish for {birthday.person_name}")
        
        logger.info(f"🎉 Sent {wishes_sent} birthday wishes")
        
    except Exception as e:
        logger.error(f"❌ Birthday check failed: {e}")
    finally:
        db.close()


async def check_festivals_and_send_greetings():
    """
    Daily job: Check for festivals and send greetings.
    Runs at 9:00 AM UTC daily.
    """
    logger.info("🎊 Running daily festival check...")
    
    db = SessionLocal()
    try:
        # Get all users with festival preferences
        users = db.query(User).all()
        
        celebration_agent = get_celebration_agent()
        greetings_sent = 0
        
        for user in users:
            if not hasattr(user, 'preferences') or not user.preferences:
                continue
            
            prefs = user.preferences
            if not prefs.auto_send_festival_wishes or not prefs.festival_countries:
                continue
            
            # Check festivals for user's selected countries
            festivals = await celebration_agent.check_todays_festivals(
                countries=prefs.festival_countries
            )
            
            if festivals:
                # Send greeting for each festival
                for festival in festivals:
                    greeting_data = await celebration_agent.generate_festival_greeting(
                        festival_name=festival['name'],
                        country=festival['country'],
                        festival_type=festival.get('type', 'cultural')
                    )
                    
                    if greeting_data['success']:
                        message = (
                            f"{greeting_data['emoji']} **{festival['name']}**\n\n"
                            f"{greeting_data['message']}\n\n"
                            f"📍 Celebrated in {festival['country']}"
                        )
                        
                        if user.telegram_id:
                            await send_message_to_user(user.telegram_id, message)
                            greetings_sent += 1
                            logger.info(f"✅ Sent {festival['name']} greeting to user {user.id}")
        
        logger.info(f"🎉 Sent {greetings_sent} festival greetings")
        
    except Exception as e:
        logger.error(f"❌ Festival check failed: {e}")
    finally:
        db.close()


async def send_daily_task_digest():
    """
    Daily job: Send task digest to all users.
    Runs at 9:00 AM UTC daily.
    """
    logger.info("📊 Sending daily task digests...")
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        
        notification_agent = get_notification_agent()
        digests_sent = 0
        
        for user in users:
            # Check preferences
            if hasattr(user, 'preferences') and user.preferences:
                if not user.preferences.enable_daily_digest:
                    continue
            
            # Get user's pending tasks
            pending_tasks = db.query(Task).filter(
                Task.user_id == user.id,
                Task.status == TaskStatusEnum.PENDING
            ).all()
            
            if not pending_tasks:
                continue
            
            # Convert to dict format
            tasks_data = [{
                'id': t.id,
                'title': t.title,
                'priority': t.priority.value if t.priority else 'medium',
                'priority_score': t.priority_score or 50,
                'due_date': t.due_date.isoformat() if t.due_date else None,
                'estimated_effort_minutes': t.estimated_effort_minutes
            } for t in pending_tasks]
            
            # Generate digest
            digest = await notification_agent.generate_daily_digest(tasks=tasks_data)
            
            if digest['success']:
                stats = digest.get('stats', {})
                message = (
                    f"📋 **Daily Task Digest**\n\n"
                    f"{digest['message']}\n\n"
                    f"📊 **Today's Focus:**\n{digest.get('priority_focus', 'Start with high-priority tasks')}\n\n"
                    f"💡 **Tip:** {digest.get('motivation_tip', 'One task at a time!')}\n\n"
                    f"Overdue: {stats.get('overdue_count', 0)} | "
                    f"Today: {stats.get('today_count', 0)} | "
                    f"Upcoming: {stats.get('upcoming_count', 0)}"
                )
                
                if user.telegram_id:
                    await send_message_to_user(user.telegram_id, message)
                    digests_sent += 1
                    logger.info(f"✅ Sent digest to user {user.id}")
        
        logger.info(f"📨 Sent {digests_sent} daily digests")
        
    except Exception as e:
        logger.error(f"❌ Daily digest failed: {e}")
    finally:
        db.close()


async def check_task_reminders():
    """
    Hourly job: Check for tasks due soon and send reminders.
    Runs every hour.
    """
    logger.info("⏰ Checking task reminders...")
    
    db = SessionLocal()
    try:
        # Get all pending tasks with due dates
        now = datetime.utcnow()
        
        tasks = db.query(Task).filter(
            Task.status == TaskStatusEnum.PENDING,
            Task.due_date.isnot(None)
        ).all()
        
        notification_agent = get_notification_agent()
        reminders_sent = 0
        
        for task in tasks:
            # Check if reminder should be sent (2 hours before)
            time_until = (task.due_date - now).total_seconds() / 3600
            
            if 1.5 <= time_until <= 2.5:  # 2-hour window
                user = db.query(User).filter(User.id == task.user_id).first()
                if not user or not user.telegram_id:
                    continue
                
                # Generate reminder
                task_data = {
                    'id': task.id,
                    'title': task.title,
                    'priority': task.priority.value if task.priority else 'medium',
                    'due_date': task.due_date.isoformat(),
                    'estimated_effort_minutes': task.estimated_effort_minutes
                }
                
                reminder = await notification_agent.generate_task_reminder(
                    task=task_data,
                    reminder_type="upcoming"
                )
                
                if reminder['success']:
                    message = (
                        f"⏰ **Task Reminder**\n\n"
                        f"{reminder['message']}\n\n"
                        f"💡 {reminder.get('suggested_action', 'Start working on it now!')}"
                    )
                    
                    await send_message_to_user(user.telegram_id, message)
                    reminders_sent += 1
                    logger.info(f"✅ Sent reminder for task {task.id}")
        
        logger.info(f"📨 Sent {reminders_sent} task reminders")
        
    except Exception as e:
        logger.error(f"❌ Task reminder check failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Initialize and start the daily scheduler."""
    global scheduler
    
    if scheduler is not None:
        logger.warning("⚠️ Scheduler already running")
        return
    
    scheduler = AsyncIOScheduler()
    
    # Birthday and festival check - Daily at 9:00 AM UTC
    scheduler.add_job(
        check_birthdays_and_send_wishes,
        CronTrigger(hour=9, minute=0),
        id="birthday_check",
        name="Daily Birthday Check"
    )
    
    scheduler.add_job(
        check_festivals_and_send_greetings,
        CronTrigger(hour=9, minute=0),
        id="festival_check",
        name="Daily Festival Check"
    )
    
    # Daily digest - 9:00 AM UTC
    scheduler.add_job(
        send_daily_task_digest,
        CronTrigger(hour=9, minute=0),
        id="daily_digest",
        name="Daily Task Digest"
    )
    
    # Task reminders - Every hour
    scheduler.add_job(
        check_task_reminders,
        CronTrigger(minute=0),  # Every hour at :00
        id="task_reminders",
        name="Hourly Task Reminders"
    )
    
    scheduler.start()
    logger.info("✅ Scheduler started with 4 jobs")


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("✅ Scheduler stopped")


# Helper function for sending Telegram messages
async def send_message_to_user(telegram_id: int, message: str):
    """Send message to user via Telegram."""
    try:
        from app.telegram.bot import bot_application
        
        if bot_application:
            await bot_application.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")
