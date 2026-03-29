import aiosqlite
import logging
from datetime import datetime, timedelta
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseSimple:
    def __init__(self, db_path="bot_simple.db"):
        self.db_path = db_path
        self.conn = None

    async def init_db(self):
        """Инициализация базы данных"""
        self.conn = await aiosqlite.connect(self.db_path)
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_active BOOLEAN DEFAULT 1,
                subscription_end TEXT,
                is_trial BOOLEAN DEFAULT 0,
                has_used_trial BOOLEAN DEFAULT 0,
                referrer_id INTEGER,
                referral_code TEXT UNIQUE,
                balance REAL DEFAULT 0.0,
                has_received_bonus BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                converted_to_paid_at TEXT,
                notified_7_days BOOLEAN DEFAULT 0,
                notified_3_days BOOLEAN DEFAULT 0,
                notified_1_day BOOLEAN DEFAULT 0,
                notified_24h BOOLEAN DEFAULT 0,
                notified_2h BOOLEAN DEFAULT 0,
                ref_percent INTEGER DEFAULT 25,
                ref_status TEXT DEFAULT 'referrer',
                earned_total REAL DEFAULT 0.0,
                available_balance REAL DEFAULT 0.0,
                total_referrals INTEGER DEFAULT 0,
                paid_referrals INTEGER DEFAULT 0,
                trial_referrals INTEGER DEFAULT 0
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                plan_type TEXT,
                status TEXT,
                paid_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                tx_hash TEXT
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS referral_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referral_id INTEGER,
                payment_id TEXT,
                amount REAL,
                percent INTEGER,
                earned REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS subscription_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id TEXT,
                first_warning_at TEXT DEFAULT CURRENT_TIMESTAMP,
                warned_1_day BOOLEAN DEFAULT 0,
                warned_2_days BOOLEAN DEFAULT 0,
                warned_3_days BOOLEAN DEFAULT 0,
                kicked BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS subscription_extensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                days_added INTEGER NOT NULL,
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        self.conn.row_factory = aiosqlite.Row
        await self.conn.commit()
        logger.info("База данных инициализирована")
        return self.conn

    async def close(self):
        """Закрытие соединения с БД"""
        if self.conn:
            await self.conn.close()

    async def get_user(self, user_id: int):
        """Получение пользователя по ID"""
        async with self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def create_user(self, user_id: int, referrer_id: int = None):
        """Создание нового пользователя"""
        try:
            if referrer_id == user_id:
                referrer_id = None
            
            await self.conn.execute(
                "INSERT INTO users (user_id, referrer_id) VALUES (?, ?)",
                (user_id, referrer_id)
            )
            await self.conn.commit()
            return await self.get_user(user_id)
        except aiosqlite.IntegrityError:
            return await self.get_user(user_id)

    async def set_referral_code(self, user_id: int, code: str):
        """Установка реферального кода"""
        await self.conn.execute(
            "UPDATE users SET referral_code = ? WHERE user_id = ?",
            (code, user_id)
        )
        await self.conn.commit()
        return await self.get_user(user_id)

    async def get_user_by_referral_code(self, code: str):
        """Получение пользователя по реферальному коду"""
        async with self.conn.execute(
            "SELECT * FROM users WHERE referral_code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                user = dict(row)
                if user.get('ref_percent') == 50 and user.get('ref_status') == 'partner':
                    return user
                elif user.get('converted_to_paid_at'):
                    return user
            return None

    async def activate_trial(self, user_id: int, trial_days: int):
        """Активация тест-драйва"""
        subscription_end = (datetime.now() + timedelta(days=trial_days)).isoformat()
        await self.conn.execute(
            "UPDATE users SET is_trial = 1, has_used_trial = 1, subscription_end = ? WHERE user_id = ?",
            (subscription_end, user_id)
        )
        await self.conn.commit()
        return await self.get_user(user_id)

    async def extend_subscription(self, user_id: int, days: int, is_trial: bool = False, plan_type: str = None):
        """Продление подписки"""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        if user.get('subscription_end'):
            try:
                current_end = datetime.fromisoformat(user['subscription_end'])
                if current_end > datetime.now():
                    new_end = current_end + timedelta(days=days)
                else:
                    new_end = datetime.now() + timedelta(days=days)
            except:
                new_end = datetime.now() + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        subscription_end = new_end.isoformat()
        
        if not is_trial:
            if not user.get('converted_to_paid_at'):
                converted_to_paid_at = datetime.now().isoformat()
                
                should_generate_ref_code = False
                if plan_type and plan_type != "week":
                    should_generate_ref_code = True
                
                if should_generate_ref_code and not user.get('referral_code'):
                    referral_code = str(uuid.uuid4())[:8]
                    await self.conn.execute(
                        "UPDATE users SET subscription_end = ?, is_trial = 0, converted_to_paid_at = ?, referral_code = ? WHERE user_id = ?",
                        (subscription_end, converted_to_paid_at, referral_code, user_id)
                    )
                else:
                    await self.conn.execute(
                        "UPDATE users SET subscription_end = ?, is_trial = 0, converted_to_paid_at = ? WHERE user_id = ?",
                        (subscription_end, converted_to_paid_at, user_id)
                    )
            else:
                await self.conn.execute(
                    "UPDATE users SET subscription_end = ?, is_trial = 0 WHERE user_id = ?",
                    (subscription_end, user_id)
                )
        else:
            await self.conn.execute(
                "UPDATE users SET subscription_end = ?, is_trial = 1 WHERE user_id = ?",
                (subscription_end, user_id)
            )
        
        await self.conn.commit()
        return await self.get_user(user_id)

    async def create_payment(self, user_id: int, invoice_id: str, amount: float, currency: str, plan_type: str):
        """Создание записи о платеже"""
        await self.conn.execute(
            "INSERT INTO payments (invoice_id, user_id, amount, currency, plan_type, status) VALUES (?, ?, ?, ?, ?, ?)",
            (invoice_id, user_id, amount, currency, plan_type, 'pending')
        )
        await self.conn.commit()
        
        async with self.conn.execute(
            "SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_payment_status(self, invoice_id: str, status: str):
        """Обновление статуса платежа"""
        paid_at = datetime.now().isoformat() if status == 'paid' else None
        
        if paid_at:
            await self.conn.execute(
                "UPDATE payments SET status = ?, paid_at = ? WHERE invoice_id = ?",
                (status, paid_at, invoice_id)
            )
        else:
            await self.conn.execute(
                "UPDATE payments SET status = ? WHERE invoice_id = ?",
                (status, invoice_id)
            )
        
        await self.conn.commit()
        
        async with self.conn.execute(
            "SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_referral(self, referrer_id: int, referral_id: int):
        """Добавление реферала и увеличение счетчика"""
        await self.conn.execute(
            "UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = ?",
            (referrer_id,)
        )
        await self.conn.commit()

    async def add_paid_referral(self, referrer_id: int, referral_id: int):
        """Добавление оплатившего реферала"""
        await self.conn.execute(
            "UPDATE users SET paid_referrals = paid_referrals + 1 WHERE user_id = ?",
            (referrer_id,)
        )
        await self.conn.commit()

    async def add_trial_referral(self, referrer_id: int, referral_id: int):
        """Добавление реферала, использовавшего триал"""
        await self.conn.execute(
            "UPDATE users SET trial_referrals = trial_referrals + 1 WHERE user_id = ?",
            (referrer_id,)
        )
        await self.conn.commit()

    async def add_referral_earning(self, referrer_id: int, referral_id: int, payment_id: str, amount: float, percent: int, earned: float):
        """Добавление записи о начислении реферального вознаграждения"""
        await self.conn.execute(
            """INSERT INTO referral_earnings 
               (referrer_id, referral_id, payment_id, amount, percent, earned) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (referrer_id, referral_id, payment_id, amount, percent, earned)
        )
        
        await self.conn.execute(
            "UPDATE users SET earned_total = earned_total + ?, available_balance = available_balance + ? WHERE user_id = ?",
            (earned, earned, referrer_id)
        )
        
        await self.conn.commit()

    async def get_referral_stats(self, user_id: int):
        """Получение статистики рефералов"""
        async with self.conn.execute(
            "SELECT total_referrals, paid_referrals, trial_referrals, earned_total, available_balance, ref_percent, ref_status FROM users WHERE user_id = ?", 
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def update_ref_percent(self, user_id: int, percent: int, status: str = None):
        """Обновление процента и статуса реферера"""
        if status:
            await self.conn.execute(
                "UPDATE users SET ref_percent = ?, ref_status = ? WHERE user_id = ?",
                (percent, status, user_id)
            )
        else:
            await self.conn.execute(
                "UPDATE users SET ref_percent = ? WHERE user_id = ?",
                (percent, user_id)
            )
        await self.conn.commit()
        return await self.get_user(user_id)

    async def create_withdrawal(self, user_id: int, amount: float):
        """Создание заявки на вывод"""
        await self.conn.execute(
            "INSERT INTO withdrawals (user_id, amount, status) VALUES (?, ?, ?)",
            (user_id, amount, 'pending')
        )
        
        await self.conn.execute(
            "UPDATE users SET available_balance = available_balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        
        await self.conn.commit()
        
        async with self.conn.execute(
            "SELECT * FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_withdrawals(self, user_id: int, limit: int = 10):
        """Получение истории выводов"""
        withdrawals = []
        async with self.conn.execute(
            "SELECT * FROM withdrawals WHERE user_id = ? ORDER BY id DESC LIMIT ?", 
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                withdrawals.append(dict(row))
        return withdrawals

    async def update_withdrawal_status(self, withdrawal_id: int, status: str, tx_hash: str = None):
        """Обновление статуса вывода"""
        completed_at = datetime.now().isoformat() if status == 'completed' else None
        
        if tx_hash:
            await self.conn.execute(
                "UPDATE withdrawals SET status = ?, completed_at = ?, tx_hash = ? WHERE id = ?",
                (status, completed_at, tx_hash, withdrawal_id)
            )
        else:
            await self.conn.execute(
                "UPDATE withdrawals SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, withdrawal_id)
            )
        
        await self.conn.commit()

    async def get_referrals(self, user_id: int):
        """Получение списка рефералов"""
        referrals = []
        async with self.conn.execute(
            """SELECT u.user_id, u.created_at, u.converted_to_paid_at, u.has_used_trial,
                      COUNT(p.invoice_id) as payments_count,
                      SUM(p.amount) as total_spent
               FROM users u
               LEFT JOIN payments p ON u.user_id = p.user_id AND p.status = 'paid'
               WHERE u.referrer_id = ?
               GROUP BY u.user_id
               ORDER BY u.created_at DESC""",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                referrals.append(dict(row))
        return referrals

    async def get_referral_earnings(self, user_id: int, limit: int = 10):
        """Получение истории начислений"""
        earnings = []
        async with self.conn.execute(
            """SELECT re.*, u.user_id as referral_user_id
               FROM referral_earnings re
               LEFT JOIN users u ON re.referral_id = u.user_id
               WHERE re.referrer_id = ?
               ORDER BY re.created_at DESC LIMIT ?""",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                earnings.append(dict(row))
        return earnings

    async def get_trial_referrals_count(self, user_id: int):
        """Количество рефералов, использовавших триал"""
        async with self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ? AND has_used_trial = 1", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    # СИСТЕМА ПРЕДУПРЕЖДЕНИЙ
    async def add_subscription_warning(self, user_id: int, chat_id: str):
        """Добавить предупреждение о подписке"""
        try:
            await self.conn.execute(
                "INSERT OR REPLACE INTO subscription_warnings (user_id, chat_id, first_warning_at) VALUES (?, ?, ?)",
                (user_id, chat_id, datetime.now().isoformat())
            )
            await self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении предупреждения: {e}")
            return False

    async def get_subscription_warning(self, user_id: int, chat_id: str):
        """Получить предупреждение о подписке"""
        async with self.conn.execute(
            "SELECT * FROM subscription_warnings WHERE user_id = ? AND chat_id = ?", (user_id, chat_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def remove_subscription_warning(self, user_id: int, chat_id: str):
        """Удалить предупреждение о подписке"""
        await self.conn.execute(
            "DELETE FROM subscription_warnings WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id)
        )
        await self.conn.commit()

    async def update_warning_status(self, user_id: int, chat_id: str, warned_day: int = None, kicked: bool = None):
        """Обновить статус предупреждения"""
        if warned_day is not None:
            column = f"warned_{warned_day}_days"
            await self.conn.execute(
                f"UPDATE subscription_warnings SET {column} = 1 WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
        if kicked is not None:
            await self.conn.execute(
                "UPDATE subscription_warnings SET kicked = 1 WHERE user_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
        await self.conn.commit()

    async def get_all_warnings(self, chat_id: str = None):
        """Получить все предупреждения"""
        warnings = []
        if chat_id:
            async with self.conn.execute(
                "SELECT * FROM subscription_warnings WHERE chat_id = ?", (chat_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    warnings.append(dict(row))
        else:
            async with self.conn.execute(
                "SELECT * FROM subscription_warnings"
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    warnings.append(dict(row))
        return warnings

    async def get_expired_users(self):
        """Пользователи с истекшей подпиской"""
        current_time = datetime.now().isoformat()
        users = []
        async with self.conn.execute(
            "SELECT * FROM users WHERE subscription_end < ? AND is_active = 1", (current_time,)
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                users.append(dict(row))
        return users

    async def get_trial_users(self):
        """Пользователи на триале"""
        users = []
        async with self.conn.execute(
            "SELECT * FROM users WHERE is_trial = 1"
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                users.append(dict(row))
        return users

    async def mark_notified(self, user_id: int, notification_type: str):
        """Отметить уведомление как отправленное"""
        column_map = {
            '7_days': 'notified_7_days',
            '3_days': 'notified_3_days',
            '1_day': 'notified_1_day',
            '24h': 'notified_24h',
            '2h': 'notified_2h'
        }
        
        if notification_type in column_map:
            column = column_map[notification_type]
            await self.conn.execute(
                f"UPDATE users SET {column} = 1 WHERE user_id = ?",
                (user_id,)
            )
            await self.conn.commit()

    async def get_referrals_count(self, user_id: int):
        """Количество рефералов"""
        async with self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_paid_referrals_count(self, user_id: int):
        """Количество рефералов, купивших подписку"""
        async with self.conn.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ? AND converted_to_paid_at IS NOT NULL", (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

db = DatabaseSimple()