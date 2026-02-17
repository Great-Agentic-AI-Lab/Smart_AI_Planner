"""
Dynamic Scheduler - Per-User Timezone & Time Settings
- Runs every minute, checks each user's configured time + timezone
- Tracks last sent date per user to send ONCE per day only
- If settings change, next run picks them up automatically
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date
import logging
import pytz

from app.database import SessionLocal
from app.models import User, Birthday, Task, TaskStatusEnum

logger = logging.getLogger(__name__)
scheduler: AsyncIOScheduler = None


# CORE: Send Telegram message
async def send_message_to_user(telegram_id: int, message: str):
    """Send message via Telegram. Defined here to avoid circular import."""
    try:
        from app.telegram.bot import bot_application
        if bot_application:
            await bot_application.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Message sent to {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to send to {telegram_id}: {e}")


# HELPERS
def is_users_send_time(prefs) -> bool:
    """
    Check if NOW matches user's configured send time in their timezone.
    Called every minute - only returns True for exactly 1 minute per day.
    """
    try:
        user_tz = pytz.timezone(prefs.timezone or "UTC")
        now_user = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(user_tz)

        from datetime import time as dtime
        send_time = prefs.daily_digest_time or dtime(9, 0)

        return (now_user.hour == send_time.hour and
                now_user.minute == send_time.minute)
    except Exception as e:
        logger.error(f"Timezone check error: {e}")
        return False


def already_sent_today(last_sent_date) -> bool:
    """
    Returns True if already sent today.
    Prevents duplicate messages even if server restarts.
    """
    if last_sent_date is None:
        return False
    return last_sent_date == date.today()


# JOB 1: Birthday Wishes
async def check_birthdays_and_send_wishes():
    """
    Runs every minute.
    Sends ONCE per day per user at their configured time in their timezone.
    """
    db = SessionLocal()
    try:
        from app.agents import get_celebration_agent
        celebration_agent = get_celebration_agent()
        users = db.query(User).all()

        for user in users:
            prefs = user.preferences
            if not prefs or not prefs.auto_send_birthday_wishes:
                continue

            # Skip if already sent today
            if already_sent_today(prefs.last_birthday_sent_date):
                continue

            # Only send at user's configured time in their timezone
            if not is_users_send_time(prefs):
                continue

            logger.info(f"Checking birthdays for user {user.id} ({prefs.timezone})")

            birthdays = db.query(Birthday).filter(Birthday.user_id == user.id).all()
            sent_any = False

            for birthday in birthdays:
                if birthday.is_birthday_today() and birthday.send_on_day:
                    wish_data = await celebration_agent.generate_birthday_wish(
                        name=birthday.person_name,
                        relation=birthday.relation,
                        age=birthday.age,
                        interests=birthday.interests
                    )
                    if wish_data['success'] and user.telegram_id:
                        await send_message_to_user(
                            user.telegram_id,
                            f"**Birthday Reminder!**\n\n{wish_data['message']}"
                        )
                        sent_any = True
                        logger.info(f"Sent birthday wish for {birthday.person_name} to user {user.id}")

            # Mark today as sent so it won't fire again this minute or any other
            if sent_any:
                prefs.last_birthday_sent_date = date.today()
                db.commit()

    except Exception as e:
        logger.error(f"Birthday check failed: {e}")
    finally:
        db.close()


# JOB 2: Festival Greetings
async def check_festivals_and_send_greetings():
    """
    Runs every minute.
    Sends ONCE per day per user at their configured time in their timezone.
    """
    db = SessionLocal()
    try:
        from app.agents import get_celebration_agent
        celebration_agent = get_celebration_agent()
        users = db.query(User).all()

        for user in users:
            prefs = user.preferences
            if not prefs or not prefs.auto_send_festival_wishes:
                continue
            if not prefs.festival_countries:
                continue

            # Skip if already sent today
            if already_sent_today(prefs.last_festival_sent_date):
                continue

            # Only send at user's configured time in their timezone
            if not is_users_send_time(prefs):
                continue

            logger.info(f"🎉 Checking festivals for user {user.id} - {prefs.festival_countries}")

            festivals = await celebration_agent.check_todays_festivals(
                countries=prefs.festival_countries
            )

            if festivals:
                for festival in festivals:
                    greeting_data = await celebration_agent.generate_festival_greeting(
                        festival_name=festival['name'],
                        country=festival['country'],
                        festival_type=festival.get('type', 'cultural')
                    )
                    if greeting_data['success'] and user.telegram_id:
                        await send_message_to_user(
                            user.telegram_id,
                            f"{greeting_data['emoji']} **{festival['name']}**\n\n"
                            f"{greeting_data['message']}\n\n"
                            f"🌍 Celebrated in {festival['country']}"
                        )
                        logger.info(f"✅ Sent {festival['name']} to user {user.id}")

                # Mark today as sent
                prefs.last_festival_sent_date = date.today()
                db.commit()

    except Exception as e:
        logger.error(f"Festival check failed: {e}")
    finally:
        db.close()


# JOB 3: Daily Task Digest
async def send_daily_task_digest():
    """
    Runs every minute.
    Sends ONCE per day per user at their configured time in their timezone.
    """
    db = SessionLocal()
    try:
        from app.agents import get_notification_agent
        notification_agent = get_notification_agent()
        users = db.query(User).all()

        for user in users:
            prefs = user.preferences
            if not prefs or not prefs.enable_daily_digest:
                continue

            # Skip if already sent today
            if already_sent_today(prefs.last_digest_sent_date):
                continue

            # Only send at user's configured time in their timezone
            if not is_users_send_time(prefs):
                continue

            logger.info(f"Sending digest to user {user.id} ({prefs.timezone} / {prefs.daily_digest_time})")

            pending_tasks = db.query(Task).filter(
                Task.user_id == user.id,
                Task.status == TaskStatusEnum.PENDING
            ).all()

            if not pending_tasks:
                # Still mark as sent so we don't keep checking
                prefs.last_digest_sent_date = date.today()
                db.commit()
                continue

            tasks_data = [{
                'id': t.id,
                'title': t.title,
                'priority': t.priority.value if t.priority else 'medium',
                'priority_score': t.priority_score or 50,
                'due_date': t.due_date.isoformat() if t.due_date else None,
                'estimated_effort_minutes': t.estimated_effort_minutes
            } for t in pending_tasks]

            digest = await notification_agent.generate_daily_digest(tasks=tasks_data)

            if digest['success'] and user.telegram_id:
                stats = digest.get('stats', {})
                message = (
                    f"📋 **Daily Task Digest**\n\n"
                    f"{digest['message']}\n\n"
                    f"🎯 **Today's Focus:**\n{digest.get('priority_focus', 'Start with high-priority tasks')}\n\n"
                    f"💡 **Tip:** {digest.get('motivation_tip', 'One task at a time!')}\n\n"
                    f"⚠️ Overdue: {stats.get('overdue_count', 0)} | "
                    f"📅 Today: {stats.get('today_count', 0)} | "
                    f"🔜 Upcoming: {stats.get('upcoming_count', 0)}"
                )
                await send_message_to_user(user.telegram_id, message)
                logger.info(f"Sent digest to user {user.id}")

            # Mark today as sent
            prefs.last_digest_sent_date = date.today()
            db.commit()

    except Exception as e:
        logger.error(f"Daily digest failed: {e}")
    finally:
        db.close()


# JOB 4: Task Reminders (hourly)
async def check_task_reminders():
    """Runs every hour. Sends reminder for tasks due in ~2 hours."""
    db = SessionLocal()
    try:
        from app.agents import get_notification_agent
        notification_agent = get_notification_agent()
        now = datetime.utcnow()

        tasks = db.query(Task).filter(
            Task.status == TaskStatusEnum.PENDING,
            Task.due_date.isnot(None)
        ).all()

        for task in tasks:
            time_until = (task.due_date - now).total_seconds() / 3600
            if not (1.5 <= time_until <= 2.5):
                continue

            user = db.query(User).filter(User.id == task.user_id).first()
            if not user or not user.telegram_id:
                continue

            prefs = user.preferences
            if prefs and not prefs.enable_task_reminders:
                continue

            reminder = await notification_agent.generate_task_reminder(
                task={
                    'id': task.id,
                    'title': task.title,
                    'priority': task.priority.value if task.priority else 'medium',
                    'due_date': task.due_date.isoformat(),
                    'estimated_effort_minutes': task.estimated_effort_minutes
                },
                reminder_type="upcoming"
            )

            if reminder['success']:
                await send_message_to_user(
                    user.telegram_id,
                    f"⏰ **Task Reminder**\n\n"
                    f"{reminder['message']}\n\n"
                    f"💡 {reminder.get('suggested_action', 'Start working on it now!')}"
                )
                logger.info(f"✅ Sent reminder for task {task.id} to user {user.id}")

    except Exception as e:
        logger.error(f"❌ Task reminder check failed: {e}")
    finally:
        db.close()


# START / STOP
def start_scheduler():
    """
    Dynamic per-user scheduler.
    
    Logic flow every minute:
    1. Is it this user's send time in their timezone? NO → skip
    2. Was it already sent today? YES → skip  
    3. Send message + mark date in DB
    
    Result: exactly 1 message per user per day, at their time, in their timezone.
    If user changes /settime or /settimezone → takes effect next day automatically.
    """
    global scheduler

    if scheduler is not None:
        logger.warning("⚠️ Scheduler already running")
        return

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(check_birthdays_and_send_wishes,  CronTrigger(minute='*'), id="birthday_check",  name="Birthday Check")
    scheduler.add_job(check_festivals_and_send_greetings, CronTrigger(minute='*'), id="festival_check", name="Festival Check")
    scheduler.add_job(send_daily_task_digest,            CronTrigger(minute='*'), id="daily_digest",    name="Daily Digest")
    scheduler.add_job(check_task_reminders,              CronTrigger(minute=0),   id="task_reminders",  name="Task Reminders")

    scheduler.start()
    logger.info("Dynamic scheduler started!")
    logger.info("   Logic: runs every minute → checks user TZ + time → sends ONCE per day per user")


def stop_scheduler():
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("Scheduler stopped")
