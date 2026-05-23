import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import time
import pytz

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"

def get_price(symbol: str) -> float | None:
    """Lấy giá từ Binance API với timeout và retry."""
    try:
        response = requests.get(
            BINANCE_URL,
            params={"symbol": symbol},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return float(data["price"])
    except requests.exceptions.Timeout:
        logger.error(f"Timeout khi lấy giá {symbol}")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Lỗi kết nối khi lấy giá {symbol}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error {e.response.status_code} khi lấy giá {symbol}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Lỗi parse dữ liệu {symbol}: {e}")
        return None

def format_price(price: float) -> str:
    """Format giá với dấu phẩy ngàn."""
    return f"{price:,.2f}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *BTC/ETH Strategy Bot*\n\n"
        "/chienluoc – Phân tích ngay\n"
        "/gia – Xem giá hiện tại\n\n"
        "Bot tự động gửi lúc *7:00 sáng* mỗi ngày."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def gia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /gia - hiển thị giá BTC và ETH hiện tại."""
    msg = await update.message.reply_text("⏳ Đang lấy giá...")

    btc = get_price("BTCUSDT")
    eth = get_price("ETHUSDT")

    if btc is None and eth is None:
        await msg.edit_text("❌ Không lấy được giá. Vui lòng thử lại sau.")
        return

    lines = ["💰 *Giá hiện tại*\n"]
    if btc:
        lines.append(f"• BTC: `${format_price(btc)}`")
    else:
        lines.append("• BTC: ❌ Không lấy được")

    if eth:
        lines.append(f"• ETH: `${format_price(eth)}`")
    else:
        lines.append("• ETH: ❌ Không lấy được")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")

async def chienluoc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /chienluoc - phân tích đơn giản dựa trên giá."""
    msg = await update.message.reply_text("⏳ Đang phân tích thị trường...")

    btc = get_price("BTCUSDT")
    eth = get_price("ETHUSDT")

    if btc is None or eth is None:
        await msg.edit_text("❌ Lỗi lấy giá. Thử lại sau.")
        return

    # Tỉ lệ ETH/BTC
    ratio = eth / btc * 100

    # Phân tích đơn giản
    if btc > 100000:
        btc_signal = "🟢 BTC đang ở vùng cao – cân nhắc chốt lời một phần"
    elif btc > 80000:
        btc_signal = "🟡 BTC đang ở vùng trung bình – giữ vị thế"
    else:
        btc_signal = "🔴 BTC đang ở vùng thấp – cơ hội tích lũy"

    if ratio > 5:
        eth_signal = "🟢 ETH mạnh hơn BTC – ETH đang dẫn dắt"
    elif ratio > 3:
        eth_signal = "🟡 ETH theo sát BTC"
    else:
        eth_signal = "🔴 ETH yếu hơn BTC"

    text = (
        f"📊 *Phân tích thị trường*\n\n"
        f"• BTC: `${format_price(btc)}`\n"
        f"• ETH: `${format_price(eth)}`\n"
        f"• Tỉ lệ ETH/BTC: `{ratio:.2f}%`\n\n"
        f"{btc_signal}\n"
        f"{eth_signal}"
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def gui_bao_cao_sang(context: ContextTypes.DEFAULT_TYPE):
    """Gửi báo cáo tự động lúc 7:00 sáng."""
    chat_id = context.job.chat_id

    btc = get_price("BTCUSDT")
    eth = get_price("ETHUSDT")

    if btc is None or eth is None:
        await context.bot.send_message(chat_id, "❌ Không lấy được giá sáng nay.")
        return

    text = (
        f"🌅 *Báo cáo sáng – BTC/ETH*\n\n"
        f"• BTC: `${format_price(btc)}`\n"
        f"• ETH: `${format_price(eth)}`\n\n"
        f"Gõ /chienluoc để xem phân tích đầy đủ."
    )
    await context.bot.send_message(chat_id, text, parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gia", gia))
    app.add_handler(CommandHandler("chienluoc", chienluoc))

    # Lên lịch gửi 7:00 sáng mỗi ngày (múi giờ VN)
    # Thay YOUR_CHAT_ID bằng chat_id của bạn
    # app.job_queue.run_daily(
    #     gui_bao_cao_sang,
    #     time=time(7, 0, tzinfo=pytz.timezone("Asia/Ho_Chi_Minh")),
    #     chat_id=YOUR_CHAT_ID
    # )

    logger.info("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
