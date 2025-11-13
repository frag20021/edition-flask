import time
import threading
import os
import base64
import uuid
from concurrent.futures import ThreadPoolExecutor

# --- استيراد أدوات تيليجرام والخدمات الخارجية ---
import telegram_utils as tg
import services

# --- الإعدادات العامة ---
USER_STATES = {} 
ACTIVE_VIDEO_JOBS = {} 
TEMP_DIR = 'temp_images'
ADMIN_CHAT_ID = "5894888687"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


# --- دالة مساعدة لإعادة التوجيه إلى المشرف ---
def _forward_to_admin(text):
    try:
        tg.send_message(ADMIN_CHAT_ID, text)
    except Exception as e:
        print(f"ADMIN FORWARD ERROR: Could not send message to admin. Error: {e}")


# --- لوحات المفاتيح (Keyboards) ---
MAIN_KEYBOARD = { "inline_keyboard": [ [{"text": "🖼️ إنشاء صورة", "callback_data": "generate_image"}, {"text": "✨ تحسين الوصف (Prompt)", "callback_data": "enhance_prompt"}], [{"text": "📄 وصف صورة", "callback_data": "describe_image"}, {"text": "🎨 تعديل صورة", "callback_data": "edit_image_start"}], [{"text": "🎞️ إنشاء فيديو", "callback_data": "create_video"}] ] }
IMAGE_COUNT_SELECTION_KEYBOARD = { "inline_keyboard": [ [{"text": "🖼️ صورتان", "callback_data": "select_img_count:2"}, {"text": "🖼️🖼️ 4 صور", "callback_data": "select_img_count:4"}] ] }
PROMPT_ENHANCE_CONFIRMATION_KEYBOARD_EDIT = { "inline_keyboard": [ [{"text": "✅ نعم، قم بالتحسين", "callback_data": "confirm_enhance_edit_prompt"}, {"text": "❌ لا، ابدأ بالوصف الحالي", "callback_data": "skip_enhance_edit_prompt"}] ] }
VIDEO_MODEL_SELECTION_KEYBOARD = { "inline_keyboard": [ [{"text": "VEO", "callback_data": "select_model:veo"}, {"text": "Sora", "callback_data": "select_model:sora"}, {"text": "Sora Pro", "callback_data": "select_model:sora_pro"}], [{"text": "Kling (Turbo)", "callback_data": "select_model:kling"}, {"text": "Kling (Standard)", "callback_data": "select_model:kling_standard"}], [{"text": "⬅️ عودة للقائمة الرئيسية", "callback_data": "back_to_main"}] ] }
VEO_SORA_OPTIONS_KEYBOARD = { "inline_keyboard": [ [{"text": "🎬 من نص فقط", "callback_data": "type_select:from_text"}, {"text": "🖼️ من صورة ونص", "callback_data": "type_select:from_image"}], [{"text": "⬅️ عودة لاختيار الموديل", "callback_data": "back_to_model_select"}] ]}
KLING_OPTIONS_KEYBOARD = { "inline_keyboard": [ [{"text": "🖼️ من صورة ونص", "callback_data": "type_select:from_image"}], [{"text": "⬅️ عودة لاختيار الموديل", "callback_data": "back_to_model_select"}] ]}
PROMPT_ENHANCE_CONFIRMATION_KEYBOARD = { "inline_keyboard": [ [{"text": "✅ نعم، قم بالتحسين", "callback_data": "confirm_enhance_video_prompt"}, {"text": "❌ لا، ابدأ بالوصف الحالي", "callback_data": "skip_enhance_video_prompt"}] ]}


# --- دوال العمال (Workers) ---

def image_generation_worker(chat_id, message_id, image_prompt, session, waiting_message_id, user_info, image_count):
    tg.send_chat_action(chat_id, "upload_photo")
    
    results = []
    def task(prompt):
        result_url = services.generate_image_from_prompt(prompt)
        if result_url:
            results.append(result_url)

    with ThreadPoolExecutor(max_workers=image_count) as executor:
        for _ in range(image_count):
            executor.submit(task, image_prompt)

    if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
    
    if results:
        _forward_to_admin(f"✅ **{len(results)} صور جديدة**\n\n**من:** {user_info}\n**النتائج:**\n" + "\n".join(results))
        tg.send_media_group(chat_id, results, caption=f"تم إنشاء {len(results)} صور بنجاح.", reply_to_message_id=message_id)
    else:
        _forward_to_admin(f"❌ **فشل إنشاء صورة**\n\n**من:** {user_info}\n**الوصف:** `{image_prompt}`")
        tg.send_message(chat_id, "حدث خطأ أثناء إنشاء الصورة. يرجى المحاولة مرة أخرى.", reply_to_message_id=message_id)
    
    tg.send_message(chat_id, "القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)

def edit_image_worker(chat_id, message_id, image_file_id, edit_prompt, waiting_message_id, user_info, image_count):
    tg.send_chat_action(chat_id, "upload_photo")
    file_path = tg.get_file_path(image_file_id)
    if not file_path:
        if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
        tg.send_message(chat_id, "خطأ: لم أتمكن من تحميل الصورة من تيليجرام.", reply_to_message_id=message_id); return

    image_bytes = tg.download_image_as_bytes(file_path)
    if not image_bytes:
        if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
        tg.send_message(chat_id, "خطأ: فشل تحميل بيانات الصورة.", reply_to_message_id=message_id); return

    results = []
    def task(prompt):
        thread_local_path = os.path.join(TEMP_DIR, f'{chat_id}_{uuid.uuid4()}.jpg')
        with open(thread_local_path, 'wb') as f_copy:
            f_copy.write(image_bytes)
        
        result_url = services.edit_image_with_digen(thread_local_path, prompt)
        if result_url:
            results.append(result_url)
        
        if os.path.exists(thread_local_path):
            os.remove(thread_local_path)

    with ThreadPoolExecutor(max_workers=image_count) as executor:
        for _ in range(image_count):
            executor.submit(task, edit_prompt)

    if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
    
    if results:
        _forward_to_admin(f"🎨 **{len(results)} صور معدلة**\n\n**من:** {user_info}\n**النتائج:**\n" + "\n".join(results))
        tg.send_media_group(chat_id, results, caption=f"تم تعديل وإنشاء {len(results)} صور بنجاح.", reply_to_message_id=message_id)
    else:
        _forward_to_admin(f"❌ **فشل تعديل صورة**\n\n**من:** {user_info}\n**الوصف:** `{edit_prompt}`")
        tg.send_message(chat_id, "فشل تعديل الصورة. يرجى المحاولة مرة أخرى أو التأكد من صلاحية التوكن.", reply_to_message_id=message_id)
    
    tg.send_message(chat_id, "القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)

def describe_image_worker(chat_id, message_id, file_id, waiting_message_id, user_info):
    tg.send_chat_action(chat_id, "typing")
    file_path = tg.get_file_path(file_id)
    if not file_path:
        if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
        tg.send_message(chat_id, "خطأ: لم أتمكن من تحميل الصورة.", reply_to_message_id=message_id); return
    image_base64 = tg.download_image_as_base64(file_path)
    if not image_base64:
        if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
        tg.send_message(chat_id, "خطأ: فشل في معالجة بيانات الصورة.", reply_to_message_id=message_id); return
    description, _ = services.describe_image_with_gemini(image_base64)
    if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
    _forward_to_admin(f"📄 **وصف صورة**\n\n**من:** {user_info}\n**الوصف الناتج:** {description[:1000]}")
    tg.send_message(chat_id, f"**وصف الصورة:**\n\n{description}", reply_to_message_id=message_id)
    tg.send_message(chat_id, "القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)

def enhance_prompt_worker(chat_id, message_id, simple_prompt, waiting_message_id, user_info):
    tg.send_chat_action(chat_id, "typing")
    enhanced_prompt, _ = services.generate_enhanced_prompt("image_gen", simple_prompt) # Default to image_gen
    if waiting_message_id: tg.delete_message(chat_id, waiting_message_id)
    _forward_to_admin(f"✨ **تحسين وصف**\n\n**من:** {user_info}\n**الأصلي:** `{simple_prompt}`\n**المحسّن:** `{enhanced_prompt}`")
    tg.send_message(chat_id, f"**الوصف المحسّن (Prompt):**\n\n`{enhanced_prompt}`\n\nيمكنك الآن نسخ هذا الوصف واستخدامه في 'إنشاء صورة'.", reply_to_message_id=message_id)
    tg.send_message(chat_id, "القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)

def video_generation_worker(chat_id, message_id, prompt, start_job_function, user_info, file_id=None, enhanced_prompt=None):
    job_id = str(uuid.uuid4())
    cancel_event = threading.Event()
    ACTIVE_VIDEO_JOBS[job_id] = cancel_event
    keyboard = {"inline_keyboard": [[{"text": "❌ إلغاء", "callback_data": f"cancel_video:{job_id}"}]]}
    status_msg = tg.send_message(chat_id, "تم استلام الطلب 🎬\nجاري إنشاء الفيديو... قد تستغرق العملية عدة دقائق.", reply_to_message_id=message_id, reply_markup=keyboard)
    status_message_id = status_msg['result']['message_id']
    final_prompt = enhanced_prompt or prompt
    try:
        generation_info = None
        if file_id:
            file_path = tg.get_file_path(file_id)
            if not file_path:
                tg.edit_message_text(chat_id, status_message_id, "خطأ: لم أتمكن من تحميل الصورة من تيليجرام."); return
            image_bytes = tg.download_image_as_bytes(file_path)
            if not image_bytes:
                tg.edit_message_text(chat_id, status_message_id, "خطأ: حدث خطأ أثناء تحميل بيانات الصورة."); return
            upload_info = services.upload_image_for_video(image_bytes, f"{uuid.uuid4()}.jpg")
            if not upload_info:
                tg.edit_message_text(chat_id, status_message_id, "خطأ: فشل رفع الصورة لخدمة الفيديو."); return
            tg.send_chat_action(chat_id, "upload_video")
            generation_info = start_job_function(final_prompt, upload_info['cdnUrl'], upload_info['uploadId'])
        else:
            tg.send_chat_action(chat_id, "upload_video")
            generation_info = start_job_function(final_prompt)
        if not generation_info:
            tg.edit_message_text(chat_id, status_message_id, "خطأ: فشل بدء مهمة إنشاء الفيديو.")
            return
        video_url = services.poll_for_video_result(generation_info['request_id'], generation_info['history_id'], cancel_event)
        if video_url == "CANCELLED":
            tg.edit_message_text(chat_id, status_message_id, "تم إلغاء عملية إنشاء الفيديو.")
        elif video_url:
            _forward_to_admin(f"🎞️ **فيديو جديد**\n\n**من:** {user_info}\n**النموذج:** {start_job_function.__name__}\n**الرابط:** {video_url}")
            tg.edit_message_text(chat_id, status_message_id, "اكتمل إنشاء الفيديو! جاري الإرسال...")
            caption_text = f"فيديو من: {start_job_function.__name__}"
            video_message = tg.send_video(chat_id, video_url, caption=caption_text, reply_to_message_id=message_id)
            tg.delete_message(chat_id, status_message_id)
            if enhanced_prompt:
                video_msg_id = video_message.get('result', {}).get('message_id', message_id)
                tg.send_message(chat_id, f"**تم استخدام الوصف المحسّن التالي:**\n\n`{enhanced_prompt}`", reply_to_message_id=video_msg_id)
        else:
            _forward_to_admin(f"❌ **فشل إنشاء فيديو**\n\n**من:** {user_info}\n**النموذج:** {start_job_function.__name__}\n**الوصف:** `{final_prompt}`")
            tg.edit_message_text(chat_id, status_message_id, "فشلت عملية إنشاء الفيديو أو استغرقت وقتاً طويلاً.")
    finally:
        if job_id in ACTIVE_VIDEO_JOBS:
            del ACTIVE_VIDEO_JOBS[job_id]
        time.sleep(1)
        tg.send_message(chat_id, "القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)


# --- المنطق الرئيسي للبوت ---
def process_update(update, chat_sessions):
    
    if 'callback_query' in update:
        callback_query = update['callback_query']
        chat_id = str(callback_query['message']['chat']['id'])
        message_id = callback_query['message']['message_id']
        callback_id = callback_query['id']
        data = callback_query['data']
        session = chat_sessions.setdefault(chat_id, {"last_image_file_id": None})
        user_context = USER_STATES.get(chat_id, {})

        tg.answer_callback_query(callback_id)

        if data.startswith("select_img_count:"):
            image_count = int(data.split(":")[1])
            gen_type = user_context.get('type')
            
            tg.delete_message(chat_id, message_id)
            sent_msg = tg.send_message(chat_id, f"جاري إعداد {image_count} صور...", reply_to_message_id=user_context.get('original_message_id'))
            waiting_message_id = sent_msg.get('result', {}).get('message_id')

            if gen_type == 'image_gen':
                prompt = user_context.get('prompt')
                USER_STATES.pop(chat_id, None)
                threading.Thread(target=image_generation_worker, args=(chat_id, user_context.get('original_message_id'), prompt, session, waiting_message_id, user_context.get('user_info'), image_count)).start()
            elif gen_type == 'image_edit':
                final_prompt = user_context.get('final_prompt')
                file_id = user_context.get('file_id')
                USER_STATES.pop(chat_id, None)
                threading.Thread(target=edit_image_worker, args=(chat_id, user_context.get('original_message_id'), file_id, final_prompt, waiting_message_id, user_context.get('user_info'), image_count)).start()
            return
            
        if data == 'confirm_enhance_edit_prompt' or data == 'skip_enhance_edit_prompt':
            if user_context.get('state') == 'awaiting_edit_prompt_enhance_confirmation':
                final_prompt = user_context['original_prompt']
                if data == 'confirm_enhance_edit_prompt':
                    tg.edit_message_text(chat_id, message_id, "جاري تحسين الوصف...")
                    file_path = tg.get_file_path(user_context['file_id'])
                    image_base64 = tg.download_image_as_base64(file_path) if file_path else None
                    if image_base64:
                        enhanced_prompt, _ = services.generate_enhanced_prompt("image_edit", final_prompt, image_base64)
                        if "حظر" not in enhanced_prompt:
                            final_prompt = enhanced_prompt
                    _forward_to_admin(f"✨ **تحسين وصف تعديل (موافقة)**\n\n**من:** {user_context['user_info']}\n**الأصلي:** `{user_context['original_prompt']}`\n**المحسّن:** `{final_prompt}`")
                    tg.send_message(chat_id, f"**سيتم استخدام الوصف المحسّن التالي:**\n`{final_prompt}`")
                else:
                    _forward_to_admin(f"✍️ **تخطي تحسين وصف التعديل**\n\n**من:** {user_context['user_info']}\n**الوصف المستخدم:** `{final_prompt}`")

                USER_STATES[chat_id] = {
                    'state': 'awaiting_image_count_selection', 'type': 'image_edit',
                    'file_id': user_context['file_id'], 'final_prompt': final_prompt,
                    'original_message_id': user_context['original_message_id'], 'user_info': user_context['user_info']
                }
                tg.edit_message_text(chat_id, message_id, "كم عدد الصور المعدلة التي تريد إنشاءها؟", reply_markup=IMAGE_COUNT_SELECTION_KEYBOARD)
            return

        if data == 'generate_image':
            USER_STATES[chat_id] = {'state': 'awaiting_prompt', 'type': 'image_gen'}
            tg.send_message(chat_id, "يرجى إرسال الوصف (prompt) لإنشاء الصورة.")
        elif data == 'enhance_prompt':
            USER_STATES[chat_id] = {'state': 'awaiting_prompt', 'type': 'prompt_enhance'}
            tg.send_message(chat_id, "يرجى إرسال فكرة بسيطة، وسأقوم بتحويلها إلى وصف احترافي.")
        elif data == 'describe_image':
            USER_STATES[chat_id] = {'state': 'awaiting_image', 'type': 'describe'}
            tg.send_message(chat_id, "يرجى إرسال الصورة التي تريد وصفها.")
        elif data == 'edit_image_start':
            USER_STATES[chat_id] = {'state': 'awaiting_image', 'type': 'edit'}
            tg.send_message(chat_id, "يرجى إرسال الصورة التي تريد تعديلها.")
        elif data == 'create_video':
            tg.edit_message_text(chat_id, message_id, "اختر موديل الفيديو:", reply_markup=VIDEO_MODEL_SELECTION_KEYBOARD)
        elif data.startswith("select_model:"):
            model = data.split(":", 1)[1]
            USER_STATES[chat_id] = {'state': 'awaiting_type_selection', 'model': model}
            if model in ['veo', 'sora', 'sora_pro']:
                tg.edit_message_text(chat_id, message_id, f"اختر نوع الإدخال لموديل {model.upper()}:", reply_markup=VEO_SORA_OPTIONS_KEYBOARD)
            elif model in ['kling', 'kling_standard']:
                tg.edit_message_text(chat_id, message_id, f"موديل {model.replace('_', ' ').title()} يدعم الإنشاء من صورة ونص فقط.", reply_markup=KLING_OPTIONS_KEYBOARD)
        elif data.startswith("type_select:"):
            gen_type = data.split(":", 1)[1]
            model_info = USER_STATES.get(chat_id)
            if model_info and model_info.get('state') == 'awaiting_type_selection':
                model = model_info['model']
                if gen_type == 'from_image':
                    USER_STATES[chat_id] = {'state': 'awaiting_video_image', 'model': model}
                    tg.edit_message_text(chat_id, message_id, f"تمام. يرجى الآن إرسال الصورة التي تريد تحريكها باستخدام موديل {model.upper()}.")
                else:
                    USER_STATES[chat_id] = {'state': 'awaiting_prompt', 'type': f'{model}_from_text'}
                    tg.edit_message_text(chat_id, message_id, f"أرسل الوصف لإنشاء فيديو من نص باستخدام موديل {model.upper()}.")
        elif data == 'confirm_enhance_video_prompt' or data == 'skip_enhance_video_prompt':
            if user_context and user_context.get('state') == 'awaiting_video_prompt_enhance_confirmation':
                original_prompt = user_context['original_prompt']
                user_info = user_context['user_info']
                enhanced_prompt = None
                if data == 'confirm_enhance_video_prompt':
                    tg.edit_message_text(chat_id, message_id, "جاري تحسين الوصف...")
                    if user_context.get('file_id'):
                        file_path = tg.get_file_path(user_context['file_id'])
                        image_base64 = tg.download_image_as_base64(file_path) if file_path else None
                        if image_base64:
                            enhanced_prompt, _ = services.generate_enhanced_prompt("video_image", original_prompt, image_base64)
                    else:
                        enhanced_prompt, _ = services.generate_enhanced_prompt("video_text", original_prompt)
                    _forward_to_admin(f"✨ **تحسين وصف فيديو (موافقة)**\n\n**من:** {user_info}\n**الأصلي:** `{original_prompt}`\n**المحسّن:** `{enhanced_prompt}`")
                else:
                    _forward_to_admin(f"✍️ **تخطي تحسين وصف الفيديو**\n\n**من:** {user_context['user_info']}\n**الوصف المستخدم:** `{original_prompt}`")
                USER_STATES.pop(chat_id, None)
                tg.delete_message(chat_id, message_id)
                job_map = {
                    'veo_from_text': (services.start_veo_text_to_video_job, None), 'sora_from_text': (services.start_sora_text_to_video_job, None), 'sora_pro_from_text': (services.start_sora_pro_text_to_video_job, None),
                    'veo_from_image': (services.start_veo_image_to_video_job, user_context.get('file_id')), 'sora_from_image': (services.start_sora_image_to_video_job, user_context.get('file_id')),
                    'sora_pro_from_image': (services.start_sora_pro_image_to_video_job, user_context.get('file_id')), 'kling_from_image': (services.start_kling_image_to_video_job, user_context.get('file_id')),
                    'kling_standard_from_image': (services.start_kling_standard_image_to_video_job, user_context.get('file_id')),
                }
                gen_type = f"{user_context['model']}_{user_context['gen_type']}"
                start_job_function, file_id = job_map.get(gen_type, (None, None))
                if start_job_function:
                    threading.Thread(target=video_generation_worker, args=(chat_id, user_context['original_message_id'], original_prompt, start_job_function, user_info, file_id, enhanced_prompt)).start()
        elif data == 'back_to_model_select':
            USER_STATES.pop(chat_id, None)
            tg.edit_message_text(chat_id, message_id, "اختر موديل الفيديو:", reply_markup=VIDEO_MODEL_SELECTION_KEYBOARD)
        elif data == 'back_to_main':
            USER_STATES.pop(chat_id, None)
            tg.edit_message_text(chat_id, message_id, "القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)
        elif data.startswith("cancel_video:"):
            job_id = data.split(":", 1)[1]
            if job_id in ACTIVE_VIDEO_JOBS:
                ACTIVE_VIDEO_JOBS[job_id].set()
        return

    if 'message' not in update: return
    message = update['message']
    
    if message['chat']['type'] != 'private' or message.get('from', {}).get('is_bot'): return

    chat_id = str(message['chat']['id'])
    message_id = message['message_id']
    session = chat_sessions.setdefault(chat_id, {"last_image_file_id": None})
    user_context = USER_STATES.get(chat_id)
    
    user = message.get('from', {})
    user_id = user.get('id')
    first_name = user.get('first_name', '')
    last_name = user.get('last_name', '')
    username = user.get('username')
    user_info = f"{first_name} {last_name}".strip()
    if username: user_info += f" (@{username})"
    user_info += f" [ID: {user_id}]"

    prompt = (message.get('text') or message.get('caption', '')).strip()
    if prompt.lower() == '/start':
        _forward_to_admin(f"🚀 **مستخدم جديد / /start**\n\n**من:** {user_info}")
        USER_STATES.pop(chat_id, None)
        session['last_image_file_id'] = None
        tg.send_message(chat_id, "أهلاً بك. اختر إحدى الخدمات من القائمة:", reply_markup=MAIN_KEYBOARD)
        return
    if prompt.lower() == '/clear':
        USER_STATES.pop(chat_id, None)
        session['last_image_file_id'] = None
        tg.send_message(chat_id, "تم مسح الذاكرة والحالة. للبدء من جديد اضغط /start", reply_to_message_id=message_id)
        return

    if not user_context:
        _forward_to_admin(f"💬 **رسالة بدون سياق**\n\n**من:** {user_info}\n**النص:** `{prompt}`")
        tg.send_message(chat_id, "يرجى اختيار أمر من القائمة أو اضغط /start للبدء.", reply_markup=MAIN_KEYBOARD)
        return

    state = user_context.get('state')
    
    if state == 'awaiting_image':
        if 'photo' in message:
            file_id = message['photo'][-1]['file_id']
            image_type = user_context.get('type')
            caption = f"🖼️ **صورة مُستلمة**\n\n**من:** {user_info}\n**للعملية:** `{image_type}`"
            tg.send_photo(ADMIN_CHAT_ID, file_id, caption=caption)
            if image_type == 'describe':
                USER_STATES.pop(chat_id, None)
                sent_msg = tg.send_message(chat_id, "جاري تحليل ووصف الصورة...", reply_to_message_id=message_id)
                waiting_message_id = sent_msg.get('result', {}).get('message_id')
                threading.Thread(target=describe_image_worker, args=(chat_id, message_id, file_id, waiting_message_id, user_info)).start()
            elif image_type == 'edit':
                USER_STATES[chat_id] = {'state': 'awaiting_prompt', 'type': 'image_edit', 'file_id': file_id}
                tg.send_message(chat_id, "تم استلام الصورة. يرجى الآن إرسال تعليمات التعديل.", reply_to_message_id=message_id)
        else:
            tg.send_message(chat_id, "لم يتم إرسال صورة. يرجى المحاولة مرة أخرى.", reply_to_message_id=message_id)
        return

    elif state == 'awaiting_prompt':
        gen_type = user_context.get('type')
        _forward_to_admin(f"📝 **وصف مُستلم**\n\n**من:** {user_info}\n**للعملية:** `{gen_type}`\n**النص:** `{prompt}`")
        if gen_type == 'image_gen':
            USER_STATES[chat_id] = { 'state': 'awaiting_image_count_selection', 'type': 'image_gen', 'prompt': prompt, 'original_message_id': message_id, 'user_info': user_info }
            tg.send_message(chat_id, "كم عدد الصور التي تريد إنشاءها؟", reply_markup=IMAGE_COUNT_SELECTION_KEYBOARD, reply_to_message_id=message_id)
        elif gen_type == 'image_edit':
            USER_STATES[chat_id] = { 'state': 'awaiting_edit_prompt_enhance_confirmation', 'file_id': user_context['file_id'], 'original_prompt': prompt, 'original_message_id': message_id, 'user_info': user_info }
            tg.send_message(chat_id, "هل تريد تحسين الوصف؟ (سيتم تحليل الصورة لتقديم أفضل وصف)", reply_markup=PROMPT_ENHANCE_CONFIRMATION_KEYBOARD_EDIT, reply_to_message_id=message_id)
        elif gen_type == 'prompt_enhance':
            USER_STATES.pop(chat_id, None)
            sent_msg = tg.send_message(chat_id, "جاري تحليل الفكرة وتحسينها...", reply_to_message_id=message_id)
            waiting_message_id = sent_msg.get('result', {}).get('message_id')
            threading.Thread(target=enhance_prompt_worker, args=(chat_id, message_id, prompt, waiting_message_id, user_info)).start()
        elif gen_type in ['veo_from_text', 'sora_from_text', 'sora_pro_from_text']:
            model = gen_type.split('_')[0]
            USER_STATES[chat_id] = { 'state': 'awaiting_video_prompt_enhance_confirmation', 'model': model if 'pro' not in gen_type else 'sora_pro', 'file_id': None, 'original_prompt': prompt, 'original_message_id': message_id, 'gen_type': 'from_text', 'user_info': user_info }
            tg.send_message(chat_id, "هل تريد تحسين الوصف باستخدام الذكاء الاصطناعي؟", reply_markup=PROMPT_ENHANCE_CONFIRMATION_KEYBOARD, reply_to_message_id=message_id)
        return

    # Video states
    if state == 'awaiting_video_image':
        if 'photo' in message:
            file_id = message['photo'][-1]['file_id']
            caption = f"📸 **صورة فيديو**\n\n**من:** {user_info}\n**النموذج:** `{user_context.get('model')}`"
            tg.send_photo(ADMIN_CHAT_ID, file_id, caption=caption)
            model = user_context.get('model')
            USER_STATES[chat_id] = {'state': 'awaiting_video_prompt', 'model': model, 'file_id': file_id}
            tg.send_message(chat_id, "صورة ممتازة. الآن يرجى إرسال الوصف النصي للحركة التي تريد إضافتها.", reply_to_message_id=message_id)
        else:
            tg.send_message(chat_id, "الرجاء إرسال صورة.", reply_to_message_id=message_id)
        return
    elif state == 'awaiting_video_prompt':
        _forward_to_admin(f"🎬 **وصف فيديو (مع صورة)**\n\n**من:** {user_info}\n**النص:** `{prompt}`")
        model = user_context.get('model')
        file_id = user_context.get('file_id')
        USER_STATES[chat_id] = { 'state': 'awaiting_video_prompt_enhance_confirmation', 'model': model, 'file_id': file_id, 'original_prompt': prompt, 'original_message_id': message_id, 'gen_type': 'from_image', 'user_info': user_info }
        tg.send_message(chat_id, "هل تريد تحسين الوصف باستخدام الذكاء الاصطناعي؟ (سيفهم الصورة لتحسين أفضل)", reply_markup=PROMPT_ENHANCE_CONFIRMATION_KEYBOARD, reply_to_message_id=message_id)
        return
