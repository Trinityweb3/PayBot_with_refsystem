import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup,
    KeyboardButton, ReplyKeyboardRemove, ChatMemberUpdated
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode, ChatMemberStatus

from config import config
from database_simple import db
from crypto_payment import crypto_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ==================== КЛАВИАТУРЫ ====================

def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню - обычная клавиатура"""
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="💎 Приобрести доступ"),
        KeyboardButton(text="🎁 Тест на 48 часов")
    )
    builder.row(
        KeyboardButton(text="📦 Контент"),
        KeyboardButton(text="👤 Мой профиль")
    )
    builder.row(
        KeyboardButton(text="👥 Партнерская система"),
        KeyboardButton(text="💰 Получить выплату")
    )
    builder.row(
        KeyboardButton(text="❓ Вопросы")
    )
    
    return builder.as_markup(resize_keyboard=True)

def create_back_to_main_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой 'Назад'"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⬅️ Назад в меню"))
    return builder.as_markup(resize_keyboard=True)

def create_payment_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для оплаты"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💳 Неделя",
            callback_data="subscribe:week"
        ),
        InlineKeyboardButton(
            text="💎 Месяц (рекомендуем)",
            callback_data="subscribe:month"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔥 Навсегда",
            callback_data="subscribe:forever"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back:main"
        )
    )
    
    return builder.as_markup()

def create_profile_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура профиля"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="👥 Партнерка",
            callback_data="profile:partners"
        ),
        InlineKeyboardButton(
            text="💰 Выплаты",
            callback_data="profile:payouts"
        )
    )
    
    return builder.as_markup()

def create_partner_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура партнерки"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="📊 Полная статистика",
            callback_data="partners:stats"
        ),
        InlineKeyboardButton(
            text="📈 Мои начисления",
            callback_data="partners:earnings"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back:profile"
        )
    )
    
    return builder.as_markup()

def create_payout_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура выплат"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="💰 Запросить выплату",
            callback_data="payout:request"
        ),
        InlineKeyboardButton(
            text="📋 Мои заявки",
            callback_data="payout:history"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back:profile"
        )
    )
    
    return builder.as_markup()

def get_start_message(user_id: int, user_data: Optional[Dict] = None) -> str:
    balance = user_data.get('available_balance', 0.0) if user_data else 0.0
    sub_status = "❌ отсутствует"
    
    if user_data and user_data.get('subscription_end'):
        try:
            end = datetime.fromisoformat(user_data['subscription_end'])
            if end > datetime.now():
                days = (end - datetime.now()).days
                if user_data.get('is_trial'):
                    sub_status = f"🎁 тестовый период, {days} д."
                else:
                    sub_status = f"✅ активна, {days} д."
        except:
            pass
    
    return (
        f"🔮 <b>Tom's Mirror</b> — Миррор СНГ ифлов + underradar DAO\n\n"
        
        f"<b>👤 Ваш аккаунт:</b>\n"
        f"├ ID: <code>{user_id}</code>\n"
        f"├ Доступно к выводу: <b>{balance:.1f} USDT</b>\n"
        f"└ Подписка: {sub_status}\n\n"
        
        f"<b>🎯 Что вы получаете:</b>\n"
        f"• Доступ к закрытым каналам\n"
        f"• DAO c пушовером\n"
        f"• Постоянные обновления\n"
        f"• Поддержку 24/7\n\n"
        
        f"<i>Выберите действие в меню ниже ↓</i>"
    )

def get_content_message() -> str:
    channels = "\n".join([f"• {channel}" for channel in config.PRIVATE_CHANNELS])
    
    return (
        f"📦 <b>Контент Tom's Mirror</b>\n\n"
        
        f"<b>━━━━━━━━━━━━━━━</b>\n"
        f"<b>🔒 ЗАКРЫТЫЕ КАНАЛЫ</b>\n"
        f"<b>━━━━━━━━━━━━━━━</b>\n"
        f"{channels}\n\n"
        
        f"<i>Доступ ко всему контенту открывается сразу после оплаты</i>"
    )

def get_trial_message() -> str:
    return (
        f"🎁 <b>Тестовый доступ на 48 часов</b>\n\n"
        
        f"Получите полный доступ ко всем возможностям Tom's Mirror на 2 дня абсолютно бесплатно!\n\n"
        
        f"<b>✅ Что входит:</b>\n"
        f"• Весь контент (каналы + инструменты)\n"
        f"• Техническая поддержка\n"
        f"• Обновления в реальном времени\n\n"
        
        f"<b>⚠️ Ограничения теста:</b>\n"
        f"• Партнерская система не активна\n"
        f"• Нет доступа к приглашениям\n"
        f"• Доступ только 1 раз\n\n"
        
        f"<i>После теста рекомендуем оформить подписку от месяца для получения партнерской ссылки</i>"
    )

def get_subscribe_message() -> str:
    prices = config.PRICES
    
    return (
        f"💎 <b>Приобрести доступ к Tom's Mirror</b>\n\n"
        
        f"<b>Выбирайте тариф и получайте:</b>\n"
        f"• Тёплое дао с Pushover,\n"
        f"• Мирроры топ СНГ инфлов\n\n"
        
        f"<b>━━━━━━━━━━━━━━━</b>\n"
        f"<b>💰 ТАРИФЫ</b>\n"
        f"<b>━━━━━━━━━━━━━━━</b>\n"
        f"{prices['week']['emoji']} <b>Неделя</b> — {prices['week']['amount']} USDT\n"
        f"└ Идеально для знакомства\n\n"
        
        f"{prices['month']['emoji']} <b>Месяц</b> — {prices['month']['amount']} USDT\n"
        f"└ + Партнерская система c 25% рефкой\n\n"
        
        f"{prices['forever']['emoji']} <b>Год подписки</b> — {prices['forever']['amount']} USDT\n"
        f"└ 🏆 Максимальная выгода\n\n"
        
        f"<i>Выберите тариф для оплаты ↓</i>"
    )

def get_profile_message(user_id: int, user_data: Dict) -> str:
    created = user_data.get('created_at', 'неизвестно')
    if created and created != 'неизвестно':
        try:
            created = datetime.fromisoformat(created).strftime("%d.%m.%Y")
        except:
            pass
    
    sub_status = "отсутствует"
    sub_end = ""
    if user_data.get('subscription_end'):
        try:
            end = datetime.fromisoformat(user_data['subscription_end'])
            if end > datetime.now():
                days = (end - datetime.now()).days
                if user_data.get('is_trial'):
                    sub_status = f"🎁 тестовый"
                    sub_end = f"({days} д. осталось)"
                else:
                    sub_status = f"✅ активна"
                    sub_end = f"({days} д. осталось)"
        except:
            pass
    
    total_refs = user_data.get('total_referrals', 0)
    paid_refs = user_data.get('paid_referrals', 0)
    earned_total = user_data.get('earned_total', 0.0)
    available = user_data.get('available_balance', 0.0)
    
    return (
        f"👤 <b>Ваш профиль в Tom's Mirror</b>\n\n"
        
        f"<b>📋 ОБЩАЯ ИНФОРМАЦИЯ</b>\n"
        f"├ ID: <code>{user_id}</code>\n"
        f"├ Регистрация: {created}\n"
        f"├ Доступ: {sub_status} {sub_end}\n"
        f"└ Баланс: <b>{user_data.get('balance', 0.0):.1f} USDT</b>\n\n"
        
        f"<b>👥 ПАРТНЕРСКАЯ СИСТЕМА</b>\n"
        f"├ Приглашено: {total_refs} чел.\n"
        f"├ Из них оплатили: {paid_refs} чел.\n"
        f"├ Всего заработано: <b>{earned_total:.1f} USDT</b>\n"
        f"└ Доступно к выводу: <b>{available:.1f} USDT</b>\n\n"
        
        f"<i>Используйте кнопки ниже для управления ↓</i>"
    )

def get_partner_message(user_data: Dict) -> str:
    stats = user_data
    percent = stats.get('ref_percent', 25)
    status = stats.get('ref_status', 'referrer')
    status_ru = "🎯 Партнер (Whitelist)" if status == 'partner' else "👤 Реферер"
    
    total_refs = stats.get('total_referrals', 0)
    paid_refs = stats.get('paid_referrals', 0)
    trial_refs = stats.get('trial_referrals', 0)
    earned_total = stats.get('earned_total', 0.0)
    available = stats.get('available_balance', 0.0)
    
    ref_link = ""
    if user_data.get('referral_code'):
        ref_link = f"\n\n<b>🔗 Ваша партнерская ссылка:</b>\n<code>https://t.me/toms_mirror_bot?start={user_data['referral_code']}</code>"
    
    return (
        f"👥 <b>Партнерская система Tom's Mirror</b>\n\n"
        
        f"<b>🎯 ВАШ СТАТУС</b>\n"
        f"├ {status_ru}\n"
        f"└ Ваш процент: <b>{percent}%</b>\n\n"
        
        f"<b>📊 СТАТИСТИКА</b>\n"
        f"├ Всего приглашено: {total_refs}\n"
        f"├ Активировали тест: {trial_refs}\n"
        f"├ Оплатили подписку: {paid_refs}\n"
        f"├ Заработано всего: <b>{earned_total:.1f} USDT</b>\n"
        f"└ Доступно к выводу: <b>{available:.1f} USDT</b>"
        
        f"{ref_link}\n\n"
        
        f"<i>Приглашайте друзей и получайте {percent}% с каждого их платежа!</i>"
    )

def get_payout_message(user_data: Dict) -> str:
    """Сообщение о выплатах"""
    available = user_data.get('available_balance', 0.0)
    min_amount = config.WITHDRAW_MIN
    
    if available < min_amount:
        return (
            f"💰 <b>Вывод средств из Tom's Mirror</b>\n\n"
            
            f"<b>📊 ВАШ БАЛАНС</b>\n"
            f"├ Доступно: <b>{available:.1f} USDT</b>\n"
            f"└ Минимум для вывода: <b>{min_amount:.1f} USDT</b>\n\n"
            
            f"<b>⚠️ ВНИМАНИЕ</b>\n"
            f"Для запроса выплаты необходимо набрать минимум {min_amount:.1f} USDT\n\n"
            
            f"<i>Приглашайте больше друзей через партнерскую систему, чтобы быстрее набрать нужную сумму</i>"
        )
    
    return (
        f"💰 <b>Вывод средств из Tom's Mirror</b>\n\n"
        
        f"<b>✅ ВАШ БАЛАНС</b>\n"
        f"├ Доступно: <b>{available:.1f} USDT</b>\n"
        f"└ Минимум: <b>{min_amount:.1f} USDT</b>\n\n"
        
        f"<b>📋 КАК ПОЛУЧИТЬ</b>\n"
        f"1. Нажмите 'Запросить выплату'\n"
        f"2. Средства будут заморожены\n"
        f"3. Выплата в течение 24 часов\n"
        f"4. Получите USDT на ваш кошелек\n\n"
        
        f"<i>Все выплаты обрабатываются вручную для вашей безопасности</i>"
    )

def get_help_message() -> str:
    """Сообщение помощи"""
    faq_items = []
    for item in config.FAQ:
        faq_items.append(f"<b>▫️ {item['q']}</b>")
        faq_items.append(f"{item['a']}\n")
    
    faq_text = "\n".join(faq_items).strip()
    
    return (
        f"❓ <b>Частые вопросы о Tom's Mirror</b>\n\n"
        
        f"{faq_text}\n\n"
        
        f"<b>👨‍💻 ТЕХПОДДЕРЖКА</b>\n"
        f"Если ваш вопрос остался без ответа, напишите напрямую: @tom_support\n\n"
        
        f"<i>Мы всегда на связи и готовы помочь!</i>"
    )

# ==================== КОМАНДА /CHECK_ALL - ПОЛНАЯ ПРОВЕРКА ====================

@router.message(Command("check_all"))
async def check_all_command(message: Message):
    """АДМИН КОМАНДА: Полная проверка всех пользователей чата"""
    user_id = message.from_user.id
    
    # Проверка прав администратора
    if user_id != config.ADMIN_ID:
        await message.answer("❌ Доступ запрещен. Эта команда только для администратора.")
        return
    
    if not config.FORUM_CHAT_ID:
        await message.answer("❌ FORUM_CHAT_ID не указан в конфиге")
        return
    
    # Отправляем подтверждение
    confirm_keyboard = InlineKeyboardBuilder()
    confirm_keyboard.row(
        InlineKeyboardButton(text="✅ Да, запустить проверку", callback_data="check_all:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="check_all:cancel")
    )
    
    await message.answer(
        f"⚠️ <b>ПОДТВЕРЖДЕНИЕ ПОЛНОЙ ПРОВЕРКИ</b>\n\n"
        f"<b>Будет выполнено:</b>\n"
        f"• Проверка ВСЕХ пользователей в чате {config.FORUM_CHAT_ID}\n"
        f"• Отправка предупреждений пользователям без подписки\n"
        f"• Блокировка пользователей с истекшим сроком ({config.WARNING_DAYS}+ дней)\n"
        f"• Отправка ссылок пользователям с активной подпиской\n\n"
        f"<b>Внимание:</b> Это может занять несколько минут.\n\n"
        f"<i>Подтвердите действие:</i>",
        reply_markup=confirm_keyboard.as_markup()
    )

@router.callback_query(F.data.startswith("check_all:"))
async def check_all_callback(callback: CallbackQuery):
    """Обработка подтверждения / отмены проверки"""
    user_id = callback.from_user.id
    
    if user_id != config.ADMIN_ID:
        await callback.answer("❌ Доступ запрещен")
        return
    
    action = callback.data.split(":")[1]
    
    if action == "cancel":
        await callback.message.edit_text("❌ <b>Проверка отменена</b>")
        await callback.answer()
        return
    
    elif action == "confirm":
        await callback.message.edit_text(
            "🔄 <b>Запускаю полную проверку всех пользователей...</b>\n\n"
            "Это займет некоторое время. Статус будет обновляться."
        )
        await callback.answer()
        
        # Запускаем полную проверку
        asyncio.create_task(run_full_check(callback.message))

async def run_full_check(status_message: Message):
    """Запуск полной проверки с отправкой статуса"""
    try:
        start_time = datetime.now()
        
        # Получаем всех пользователей
        users = await get_all_chat_users()
        
        await status_message.edit_text(
            f"🔄 <b>Проверка пользователей...</b>\n\n"
            f"📊 Всего найдено: {len(users)} пользователей\n"
            f"⏳ Начинаем обработку..."
        )
        
        stats = {
            'total': len(users),
            'checked': 0,
            'with_subscription': 0,
            'without_subscription': 0,
            'banned': 0,
            'warned': 0,
            'invited': 0,
            'failed': 0
        }
        
        # Обрабатываем каждого пользователя
        for i, user_id in enumerate(users, 1):
            try:
                result = await process_user_check(user_id)
                
                stats['checked'] = i
                stats['with_subscription'] += result['has_subscription']
                stats['without_subscription'] += result['no_subscription']
                stats['banned'] += result['banned']
                stats['warned'] += result['warned']
                stats['invited'] += result['invited']
                stats['failed'] += result['failed']
                
                # Обновляем статус каждые 10 пользователей
                if i % 10 == 0:
                    elapsed = (datetime.now() - start_time).seconds
                    await status_message.edit_text(
                        f"🔄 <b>Идет проверка...</b>\n\n"
                        f"📊 <b>Прогресс:</b> {i}/{len(users)} ({int(i/len(users)*100)}%)\n"
                        f"⏱ Прошло: {elapsed} сек\n\n"
                        f"✅ С подпиской: {stats['with_subscription']}\n"
                        f"❌ Без подписки: {stats['without_subscription']}\n"
                        f"🔨 Забанено: {stats['banned']}\n"
                        f"⚠️ Предупреждено: {stats['warned']}\n"
                        f"🔗 Отправлено ссылок: {stats['invited']}\n"
                        f"⚠️ Ошибок: {stats['failed']}"
                    )
                
                # Небольшая задержка чтобы не спамить
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Ошибка при проверке пользователя {user_id}: {e}")
                stats['failed'] += 1
        
        # Финальный отчет
        elapsed = (datetime.now() - start_time).seconds
        report = (
            f"✅ <b>ПОЛНАЯ ПРОВЕРКА ЗАВЕРШЕНА!</b>\n\n"
            f"<b>📊 СТАТИСТИКА:</b>\n"
            f"• Всего проверено: {stats['total']}\n"
            f"• Время выполнения: {elapsed} сек\n\n"
            f"<b>👥 ПОЛЬЗОВАТЕЛИ:</b>\n"
            f"• С активной подпиской: {stats['with_subscription']}\n"
            f"• Без подписки: {stats['without_subscription']}\n\n"
            f"<b>⚡ ДЕЙСТВИЯ:</b>\n"
            f"• Заблокировано (3+ дней): {stats['banned']}\n"
            f"• Отправлено предупреждений: {stats['warned']}\n"
            f"• Отправлено ссылок в чат: {stats['invited']}\n"
            f"• Ошибок при обработке: {stats['failed']}\n\n"
            f"<i>Проверка завершена {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
        )
        
        await status_message.edit_text(report)
        
        # Отправляем дополнительное сообщение админу
        await bot.send_message(
            config.ADMIN_ID,
            f"📋 <b>Детальный отчет о проверке</b>\n\n"
            f"{report}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в run_full_check: {e}")
        await status_message.edit_text(f"❌ <b>Ошибка при проверке:</b>\n{e}")

async def get_all_chat_users() -> list:
    """Получение ВСЕХ пользователей чата"""
    users = set()
    
    try:
        # 1. Получаем администраторов
        admins = await bot.get_chat_administrators(config.FORUM_CHAT_ID)
        for admin in admins:
            users.add(admin.user.id)
        
        # 2. Получаем пользователей из БД (кто был в чате)
        async with db.conn.execute(
            "SELECT DISTINCT user_id FROM subscription_warnings WHERE chat_id = ?",
            (str(config.FORUM_CHAT_ID),)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                users.add(row[0])
        
        # 3. Получаем всех пользователей бота
        async with db.conn.execute(
            "SELECT user_id FROM users"
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                users.add(row[0])
        
        logger.info(f"Всего найдено пользователей для проверки: {len(users)}")
        return list(users)
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        return []

async def process_user_check(user_id: int) -> dict:
    """Обработка одного пользователя"""
    result = {
        'has_subscription': 0,
        'no_subscription': 0,
        'banned': 0,
        'warned': 0,
        'invited': 0,
        'failed': 0
    }
    
    try:
        # Пропускаем администраторов
        try:
            chat_member = await bot.get_chat_member(config.FORUM_CHAT_ID, user_id)
            if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return result
        except:
            pass
        
        # Получаем данные пользователя
        user = await db.get_user(user_id)
        
        # Проверяем подписку
        has_subscription = False
        if user and user.get('subscription_end'):
            try:
                end = datetime.fromisoformat(user['subscription_end'])
                if end > datetime.now():
                    has_subscription = True
            except:
                pass
        
        if has_subscription:
            result['has_subscription'] = 1
            
            # Отправляем ссылку в приватный чат
            try:
                # Проверяем, есть ли уже пользователь в чате
                try:
                    await bot.get_chat_member(config.PRIVATE_CHAT_ID, user_id)
                    # Уже в чате
                except:
                    # Не в чате - отправляем ссылку
                    await add_to_chat(user_id)
                    result['invited'] = 1
                
                # Удаляем предупреждение если есть
                await db.remove_subscription_warning(user_id, str(config.FORUM_CHAT_ID))
                
            except Exception as e:
                logger.error(f"Ошибка при отправке ссылки {user_id}: {e}")
                result['failed'] = 1
        else:
            result['no_subscription'] = 1
            
            # Проверяем предупреждение
            warning = await db.get_subscription_warning(user_id, str(config.FORUM_CHAT_ID))
            
            if warning:
                first_warning = datetime.fromisoformat(warning['first_warning_at'])
                days_passed = (datetime.now() - first_warning).days
                
                # Если прошло 3+ дней - БАНИМ
                if days_passed >= config.WARNING_DAYS and not warning.get('kicked'):
                    try:
                        # Баним пользователя
                        await bot.ban_chat_member(config.FORUM_CHAT_ID, user_id)
                        await db.update_warning_status(user_id, str(config.FORUM_CHAT_ID), kicked=True)
                        result['banned'] = 1
                        
                        # Отправляем уведомление о блокировке
                        try:
                            await bot.send_message(
                                user_id,
                                f"❌ <b>ВЫ ЗАБЛОКИРОВАНЫ В ЧАТЕ</b>\n\n"
                                f"Вы были заблокированы в чате из-за отсутствия активной подписки.\n"
                                f"Срок в {config.WARNING_DAYS} дня истёк.\n\n"
                                f"📅 Дата блокировки: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                                f"💎 Чтобы вернуться, оплатите подписку и напишите в поддержку: @tom_support"
                            )
                        except:
                            pass
                        
                    except Exception as e:
                        logger.error(f"Не удалось забанить {user_id}: {e}")
                        result['failed'] = 1
                else:
                    # Отправляем напоминание
                    days_left = config.WARNING_DAYS - days_passed
                    try:
                        await bot.send_message(
                            user_id,
                            f"⚠️ <b>НАПОМИНАНИЕ О ПОДПИСКЕ</b>\n\n"
                            f"У вас отсутствует активная подписка на Tom's Mirror.\n\n"
                            f"⏰ <b>Осталось дней: {days_left}</b>\n"
                            f"📅 Дата блокировки: {(first_warning + timedelta(days=config.WARNING_DAYS)).strftime('%d.%m.%Y')}\n\n"
                            f"💎 Оплатить подписку: /buy\n"
                            f"👤 Проверить статус: /me"
                        )
                        result['warned'] = 1
                    except:
                        pass
            else:
                # Нет предупреждения - создаем и отправляем первое
                await db.add_subscription_warning(user_id, str(config.FORUM_CHAT_ID))
                
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
                        f"У вас отсутствует активная подписка на Tom's Mirror.\n\n"
                        f"⏰ <b>У вас есть {config.WARNING_DAYS} дня на оплату подписки.</b>\n"
                        f"❌ После этого вы будете НАВСЕГДА заблокированы в чате.\n\n"
                        f"💎 Оплатить подписку: /buy\n"
                        f"👤 Проверить статус: /me\n\n"
                        f"<i>Дата блокировки: {(datetime.now() + timedelta(days=config.WARNING_DAYS)).strftime('%d.%m.%Y')}</i>"
                    )
                    result['warned'] = 1
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
        result['failed'] = 1
    
    return result

# ==================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ КОМАНД ====================

@router.message(CommandStart())
async def start_handler(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    args = message.text.split()
    
    referrer_id = None
    if len(args) > 1:
        referrer = await db.get_user_by_referral_code(args[1])
        if referrer and referrer['user_id'] != user_id:
            if referrer.get('ref_percent') == 50 and referrer.get('ref_status') == 'partner':
                referrer_id = referrer['user_id']
            elif referrer.get('converted_to_paid_at'):
                referrer_id = referrer['user_id']
    
    user = await db.get_user(user_id)
    
    if not user:
        user = await db.create_user(user_id, referrer_id)
        
        if referrer_id:
            await db.add_referral(referrer_id, user_id)
            logger.info(f"Пользователь {user_id} зарегистрирован по ссылке от {referrer_id}")
    
    ref_stats = await db.get_referral_stats(user_id)
    if ref_stats:
        user.update(ref_stats)
    
    await message.answer(
        get_start_message(user_id, user),
        reply_markup=create_main_menu_keyboard()
    )

@router.message(F.text == "⬅️ Назад в меню")
async def back_to_main_handler(message: Message):
    """Обработчик кнопки 'Назад в меню'"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if user:
        ref_stats = await db.get_referral_stats(user_id)
        if ref_stats:
            user.update(ref_stats)
    
    await message.answer(
        get_start_message(user_id, user),
        reply_markup=create_main_menu_keyboard()
    )

@router.message(F.text == "📦 Контент")
async def content_handler(message: Message):
    """Обработчик кнопки 'Контент'"""
    await message.answer(
        get_content_message(),
        reply_markup=create_back_to_main_keyboard()
    )

@router.message(F.text == "🎁 Тест на 48 часов")
async def trial_handler(message: Message):
    """Обработчик кнопки 'Тест на 48 часов'"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return
    
    if user.get('has_used_trial'):
        await message.answer("❌ Вы уже использовали тестовый период!", reply_markup=create_back_to_main_keyboard())
        return
    
    if user.get('subscription_end'):
        try:
            end = datetime.fromisoformat(user['subscription_end'])
            if end > datetime.now():
                await message.answer("⚠️ У вас уже есть активный доступ!", reply_markup=create_back_to_main_keyboard())
                return
        except:
            pass
    
    await message.answer(
        get_trial_message(),
        reply_markup=create_back_to_main_keyboard()
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎁 Активировать тест", callback_data="trial:activate"))
    await message.answer("Нажмите кнопку ниже для активации:", reply_markup=builder.as_markup())

@router.message(F.text == "💎 Приобрести доступ")
async def subscribe_handler(message: Message):
    """Обработчик кнопки 'Приобрести доступ'"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if user and user.get('subscription_end'):
        end = datetime.fromisoformat(user['subscription_end'])
        if end > datetime.now():
            days = (end - datetime.now()).days
            await message.answer(f"ℹ️ У вас уже есть доступ на {days} дней")
    
    await message.answer(
        get_subscribe_message(),
        reply_markup=create_payment_keyboard()
    )

@router.message(F.text == "👤 Мой профиль")
async def profile_handler(message: Message):
    """Обработчик кнопки 'Мой профиль'"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    user.update(ref_stats)
    
    await message.answer(
        get_profile_message(user_id, user),
        reply_markup=create_profile_keyboard()
    )

@router.message(F.text == "👥 Партнерская система")
async def partner_system_handler(message: Message):
    """Обработчик кнопки 'Партнерская система'"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    if ref_stats:
        user.update(ref_stats)
    
    await message.answer(
        get_partner_message(user),
        reply_markup=create_partner_keyboard()
    )

@router.message(F.text == "💰 Получить выплату")
async def payout_handler(message: Message):
    """Обработчик кнопки 'Получить выплату'"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    if ref_stats:
        user.update(ref_stats)
    
    await message.answer(
        get_payout_message(user),
        reply_markup=create_payout_keyboard()
    )

@router.message(F.text == "❓ Вопросы")
async def help_handler(message: Message):
    """Обработчик кнопки 'Вопросы'"""
    await message.answer(
        get_help_message(),
        reply_markup=create_back_to_main_keyboard()
    )

# ==================== ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ====================

@router.callback_query(F.data == "back:main")
async def back_main_callback(callback: CallbackQuery):
    """Возврат в главное меню из инлайн-кнопки"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if user:
        ref_stats = await db.get_referral_stats(user_id)
        if ref_stats:
            user.update(ref_stats)
    
    await callback.message.edit_text(
        get_start_message(user_id, user),
        reply_markup=None
    )
    await callback.answer()
    
    await callback.message.answer(
        "Главное меню:",
        reply_markup=create_main_menu_keyboard()
    )

@router.callback_query(F.data == "back:profile")
async def back_profile_callback(callback: CallbackQuery):
    """Возврат в профиль из инлайн-кнопки"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйтесь")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    user.update(ref_stats)
    
    await callback.message.edit_text(
        get_profile_message(user_id, user),
        reply_markup=create_profile_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "trial:activate")
async def trial_activate_callback(callback: CallbackQuery):
    """Активация тестового периода"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйтесь")
        return
    
    if user.get('has_used_trial'):
        await callback.answer("❌ Вы уже использовали тестовый период!", show_alert=True)
        return
    
    if user.get('subscription_end'):
        try:
            end = datetime.fromisoformat(user['subscription_end'])
            if end > datetime.now():
                await callback.answer("⚠️ У вас уже есть активный доступ!", show_alert=True)
                return
        except:
            pass
    
    user = await db.activate_trial(user_id, config.TRIAL_DAYS)
    
    chat_added = await add_to_chat(user_id)
    
    if chat_added:
        await callback.message.edit_text(
            f"🎉 <b>Тестовый доступ активирован!</b>\n\n"
            f"<b>✅ ВЫ ПОЛУЧИЛИ:</b>\n"
            f"• Полный доступ на {config.TRIAL_DAYS} дня\n"
            f"• Все каналы и инструменты\n"
            f"• Техническую поддержку\n\n"
            f"<b>🔗 Ссылка на приватный чат отправлена выше.</b>\n\n"
            f"<b>⚠️ ОГРАНИЧЕНИЯ ТЕСТА:</b>\n"
            f"• Партнерская система не активна\n"
            f"• Нет партнерской ссылки\n"
            f"• Доступ только 1 раз\n\n"
            f"<i>После окончания теста оформите подписку от месяца для получения партнерской ссылки</i>"
        )
    else:
        await callback.message.edit_text(
            f"🎉 <b>Тестовый доступ активирован!</b>\n\n"
            f"Однако не удалось отправить ссылку на чат.\n"
            f"Пожалуйста, свяжитесь с поддержкой: @tom_support"
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("subscribe:"))
async def process_subscription(callback: CallbackQuery):
    """Обработка выбора тарифа"""
    plan_type = callback.data.replace("subscribe:", "")
    
    if plan_type not in config.PRICES:
        await callback.answer("❌ Ошибка выбора тарифа")
        return
    
    plan = config.PRICES[plan_type]
    user_id = callback.from_user.id
    
    invoice = await crypto_bot.create_invoice(
        amount=plan["amount"],
        currency=plan["currency"],
        description=plan["description"],
        plan_type=plan_type
    )
    
    if not invoice:
        await callback.message.answer("❌ Ошибка при создании платежа")
        return
    
    await db.create_payment(
        user_id=user_id,
        invoice_id=invoice["invoice_id"],
        amount=plan["amount"],
        currency=plan["currency"],
        plan_type=plan_type
    )
    
    plan_descriptions = {
        "week": "Недельный доступ",
        "month": "Месячный доступ + партнерка",
        "forever": "Пожизненный доступ + партнерка"
    }
    
    plan_benefits = {
        "week": ["Доступ на 7 дней", "Весь контент", "Поддержка"],
        "month": ["Доступ на 30 дней", "Партнерская система", "Реферальная ссылка", "Все бонусы"],
        "forever": ["Пожизненный доступ", "Приоритетная поддержка", "Все будущие обновления", "Максимальная выгода"]
    }
    
    await callback.message.edit_text(
        f"💎 <b>Оплата тарифа: {plan_descriptions.get(plan_type)}</b>\n\n"
        
        f"<b>📊 ДЕТАЛИ:</b>\n"
        f"• Сумма: <b>{plan['amount']} {plan['currency']}</b>\n"
        f"• Срок: {plan['days']} дней\n"
        f"• Описание: {plan['description']}\n\n"
        
        f"<b>✅ ВЫ ПОЛУЧАЕТЕ:</b>\n" + "\n".join([f"• {benefit}" for benefit in plan_benefits.get(plan_type, [])]) + "\n\n"
        
        f"<b>🔗 ССЫЛКА ДЛЯ ОПЛАТЫ:</b>\n"
        f"<code>{invoice['pay_url']}</code>\n\n"
        
        f"<i>Ссылка действительна 30 минут\nПосле оплаты доступ откроется автоматически</i>"
    )
    
    await callback.answer()

@router.callback_query(F.data == "profile:partners")
async def profile_partners_callback(callback: CallbackQuery):
    """Переход к партнерской системе из профиля"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйтесь")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    if ref_stats:
        user.update(ref_stats)
    
    await callback.message.edit_text(
        get_partner_message(user),
        reply_markup=create_partner_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "profile:payouts")
async def profile_payouts_callback(callback: CallbackQuery):
    """Переход к выплатам из профиля"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйтесь")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    if ref_stats:
        user.update(ref_stats)
    
    await callback.message.edit_text(
        get_payout_message(user),
        reply_markup=create_payout_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "partners:stats")
async def partners_stats_callback(callback: CallbackQuery):
    """Детальная статистика партнерки"""
    user_id = callback.from_user.id
    referrals = await db.get_referrals(user_id)
    
    if not referrals:
        stats_text = "📊 <b>Детальная статистика</b>\n\nУ вас пока нет приглашенных пользователей.\n\nПриглашайте друзей и получайте проценты с их платежей!"
    else:
        stats_text = "📊 <b>Детальная статистика ваших рефералов</b>\n\n"
        
        for i, ref in enumerate(referrals, 1):
            user_id_ref = ref['user_id']
            created = datetime.fromisoformat(ref['created_at']).strftime("%d.%m.%Y") if ref['created_at'] else "неизвестно"
            paid = "✅" if ref['converted_to_paid_at'] else "❌"
            payments = ref['payments_count'] or 0
            spent = ref['total_spent'] or 0.0
            
            stats_text += (
                f"<b>{i}. ID: {user_id_ref}</b>\n"
                f"├ 📅 Регистрация: {created}\n"
                f"├ 💰 Платежей: {payments} на {spent:.1f}$\n"
                f"└ 🎁 Статус: {paid}\n\n"
            )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back:profile"))
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "partners:earnings")
async def partners_earnings_callback(callback: CallbackQuery):
    """История начислений партнерки"""
    user_id = callback.from_user.id
    earnings = await db.get_referral_earnings(user_id, 10)
    
    if not earnings:
        earnings_text = "📈 <b>История начислений</b>\n\nУ вас пока нет начислений от партнерской программы.\n\nПриглашайте друзей и получайте проценты с их платежей!"
    else:
        earnings_text = "📈 <b>История ваших начислений</b>\n\n"
        
        total_earned = sum([earn['earned'] for earn in earnings])
        
        for i, earn in enumerate(earnings, 1):
            amount = earn['amount']
            percent = earn['percent']
            earned = earn['earned']
            created = datetime.fromisoformat(earn['created_at']).strftime("%d.%m.%Y %H:%M")
            ref_id = earn['referral_id']
            
            earnings_text += (
                f"<b>{i}. От реферала {ref_id}</b>\n"
                f"├ 💸 Сумма платежа: {amount:.1f}$\n"
                f"├ 📊 Ваш процент: {percent}%\n"
                f"├ 🎯 Ваш доход: {earned:.1f}$\n"
                f"└ 📅 Дата: {created}\n\n"
            )
        
        earnings_text += f"<b>💰 Всего заработано: {total_earned:.1f}$</b>"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back:profile"))
    
    await callback.message.edit_text(
        earnings_text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "payout:request")
async def payout_request_callback(callback: CallbackQuery):
    """Запрос на вывод средств"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Сначала зарегистрируйтесь")
        return
    
    ref_stats = await db.get_referral_stats(user_id)
    if ref_stats:
        user.update(ref_stats)
    
    available = user.get('available_balance', 0.0)
    min_amount = config.WITHDRAW_MIN
    
    if available < min_amount:
        await callback.answer(
            f"❌ Минимальная сумма вывода: {min_amount:.1f} USDT", 
            show_alert=True
        )
        return
    
    withdrawal = await db.create_withdrawal(user_id, available)
    
    if withdrawal:
        if config.ADMIN_ID:
            try:
                await bot.send_message(
                    config.ADMIN_ID,
                    f"🤑 <b>НОВАЯ ЗАЯВКА НА ВЫВОД!</b>\n\n"
                    f"👤 Пользователь: {user_id}\n"
                    f"💰 Сумма: {available:.1f} USDT\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"🆔 ID вывода: {withdrawal['id']}"
                )
            except:
                pass
        
        await callback.message.edit_text(
            f"✅ <b>Заявка на вывод создана!</b>\n\n"
            f"<b>📋 ДЕТАЛИ ЗАЯВКИ:</b>\n"
            f"├ Номер: #{withdrawal['id']}\n"
            f"├ Сумма: <b>{available:.1f} USDT</b>\n"
            f"├ Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"└ Статус: ⏳ Ожидает обработки\n\n"
            f"<i>Спасибо, что вы с нами! 💫</i>"
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка при создании заявки</b>\n\nПожалуйста, попробуйте позже или обратитесь в поддержку."
        )
    
    await callback.answer()

@router.callback_query(F.data == "payout:history")
async def payout_history_callback(callback: CallbackQuery):
    """История выводов"""
    user_id = callback.from_user.id
    withdrawals = await db.get_withdrawals(user_id, 10)
    
    if not withdrawals:
        history_text = "📋 <b>История выводов</b>\n\nУ вас пока нет заявок на вывод."
    else:
        history_text = "📋 <b>История ваших выводов</b>\n\n"
        
        for i, wd in enumerate(withdrawals, 1):
            amount = wd['amount']
            status = wd['status']
            created = datetime.fromisoformat(wd['created_at']).strftime("%d.%m.%Y %H:%M")
            
            status_emoji = {
                'pending': '⏳',
                'completed': '✅',
                'rejected': '❌'
            }.get(status, '❓')
            
            status_text = {
                'pending': 'Ожидает',
                'completed': 'Выплачен',
                'rejected': 'Отклонен'
            }.get(status, status)
            
            history_text += (
                f"<b>{i}. Заявка #{wd['id']}</b>\n"
                f"├ 💰 Сумма: {amount:.1f}$\n"
                f"├ 📊 Статус: {status_emoji} {status_text}\n"
                f"└ 📅 Дата: {created}\n\n"
            )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back:profile"))
    
    await callback.message.edit_text(
        history_text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ В ЧАТЕ ====================

@router.message(F.chat.id == config.FORUM_CHAT_ID)
async def check_forum_user_subscription(message: Message):
    """Проверка подписки пользователя в форуме"""
    if message.from_user.is_bot:
        return
    
    user_id = message.from_user.id
    
    # Проверяем, не администратор ли
    try:
        chat_member = await bot.get_chat_member(message.chat.id, user_id)
        if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            return
    except:
        pass
    
    # Проверяем подписку
    has_subscription = await check_user_subscription(user_id, str(message.chat.id))
    
    if not has_subscription:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
            
            try:
                await bot.send_message(
                    user_id,
                    f"⚠️ <b>Ваше сообщение удалено из чата!</b>\n\n"
                    f"У вас отсутствует активная подписка на Tom's Mirror.\n"
                    f"Оплатите подписку, чтобы продолжить общение в чате:\n"
                    f"💎 /buy"
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение: {e}")

@router.chat_member(F.chat.id == config.FORUM_CHAT_ID)
async def handle_chat_member_update(update: ChatMemberUpdated):
    """Обработка обновлений участников чата"""
    user_id = update.new_chat_member.user.id
    
    if update.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
        await check_user_subscription(user_id, str(update.chat.id))
        logger.info(f"Пользователь {user_id} присоединился к чату {update.chat.id}")

# ==================== ФУНКЦИИ ДЛЯ ПРОВЕРКИ ПОДПИСОК ====================

async def check_user_subscription(user_id: int, chat_id: str = None) -> bool:
    """Проверка подписки пользователя и отправка предупреждений"""
    if not chat_id:
        chat_id = config.FORUM_CHAT_ID
    
    if not chat_id:
        return True
    
    # Проверяем, не является ли пользователь администратором
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            return True
    except:
        pass
    
    user = await db.get_user(user_id)
    
    has_active_subscription = False
    if user and user.get('subscription_end'):
        try:
            end = datetime.fromisoformat(user['subscription_end'])
            if end > datetime.now():
                has_active_subscription = True
        except:
            pass
    
    if has_active_subscription:
        await db.remove_subscription_warning(user_id, chat_id)
        return True
    else:
        warning = await db.get_subscription_warning(user_id, chat_id)
        
        if not warning:
            await db.add_subscription_warning(user_id, chat_id)
            
            try:
                await bot.send_message(
                    user_id,
                    f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
                    f"У вас отсутствует активная подписка на Tom's Mirror.\n\n"
                    f"⏰ <b>У вас есть {config.WARNING_DAYS} дня на оплату подписки.</b>\n"
                    f"❌ После этого вы будете НАВСЕГДА заблокированы в чате.\n\n"
                    f"💎 Оплатить подписку: /buy\n"
                    f"👤 Проверить статус: /me\n\n"
                    f"<i>Дата блокировки: {(datetime.now() + timedelta(days=config.WARNING_DAYS)).strftime('%d.%m.%Y')}</i>"
                )
                logger.info(f"Отправлено первое предупреждение пользователю {user_id} в чате {chat_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить предупреждение пользователю {user_id}: {e}")
            
            return False
        else:
            first_warning = datetime.fromisoformat(warning['first_warning_at'])
            days_passed = (datetime.now() - first_warning).days
            
            if days_passed >= 1 and not warning.get('warned_1_day'):
                try:
                    await bot.send_message(
                        user_id,
                        f"⏰ <b>НАПОМИНАНИЕ (1 день)</b>\n\n"
                        f"Прошёл 1 день с момента предупреждения.\n"
                        f"У вас осталось {config.WARNING_DAYS - 1} дня на оплату подписки.\n\n"
                        f"❌ Дата блокировки: {(first_warning + timedelta(days=config.WARNING_DAYS)).strftime('%d.%m.%Y')}\n\n"
                        f"💎 Оплатить: /buy"
                    )
                    await db.update_warning_status(user_id, chat_id, warned_day=1)
                except:
                    pass
            
            if days_passed >= 2 and not warning.get('warned_2_days'):
                try:
                    await bot.send_message(
                        user_id,
                        f"🚨 <b>СРОЧНОЕ НАПОМИНАНИЕ (2 дня)</b>\n\n"
                        f"Прошло 2 дня! Завтра вы будете НАВСЕГДА заблокированы в чате.\n\n"
                        f"💎 Оплатите подписку СЕГОДНЯ, чтобы остаться в чате."
                    )
                    await db.update_warning_status(user_id, chat_id, warned_day=2)
                except:
                    pass
            
            if days_passed >= config.WARNING_DAYS and not warning.get('kicked'):
                try:
                    if not has_active_subscription:
                        await bot.ban_chat_member(chat_id, user_id)
                        await db.update_warning_status(user_id, chat_id, kicked=True)
                        logger.info(f"Пользователь {user_id} ЗАБАНЕН в чате {chat_id}")
                        
                        try:
                            await bot.send_message(
                                user_id,
                                f"❌ <b>ВЫ ЗАБЛОКИРОВАНЫ В ЧАТЕ</b>\n\n"
                                f"Вы были заблокированы в чате из-за отсутствия активной подписки.\n"
                                f"Срок в {config.WARNING_DAYS} дня истёк.\n\n"
                                f"💎 Чтобы вернуться, оплатите подписку и напишите в поддержку: @tom_support"
                            )
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Не удалось забанить пользователя {user_id}: {e}")
            
            return False

async def subscription_warnings_checker():
    """Проверяет предупреждения и банит просроченных пользователей (каждые 6 часов)"""
    logger.info("Запуск фоновой проверки предупреждений о подписке")
    while True:
        try:
            if config.FORUM_CHAT_ID:
                warnings = await db.get_all_warnings(config.FORUM_CHAT_ID)
                
                try:
                    admins = await bot.get_chat_administrators(config.FORUM_CHAT_ID)
                    admin_ids = [admin.user.id for admin in admins]
                except:
                    admin_ids = []
                
                banned_today = 0
                
                for warning in warnings:
                    if warning.get('kicked'):
                        continue
                    
                    user_id = warning['user_id']
                    
                    if user_id in admin_ids:
                        continue
                    
                    first_warning = datetime.fromisoformat(warning['first_warning_at'])
                    days_passed = (datetime.now() - first_warning).days
                    
                    user = await db.get_user(user_id)
                    has_subscription = False
                    
                    if user and user.get('subscription_end'):
                        try:
                            end = datetime.fromisoformat(user['subscription_end'])
                            if end > datetime.now():
                                has_subscription = True
                        except:
                            pass
                    
                    if has_subscription:
                        await db.remove_subscription_warning(user_id, config.FORUM_CHAT_ID)
                        continue
                    
                    if days_passed >= config.WARNING_DAYS:
                        try:
                            await bot.ban_chat_member(config.FORUM_CHAT_ID, user_id)
                            await db.update_warning_status(user_id, config.FORUM_CHAT_ID, kicked=True)
                            banned_today += 1
                            logger.info(f"Пользователь {user_id} ЗАБАНЕН в чате (дней: {days_passed})")
                            
                            try:
                                await bot.send_message(
                                    user_id,
                                    f"❌ <b>ВЫ ЗАБЛОКИРОВАНЫ В ЧАТЕ</b>\n\n"
                                    f"Срок в {config.WARNING_DAYS} дня истёк.\n\n"
                                    f"💎 Чтобы вернуться, оплатите подписку: /buy"
                                )
                            except:
                                pass
                        except Exception as e:
                            logger.error(f"Не удалось забанить {user_id}: {e}")
                
                if banned_today > 0 and config.ADMIN_ID:
                    try:
                        await bot.send_message(
                            config.ADMIN_ID,
                            f"🔨 <b>Автоматическая блокировка</b>\n\n"
                            f"Забанено пользователей за неуплату: {banned_today}"
                        )
                    except:
                        pass
            
            await asyncio.sleep(21600)  # 6 часов
        except Exception as e:
            logger.error(f"Ошибка в subscription_warnings_checker: {e}")
            await asyncio.sleep(3600)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def add_to_chat(user_id: int):
    """Добавление пользователя в приватный чат"""
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHAT_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(days=1)
        )
        
        await bot.send_message(
            user_id,
            f"🔗 <b>Ваша ссылка для входа в приватный чат:</b>\n\n"
            f"<code>{invite_link.invite_link}</code>\n\n"
            f"<i>Ссылка действительна 24 часа и одноразовая! Не передавайте ее другим.</i>"
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении {user_id} в чат: {e}")
        return False

async def handle_payment(user_id: int, invoice_id: str, amount: float, plan_type: str = None):
    """Обработка платежа с партнерской логикой"""
    try:
        async with db.conn.execute(
            "SELECT status FROM payments WHERE invoice_id = ?", (invoice_id,)
        ) as cursor:
            payment_check = await cursor.fetchone()
            if payment_check and payment_check[0] in ['paid', 'processed']:
                logger.info(f"Платеж {invoice_id} уже обработан")
                return
        
        payment = await db.update_payment_status(invoice_id, 'paid')
        if not payment:
            return
        
        if not plan_type:
            plan_type, days = crypto_bot.get_plan_by_amount(amount)
            if not plan_type:
                await bot.send_message(user_id, "❌ Ошибка: неизвестная сумма платежа")
                return
        else:
            days = config.PRICES[plan_type]["days"]
        
        user = await db.extend_subscription(user_id, days, is_trial=False, plan_type=plan_type)
        if not user:
            return
        
        referrer_id = user.get('referrer_id')
        if referrer_id:
            referrer = await db.get_user(referrer_id)
            if referrer:
                percent = referrer.get('ref_percent', config.REFERRAL_PERCENT_NORMAL)
                earned = amount * (percent / 100)
                
                await db.add_referral_earning(
                    referrer_id=referrer_id,
                    referral_id=user_id,
                    payment_id=invoice_id,
                    amount=amount,
                    percent=percent,
                    earned=earned
                )
                
                if not user.get('converted_to_paid_at'):
                    await db.add_paid_referral(referrer_id, user_id)
                
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🎉 <b>НОВОЕ НАЧИСЛЕНИЕ!</b>\n\n"
                        f"👤 Реферал: {user_id}\n"
                        f"💸 Платёж: {amount:.1f}$\n"
                        f"📊 Ваш процент: {percent}%\n"
                        f"💰 Доход: {earned:.1f}$"
                    )
                except:
                    pass
        
        chat_added = await add_to_chat(user_id)
        user = await db.get_user(user_id)
        
        plan_names = {
            "week": "Недельный доступ",
            "month": "Месячный доступ", 
            "forever": "Пожизненный доступ"
        }
        
        if chat_added:
            message_parts = [
                f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>",
                f"",
                f"<b>📊 ТАРИФ:</b> {plan_names.get(plan_type, plan_type)}",
                f"<b>⏰ СРОК:</b> {days} дней",
                f"",
                f"<b>🔗 Ссылка на приватный чат отправлена выше.</b>",
                f""
            ]
            
            if plan_type == "week":
                message_parts.append("⚠️ <b>На недельной подписке партнерская система НЕ доступна.</b>")
                message_parts.append("💎 Чтобы получить партнерскую ссылку, выберите тариф на месяц или навсегда.")
            else:
                if user.get('referral_code'):
                    me = await bot.get_me()
                    ref_link = f"https://t.me/{me.username}?start={user['referral_code']}"
                    message_parts.append(f"<b>👥 ВАША ПАРТНЕРСКАЯ ССЫЛКА:</b>")
                    message_parts.append(f"<code>{ref_link}</code>")
                    message_parts.append("")
                    message_parts.append(f"💰 <b>Теперь вы получаете {user.get('ref_percent', config.REFERRAL_PERCENT_NORMAL)}% с платежей рефералов!</b>")
                else:
                    message_parts.append("👥 Партнерская ссылка будет доступна в профиле (/me)")
            
            message_parts.append("")
            message_parts.append("<i>Спасибо, что выбираете Tom's Mirror! 🚀</i>")
            
            await bot.send_message(user_id, "\n".join(message_parts))
        else:
            await bot.send_message(
                user_id,
                f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
                f"<b>📊 ТАРИФ:</b> {plan_names.get(plan_type, plan_type)}\n"
                f"<b>⏰ СРОК:</b> {days} дней\n\n"
                f"⚠️ <b>Не удалось отправить ссылку на чат.</b>\n"
                f"Пожалуйста, свяжитесь с поддержкой: @tom_support"
            )
        
        if config.FORUM_CHAT_ID:
            await db.remove_subscription_warning(user_id, config.FORUM_CHAT_ID)
        
        logger.info(f"Платеж {invoice_id} обработан для {user_id}, план: {plan_type}")
        
    except Exception as e:
        logger.error(f"Ошибка обработки платежа: {e}", exc_info=True)

async def payment_checker():
    """Проверка платежей"""
    logger.info("Запуск проверки платежей")
    while True:
        try:
            async with db.conn.execute(
                "SELECT * FROM payments WHERE status = 'pending'"
            ) as cursor:
                async for row in cursor:
                    payment = dict(row)
                    invoice = await crypto_bot.check_payment(payment['invoice_id'])
                    if invoice and invoice.get("status") == "paid":
                        await handle_payment(
                            payment['user_id'], 
                            payment['invoice_id'], 
                            payment['amount'], 
                            payment['plan_type']
                        )
                        await db.update_payment_status(payment['invoice_id'], 'processed')
            
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка payment_checker: {e}")
            await asyncio.sleep(60)

async def subscription_checker():
    """Проверка истекших подписок"""
    logger.info("Запуск проверки подписок")
    while True:
        try:
            expired_users = await db.get_expired_users()
            for user in expired_users:
                await remove_from_chat(user['user_id'])
                
                if user.get('is_trial'):
                    msg = "🎁 <b>Тестовый период закончился!</b>\n\n💎 Продлить доступ можно через меню 'Приобрести доступ'"
                else:
                    msg = "⏰ <b>Ваша подписка закончилась!</b>\n\n💎 Продлить доступ можно через меню 'Приобрести доступ'"
                
                try:
                    await bot.send_message(user['user_id'], msg)
                except:
                    pass
                
                await db.conn.execute(
                    "UPDATE users SET is_active = 0, is_trial = 0 WHERE user_id = ?",
                    (user['user_id'],)
                )
                await db.conn.commit()
            
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Ошибка subscription_checker: {e}")
            await asyncio.sleep(300)

async def remove_from_chat(user_id: int):
    """Удаление пользователя из приватного чата"""
    try:
        await bot.ban_chat_member(
            chat_id=config.PRIVATE_CHAT_ID,
            user_id=user_id
        )
        await bot.unban_chat_member(
            chat_id=config.PRIVATE_CHAT_ID,
            user_id=user_id
        )
        logger.info(f"Пользователь {user_id} удален из чата")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
        return False

async def clean_expired_invoices():
    """Очистка просроченных инвойсов"""
    while True:
        try:
            expiry_time = (datetime.now() - timedelta(hours=1)).isoformat()
            
            await db.conn.execute(
                "DELETE FROM payments WHERE status = 'pending' AND paid_at IS NULL AND created_at < ?",
                (expiry_time,)
            )
            await db.conn.commit()
            
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Ошибка в clean_expired_invoices: {e}")
            await asyncio.sleep(300)

# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

async def main():
    try:
        logger.info("=" * 60)
        logger.info("Запуск Telegram бота Tom's Mirror...")
        
        await db.init_db()
        
        me = await bot.get_me()
        logger.info(f"Бот: @{me.username} (ID: {me.id})")
        logger.info(f"Приватный чат: {config.PRIVATE_CHAT_ID}")
        logger.info(f"Форум для проверки подписок: {config.FORUM_CHAT_ID or 'Не указан'}")
        logger.info(f"Дни до блокировки: {config.WARNING_DAYS}")
        
        if config.FORUM_CHAT_ID:
            try:
                chat = await bot.get_chat(config.FORUM_CHAT_ID)
                logger.info(f"Чат форума найден: {chat.title}")
                
                chat_member = await bot.get_chat_member(config.FORUM_CHAT_ID, me.id)
                if chat_member.status in ['administrator', 'creator']:
                    logger.info("✅ Бот является администратором в чате форума")
                    if hasattr(chat_member, 'can_restrict_members') and not chat_member.can_restrict_members:
                        logger.warning("⚠️ У бота нет права на блокировку пользователей!")
                    else:
                        logger.info("✅ У бота есть право на блокировку пользователей")
                else:
                    logger.warning("❌ Бот НЕ является администратором в чате форума!")
            except Exception as e:
                logger.error(f"Ошибка при проверке чата форума: {e}")
        
        logger.info("Запуск фоновых задач...")
        asyncio.create_task(payment_checker())
        asyncio.create_task(subscription_checker())
        asyncio.create_task(subscription_warnings_checker())
        asyncio.create_task(clean_expired_invoices())
        
        logger.info("Все задачи запущены")
        logger.info("=" * 60)
        
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}", exc_info=True)
        raise
    finally:
        logger.info("Бот Tom's Mirror остановлен")
        await db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
