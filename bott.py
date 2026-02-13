import os
import socket
import ipaddress
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# دالة للطباعة الفورية في سجلات Render
def log(message):
    print(message, flush=True)

# --- إعدادات خادم الويب لـ Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args):
        return # لمنع امتلاء السجلات بطلبات فحص الحالة

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    log(f"--- Health check server started on port {port} ---")
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
    await update.message.reply_text("البوت يعمل! أرسل نطاق CIDR للفحص.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    log(f"Received request to scan: {text}")
    await update.message.reply_text("جاري الفحص...")
    
    found_ips = []
    try:
        network = ipaddress.ip_network(text, strict=False)
        for ip in network:
            if await check_port(ip):
                found_ips.append(str(ip))
                if len(found_ips) >= 10:
                    await update.message.reply_text("\n".join(found_ips))
                    found_ips = []
    except Exception as e:
        log(f"Error: {e}")
        await update.message.reply_text(f"خطأ في الصيغة: {e}")

    if found_ips:
        await update.message.reply_text("النتائج:\n" + "\n".join(found_ips))
    else:
        await update.message.reply_text("انتهى الفحص.")

if __name__ == '__main__':
    log("--- Starting Application ---")
    if not TOKEN:
        log("FATAL ERROR: TELEGRAM_TOKEN is missing!")
        sys.exit(1)
    else:
        # تشغيل خادم الصحة
        threading.Thread(target=run_health_check_server, daemon=True).start()
        
        # تشغيل البوت
        log("Initializing Telegram Bot...")
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        log("Bot is polling now...")
        application.run_polling()
