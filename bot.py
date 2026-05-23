import os
import asyncio
import logging
import requests
from datetime import datetime
from anthropic import Anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CHAT_ID = os.environ.get("CHAT_ID")

anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

def fetch_prices():
    """Thử nhiều API, lấy cái nào được trước"""
    # 1. Thử Binance
    try:
        btc = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", headers=HEADERS, timeout=8).json()
        eth = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT", headers=HEADERS, timeout=8).json()
        if "lastPrice" in btc:
            logger.info("Dùng Binance API")
            return {
                "btc_price": float(btc["lastPrice"]), "btc_change": float(btc["priceChangePercent"]),
                "btc_high": float(btc["highPrice"]), "btc_low": float(btc["lowPrice"]),
                "eth_price": float(eth["lastPrice"]), "eth_change": float(eth["priceChangePercent"]),
                "eth_high": float(eth["highPrice"]), "eth_low": float(eth["lowPrice"]),
            }
    except Exception as e:
        logger.warning(f"Binance lỗi: {e}")

    # 2. Thử OKX
    try:
        btc = requests.get("https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT", headers=HEADERS, timeout=8).json()
        eth = requests.get("https://www.okx.com/api/v5/market/ticker?instId=ETH-USDT", headers=HEADERS, timeout=8).json()
        if btc.get("data"):
            b, e = btc["data"][0], eth["data"][0]
            logger.info("Dùng OKX API")
            return {
                "btc_price": float(b["last"]), "btc_change": float(b["change24h"]) * 100 if float(b["open24h"]) else 0,
                "btc_high": float(b["high24h"]), "btc_low": float(b["low24h"]),
                "eth_price": float(e["last"]), "eth_change": float(e["change24h"]) * 100 if float(e["open24h"]) else 0,
                "eth_high": float(e["high24h"]), "eth_low": float(e["low24h"]),
            }
    except Exception as e:
        logger.warning(f"OKX lỗi: {e}")

    # 3. Thử CoinCap
    try:
        btc = requests.get("https://api.coincap.io/v2/assets/bitcoin", headers=HEADERS, timeout=8).json()["data"]
        eth = requests.get("https://api.coincap.io/v2/assets/ethereum", headers=HEADERS, timeout=8).json()["data"]
        logger.info("Dùng CoinCap API")
        return {
            "btc_price": float(btc["priceUsd"]), "btc_change": float(btc["changePercent24Hr"]),
            "btc_high": float(btc["priceUsd"]) * 1.02, "btc_low": float(btc["priceUsd"]) * 0.98,
            "eth_price": float(eth["priceUsd"]), "eth_change": float(eth["changePercent24Hr"]),
            "eth_high": float(eth["priceUsd"]) * 1.02, "eth_low": float(eth["priceUsd"]) * 0.98,
        }
    except Exception as e:
        logger.warning(f"CoinCap lỗi: {e}")

    return None


def generate_strategy(prices):
    today = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%d/%m/%Y")
    prompt = f"""Bạn là trader chuyên nghiệp phân tích crypto. Hôm nay là {today}.

Dữ liệu giá hiện tại:
- BTC: ${prices['btc_price']:,.0f} | 24h: {prices['btc_change']:+.2f}% | High: ${prices['btc_high']:,.0f} | Low: ${prices['btc_low']:,.0f}
- ETH: ${prices['eth_price']:,.2f} | 24h: {prices['eth_change']:+.2f}% | High: ${prices['eth_high']:,.2f} | Low: ${prices['eth_low']:,.2f}

Phân tích đa khung H4-D1-D3-W và lên kế hoạch giao dịch theo format (dùng emoji, ngắn gọn cho Telegram):

📊 *CHIẾN LƯỢC NGÀY {today}*

*BTC/USD* ${prices['btc_price']:,.0f}
• Bias: [Bull/Bear/Neutral]
• Range: $X – $X
• 🟢 LONG: $X–$X | SL $X | TP $X
• 🔴 SHORT: $X–$X | SL $X | TP $X
• ⚠️ Tránh: $X–$X
• Kịch bản: [mô tả ngắn]

*ETH/USD* ${prices['eth_price']:,.2f}
• Bias: [Bull/Bear/Neutral]
• Range: $X – $X
• 🟢 LONG: $X–$X | SL $X | TP $X
• 🔴 SHORT: $X–$X | SL $X | TP $X
• ⚠️ Tránh: $X–$X
• Kịch bản: [mô tả ngắn]

📌 *Lưu ý:*
[2-3 điểm quan trọng]"""

    message = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def send_strategy(bot, chat_id):
    try:
        await bot.send_message(chat_id=chat_id, text="⏳ Đang phân tích thị trường...")
        prices = fetch_prices()
        if not prices:
            await bot.send_message(chat_id=chat_id, text="❌ Lỗi lấy giá từ tất cả API. Thử lại sau.")
            return
        strategy = generate_strategy(prices)
        await bot.send_message(chat_id=chat_id, text=strategy, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {str(e)[:200]}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *BTC/ETH Strategy Bot*\n\n"
        "/chienluoc – Phân tích ngay\n"
        "/gia – Xem giá hiện tại\n\n"
        "Bot tự động gửi lúc *7:00 sáng* mỗi ngày.",
        parse_mode="Markdown"
    )


async def cmd_chienluoc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_strategy(context.bot, update.effective_chat.id)


async def cmd_gia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = fetch_prices()
    if not prices:
        await update.message.reply_text("❌ Không lấy được giá.")
        return
    text = (
        f"💰 *Giá hiện tại*\n\n"
        f"*BTC:* ${prices['btc_price']:,.0f} ({prices['btc_change']:+.2f}%)\n"
        f"  H: ${prices['btc_high']:,.0f} | L: ${prices['btc_low']:,.0f}\n\n"
        f"*ETH:* ${prices['eth_price']:,.2f} ({prices['eth_change']:+.2f}%)\n"
        f"  H: ${prices['eth_high']:,.2f} | L: ${prices['eth_low']:,.2f}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def scheduled_job(bot):
    logger.info("Chạy scheduled 7:00 sáng...")
    await send_strategy(bot, CHAT_ID)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chienluoc", cmd_chienluoc))
    app.add_handler(CommandHandler("gia", cmd_gia))

    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Ho_Chi_Minh"))
    scheduler.add_job(
        lambda: asyncio.ensure_future(scheduled_job(app.bot)),
        trigger="cron", hour=7, minute=0,
    )
    scheduler.start()
    logger.info("Bot khởi động OK.")
    app.run_polling()


if __name__ == "__main__":
    main()
