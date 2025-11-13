import time
import traceback

# --- استيراد الأدوات والمنطق ---
# نستورد دالة جلب التحديثات من أدوات تيليجرام
from telegram_utils import get_updates, load_chat_sessions, save_chat_sessions
# نستورد دالة معالجة التحديثات من منطق البوت
from bot_logic import process_update

# --- الإعدادات الرئيسية ---
SAVE_INTERVAL_SECONDS = 60

def main():
    """
    الحلقة الرئيسية للبوت.
    هذه الدالة مسؤولة فقط عن جلب التحديثات وتمريرها للمعالج.
    """
    offset = None
    chat_sessions = load_chat_sessions()
    last_save_time = time.time()
    
    print("Professional Bot started. Awaiting commands... 🤖")

    try:
        while True:
            # 1. جلب التحديثات من تيليجرام
            updates = get_updates(offset)
            
            if updates and 'result' in updates:
                for update in updates['result']:
                    try:
                        # 2. تمرير كل تحديث إلى دالة المعالجة في bot_logic.py
                        process_update(update, chat_sessions)
                    except Exception as e:
                        print(f"CRITICAL ERROR processing update {update.get('update_id')}: {e}")
                        traceback.print_exc()
                    
                    # تحديث الـ offset لآخر تحديث تم استلامه
                    offset = update['update_id'] + 1
            
            # 3. حفظ الجلسات بشكل دوري
            if time.time() - last_save_time > SAVE_INTERVAL_SECONDS:
                save_chat_sessions(chat_sessions)
                last_save_time = time.time()

    except KeyboardInterrupt:
        print("\nStopping bot...")
    except Exception as e:
        print(f"A critical, unhandled error occurred in the main loop: {e}")
        traceback.print_exc()
    finally:
        # 4. الحفظ النهائي قبل إغلاق البوت
        print("Final save before shutdown.")
        save_chat_sessions(chat_sessions)
        print("Shutdown complete.")

if __name__ == '__main__':
    main()