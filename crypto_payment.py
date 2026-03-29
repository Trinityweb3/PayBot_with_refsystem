import aiohttp
import logging
from typing import Optional, Dict, Tuple
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoPayment:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api"
        self.headers = {
            "Crypto-Pay-API-Token": token,
            "Content-Type": "application/json"
        }

    def get_plan_by_amount(self, amount: float) -> Tuple[Optional[str], Optional[int]]:
        """Определяем тариф по сумме платежа"""
        for plan_type, plan_data in config.PRICES.items():
            if abs(amount - plan_data["amount"]) < 0.01:
                return plan_type, plan_data["days"]
        return None, None

    async def create_invoice(self, amount: float, currency: str = "USDT",
                             description: str = None, plan_type: str = None) -> Optional[Dict]:
        url = f"{self.base_url}/createInvoice"
        
        if not description and plan_type and plan_type in config.PRICES:
            description = config.PRICES[plan_type]["description"]
        
        payload = {
            "asset": currency,
            "amount": str(amount),
            "description": description or "Оплата подписки",
            "expires_in": 1800,
            "paid_btn_name": "openBot",
            "paid_btn_url": f"https://t.me/{config.BOT_NAME}",
            "allow_comments": False,
            "allow_anonymous": False
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result")
                    else:
                        logger.error(f"Error creating invoice: {data}")
                        return None
            except Exception as e:
                logger.error(f"Exception creating invoice: {e}")
                return None

    async def get_invoices(self, invoice_ids: Optional[str] = None,
                           status: Optional[str] = None,
                           offset: int = 0, count: int = 100) -> Optional[Dict]:
        url = f"{self.base_url}/getInvoices"
        params = {"offset": offset, "count": count}
        if status:
            params["status"] = status
        if invoice_ids:
            params["invoice_ids"] = invoice_ids
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=self.headers, params=params) as response:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result")
                    else:
                        logger.error(f"Error getting invoices: {data}")
                        return None
            except Exception as e:
                logger.error(f"Exception getting invoices: {e}")
                return None

    async def check_payment(self, invoice_id: str) -> Optional[Dict]:
        invoices = await self.get_invoices(invoice_ids=invoice_id)
        if invoices and "items" in invoices and len(invoices["items"]) > 0:
            return invoices["items"][0]
        return None

crypto_bot = CryptoPayment(config.CRYPTO_BOT_TOKEN)