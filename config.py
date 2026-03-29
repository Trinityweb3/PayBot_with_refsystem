import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    CRYPTO_BOT_TOKEN: str = os.getenv("CRYPTO_BOT_TOKEN")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    
    PRIVATE_CHAT_ID: str = os.getenv("PRIVATE_CHAT_ID")
    
    FORUM_CHAT_ID: str = os.getenv("FORUM_CHAT_ID", "")
    
    BOT_NAME: str = "toms_mirror_bot"
    
    PRICES = {
        "week": {"amount": 5, "days": 7, "currency": "USDT", "description": "7 дней доступа", "emoji": "💳"},
        "month": {"amount": 15, "days": 30, "currency": "USDT", "description": "30 дней доступа", "emoji": "💎"},
        "year": {"amount": 50, "days": 365, "currency": "USDT", "description": "Год доступа", "emoji": "🔥"}
    }
    
    TRIAL_DAYS: int = int(os.getenv("TRIAL_DAYS", "2"))
    
    REFERRAL_PERCENT_NORMAL: int = 25
    REFERRAL_PERCENT_PARTNER: int = 50
    WITHDRAW_MIN: float = 5.0
    
    WARNING_DAYS: int = 3
    
    PRIVATE_CHANNELS = [
        "LanosPark typing... + private",
        "Арбуз",
        "D Private",
        "Kодик вротик",
        "Dao Dao ДаОшЕчКа",
        "Arty private + positions + chat",
        "Вкусно? Вкусно!",
        "KD не балуется",
        "Криптоговно",
        "Свиные уши",
        "Ramar private",
        "КриптоБункер",
        "Happy",
        "Грязный щитпост",
        "etc."
    ]

    FAQ = [
        {"q": "Какой формат доступа?", "a": "Оплата через кб -> бот видит оплату -> кидает ссылку"},
        {"q": "Есть ли пробный период?", "a": "Да, /trial"},
        {"q": "Добавляются ли новые каналы?", "a": "Работаем братик"},
        {"q": "Тех.поддержка", "a": "@toms_mirrors"}
    ]
    
    PAYMENT_CHECK_INTERVAL: int = 30
    SUBSCRIPTION_CHECK_INTERVAL: int = 3600

config = Config()

required_vars = ["BOT_TOKEN", "CRYPTO_BOT_TOKEN", "PRIVATE_CHAT_ID"]
for var in required_vars:
    if not getattr(config, var):
        raise ValueError(f"Отсутствует обязательная переменная: {var}")
