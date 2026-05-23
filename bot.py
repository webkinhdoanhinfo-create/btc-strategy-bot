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


def fetch_prices():
    """Lấy giá BTC và ETH từ CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum",
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_high_24h": "true",
            "include_low_24h": "true",
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        btc = data["bitcoin"]
        eth = data["ethereum"]
        return {
            "btc_price": btc["usd"],
            "btc_change": btc["usd_24h_change"],
            "btc_high": btc["usd_24h_high"],
            "btc_low": btc["usd_24h_low"],
            "eth_price": eth["usd"],
            "eth_change": eth["usd_24h_change"],
            "eth_high": eth["usd_24h_high"],
            "eth_low": eth["usd_24h_low"],
        }
    except Exception as e:
        logger.error(f"Lỗi fetch giá: {e}")
        return None


def generate_strategy(prices):
    """Gọi Claude API phân tích chiến lược"""
    today = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%d/%m/%Y")

    prompt = f"""Bạn là trader chuyên nghiệp phân tích crypto. Hôm nay là {today}.

Dữ liệu giá hiện tại:
- BTC: ${prices['btc_price']:,.0f} | 24h: {prices['btc_change']:+.2f}% | High: ${prices['btc_high']:,.0f} | Low: ${prices['btc_low']:,.0f}
- ETH: ${prices['eth_price']:,.2f} | 24h: {prices['eth_change']:+.2f}% | High: ${prices['eth_high']:,.2f} | Low: ${prices['eth_low']:,.2f}

Hãy phân tích đa khung H4-D1-D3-W và lên kế hoạch giao dịch ngày hôm nay theo format sau (dùng emoji, ngắn gọn súc tích cho Telegram):

📊 *CHIẾN LƯỢC NGÀY {today}*

*BTC/USD* ${prices['btc_price']:,.0f}
• Bias tổng: [Bull/Bear/Neutral]
• Range hôm nay: $X – $X
• 🟢 LONG: vùng $X–$X | SL $X | TP $X
• 🔴 SHORT: vùng $X–$X | SL $X | TP $X
• ⚠️ Vùng tránh: $X–$X
• Kịch bản chính: [mô tả ngắn]

*ETH/USD* ${prices['eth_price']:,.2f}
• Bias tổng: [Bull/Bear/Neutral]
• Range hôm nay: $X – $X
• 🟢 LONG: vùng $X–$X | SL $X | TP $X
• 🔴 SHORT: vùng $X–$X | SL $X | TP $X
• ⚠️ Vùng tránh: $X–$X
• Kịch bản chính: [mô tả ngắn]

📌 *Lưu ý quan trọng hôm nay:*
[2-3 điểm cần chú ý]

_Chỉ đổi hướng khi break trend có xác nhận H4. Quản lý vốn: max 2-3% mỗi lệnh._"""

    message = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def send_strategy(bot, chat_id):
    """Fetch giá → phân tích → gửi Telegram"""
    try:
        await bot.send_message(chat_id=chat_id, text="⏳ Đang phân tích thị trường...")
        prices = fetch_prices()
        if not prices:
            await bot.send_message(chat_id=chat_id, text="❌ Lỗi lấy giá. Thử lại sau.")
            return
        strategy = generate_strategy(prices)
        await bot.send_message(
            chat_id=chat_id,
            text=strategy,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Lỗi send_strategy: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Lỗi: {str(e)}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *BTC/ETH Strategy Bot*\n\n"
        "Lệnh có sẵn:\n"
        "/chienluoc – Phân tích ngay bây giờ\n"
        "/gia – Xem giá BTC/ETH hiện tại\n\n"
        "Bot sẽ tự động gửi chiến lược lúc *7:00 sáng* mỗi ngày.",
        parse_mode="Markdown"
    )


async def cmd_chienluoc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /chienluoc – trigger thủ công"""
    await send_strategy(context.bot, update.effective_chat.id)


async def cmd_gia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /gia – xem giá nhanh"""
    prices = fetch_prices()
    if not prices:
        await update.message.reply_text("❌ Không lấy được giá.")
        return
    text = (
        f"💰 *Giá hiện tại*\n\n"
        f"*BTC:* ${prices['btc_price']:,.0f} ({prices['btc_change']:+.2f}%)\n"
        f"  High: ${prices['btc_high']:,.0f} | Low: ${prices['btc_low']:,.0f}\n\n"
        f"*ETH:* ${prices['eth_price']:,.2f} ({prices['eth_change']:+.2f}%)\n"
        f"  High: ${prices['eth_high']:,.2f} | Low: ${prices['eth_low']:,.2f}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def scheduled_job(bot):
    """Job chạy lúc 7:00 sáng"""
    logger.info("Chạy scheduled job 7:00 sáng...")
    await send_strategy(bot, CHAT_ID)


async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chienluoc", cmd_chienluoc))
    app.add_handler(CommandHandler("gia", cmd_gia))

    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Asia/Ho_Chi_Minh"))
    scheduler.add_job(
        scheduled_job,
        trigger="cron",
        hour=7,
        minute=0,
        args=[app.bot]
    )
    scheduler.start()
    logger.info("Bot đã khởi động. Scheduler 7:00 sáng VN đã bật.")

    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
