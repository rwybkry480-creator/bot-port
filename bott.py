import os
import socket
import ipaddress
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- إعدادات خادم الويب لـ Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080)) # Render يحدد المنفذ تلقائياً
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Health check server started on port {port}")
    server.serve_forever()

# --- منطق البوت الأساسي ---
TOKEN = os.getenv("TELEGRAM_TOKEN")

async def check_port(ip, port=8080):
    try:
        conn = asyncio.open_connection(str(ip), port)
        _, writer = await asyncio.wait_for(conn, timeout=1.0)
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك! أرسل لي نطاقات CIDR وسأفحص المنفذ 8080."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lines = text.split('\n')
    await update.message.reply_text("جاري الفحص... يرجى الانتظار.")
    
    found_ips = []
    for line in lines:
        try:
            network = ipaddress.ip_network(line.strip(), strict=False)
            for ip in network:
                if await check_port(ip):
                    found_ips.append(str(ip))
                    if len(found_ips) >= 10:
                        await update.message.reply_text("\n".join(found_ips))
                        found_ips = []
        except ValueError:
            try:
                ip = ipaddress.ip_address(line.strip())
                if await check_port(ip):
                    found_ips.append(str(ip))
            except ValueError:
                continue

    if found_ips:
        await update.message.reply_text("النتائج:\n" + "\n".join(found_ips))
    else:
        await update.message.reply_text("انتهى الفحص ولم يتم العثور على نتائج.")

if __name__ == '__main__':
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN is missing!")
    else:
        # تشغيل خادم الصحة في خيط (Thread) منفصل
        threading.Thread(target=run_health_check_server, daemon=True).start()
        
        # تشغيل البوت
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("Bot is starting...")
        application.run_polling()
