# main.py

import os
import requests
import traceback
from flask import Flask, request

# --- استيراد منطق البوت ودوال الجلسات ---
from bot_logic import process_update
from telegram_utils import load_chat_sessions, save_chat_sessions, BOT_TOKEN, TELEGRAM_API_URL

# --- إعداد Flask ---
app = Flask(__name__)

# --- تحميل الجلسات عند بدء التشغيل ---
# هذا مهم لضمان استمرارية بيانات المستخدمين بين عمليات إعادة التشغيل
chat_sessions = load_chat_sessions()
print("Bot sessions loaded successfully.")

# --- نقطة النهاية الرئيسية (Health Check) ---
# تستخدمها منصات الاستضافة للتأكد من أن تطبيقك يعمل
@app.route('/')
def home():
    return "<h1>Bot is alive and running!</h1>"

# --- نقطة النهاية للـ Webhook ---
# تيليجرام سيرسل كل التحديثات (الرسائل، الضغطات على الأزرار) إلى هذا الرابط
# استخدام توكن البوت في الرابط هو طريقة شائعة وبسيطة لزيادة الأمان
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.is_json:
        update = request.get_json()
        try:
            # 1. تمرير التحديث إلى دالة المعالجة الرئيسية في bot_logic.py
            process_update(update, chat_sessions)
            
            # 2. حفظ الجلسة بعد كل تحديث لضمان عدم فقدان البيانات
            save_chat_sessions(chat_sessions)
            
        except Exception as e:
            print(f"CRITICAL ERROR processing update from webhook: {e}")
            traceback.print_exc()
        
        # 3. إرجاع استجابة ناجحة لتيليجرام
        return {'status': 'ok'}, 200
    else:
        # إذا لم يكن الطلب JSON، فهذا يعني أنه ليس من تيليجرام
        return {'error': 'Invalid request format'}, 400

# --- دالة لإعداد الـ Webhook مع تيليجرام (تلقائيًا عند التشغيل) ---
def set_webhook():
    # WEBHOOK_URL هو متغير بيئة يجب أن تضبطه في منصة الاستضافة
    # يجب أن يكون الرابط الكامل لتطبيقك، مثلاً: https://your-app-name.pella.app
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    
    if not WEBHOOK_URL:
        print("FATAL ERROR: WEBHOOK_URL environment variable is not set.")
        print("Please set it in your hosting platform's settings.")
        return False
        
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}/{BOT_TOKEN}"
    set_webhook_url = f"{TELEGRAM_API_URL}/setWebhook?url={full_webhook_url}&drop_pending_updates=True"
    
    try:
        response = requests.get(set_webhook_url, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get('ok'):
            print(f"--> Webhook set successfully to: {full_webhook_url}")
            print(f"--> Telegram response: {result.get('description')}")
            return True
        else:
            print(f"--> ERROR setting webhook: {result.get('description')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"--> NETWORK ERROR could not set webhook: {e}")
        return False

# --- تشغيل التطبيق ---
if __name__ == '__main__':
    # عند بدء التشغيل، قم بتعيين الـ Webhook تلقائيًا
    # هذا يضمن أنه دائمًا محدّث حتى لو تغير رابط التطبيق
    set_webhook()
    
    # الحصول على المنفذ (Port) من متغيرات البيئة، وهو ما تفضله منصات الاستضافة
    port = int(os.environ.get('PORT', 8080))
    
    # تشغيل خادم Flask
    # debug=False مهم جدًا في البيئة الإنتاجية
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
