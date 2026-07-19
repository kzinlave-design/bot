"""
Юзербот для Telegram на Telethon. Всё в одном файле.
Работает от лица ТВОЕГО аккаунта, поэтому все команды с точкой (.)
срабатывают ТОЛЬКО на твои собственные сообщения (outgoing=True) —
у других людей эти же слова никогда не вызовут команду, даже в общих чатах,
потому что Telegram помечает "outgoing" только сообщения твоей сессии.

Установка:
    pip install -r requirements.txt

Запуск (первый раз, локально):
    python userbot.py
    При первом запуске попросит номер телефона и код из Telegram —
    создастся файл userbot_session.session, никому его не показывай.

================================================================
ХОСТИНГ НА RENDER.COM ЧЕРЕЗ GITHUB
================================================================
API_ID и API_HASH зашиты прямо в коде ниже — значит репозиторий на GitHub
ОБЯЗАТЕЛЬНО должен быть приватным (Settings → Danger Zone → там же можно
сменить видимость), иначе любой сможет увидеть их в исходниках.

Шаг 1. Залей userbot.py и requirements.txt в приватный GitHub-репозиторий.

Шаг 2. На render.com: New + → Background Worker (не Web Service — бот
        ничего не слушает на HTTP-порту, это фоновый процесс).
        Подключи репозиторий и укажи:
            Build Command: pip install -r requirements.txt
            Start Command: python userbot.py

----------------------------------------------------------------
ВАРИАНТ: ХОСТИНГ КАК WEB SERVICE (если Background Worker недоступен)
----------------------------------------------------------------
Render засчитывает сервис "живым", только если он отвечает на HTTP-запросы
по порту из переменной окружения PORT. Юзербот сам по себе ничего не
слушает, поэтому в файл встроен крошечный веб-сервер (см. функцию
_run_web_server ниже) — он поднимается автоматически, если Render передал
переменную PORT, и никак не мешает командам бота.

New + → Web Service → подключи репозиторий → укажи:
    Build Command: pip install -r requirements.txt
    Start Command: python userbot.py
    Health Check Path: /
PORT Render передаёт сам, вручную его задавать не нужно.

⚠️ У Web Service на бесплатном тарифе Render есть нюанс: если на сервис
долго нет входящих HTTP-запросов, Render "усыпляет" его — а вместе с ним
и юзербот перестанет отвечать на команды в Telegram, пока не придёт новый
HTTP-запрос и Render не разбудит сервис. Из-за этого Background Worker —
более надёжный вариант именно для юзербота, который должен работать
постоянно. Web Service имеет смысл, если на твоём аккаунте Render
Background Worker недоступен или ты специально хочешь держать URL для
пинга (например, внешним UptimeRobot, чтобы не давать сервису засыпать).

Шаг 3. Первый запуск на Render потребует ввести код из Telegram — это
        нужно сделать через вкладку Shell на Render (там можно запустить
        интерактивную команду и ввести код). После этого появится файл
        userbot_session.session — но у Render бесплатный диск временный,
        поэтому при каждом новом деплое (например, при обновлении кода)
        файл будет создаваться заново и снова спросит код. Если это
        неудобно — скажи, добавлю вариант с постоянным диском (Render
        Disk, платно) или со StringSession (без файла вообще).

Шаг 4. Проверка: во вкладке Logs должно появиться
            🚀 Юзербот запускается...
            ✅ Юзербот запущен! Напиши себе .пмщ чтобы увидеть все команды.
"""

import asyncio
import os
import time
import random
import string
import ast
import operator
import hashlib
import base64 as b64
import uuid as uuid_lib
import urllib.parse
import math
from datetime import datetime, date
from zoneinfo import ZoneInfo

from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.types import InputMediaPoll, Poll, PollAnswer
import yt_dlp
import requests
import qrcode
import pyfiglet
from num2words import num2words
from aiohttp import web

# ==================== НАСТРОЙКИ ====================
API_ID = 35405573
API_HASH = "e0c264702c9dc3f9dc79a4c0385fca4c"

SESSION_NAME = "userbot_session"
DOWNLOADS_DIR = "downloads"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
START_TIME = time.time()
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ==================== СОСТОЯНИЕ АВТООТВЕТЧИКА ====================
autoresponder = {"enabled": False, "word": None, "text": None}
last_replied = {}  # chat_id -> timestamp последнего автоответа (кулдаун 1 час)

# ==================== ВАЛЮТЫ ====================
CURRENCY_WORDS = {
    "доллар": "USD", "доллара": "USD", "долларов": "USD", "usd": "USD",
    "тенге": "KZT", "kzt": "KZT",
    "манат": "AZN", "маната": "AZN", "манатов": "AZN", "манатах": "AZN", "azn": "AZN",
    "рубль": "RUB", "рубля": "RUB", "рублей": "RUB", "rub": "RUB",
    "евро": "EUR", "eur": "EUR",
    "гривна": "UAH", "гривны": "UAH", "гривен": "UAH", "uah": "UAH",
    "сом": "KGS", "сома": "KGS", "сомов": "KGS", "kgs": "KGS",
    "юань": "CNY", "юаня": "CNY", "cny": "CNY",
    "фунт": "GBP", "фунтов": "GBP", "gbp": "GBP",
    "лира": "TRY", "лир": "TRY", "try": "TRY",
    "сум": "UZS", "сума": "UZS", "сумов": "UZS", "uzs": "UZS",
}
TARGET_CURRENCIES = ["USD", "EUR", "RUB", "KZT", "UAH", "KGS", "AZN", "CNY", "GBP", "TRY", "UZS"]
CURRENCY_NAMES = {
    "USD": "Доллар США", "EUR": "Евро", "RUB": "Российский рубль", "KZT": "Тенге",
    "UAH": "Гривна", "KGS": "Киргизский сом", "AZN": "Азербайджанский манат",
    "CNY": "Юань", "GBP": "Фунт стерлингов", "TRY": "Турецкая лира", "UZS": "Узбекский сум",
}

async def get_rates(base):
    loop = asyncio.get_event_loop()
    def _fetch():
        r = requests.get(f"https://api.exchangerate-api.com/v4/latest/{base}", timeout=10)
        r.raise_for_status()
        return r.json()
    return await loop.run_in_executor(None, _fetch)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.к (\d+(?:\.\d+)?)\s*(\S+)"))
async def currency_handler(event):
    amount = float(event.pattern_match.group(1))
    word = event.pattern_match.group(2).lower()
    base = CURRENCY_WORDS.get(word)
    if not base:
        await event.edit(f"❌ Не знаю такую валюту: {word}\nПримеры: доллар, тенге, рубль, манат, евро, юань")
        return
    await event.edit("💱 Считаю курс...")
    try:
        data = await get_rates(base)
        rates = data["rates"]
        lines = [f"💰 {amount:g} {CURRENCY_NAMES.get(base, base)} =\n"]
        for cur in TARGET_CURRENCIES:
            if cur == base or cur not in rates:
                continue
            value = amount * rates[cur]
            lines.append(f"{CURRENCY_NAMES.get(cur, cur)}: {value:,.2f} {cur}")
        await event.edit("\n".join(lines))
    except Exception as e:
        await event.edit(f"❌ Не удалось получить курс: {e}")

# ==================== АВТООТВЕТЧИК ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.автоответ (?!выкл$|статус$)(\S+) (.+)"))
async def set_autoresponder(event):
    word = event.pattern_match.group(1).lower()
    text = event.pattern_match.group(2)
    autoresponder.update(enabled=True, word=word, text=text)
    last_replied.clear()
    await event.edit(f"✅ Автоответ включён\nСлово-триггер: {word}\nОтвет: {text}\n(одному собеседнику — не чаще раза в час)")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.автоответ выкл$"))
async def disable_autoresponder(event):
    autoresponder["enabled"] = False
    await event.edit("🔕 Автоответ выключен")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.автоответ статус$"))
async def status_autoresponder(event):
    if autoresponder["enabled"]:
        await event.edit(f"🔔 Автоответ включён\nСлово: {autoresponder['word']}\nОтвет: {autoresponder['text']}")
    else:
        await event.edit("🔕 Автоответ выключен")

@client.on(events.NewMessage(incoming=True))
async def autoresponder_trigger(event):
    if not autoresponder["enabled"]:
        return
    text = (event.raw_text or "").lower()
    if not autoresponder["word"] or autoresponder["word"] not in text:
        return
    chat_id = event.chat_id
    now = time.time()
    if now - last_replied.get(chat_id, 0) < 3600:
        return
    last_replied[chat_id] = now
    await event.reply(autoresponder["text"])

# ==================== СКАЧИВАНИЕ ВИДЕО ====================
async def download_video(url, out_path):
    ydl_opts = {"outtmpl": out_path, "format": "best[ext=mp4]/best", "quiet": True, "no_warnings": True, "noplaylist": True}
    loop = asyncio.get_event_loop()
    def _run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    await loop.run_in_executor(None, _run)

async def handle_download(event, url, source_name):
    file_path = os.path.join(DOWNLOADS_DIR, f"{event.id}.mp4")
    await event.edit(f"⏳ Скачиваю видео с {source_name}...")
    try:
        await download_video(url, file_path)
        await event.edit("📤 Отправляю файл...")
        await client.send_file(event.chat_id, file_path, reply_to=event.reply_to_msg_id, caption=f"📹 {source_name}")
        await event.delete()
    except Exception as e:
        await event.edit(f"❌ Не удалось скачать видео: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ют (.+)"))
async def yt_handler(event):
    await handle_download(event, event.pattern_match.group(1).strip(), "YouTube")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.тт (.+)"))
async def tt_handler(event):
    await handle_download(event, event.pattern_match.group(1).strip(), "TikTok")

# ==================== АНИМАЦИИ ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.загрузка$"))
async def loading_anim(event):
    for i in range(0, 101, 10):
        bar = "█" * (i // 10) + "░" * (10 - i // 10)
        await event.edit(f"⏳ Загрузка: [{bar}] {i}%")
        await asyncio.sleep(0.3)
    await event.edit("✅ Готово!")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.печать (.+)"))
async def typewriter_anim(event):
    text = event.pattern_match.group(1)
    current = ""
    for ch in text:
        current += ch
        await event.edit(current + "▌")
        await asyncio.sleep(0.08)
    await event.edit(text)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.волна (.+)"))
async def wave_anim(event):
    text = event.pattern_match.group(1)
    for i in range(len(text)):
        await event.edit(text[:i] + text[i].upper() + text[i + 1:])
        await asyncio.sleep(0.15)
    await event.edit(text)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.часы$"))
async def clock_anim(event):
    clocks = ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"]
    for _ in range(2):
        for c in clocks:
            await event.edit(f"{c} Тик-так...")
            await asyncio.sleep(0.1)
    await event.edit("⏰ Время вышло!")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.взрыв$"))
async def explosion_anim(event):
    for f in ["💣", "💣", "💥", "💥💥", "💥💥💥", "🔥🔥🔥", "💨💨", "💨"]:
        await event.edit(f)
        await asyncio.sleep(0.25)
    await event.edit("☠️ Бум!")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.пульс (.+)"))
async def pulse_anim(event):
    text = event.pattern_match.group(1)
    frames = [f"• {text} •", f"·• {text} •·", f"··• {text} •··", f"·• {text} •·"]
    for _ in range(3):
        for f in frames:
            await event.edit(f)
            await asyncio.sleep(0.2)
    await event.edit(text)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.огонь$"))
async def fire_anim(event):
    for i in range(1, 8):
        await event.edit("🔥" * i)
        await asyncio.sleep(0.2)
    await event.edit("🔥" * 7 + "\nВСЁ ГОРИТ! 🔥")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.светофор$"))
async def traffic_light_anim(event):
    for lights, text in [("🔴⚪⚪", "Стой"), ("🔴🟡⚪", "Приготовься"), ("⚪⚪🟢", "Езжай!")]:
        await event.edit(f"{lights}\n{text}")
        await asyncio.sleep(1)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.матрица$"))
async def matrix_anim(event):
    chars = "01アイウエオカキクケコ"
    for _ in range(10):
        line = "".join(random.choice(chars) for _ in range(20))
        await event.edit(f"```\n{line}\n```")
        await asyncio.sleep(0.15)
    await event.edit("💻 Матрица завершена")

# ==================== УТИЛИТЫ ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.пинг$"))
async def ping_handler(event):
    start = time.time()
    await event.edit("🏓 Понг...")
    await event.edit(f"🏓 Понг! `{(time.time() - start) * 1000:.2f} ms`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.аптайм$"))
async def uptime_handler(event):
    seconds = int(time.time() - START_TIME)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    await event.edit(f"⏱ Аптайм: {h}ч {m}м {s}с")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.id$"))
async def id_handler(event):
    me = await client.get_me()
    await event.edit(f"🆔 Мой ID: `{me.id}`\n💬 ID чата: `{event.chat_id}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.аватар$"))
async def avatar_handler(event):
    me = await client.get_me()
    path = await client.download_profile_photo(me, file=os.path.join(DOWNLOADS_DIR, "avatar.jpg"))
    if path:
        await client.send_file(event.chat_id, path, reply_to=event.reply_to_msg_id)
        await event.delete()
        os.remove(path)
    else:
        await event.edit("❌ У тебя нет аватарки")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.монета$"))
async def coin_handler(event):
    await event.edit(f"🪙 {random.choice(['Орёл', 'Решка'])}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.кубик$"))
async def dice_handler(event):
    await event.edit(f"🎲 Выпало: {random.randint(1, 6)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.число (\d+)$"))
async def randnum_handler(event):
    n = int(event.pattern_match.group(1))
    await event.edit(f"🔢 Случайное число: {random.randint(1, max(1, n))}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.выбери (.+)"))
async def choose_handler(event):
    options = [o.strip() for o in event.pattern_match.group(1).split(",") if o.strip()]
    if len(options) < 2:
        await event.edit("❌ Укажи минимум 2 варианта через запятую")
        return
    await event.edit(f"🤔 Мой выбор: **{random.choice(options)}**")

BALL_ANSWERS = ["Да", "Нет", "Возможно", "Определённо да", "Определённо нет", "Спроси позже", "Сложно сказать", "Скорее да", "Скорее нет"]

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.шар$"))
async def ball_handler(event):
    await event.edit(f"🎱 {random.choice(BALL_ANSWERS)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.зеркало (.+)"))
async def mirror_handler(event):
    await event.edit(event.pattern_match.group(1)[::-1])

def _build_map(upper_start, lower_start, digit_start=None):
    mapping = {}
    for i in range(26):
        mapping[ord("A") + i] = chr(upper_start + i)
        mapping[ord("a") + i] = chr(lower_start + i)
    if digit_start is not None:
        for i in range(10):
            mapping[ord("0") + i] = chr(digit_start + i)
    return mapping

BOLD_MAP = _build_map(0x1D400, 0x1D41A, 0x1D7CE)
ITALIC_MAP = _build_map(0x1D434, 0x1D44E)
ITALIC_MAP[ord("h")] = chr(0x210E)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.жирный (.+)"))
async def bold_handler(event):
    await event.edit(event.pattern_match.group(1).translate(BOLD_MAP))

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.курсив (.+)"))
async def italic_handler(event):
    await event.edit(event.pattern_match.group(1).translate(ITALIC_MAP))

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.капс (.+)"))
async def caps_handler(event):
    await event.edit(event.pattern_match.group(1).upper())

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.маленькие (.+)"))
async def lower_handler(event):
    await event.edit(event.pattern_match.group(1).lower())

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.пароль(?: (\d+))?$"))
async def password_handler(event):
    length = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 12
    length = max(4, min(length, 64))
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    await event.edit(f"🔐 Пароль: `{''.join(random.choice(chars) for _ in range(length))}`")

JOKES = [
    "Программист — это устройство для превращения кофе в баги.",
    "Работает — не трогай. Не работает — тоже не трогай, зови того, кто писал.",
    "У оптимиста стакан наполовину полон, у пессимиста — пуст, у программиста — в два раза больше памяти, чем нужно.",
]
QUOTES = [
    "Единственный способ сделать великую работу — любить то, что ты делаешь.",
    "Не бойся медленно идти, бойся остановиться.",
    "Всё, что ты можешь представить — реально.",
]

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.анекдот$"))
async def joke_handler(event):
    await event.edit(f"😄 {random.choice(JOKES)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.цитата$"))
async def quote_handler(event):
    await event.edit(f"💭 {random.choice(QUOTES)}")

_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod,
}

def safe_eval(expr):
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("unsupported expression")
    return _eval(ast.parse(expr, mode="eval").body)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.калькулятор (.+)"))
async def calc_handler(event):
    expr = event.pattern_match.group(1)
    try:
        await event.edit(f"🧮 {expr} = {safe_eval(expr)}")
    except Exception:
        await event.edit("❌ Не могу посчитать это выражение")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.qr (.+)"))
async def qr_handler(event):
    text = event.pattern_match.group(1)
    path = os.path.join(DOWNLOADS_DIR, f"qr_{event.id}.png")
    qrcode.make(text).save(path)
    await client.send_file(event.chat_id, path, reply_to=event.reply_to_msg_id, caption="📱 QR-код")
    await event.delete()
    os.remove(path)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.погода (.+)"))
async def weather_handler(event):
    city = event.pattern_match.group(1)
    await event.edit("🌤 Узнаю погоду...")
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            r = requests.get(f"https://wttr.in/{city}?format=3&lang=ru", timeout=10)
            r.raise_for_status()
            return r.text
        result = await loop.run_in_executor(None, _fetch)
        await event.edit(f"🌤 {result}")
    except Exception as e:
        await event.edit(f"❌ Не удалось получить погоду: {e}")

CITY_TIMEZONES = {
    "москва": "Europe/Moscow", "астана": "Asia/Almaty", "алматы": "Asia/Almaty",
    "баку": "Asia/Baku", "ташкент": "Asia/Tashkent", "лондон": "Europe/London",
    "нью-йорк": "America/New_York", "токио": "Asia/Tokyo", "пекин": "Asia/Shanghai",
    "дубай": "Asia/Dubai", "париж": "Europe/Paris", "берлин": "Europe/Berlin",
}

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.время (.+)"))
async def time_handler(event):
    city = event.pattern_match.group(1).lower()
    tz_name = CITY_TIMEZONES.get(city)
    if not tz_name:
        await event.edit(f"❌ Не знаю часовой пояс для: {city}")
        return
    now = datetime.now(ZoneInfo(tz_name))
    await event.edit(f"🕒 Время в {city.title()}: {now.strftime('%H:%M:%S, %d.%m.%Y')}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.инфочат$"))
async def chatinfo_handler(event):
    chat = await event.get_chat()
    name = getattr(chat, "title", None) or getattr(chat, "first_name", "Личка")
    await event.edit(f"ℹ️ Чат: {name}\n🆔 ID: `{event.chat_id}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.чистка (\d+)$"))
async def purge_handler(event):
    count = min(int(event.pattern_match.group(1)), 100)
    messages = await client.get_messages(event.chat_id, limit=count, from_user="me")
    await client.delete_messages(event.chat_id, [m.id for m in messages])

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.цвет$"))
async def color_handler(event):
    await event.edit(f"🎨 Случайный цвет: #{random.randint(0, 0xFFFFFF):06X}")

TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.транслит (.+)"))
async def translit_handler(event):
    text = event.pattern_match.group(1).lower()
    await event.edit("".join(TRANSLIT_MAP.get(ch, ch) for ch in text))

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.binary (.+)"))
async def to_binary_handler(event):
    text = event.pattern_match.group(1)
    result = " ".join(format(ord(c), "08b") for c in text)
    await event.edit(f"```\n{result}\n```")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.debinary (.+)"))
async def from_binary_handler(event):
    try:
        chars = [chr(int(b, 2)) for b in event.pattern_match.group(1).split()]
        await event.edit("".join(chars))
    except Exception:
        await event.edit("❌ Некорректный двоичный код")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.анаграмма (.+)"))
async def anagram_handler(event):
    letters = list(event.pattern_match.group(1))
    random.shuffle(letters)
    await event.edit("".join(letters))

# ==================== ШИФРЫ И КОДИРОВКИ ====================
MORSE_MAP = {
    "а": ".-", "б": "-...", "в": ".--", "г": "--.", "д": "-..", "е": ".", "ё": ".",
    "ж": "...-", "з": "--..", "и": "..", "й": ".---", "к": "-.-", "л": ".-..",
    "м": "--", "н": "-.", "о": "---", "п": ".--.", "р": ".-.", "с": "...",
    "т": "-", "у": "..-", "ф": "..-.", "х": "....", "ц": "-.-.", "ч": "---.",
    "ш": "----", "щ": "--.-", "ъ": "--.--", "ы": "-.--", "ь": "-..-", "э": "..-..",
    "ю": "..--", "я": ".-.-",
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.",
    "g": "--.", "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..",
    "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-",
    "y": "-.--", "z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    " ": "/",
}
MORSE_REVERSE = {v: k for k, v in MORSE_MAP.items()}

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.морзе (.+)"))
async def morse_handler(event):
    text = event.pattern_match.group(1).lower()
    try:
        code = " ".join(MORSE_MAP[ch] for ch in text)
        await event.edit(f"📡 `{code}`")
    except KeyError:
        await event.edit("❌ Есть символ, для которого нет кода Морзе")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.изморзе (.+)"))
async def unmorse_handler(event):
    code = event.pattern_match.group(1).split(" ")
    try:
        text = "".join(MORSE_REVERSE[c] for c in code)
        await event.edit(f"📡 {text}")
    except KeyError:
        await event.edit("❌ Некорректный код Морзе")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.base64 (.+)"))
async def to_base64_handler(event):
    text = event.pattern_match.group(1)
    result = b64.b64encode(text.encode("utf-8")).decode("utf-8")
    await event.edit(f"🔐 `{result}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.debase64 (.+)"))
async def from_base64_handler(event):
    text = event.pattern_match.group(1)
    try:
        result = b64.b64decode(text).decode("utf-8")
        await event.edit(f"🔓 {result}")
    except Exception:
        await event.edit("❌ Некорректная base64-строка")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.md5 (.+)"))
async def md5_handler(event):
    text = event.pattern_match.group(1)
    await event.edit(f"🔑 MD5: `{hashlib.md5(text.encode('utf-8')).hexdigest()}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.sha256 (.+)"))
async def sha256_handler(event):
    text = event.pattern_match.group(1)
    await event.edit(f"🔑 SHA256: `{hashlib.sha256(text.encode('utf-8')).hexdigest()}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.uuid$"))
async def uuid_handler(event):
    await event.edit(f"🆔 `{uuid_lib.uuid4()}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.шифр (\d+) (.+)"))
async def caesar_encrypt_handler(event):
    shift = int(event.pattern_match.group(1))
    text = event.pattern_match.group(2)
    alphabets = ("абвгдежзийклмнопрстуфхцчшщъыьэюя", "abcdefghijklmnopqrstuvwxyz")
    result = []
    for ch in text:
        moved = False
        for alpha in alphabets:
            full = alpha + alpha.upper()
            if ch.lower() in alpha:
                base = alpha if ch.islower() else alpha.upper()
                idx = (base.index(ch) + shift) % len(base)
                result.append(base[idx])
                moved = True
                break
        if not moved:
            result.append(ch)
    await event.edit(f"🔒 {''.join(result)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.дешифр (\d+) (.+)"))
async def caesar_decrypt_handler(event):
    shift = -int(event.pattern_match.group(1))
    text = event.pattern_match.group(2)
    alphabets = ("абвгдежзийклмнопрстуфхцчшщъыьэюя", "abcdefghijklmnopqrstuvwxyz")
    result = []
    for ch in text:
        moved = False
        for alpha in alphabets:
            if ch.lower() in alpha:
                base = alpha if ch.islower() else alpha.upper()
                idx = (base.index(ch) + shift) % len(base)
                result.append(base[idx])
                moved = True
                break
        if not moved:
            result.append(ch)
    await event.edit(f"🔓 {''.join(result)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.палиндром (.+)"))
async def palindrome_handler(event):
    text = event.pattern_match.group(1)
    clean = "".join(ch.lower() for ch in text if ch.isalnum())
    is_pal = clean == clean[::-1]
    await event.edit(f"{'✅ Это палиндром!' if is_pal else '❌ Не палиндром'}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.словами (-?\d+)$"))
async def number_to_words_handler(event):
    n = int(event.pattern_match.group(1))
    try:
        await event.edit(f"🔢 {num2words(n, lang='ru')}")
    except Exception as e:
        await event.edit(f"❌ Не удалось преобразовать: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ascii (.+)"))
async def ascii_art_handler(event):
    text = event.pattern_match.group(1)
    try:
        art = pyfiglet.figlet_format(text)
        await event.edit(f"```\n{art}\n```")
    except Exception as e:
        await event.edit(f"❌ Не удалось: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.флаг ([a-zA-Zа-яА-Я]{2})$"))
async def flag_handler(event):
    code = event.pattern_match.group(1).upper()
    try:
        flag = "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)
        await event.edit(f"🏳️ {flag}")
    except Exception:
        await event.edit("❌ Укажи двухбуквенный код страны, например: us, ru, kz")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.эмодзи (.+)"))
async def emoji_letters_handler(event):
    text = event.pattern_match.group(1).upper()
    result = []
    for ch in text:
        if ch.isalpha() and "A" <= ch <= "Z":
            result.append(chr(0x1F1E6 + ord(ch) - ord("A")))
        elif ch.isdigit():
            keycaps = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
            result.append(keycaps[int(ch)])
        elif ch == " ":
            result.append("　")
        else:
            result.append(ch)
    await event.edit(" ".join(result))

# ==================== СЛУЧАЙНЫЕ ГЕНЕРАТОРЫ ====================
NAME_FIRST_PARTS = ["Ара", "Бел", "Вел", "Гор", "Дар", "Зор", "Кир", "Лун", "Мир", "Нар", "Рав", "Тор"]
NAME_LAST_PARTS = ["ион", "ель", "гард", "мир", "слав", "дор", "рон", "вин", "тан", "лен"]

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.имя$"))
async def random_name_handler(event):
    name = random.choice(NAME_FIRST_PARTS) + random.choice(NAME_LAST_PARTS)
    await event.edit(f"🧙 Твоё фэнтези-имя: **{name}**")

COMPLIMENTS = [
    "Ты сегодня особенно продуктивен!",
    "У тебя отличное чувство стиля.",
    "Твоя идея реально крутая.",
    "С тобой приятно общаться.",
    "Ты справляешься лучше, чем думаешь.",
]

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.комплимент$"))
async def compliment_handler(event):
    await event.edit(f"💫 {random.choice(COMPLIMENTS)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.подбросить (\d+)d(\d+)$"))
async def dice_notation_handler(event):
    count = min(int(event.pattern_match.group(1)), 20)
    sides = min(int(event.pattern_match.group(2)), 1000)
    rolls = [random.randint(1, sides) for _ in range(count)]
    await event.edit(f"🎲 {count}d{sides}: {', '.join(map(str, rolls))}\nСумма: **{sum(rolls)}**")

# ==================== ВНЕШНИЕ API ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.прогноз (.+)"))
async def forecast_handler(event):
    city = event.pattern_match.group(1)
    await event.edit("🌦 Смотрю прогноз...")
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            r.raise_for_status()
            return r.json()
        data = await loop.run_in_executor(None, _fetch)
        lines = [f"🌦 Прогноз для {city.title()}:\n"]
        for day in data["weather"][:3]:
            date = day["date"]
            avg = day["avgtempC"]
            desc = day["hourly"][4]["lang_ru"][0]["value"] if "lang_ru" in day["hourly"][4] else day["hourly"][4]["weatherDesc"][0]["value"]
            lines.append(f"📅 {date}: {avg}°C, {desc}")
        await event.edit("\n".join(lines))
    except Exception as e:
        await event.edit(f"❌ Не удалось получить прогноз: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ip (.+)"))
async def ip_lookup_handler(event):
    query = event.pattern_match.group(1).strip()
    await event.edit("🌐 Ищу информацию...")
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            r = requests.get(f"http://ip-api.com/json/{query}?lang=ru", timeout=10)
            r.raise_for_status()
            return r.json()
        data = await loop.run_in_executor(None, _fetch)
        if data.get("status") != "success":
            await event.edit(f"❌ Не удалось найти: {data.get('message', query)}")
            return
        await event.edit(
            f"🌐 {query}\n📍 Страна: {data.get('country')}\n🏙 Город: {data.get('city')}\n"
            f"🏢 Провайдер: {data.get('isp')}\n🗺 Координаты: {data.get('lat')}, {data.get('lon')}"
        )
    except Exception as e:
        await event.edit(f"❌ Ошибка: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.сократить (\S+)$"))
async def shorten_url_handler(event):
    url = event.pattern_match.group(1)
    await event.edit("🔗 Сокращаю ссылку...")
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            r = requests.get("https://is.gd/create.php", params={"format": "simple", "url": url}, timeout=10)
            r.raise_for_status()
            return r.text
        result = await loop.run_in_executor(None, _fetch)
        if result.startswith("Error"):
            await event.edit(f"❌ {result}")
        else:
            await event.edit(f"🔗 {result}")
    except Exception as e:
        await event.edit(f"❌ Ошибка: {e}")

ZODIAC_MAP = {
    "овен": "aries", "телец": "taurus", "близнецы": "gemini", "рак": "cancer",
    "лев": "leo", "дева": "virgo", "весы": "libra", "скорпион": "scorpio",
    "стрелец": "sagittarius", "козерог": "capricorn", "водолей": "aquarius", "рыбы": "pisces",
}

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.гороскоп (.+)"))
async def horoscope_handler(event):
    sign_ru = event.pattern_match.group(1).lower().strip()
    sign = ZODIAC_MAP.get(sign_ru)
    if not sign:
        await event.edit("❌ Укажи знак зодиака по-русски: овен, телец, близнецы и т.д.")
        return
    await event.edit("🔮 Смотрю в звёзды...")
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            r = requests.get(
                "https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily",
                params={"sign": sign, "day": "today"}, timeout=10,
            )
            r.raise_for_status()
            return r.json()
        data = await loop.run_in_executor(None, _fetch)
        horoscope = data.get("data", {}).get("horoscope_data", "Нет данных")
        await event.edit(f"🔮 Гороскоп для «{sign_ru}»:\n{horoscope}")
    except Exception as e:
        await event.edit(f"❌ Гороскоп сейчас недоступен: {e}")

# ==================== TELEGRAM-ДЕЙСТВИЯ ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.закреп$"))
async def pin_handler(event):
    if not event.reply_to_msg_id:
        await event.edit("❌ Ответь этой командой на сообщение, которое нужно закрепить")
        return
    try:
        await client.pin_message(event.chat_id, event.reply_to_msg_id, notify=False)
        await event.edit("📌 Сообщение закреплено")
    except Exception as e:
        await event.edit(f"❌ Не удалось закрепить: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.открепить$"))
async def unpin_handler(event):
    try:
        await client.unpin_message(event.chat_id)
        await event.edit("📌 Всё откреплено")
    except Exception as e:
        await event.edit(f"❌ Не удалось открепить: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.опрос (.+)"))
async def poll_handler(event):
    parts = [p.strip() for p in event.pattern_match.group(1).split("|")]
    if len(parts) < 3:
        await event.edit("❌ Формат: .опрос Вопрос | вариант1 | вариант2 | ...")
        return
    question, options = parts[0], parts[1:10]
    try:
        answers = [PollAnswer(text=opt, option=bytes([i])) for i, opt in enumerate(options)]
        media = InputMediaPoll(poll=Poll(id=random.randint(0, 2**31 - 1), question=question, answers=answers))
        await client.send_file(event.chat_id, file=media)
        await event.delete()
    except Exception as e:
        await event.edit(f"❌ Не удалось создать опрос: {e}\n(возможно, нужно обновить telethon)")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.сохранить$"))
async def save_to_saved_handler(event):
    if not event.reply_to_msg_id:
        await event.edit("❌ Ответь на сообщение, которое нужно сохранить")
        return
    try:
        msg = await event.get_reply_message()
        await client.forward_messages("me", msg)
        await event.edit("💾 Сохранено в Избранное")
    except Exception as e:
        await event.edit(f"❌ Не удалось сохранить: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.переслать (\d+)$"))
async def forward_last_handler(event):
    count = min(int(event.pattern_match.group(1)), 50)
    try:
        messages = await client.get_messages(event.chat_id, limit=count, from_user="me")
        await client.forward_messages("me", messages)
        await event.edit(f"💾 Переслано {len(messages)} сообщений в Избранное")
    except Exception as e:
        await event.edit(f"❌ Не удалось переслать: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.статус (.+)"))
async def bio_handler(event):
    text = event.pattern_match.group(1)
    try:
        await client(UpdateProfileRequest(about=text))
        await event.edit(f"✅ Статус (о себе) обновлён:\n{text}")
    except Exception as e:
        await event.edit(f"❌ Не удалось обновить: {e}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.имяпрофиля (.+)"))
async def profile_name_handler(event):
    text = event.pattern_match.group(1)
    try:
        await client(UpdateProfileRequest(first_name=text))
        await event.edit(f"✅ Имя профиля изменено на: {text}")
    except Exception as e:
        await event.edit(f"❌ Не удалось обновить: {e}")

# ==================== ЕЩЁ АНИМАЦИИ ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.спиннер$"))
async def spinner_anim(event):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for _ in range(3):
        for f in frames:
            await event.edit(f"{f} Обрабатываю...")
            await asyncio.sleep(0.08)
    await event.edit("✅ Готово!")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.бегущаястрока (.+)"))
async def marquee_anim(event):
    text = event.pattern_match.group(1)
    width = 15
    padded = " " * width + text + " " * width
    for i in range(len(padded) - width):
        await event.edit(f"`{padded[i:i + width]}`")
        await asyncio.sleep(0.15)
    await event.edit(text)

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.таймер (\d+)$"))
async def timer_handler(event):
    seconds = min(int(event.pattern_match.group(1)), 60)
    for remaining in range(seconds, 0, -1):
        await event.edit(f"⏳ Осталось: {remaining} сек.")
        await asyncio.sleep(1)
    await event.edit("⏰ Время вышло!")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.напоминание (\d+) (.+)"))
async def reminder_handler(event):
    delay = min(int(event.pattern_match.group(1)), 21600)  # максимум 6 часов
    text = event.pattern_match.group(2)
    chat_id = event.chat_id
    await event.edit(f"⏰ Напомню через {delay} сек.: «{text}»")

    async def _remind():
        await asyncio.sleep(delay)
        await client.send_message(chat_id, f"🔔 Напоминание: {text}")

    asyncio.create_task(_remind())

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.таблицаумножения (\d+)$"))
async def multiplication_table_handler(event):
    n = min(int(event.pattern_match.group(1)), 20)
    lines = [f"{n} × {i} = {n * i}" for i in range(1, 11)]
    await event.edit("✖️ Таблица умножения:\n```\n" + "\n".join(lines) + "\n```")

# ==================== ТЕКСТ И МАТЕМАТИКА ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.длина (.+)"))
async def text_stats_handler(event):
    text = event.pattern_match.group(1)
    words = len(text.split())
    chars = len(text)
    no_spaces = len(text.replace(" ", ""))
    await event.edit(f"📊 Символов: {chars}\nБез пробелов: {no_spaces}\nСлов: {words}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.повторить (\d+) (.+)"))
async def repeat_handler(event):
    n = min(int(event.pattern_match.group(1)), 50)
    text = event.pattern_match.group(2)
    await event.edit("\n".join([text] * n))

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.хэштеги (.+)"))
async def hashtags_handler(event):
    text = event.pattern_match.group(1)
    words = [w.strip(string.punctuation) for w in text.split()]
    tags = " ".join(f"#{w}" for w in words if w)
    await event.edit(f"🏷 {tags}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.температура (-?\d+(?:\.\d+)?)\s*([cfk])\s*([cfk])$"))
async def temperature_handler(event):
    value = float(event.pattern_match.group(1))
    from_u = event.pattern_match.group(2).lower()
    to_u = event.pattern_match.group(3).lower()
    celsius = {"c": value, "f": (value - 32) * 5 / 9, "k": value - 273.15}[from_u]
    result = {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15}[to_u]
    await event.edit(f"🌡 {value}°{from_u.upper()} = {result:.2f}°{to_u.upper()}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.монетасерия (\d+)$"))
async def coin_series_handler(event):
    n = min(int(event.pattern_match.group(1)), 1000)
    flips = [random.choice(["О", "Р"]) for _ in range(n)]
    heads = flips.count("О")
    await event.edit(f"🪙 {''.join(flips[:100])}{'...' if n > 100 else ''}\nОрёл: {heads}, Решка: {n - heads}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.простое (\d+)$"))
async def prime_check_handler(event):
    n = int(event.pattern_match.group(1))
    is_prime = n > 1 and all(n % i != 0 for i in range(2, int(n ** 0.5) + 1))
    await event.edit(f"{'✅' if is_prime else '❌'} {n} {'простое' if is_prime else 'не простое'} число")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.факториал (\d+)$"))
async def factorial_handler(event):
    n = int(event.pattern_match.group(1))
    if n > 500:
        await event.edit("❌ Слишком большое число (макс. 500)")
        return
    await event.edit(f"❗ {n}! = {math.factorial(n)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.фибоначчи (\d+)$"))
async def fibonacci_handler(event):
    n = min(int(event.pattern_match.group(1)), 50)
    seq = [0, 1]
    for _ in range(n - 2):
        seq.append(seq[-1] + seq[-2])
    await event.edit(f"🔢 {', '.join(map(str, seq[:n]))}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.нод (\d+) (\d+)$"))
async def gcd_handler(event):
    a, b = int(event.pattern_match.group(1)), int(event.pattern_match.group(2))
    await event.edit(f"🔢 НОД({a}, {b}) = {math.gcd(a, b)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.нок (\d+) (\d+)$"))
async def lcm_handler(event):
    a, b = int(event.pattern_match.group(1)), int(event.pattern_match.group(2))
    await event.edit(f"🔢 НОК({a}, {b}) = {abs(a * b) // math.gcd(a, b)}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.системасчисления (\S+) (bin|dec|hex|oct) (bin|dec|hex|oct)$"))
async def base_convert_handler(event):
    raw, from_base, to_base = event.pattern_match.group(1), event.pattern_match.group(2), event.pattern_match.group(3)
    bases = {"bin": 2, "dec": 10, "hex": 16, "oct": 8}
    try:
        n = int(raw, bases[from_base])
        result = {"bin": bin(n)[2:], "dec": str(n), "hex": hex(n)[2:], "oct": oct(n)[2:]}[to_base]
        await event.edit(f"🔢 {raw} ({from_base}) → {result} ({to_base})")
    except ValueError:
        await event.edit(f"❌ «{raw}» — некорректное число для системы {from_base}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.хекс (.+)"))
async def to_hex_handler(event):
    text = event.pattern_match.group(1)
    await event.edit(f"🔡 `{text.encode('utf-8').hex()}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.изхекс (.+)"))
async def from_hex_handler(event):
    hex_str = event.pattern_match.group(1).replace(" ", "")
    try:
        await event.edit(bytes.fromhex(hex_str).decode("utf-8"))
    except Exception:
        await event.edit("❌ Некорректная hex-строка")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.урл (.+)"))
async def url_encode_handler(event):
    text = event.pattern_match.group(1)
    await event.edit(f"🔗 `{urllib.parse.quote(text)}`")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.изурл (.+)"))
async def url_decode_handler(event):
    text = event.pattern_match.group(1)
    await event.edit(f"🔗 {urllib.parse.unquote(text)}")

# ==================== ДАТЫ ====================
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.возраст (\d{2})\.(\d{2})\.(\d{4})$"))
async def age_handler(event):
    d, m, y = int(event.pattern_match.group(1)), int(event.pattern_match.group(2)), int(event.pattern_match.group(3))
    try:
        birth = date(y, m, d)
    except ValueError:
        await event.edit("❌ Некорректная дата")
        return
    today = date.today()
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    await event.edit(f"🎂 Возраст: {age} лет")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.днейдо (\d{2})\.(\d{2})\.(\d{4})$"))
async def days_until_handler(event):
    d, m, y = int(event.pattern_match.group(1)), int(event.pattern_match.group(2)), int(event.pattern_match.group(3))
    try:
        target = date(y, m, d)
    except ValueError:
        await event.edit("❌ Некорректная дата")
        return
    delta = (target - date.today()).days
    if delta >= 0:
        await event.edit(f"📅 Осталось дней: {delta}")
    else:
        await event.edit(f"📅 Прошло дней: {-delta}")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.високосный (\d{4})$"))
async def leap_year_handler(event):
    y = int(event.pattern_match.group(1))
    is_leap = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
    await event.edit(f"{'✅' if is_leap else '❌'} {y} {'високосный' if is_leap else 'не високосный'} год")

WEEKDAY_NAMES = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.деньнедели (\d{2})\.(\d{2})\.(\d{4})$"))
async def weekday_handler(event):
    d, m, y = int(event.pattern_match.group(1)), int(event.pattern_match.group(2)), int(event.pattern_match.group(3))
    try:
        target = date(y, m, d)
    except ValueError:
        await event.edit("❌ Некорректная дата")
        return
    await event.edit(f"📆 {target.strftime('%d.%m.%Y')} — {WEEKDAY_NAMES[target.weekday()]}")

# ==================== ЗАМЕТКИ ====================
notes_storage = {}  # chat_id -> list[str]

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.заметка (.+)"))
async def add_note_handler(event):
    text = event.pattern_match.group(1)
    notes_storage.setdefault(event.chat_id, []).append(text)
    await event.edit(f"📝 Заметка сохранена ({len(notes_storage[event.chat_id])} шт. в этом чате)")

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.заметки$"))
async def list_notes_handler(event):
    notes = notes_storage.get(event.chat_id, [])
    if not notes:
        await event.edit("📝 Заметок пока нет")
        return
    lines = [f"{i}. {n}" for i, n in enumerate(notes, 1)]
    await event.edit("📝 Заметки:\n" + "\n".join(lines))

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.заметкиочистить$"))
async def clear_notes_handler(event):
    notes_storage[event.chat_id] = []
    await event.edit("🗑 Все заметки в этом чате удалены")

# ==================== СПИСОК КОМАНД ====================
HELP = {
    "🎬 Скачивание видео": {".ют <ссылка>": "Скачать с YouTube", ".тт <ссылка>": "Скачать с TikTok"},
    "💱 Курс валют": {".к 500 долларов": "Показать курс в KZT/RUB/EUR и др."},
    "🤖 Автоответчик": {
        ".автоответ <слово> <текст>": "Включить (ответ раз в час одному человеку)",
        ".автоответ выкл": "Выключить", ".автоответ статус": "Текущий статус",
    },
    "✨ Анимации": {
        ".загрузка": "Прогресс-бар", ".печать <текст>": "Печатная машинка", ".волна <текст>": "Волна по буквам",
        ".часы": "Тикающие часы", ".взрыв": "Взрыв", ".пульс <текст>": "Пульсация",
        ".огонь": "Разгорающийся огонь", ".светофор": "Светофор", ".матрица": "Матрица",
    },
    "🎉 Фишки": {
        ".id": "Твой ID и ID чата", ".аватар": "Прислать твою аватарку", ".монета": "Орёл/решка",
        ".кубик": "Бросить кубик", ".число <N>": "Случайное число до N", ".выбери <a, b, c>": "Случайный выбор",
        ".шар": "Магический шар", ".зеркало <текст>": "Развернуть текст", ".жирный <текст>": "𝗝𝗶𝗿𝗻𝘆𝗶",
        ".курсив <текст>": "𝘐𝘵𝘢𝘭𝘪𝘤", ".капс <текст>": "В ВЕРХНИЙ РЕГИСТР", ".маленькие <текст>": "в нижний регистр",
        ".пароль <N>": "Сгенерировать пароль", ".анекдот": "Случайная шутка", ".цитата": "Случайная цитата",
        ".калькулятор <выражение>": "Посчитать", ".qr <текст>": "Сделать QR-код", ".погода <город>": "Погода",
        ".время <город>": "Время в другом городе", ".инфочат": "Инфо о чате", ".чистка <N>": "Удалить N своих сообщений",
        ".цвет": "Случайный HEX-цвет", ".транслит <текст>": "Транслитерация", ".binary <текст>": "В двоичный код",
        ".debinary <код>": "Из двоичного кода", ".анаграмма <текст>": "Перемешать буквы",
    },
    "🔐 Шифры и коды": {
        ".морзе <текст>": "В код Морзе", ".изморзе <код>": "Из кода Морзе",
        ".base64 <текст>": "Закодировать в base64", ".debase64 <код>": "Раскодировать base64",
        ".md5 <текст>": "MD5-хеш", ".sha256 <текст>": "SHA256-хеш", ".uuid": "Сгенерировать UUID",
        ".шифр <сдвиг> <текст>": "Шифр Цезаря", ".дешифр <сдвиг> <текст>": "Расшифровать Цезаря",
        ".палиндром <текст>": "Проверить, палиндром ли", ".словами <число>": "Число прописью",
        ".ascii <текст>": "ASCII-арт из текста (латиница)", ".флаг <код>": "Флаг страны по коду (ru, us, kz...)",
        ".эмодзи <текст>": "Текст крупными эмодзи-буквами",
    },
    "🎲 Случайности": {
        ".имя": "Случайное фэнтези-имя", ".комплимент": "Случайный комплимент",
        ".подбросить NdM": "Бросить N кубиков по M граней (напр. 2d6)",
    },
    "🌍 Внешние сервисы": {
        ".прогноз <город>": "Прогноз погоды на 3 дня", ".ip <ip/домен>": "Инфо по IP или домену",
        ".сократить <ссылка>": "Сократить ссылку", ".гороскоп <знак>": "Гороскоп на сегодня",
    },
    "📌 Telegram-действия": {
        ".закреп": "Закрепить сообщение (ответом)", ".открепить": "Открепить все сообщения",
        ".опрос Вопрос | в1 | в2": "Создать опрос", ".сохранить": "Сохранить сообщение в Избранное (ответом)",
        ".переслать <N>": "Переслать N своих сообщений в Избранное",
        ".статус <текст>": "Изменить 'о себе'", ".имяпрофиля <текст>": "Изменить имя профиля",
    },
    "✨ Ещё анимации": {
        ".спиннер": "Крутящийся спиннер", ".бегущаястрока <текст>": "Бегущая строка",
        ".таймер <сек>": "Обратный отсчёт (до 60 сек.)", ".напоминание <сек> <текст>": "Напомнить через время",
        ".таблицаумножения <N>": "Таблица умножения",
    },
    "🧮 Текст и математика": {
        ".длина <текст>": "Статистика по тексту", ".повторить <N> <текст>": "Повторить текст N раз",
        ".хэштеги <текст>": "Сделать хэштеги из слов", ".температура <N> <из><в>": "Конвертер C/F/K, напр. 100 c f",
        ".монетасерия <N>": "Подбросить монету N раз", ".простое <N>": "Проверить число на простоту",
        ".факториал <N>": "Факториал числа", ".фибоначчи <N>": "Первые N чисел Фибоначчи",
        ".нод <a> <b>": "Наибольший общий делитель", ".нок <a> <b>": "Наименьшее общее кратное",
        ".системасчисления <число> <из> <в>": "Конвертер bin/dec/hex/oct",
        ".хекс <текст>": "Текст в hex", ".изхекс <код>": "Hex в текст",
        ".урл <текст>": "URL-кодирование", ".изурл <текст>": "URL-декодирование",
    },
    "📅 Даты": {
        ".возраст ДД.ММ.ГГГГ": "Посчитать возраст", ".днейдо ДД.ММ.ГГГГ": "Сколько дней до/после даты",
        ".високосный <год>": "Проверить високосный год", ".деньнедели ДД.ММ.ГГГГ": "День недели для даты",
    },
    "📝 Заметки": {
        ".заметка <текст>": "Сохранить заметку в этом чате", ".заметки": "Показать заметки",
        ".заметкиочистить": "Удалить все заметки чата",
    },
    "⚙️ Утилиты": {".пинг": "Скорость отклика", ".аптайм": "Время работы", ".пмщ": "Это меню"},
}

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.пмщ$"))
async def help_handler(event):
    text = "🤖 **Список команд юзербота**\n\n"
    for category, cmds in HELP.items():
        text += f"{category}\n"
        for cmd, desc in cmds.items():
            text += f"  `{cmd}` — {desc}\n"
        text += "\n"
    await event.edit(text)

# ==================== ЗАПУСК ====================
async def _run_web_server():
    # Крошечный HTTP-сервер только для Render Web Service: Render считает
    # сервис "живым", пока тот отвечает на HTTP по порту из переменной PORT.
    # Сам юзербот тут ни при чём — это просто заглушка для health-check'а.
    async def handle(request):
        return web.Response(text="✅ Юзербот работает")

    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Веб-сервер для health-check запущен на порту {port}")

async def _main():
    await client.start()
    # Веб-сервер нужен только если Render (или другой хостинг) передал PORT —
    # то есть когда сервис создан как Web Service. При обычном локальном
    # запуске или как Background Worker переменной PORT нет, и сервер не поднимается.
    if os.environ.get("PORT"):
        asyncio.create_task(_run_web_server())
    print("✅ Юзербот запущен! Напиши себе .пмщ чтобы увидеть все команды.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    print("🚀 Юзербот запускается...")
    client.loop.run_until_complete(_main())
