# BTC/ETH Strategy Bot

Telegram bot tự động gửi chiến lược giao dịch BTC/ETH lúc 7:00 sáng mỗi ngày.

## Lệnh
- `/chienluoc` – Phân tích ngay
- `/gia` – Xem giá hiện tại
- `/start` – Hướng dẫn

## Deploy Railway

1. Push code lên GitHub
2. Vào railway.app → New Project → Deploy from GitHub
3. Thêm 3 biến môi trường:
   - TELEGRAM_TOKEN
   - ANTHROPIC_API_KEY
   - CHAT_ID
4. Deploy
