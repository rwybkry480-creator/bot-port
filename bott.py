import os
import ipaddress
import asyncio
import threading
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# دالة للطباعة الفورية
def log(message):
    print(message, flush=True)

# --- خادم الصحة لـ Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and fast!")
    def log_message(self, format, *args): return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- منطق الفحص المسرع ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
MAX_CONCURRENT_SCANS = 100  # عدد الفحوصات المتوازية في نفس اللحظة

async def check_port(ip, port=8080):
    """فحص المنفذ مع مهلة زمنية قصيرة جداً للسرعة"""
    try:
        # تقليل الـ timeout لزيادة السرعة (1 ثانية كافية جداً)
        conn = asyncio.open_connection(str(ip), port)
        _, writer = await asyncio.wait_for(conn, timeout=1.0)
        writer.close()
        await writer.wait_closed()
        return str(ip)
    except:
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    log(f"Scanning: {text}")
    await update.message.reply_text("🚀 جاري الفحص السريع... يرجى الانتظار.")
    
    try:
        network = ipaddress.ip_network(text, strict=False)
        all_ips = list(network)
        total = len(all_ips)
        
        found_ips = []
        # تقسيم العمل إلى مجموعات (Batches) لعدم استهلاك موارد السيرفر بالكامل
        batch_size = MAX_CONCURRENT_SCANS
        for i in range(0, total, batch_size):
            batch = all_ips[i:i+batch_size]
            # تشغيل الفحص لكل المجموعة في نفس اللحظة
            tasks = [check_port(ip) for ip in batch]
            results = await asyncio.gather(*tasks)
            
            # تصفية النتائج الناجحة
            successful_scans = [ip for ip in results if ip]
            found_ips.extend(successful_scans)
            
            # إرسال تحديث إذا وجدت نتائج كثيرة لتجنب التأخير
            if len(found_ips) >= 20:
                await update.message.reply_text("✅ تم العثور على:\n" + "\n".join(found_ips))
                found_ips = []

        if found_ips:
            await update.message.reply_text("✅ النتائج النهائية:\n" + "\n".join(found_ips))
        else:
            await update.message.reply_text("🏁 انتهى الفحص السريع.")
            
    except Exception as e:
        log(f"Error: {e}")
        await update.message.reply_text(f"❌ خطأ: {e}")

if __name__ == '__main__':
    if not TOKEN:
        log("FATAL ERROR: TELEGRAM_TOKEN is missing!")
        sys.exit(1)
    
    threading.Thread(target=run_health_check_server, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start := lambda u, c: u.message.reply_text("أرسل CIDR للفحص السريع!")))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    log("Fast Bot is running...")
    application.run_polling()
