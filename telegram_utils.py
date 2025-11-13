import requests
import json
import os
import time
import base64

# --- الإعدادات الخاصة بتيليجرام ---
BOT_TOKEN ="8063132617:AAF_W79QZ4SLE3eC25YbS5fX20rAQNLs-04"
if not BOT_TOKEN:
    print("FATAL ERROR: Bot Token missing!")
    exit()

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SESSION = requests.Session()
DATA_DIR = '/data'
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
SESSIONS_FILE = os.path.join(DATA_DIR, 'chat_sessions.json')

# --- دوال إدارة الجلسات (متعلقة بالملفات) ---
def load_chat_sessions():
    if not os.path.exists(SESSIONS_FILE):
        return {}
    try:
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_chat_sessions(sessions):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Saving sessions...")
    try:
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, ensure_ascii=False, indent=4)
        print("Save successful.")
    except Exception as e:
        print(f"ERROR saving sessions: {e}")

# --- دوال الاتصال بـ Telegram API ---
def get_updates(offset=None):
    url = f"{TELEGRAM_API_URL}/getUpdates"
    params = {'timeout': 30, 'offset': offset, 'allowed_updates': ['message', 'callback_query']}
    max_retries = 5
    retry_delay_seconds = 5
    for attempt in range(max_retries):
        try:
            response = SESSION.get(url, params=params, timeout=40)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting updates (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds)
    return {}

def send_message(chat_id, text, reply_to_message_id=None, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        response = SESSION.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Could not send message: {e}")
        return None

def send_photo(chat_id, photo, caption="", reply_to_message_id=None, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo, "caption": caption}
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        response = SESSION.post(url, json=payload, timeout=40)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Could not send photo: {e}")
        return None

# --- [جديد] دالة لإرسال مجموعة صور ---
def send_media_group(chat_id, image_urls, caption="", reply_to_message_id=None):
    if not image_urls:
        return None
    url = f"{TELEGRAM_API_URL}/sendMediaGroup"
    media = []
    for i, img_url in enumerate(image_urls):
        media_item = {"type": "photo", "media": img_url}
        if i == 0:  # Add caption to the first image only
            media_item["caption"] = caption
        media.append(media_item)
    
    payload = {'chat_id': chat_id, 'media': json.dumps(media)}
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
        
    try:
        response = SESSION.post(url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Could not send media group: {e}")
        return None

def send_video(chat_id, video_url, caption="", reply_to_message_id=None):
    url = f"{TELEGRAM_API_URL}/sendVideo"
    payload = {'chat_id': chat_id, 'video': video_url, 'caption': caption}
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    try:
        response = SESSION.post(url, json=payload, timeout=180) 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Could not send video: {e}")
        return None

def edit_message_text(chat_id, message_id, new_text, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/editMessageText"
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': new_text}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        SESSION.post(url, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"Could not edit message text: {e}")

def edit_message_reply_markup(chat_id, message_id, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/editMessageReplyMarkup"
    payload = {'chat_id': chat_id, 'message_id': message_id}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    else: 
        payload['reply_markup'] = json.dumps({})
    try:
        SESSION.post(url, json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"Could not edit message reply markup: {e}")
        
def answer_callback_query(callback_query_id, text=None):
    url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
    payload = {'callback_query_id': callback_query_id}
    if text:
        payload['text'] = text
    try:
        SESSION.post(url, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Could not answer callback query: {e}")

def send_voice(chat_id, voice_url, reply_to_message_id=None):
    url = f"{TELEGRAM_API_URL}/sendVoice"
    payload = {'chat_id': chat_id, 'voice': voice_url}
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    try:
        SESSION.post(url, json=payload, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"Could not send voice note: {e}")

def send_chat_action(chat_id, action="typing"):
    url = f"{TELEGRAM_API_URL}/sendChatAction"
    payload = {'chat_id': chat_id, 'action': action}
    try:
        SESSION.post(url, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Could not send chat action: {e}")

def get_file_path(file_id):
    url = f"{TELEGRAM_API_URL}/getFile"
    params = {'file_id': file_id}
    try:
        res = SESSION.get(url, params=params, timeout=20)
        res.raise_for_status()
        return res.json().get('result', {}).get('file_path')
    except requests.exceptions.RequestException as e:
        print(f"Could not get file path: {e}")
        return None

def download_image_as_base64(file_path):
    if not file_path: return None
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    try:
        res = SESSION.get(url, timeout=30)
        res.raise_for_status()
        return base64.b64encode(res.content).decode('utf-8')
    except requests.exceptions.RequestException as e:
        print(f"Could not download image: {e}")
        return None

def download_image_as_bytes(file_path):
    if not file_path: return None
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    try:
        res = SESSION.get(url, timeout=30)
        res.raise_for_status()
        return res.content
    except requests.exceptions.RequestException as e:
        print(f"Could not download image as bytes: {e}")
        return None

def delete_message(chat_id, message_id):
    url = f"{TELEGRAM_API_URL}/deleteMessage"
    payload = {'chat_id': chat_id, 'message_id': message_id}
    try:
        SESSION.post(url, json=payload)
    except requests.exceptions.RequestException as e:
        print(f"Could not delete message: {e}")
