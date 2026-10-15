
import asyncio
import random
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import dateparser

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8757657690:AAG4jIul7VWno_dBJ0QPUFgKYfVeawdPN2Y"  # Твой токен встроен
TIMEZONE = "Asia/Novosibirsk"                                   # Твой часовой пояс

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))

# Базы данных в памяти
user_tasks = {}         # {user_id: [список задач на день]}
user_regular_jobs = {}  # {user_id: {job_id: description}} для регулярных привычек
user_stats = {}         # {user_id: {"xp": 0, "level": 1, "completed_total": 0}}

# --- ПУЛ МОТИВИРУЮЩИХ ФРАЗ БЕЗ ПОВТОРЕНИЙ ---
MOTIVATIONAL_QUOTES = [
    "🚀 Новый день — новые возможности! Что сегодня покоряем?",
    "💡 Успех — это сумма небольших усилий, повторяемых изо дня в день. Время действовать!",
    "🔥 Не откладывай на завтра то, что сделает тебя лучше уже сегодня!",
    "🏆 Сделай шаг навстречу своим целям. Напиши план на день!",
    "✨ Дисциплина — это мост между целями и их достижениями. Погнали!",
    "⚡ Твоя энергия сегодня — ключ к твоему успеху завтра!",
    "🎯 Фокусируйся на главном. Ты сможешь свернуть горы!",
    "🌟 Маленькие победы каждый день ведут к большим результатам!"
]

def get_random_quote() -> str:
    return random.choice(MOTIVATIONAL_QUOTES)

def init_user_stats(user_id: int):
    """Инициализация профиля игрока, если его еще нет"""
    if user_id not in user_stats:
        user_stats[user_id] = {
            "xp": 0,
            "level": 1,
            "completed_total": 0
        }

def add_xp(user_id: int, amount: int) -> tuple[int, bool]:
    """Добавляет опыт и проверяет повышение уровня. Возвращает (новый уровень, был ли ап)"""
    init_user_stats(user_id)
    stats = user_stats[user_id]
    stats["xp"] += amount
    stats["completed_total"] += 1

    # Порог для перехода на следующий уровень: уровень * 100 XP
    next_level_xp = stats["level"] * 100
    leveled_up = False

    if stats["xp"] >= next_level_xp:
        stats["xp"] -= next_level_xp
        stats["level"] += 1
        leveled_up = True

    return stats["level"], leveled_up


# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👋 Я твой бот-мотиватор с **системой прокачки RPG** 🎮\n\n"
        "📌 **Что я умею:**\n"
        "• **Список дел:** просто отправь текст (каждое дело с новой строки).\n"
        "• `/list` — посмотреть задачи на день.\n"
        "• `/done` — отметить задачи выполненными (получить XP и поднять уровень!).\n"
        "• `/profile` — посмотреть свой уровень, опыт и статистику 📊\n"
        "• `/clear` — очистить задачи на день.\n"
        "• **Напоминания:** ко времени (`15:30 Созвон`), по дате (`завтра в 14:00 Врач`), регулярные (`каждые 2 часа Пить воду`).\n"
        "• `/regular` и `/del_regular` — управление привычками.",
        parse_mode="Markdown"
    )

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    init_user_stats(user_id)
    stats = user_stats[user_id]
    
    current_level = stats["level"]
    current_xp = stats["xp"]
    required_xp = current_level * 100
    total_completed = stats["completed_total"]

    await message.answer(
        f"🎮 **Твой профиль искателя приключений:**\n\n"
        f"⭐ Уровень: **{current_level}**\n"
        f"🧪 Опыт (XP): `{current_xp} / {required_xp}`\n"
        f"🏆 Всего выполнено задач: **{total_completed}**\n\n"
        f"Продолжай в том же духе! 💪",
        parse_mode="Markdown"
    )

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    tasks = user_tasks.get(message.from_user.id, [])
    if not tasks:
        await message.answer("📝 Твой список задач на сегодня пуст!")
    else:
        task_text = "\n".join([f"{i+1}. {task}" for i, task in enumerate(tasks)])
        await message.answer(
            f"📋 **Твои задачи на день:**\n\n{task_text}\n\n"
            f"Когда выполнишь, напиши `/done <номера>`, например: `/done 1 3`",
            parse_mode="Markdown"
        )

@dp.message(Command("done"))
async def cmd_done(message: types.Message):
    user_id = message.from_user.id
    tasks = user_tasks.get(user_id, [])
    
    if not tasks:
        await message.answer("📝 У тебя нет активных задач на сегодня. Сначала добавь их!")
        return

    parts = message.text.split()[1:]
    if not parts:
        await message.answer("⚠️ Укажи номера выполненных задач через пробел. Пример: `/done 1 2`", parse_mode="Markdown")
        return

    completed_indices = []
    for p in parts:
        if p.isdigit():
            idx = int(p) - 1
            if 0 <= idx < len(tasks):
                completed_indices.append(idx)

    if not completed_indices:
        await message.answer("❌ Неверные номера задач. Посмотри актуальный список через `/list`.")
        return

    completed_indices.sort(reverse=True)
    earned_xp = len(completed_indices) * 50

    for idx in completed_indices:
        tasks.pop(idx)

    new_level, leveled_up = add_xp(user_id, earned_xp)

    response = f"🎉 Отлично! Зачтено выполненных задач: **{len(completed_indices)}**.\n⚡ Получено опыта: `+{earned_xp} XP`!"
    if leveled_up:
        response += f"\n\n🔥 **ПОЗДРАВЛЯЮ! Ты повысил уровень до {new_level}!** 🏆"

    await message.answer(response, parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_tasks[message.from_user.id] = []
    await message.answer("🗑️ Список задач на день очищен!")


# --- УПРАВЛЕНИЕ РЕГУЛЯРНЫМИ НАПОМИНАНИЯМИ ---

async def send_regular_reminder(user_id: int, text: str):
    await bot.send_message(user_id, f"🔔 **Регулярное напоминание:**\n\n{text}")

@dp.message(Command("regular"))
async def cmd_regular_list(message: types.Message):
    user_id = message.from_user.id
    jobs = user_regular_jobs.get(user_id, {})
    if not jobs:
        await message.answer("📭 У тебя нет активных регулярных напоминаний.")
    else:
        text = "🔄 **Твои регулярные напоминания:**\n\n"
        for i, (job_id, desc) in enumerate(jobs.items(), 1):
            text += f"{i}. {desc} (ID: `{job_id}`)\n"
        text += "\nУдалить: `/del_regular <ID>`"
        await message.answer(text, parse_mode="Markdown")

@dp.message(Command("del_regular"))
async def cmd_del_regular(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Укажи ID или номер напоминания. Пример: `/del_regular 1`", parse_mode="Markdown")
        return
    
    target_idx = parts[1].strip()
    jobs = user_regular_jobs.get(user_id, {})
    job_ids = list(jobs.keys())
    job_to_remove = None
    
    if target_idx.isdigit() and 1 <= int(target_idx) <= len(job_ids):
        job_to_remove = job_ids[int(target_idx) - 1]
    elif target_idx in jobs:
        job_to_remove = target_idx
        
    if job_to_remove:
        scheduler.remove_job(job_to_remove)
        del jobs[job_to_remove]
        await message.answer("🗑️ Регулярное напоминание успешно удалено!")
    else:
        await message.answer("❌ Напоминание с таким номером не найдено.")


# --- УМНЫЙ ПАРСЕР ТЕКСТА ---

@dp.message(F.text)
async def handle_text_messages(message: types.Message):
    text = message.text.strip()
    user_id = message.from_user.id
    lower_text = text.lower()

    # 1. Регулярные напоминания ("каждые X часов/минут ...")
    if lower_text.startswith("каждые "):
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            num_str = parts[1]
            period_and_text = parts[2].lower()
            
            if num_str.isdigit():
                num = int(num_str)
                if "час" in period_and_text:
                    actual_text = parts[2].split(maxsplit=1)[1] if len(parts[2].split()) > 1 else "Напоминание"
                    job = scheduler.add_job(send_regular_reminder, 'interval', hours=num, args=[user_id, actual_text])
                    
                    if user_id not in user_regular_jobs:
                        user_regular_jobs[user_id] = {}
                    user_regular_jobs[user_id][job.id] = f"Каждые {num} ч: {actual_text}"
                    
                    await message.answer(f"✅ Готово! Буду напоминать: **«{actual_text}»** каждые {num} ч.", parse_mode="Markdown")
                    return
                elif "минут" in period_and_text:
                    actual_text = parts[2].split(maxsplit=1)[1] if len(parts[2].split()) > 1 else "Напоминание"
                    job = scheduler.add_job(send_regular_reminder, 'interval', minutes=num, args=[user_id, actual_text])
                    
                    if user_id not in user_regular_jobs:
                        user_regular_jobs[user_id] = {}
                    user_regular_jobs[user_id][job.id] = f"Каждые {num} мин: {actual_text}"
                    
                    await message.answer(f"✅ Готово! Буду напоминать: **«{actual_text}»** каждые {num} мин.", parse_mode="Markdown")
                    return

    # 2. Попытка распознать дату/время через dateparser
    tz = pytz.timezone(TIMEZONE)
    parsed_date = dateparser.parse(
        text,
        settings={
            'TIMEZONE': TIMEZONE,
            'RETURN_AS_TIMEZONE_AWARE': True,
            'PREFER_DATES_FROM': 'future'
        }
    )

    if parsed_date and parsed_date > datetime.now(tz):
        date_keywords = ['в', 'завтра', 'сегодня', 'послезавтра', 'понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресенье', 'январ', 'феврал', 'март', 'апрел', 'май', 'июн', 'июл', 'август', 'сентябр', 'октябр', 'ноябр', 'декабр', ':']
        if any(keyword in lower_text for keyword in date_keywords):
            async def send_date_reminder():
                await bot.send_message(user_id, f"📅 **Напоминание по дате!**\n\nСобытие: *{text}*", parse_mode="Markdown")

            scheduler.add_job(send_date_reminder, 'date', run_date=parsed_date)
            
            formatted_time = parsed_date.strftime("%d.%m.%Y в %H:%M")
            await message.answer(
                f"🗓 Отлично! Я запланировал напоминание на **{formatted_time}**.\n📝 *{text}*",
                parse_mode="Markdown"
            )
            return

    # 3. Стандартная обработка обычного списка задач на день (построчно)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        if user_id not in user_tasks:
            user_tasks[user_id] = []
        user_tasks[user_id].extend(lines)
        
        await message.answer(
            f"✅ Добавлено задач в список на день: **{len(lines)}**!\nПосмотреть весь список: /list",
            parse_mode="Markdown"
        )


# --- ФОНОВЫЕ УТРЕННИЕ/ВЕЧЕРНИЕ РАССЫЛКИ ---

async def send_morning_motivation():
    for user_id in user_tasks.keys():
        quote = get_random_quote()
        try:
            await bot.send_message(
                user_id,
                f"☀️ **Доброе утро!**\n\n{quote}\n\nНе забудь прислать мне список задач на сегодня!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")

async def send_evening_reminder():
    for user_id, tasks in user_tasks.items():
        init_user_stats(user_id)
        stats = user_stats[user_id]
        
        if tasks:
            task_text = "\n".join([f"• {task}" for task in tasks])
            text = (
                "🌆 **Вечерняя проверка задач!**\n\n"
                "Вот что осталось невыполненным сегодня:\n"
                f"{task_text}\n\n"
                f"📊 Твоя статистика:\n"
                f"• Уровень: {stats['level']} (XP: {stats['xp']}/{stats['level']*100})\n"
                f"• Всего выполнено за всё время: {stats['completed_total']}\n\n"
                "Отметь выполненное через `/done <номера>` или отдохни и наберись сил к завтрашнему дню! 👏"
            )
        else:
            text = (
                "🌆 **Вечерняя проверка задач!**\n\n"
                "У тебя не осталось активных задач на сегодня. Ты отлично потрудился! 🌟\n\n"
                f"📊 Твой уровень: **{stats['level']}** (Всего выполнено задач: {stats['completed_total']})"
            )
        
        try:
            await bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")

# --- ЗАПУСК БОТА ---

async def main():
    scheduler.add_job(send_morning_motivation, 'cron', hour=9, minute=0)
    scheduler.add_job(send_evening_reminder, 'cron', hour=20, minute=0)
    scheduler.start()

    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

