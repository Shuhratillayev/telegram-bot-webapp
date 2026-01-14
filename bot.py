import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Admin ID - Sizning Telegram ID'ingiz
ADMIN_ID = 1039720811

# Ma'lumotlar bazasi fayllari
DATA_DIR = "bot_data"
QUESTIONS_FILE = f"{DATA_DIR}/questions.json"
USERS_FILE = f"{DATA_DIR}/users.json"
RESULTS_FILE = f"{DATA_DIR}/results.json"

# Papkalarni yaratish
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(f"{DATA_DIR}/audio", exist_ok=True)
os.makedirs(f"{DATA_DIR}/images", exist_ok=True)

# Ma'lumotlarni yuklash/saqlash funksiyalari
def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Ma'lumotlar bazalarini yuklash
questions_db = load_data(QUESTIONS_FILE)
users_db = load_data(USERS_FILE)
results_db = load_data(RESULTS_FILE)

# Boshlang'ich ma'lumotlar tuzilmasi
if not questions_db:
    questions_db = {
        "ingliz_tili": [],
        "koreys_tili": [],
        "avto_test": []
    }
    save_data(QUESTIONS_FILE, questions_db)

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Foydalanuvchini ro'yxatga olish
    if user_id not in users_db:
        users_db[user_id] = {
            "name": user.first_name,
            "username": user.username,
            "registered": datetime.now().isoformat()
        }
        save_data(USERS_FILE, users_db)
    
    keyboard = [
        [InlineKeyboardButton("📚 Test yechish", callback_data="start_test")],
        [InlineKeyboardButton("📊 Natijalarim", callback_data="my_results")],
    ]
    
    # Admin uchun qo'shimcha tugma
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎓 Assalomu alaykum, {user.first_name}!\n\n"
        "Imtihon botiga xush kelibsiz!\n\n"
        "Bu yerda siz turli yo'nalishlarda test yechishingiz mumkin.",
        reply_markup=reply_markup
    )

# Test boshlash
async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇬🇧 Ingliz tili", callback_data="subject_ingliz_tili")],
        [InlineKeyboardButton("🇰🇷 Koreys tili", callback_data="subject_koreys_tili")],
        [InlineKeyboardButton("🚗 Avto test", callback_data="subject_avto_test")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📚 Yo'nalishni tanlang:",
        reply_markup=reply_markup
    )

# Yo'nalish tanlash
async def select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    subject = query.data.replace("subject_", "")
    
    # Savollar sonini tekshirish
    questions = questions_db.get(subject, [])
    
    if len(questions) == 0:
        await query.edit_message_text(
            f"⚠️ {subject.replace('_', ' ').title()} uchun hali savollar qo'shilmagan.\n\n"
            "Iltimos, keyinroq urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Orqaga", callback_data="start_test")
            ]])
        )
        return
    
    # Testni boshlash
    context.user_data['current_subject'] = subject
    context.user_data['current_question'] = 0
    context.user_data['answers'] = []
    context.user_data['score'] = 0
    
    await show_question(update, context)

# Savolni ko'rsatish
async def show_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    
    subject = context.user_data.get('current_subject')
    question_num = context.user_data.get('current_question', 0)
    questions = questions_db.get(subject, [])
    
    if question_num >= len(questions):
        await show_results(update, context)
        return
    
    question = questions[question_num]
    q_type = question['type']
    
    text = f"❓ Savol {question_num + 1}/{len(questions)}\n\n"
    text += f"📝 {question['question']}\n\n"
    
    # Savol turiga qarab ko'rsatish
    if q_type == "multiple_choice":
        keyboard = []
        for i, option in enumerate(question['options']):
            keyboard.append([InlineKeyboardButton(
                f"{chr(65+i)}) {option}", 
                callback_data=f"answer_{i}"
            )])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    elif q_type == "text_input":
        text += "✍️ Javobni yozing:"
        context.user_data['waiting_for_text'] = True
        if query:
            await query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
    
    elif q_type == "audio":
        # Audio yuborish
        audio_path = question.get('audio_file')
        if audio_path and os.path.exists(audio_path):
            keyboard = []
            for i, option in enumerate(question['options']):
                keyboard.append([InlineKeyboardButton(
                    f"{chr(65+i)}) {option}", 
                    callback_data=f"answer_{i}"
                )])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            with open(audio_path, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=audio,
                    caption=text,
                    reply_markup=reply_markup
                )
    
    elif q_type == "image":
        # Rasm yuborish
        image_path = question.get('image_file')
        if image_path and os.path.exists(image_path):
            keyboard = []
            for i, option in enumerate(question['options']):
                keyboard.append([InlineKeyboardButton(
                    f"{chr(65+i)}) {option}", 
                    callback_data=f"answer_{i}"
                )])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            with open(image_path, 'rb') as image:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image,
                    caption=text,
                    reply_markup=reply_markup
                )

# Javobni qabul qilish
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    answer_idx = int(query.data.replace("answer_", ""))
    
    subject = context.user_data.get('current_subject')
    question_num = context.user_data.get('current_question')
    questions = questions_db.get(subject, [])
    question = questions[question_num]
    
    # Javobni tekshirish
    is_correct = (answer_idx == question['correct_answer'])
    
    if is_correct:
        context.user_data['score'] += 1
        await query.answer("✅ To'g'ri!", show_alert=True)
    else:
        correct = chr(65 + question['correct_answer'])
        await query.answer(f"❌ Noto'g'ri! To'g'ri javob: {correct}", show_alert=True)
    
    context.user_data['answers'].append({
        'question': question_num,
        'answer': answer_idx,
        'correct': is_correct
    })
    
    # Keyingi savol
    context.user_data['current_question'] += 1
    await show_question(update, context)

# Matnli javobni qabul qilish
async def handle_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_text'):
        # Admin savollarini qabul qilish
        await handle_admin_message(update, context)
        return
    
    user_answer = update.message.text.strip().lower()
    
    subject = context.user_data.get('current_subject')
    question_num = context.user_data.get('current_question')
    questions = questions_db.get(subject, [])
    question = questions[question_num]
    
    correct_answer = question['correct_text'].lower()
    is_correct = (user_answer == correct_answer)
    
    if is_correct:
        context.user_data['score'] += 1
        await update.message.reply_text("✅ To'g'ri javob!")
    else:
        await update.message.reply_text(f"❌ Noto'g'ri! To'g'ri javob: {question['correct_text']}")
    
    context.user_data['answers'].append({
        'question': question_num,
        'answer': user_answer,
        'correct': is_correct
    })
    
    context.user_data['waiting_for_text'] = False
    context.user_data['current_question'] += 1
    
    await show_question(update, context)

# Natijalarni ko'rsatish
async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    subject = context.user_data.get('current_subject')
    score = context.user_data.get('score', 0)
    total = len(questions_db.get(subject, []))
    percentage = (score / total * 100) if total > 0 else 0
    
    # Natijani saqlash
    user_id = str(update.effective_user.id)
    if user_id not in results_db:
        results_db[user_id] = []
    
    results_db[user_id].append({
        'subject': subject,
        'score': score,
        'total': total,
        'percentage': percentage,
        'date': datetime.now().isoformat()
    })
    save_data(RESULTS_FILE, results_db)
    
    result_text = (
        f"🎉 Test tugadi!\n\n"
        f"📊 Natijangiz:\n"
        f"✅ To'g'ri javoblar: {score}/{total}\n"
        f"📈 Foiz: {percentage:.1f}%\n\n"
    )
    
    if percentage >= 80:
        result_text += "🏆 A'lo natija!"
    elif percentage >= 60:
        result_text += "👍 Yaxshi natija!"
    else:
        result_text += "📚 Ko'proq mashq qiling!"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Yana test yechish", callback_data="start_test")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_to_main")]
    ]
    
    if query:
        await query.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Sizda admin huquqi yo'q!")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Savol qo'shish", callback_data="admin_add_question")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        "⚙️ Admin Panel\n\nTanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Savol qo'shish boshlash
async def admin_add_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🇬🇧 Ingliz tili", callback_data="add_ingliz_tili")],
        [InlineKeyboardButton("🇰🇷 Koreys tili", callback_data="add_koreys_tili")],
        [InlineKeyboardButton("🚗 Avto test", callback_data="add_avto_test")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_panel")]
    ]
    
    await query.edit_message_text(
        "📚 Qaysi yo'nalishga savol qo'shasiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Savol turini tanlash
async def admin_select_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    subject = query.data.replace("add_", "")
    context.user_data['admin_subject'] = subject
    
    keyboard = [
        [InlineKeyboardButton("📝 Oddiy test (A,B,C,D)", callback_data="qtype_multiple_choice")],
        [InlineKeyboardButton("✍️ Javob yozish", callback_data="qtype_text_input")],
        [InlineKeyboardButton("🎧 Audio savol", callback_data="qtype_audio")],
        [InlineKeyboardButton("🖼 Rasm savol", callback_data="qtype_image")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="admin_add_question")]
    ]
    
    await query.edit_message_text(
        "Savol turini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Savol turini tanlash
async def admin_select_question_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    qtype = query.data.replace("qtype_", "")
    context.user_data['admin_qtype'] = qtype
    
    await query.edit_message_text(
        "📝 Savolni yuboring:\n\n"
        "(Masalan: What is the capital of France?)"
    )
    context.user_data['admin_step'] = 'question'

# Admin xabarlarini qabul qilish
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    step = context.user_data.get('admin_step')
    
    if step == 'question':
        context.user_data['admin_question'] = update.message.text
        
        qtype = context.user_data.get('admin_qtype')
        
        if qtype == 'text_input':
            await update.message.reply_text(
                "✅ Savol qabul qilindi!\n\n"
                "✍️ Endi to'g'ri javobni yozing:"
            )
            context.user_data['admin_step'] = 'correct_text'
        elif qtype in ['audio', 'image']:
            file_type = "audio" if qtype == 'audio' else "rasm"
            await update.message.reply_text(
                f"✅ Savol qabul qilindi!\n\n"
                f"📎 Endi {file_type} faylni yuboring:"
            )
            context.user_data['admin_step'] = 'file'
        else:
            await update.message.reply_text(
                "✅ Savol qabul qilindi!\n\n"
                "📝 Endi variantlarni yuboring (har birini alohida qatorda):\n\n"
                "Masalan:\n"
                "Paris\n"
                "London\n"
                "Berlin\n"
                "Madrid"
            )
            context.user_data['admin_step'] = 'options'
    
    elif step == 'options':
        options = update.message.text.strip().split('\n')
        context.user_data['admin_options'] = options
        
        keyboard = []
        for i, opt in enumerate(options):
            keyboard.append([InlineKeyboardButton(
                f"{chr(65+i)}) {opt}", 
                callback_data=f"correct_{i}"
            )])
        
        await update.message.reply_text(
            "✅ Variantlar qabul qilindi!\n\n"
            "✔️ To'g'ri javobni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['admin_step'] = 'correct_answer'
    
    elif step == 'correct_text':
        # Matnli javobni saqlash
        question_data = {
            'type': 'text_input',
            'question': context.user_data['admin_question'],
            'correct_text': update.message.text.strip()
        }
        
        subject = context.user_data['admin_subject']
        questions_db[subject].append(question_data)
        save_data(QUESTIONS_FILE, questions_db)
        
        await update.message.reply_text(
            "✅ Savol muvaffaqiyatli qo'shildi!\n\n"
            f"📚 {subject.replace('_', ' ').title()}\n"
            f"📊 Jami savollar: {len(questions_db[subject])}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Yana qo'shish", callback_data="admin_add_question"),
                InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_to_main")
            ]])
        )
        
        # Tozalash
        for key in ['admin_step', 'admin_question', 'admin_subject', 'admin_qtype']:
            context.user_data.pop(key, None)

# Audio/Rasm qabul qilish
async def handle_admin_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if context.user_data.get('admin_step') != 'file':
        return
    
    qtype = context.user_data.get('admin_qtype')
    
    if qtype == 'audio' and update.message.audio:
        file = await update.message.audio.get_file()
        file_path = f"{DATA_DIR}/audio/{file.file_id}.mp3"
        await file.download_to_drive(file_path)
        context.user_data['admin_file'] = file_path
        
        await update.message.reply_text(
            "✅ Audio qabul qilindi!\n\n"
            "📝 Endi variantlarni yuboring (har birini alohida qatorda):"
        )
        context.user_data['admin_step'] = 'options'
    
    elif qtype == 'image' and update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_path = f"{DATA_DIR}/images/{file.file_id}.jpg"
        await file.download_to_drive(file_path)
        context.user_data['admin_file'] = file_path
        
        await update.message.reply_text(
            "✅ Rasm qabul qilindi!\n\n"
            "📝 Endi variantlarni yuboring (har birini alohida qatorda):"
        )
        context.user_data['admin_step'] = 'options'

# To'g'ri javobni tanlash
async def admin_select_correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    correct_idx = int(query.data.replace("correct_", ""))
    
    qtype = context.user_data.get('admin_qtype')
    question_data = {
        'type': qtype,
        'question': context.user_data['admin_question'],
        'options': context.user_data['admin_options'],
        'correct_answer': correct_idx
    }
    
    if qtype in ['audio', 'image']:
        file_key = 'audio_file' if qtype == 'audio' else 'image_file'
        question_data[file_key] = context.user_data['admin_file']
    
    subject = context.user_data['admin_subject']
    questions_db[subject].append(question_data)
    save_data(QUESTIONS_FILE, questions_db)
    
    await query.edit_message_text(
        "✅ Savol muvaffaqiyatli qo'shildi!\n\n"
        f"📚 {subject.replace('_', ' ').title()}\n"
        f"📊 Jami savollar: {len(questions_db[subject])}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Yana qo'shish", callback_data="admin_add_question"),
            InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_to_main")
        ]])
    )
    
    # Tozalash
    for key in ['admin_step', 'admin_question', 'admin_options', 'admin_subject', 'admin_qtype', 'admin_file']:
        context.user_data.pop(key, None)

# Statistika
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    total_users = len(users_db)
    total_tests = sum(len(results) for results in results_db.values())
    
    stats_text = (
        "📊 Bot Statistikasi\n\n"
        f"👥 Foydalanuvchilar: {total_users}\n"
        f"✅ Yechilgan testlar: {total_tests}\n\n"
        f"📚 Savollar soni:\n"
    )
    
    for subject, questions in questions_db.items():
        stats_text += f"  • {subject.replace('_', ' ').title()}: {len(questions)}\n"
    
    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="admin_panel")
        ]])
    )

# Mening natijalarim
async def my_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    results = results_db.get(user_id, [])
    
    if not results:
        await query.edit_message_text(
            "📊 Sizda hali natijalar yo'q.\n\n"
            "Test yechib ko'ring!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📚 Test yechish", callback_data="start_test"),
                InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_main")
            ]])
        )
        return
    
    results_text = "📊 Mening natijalarim:\n\n"
    
    for i, result in enumerate(results[-10:], 1):  # Oxirgi 10 ta
        subject = result['subject'].replace('_', ' ').title()
        score = result['score']
        total = result['total']
        percentage = result['percentage']
        
        results_text += f"{i}. {subject}\n"
        results_text += f"   ✅ {score}/{total} ({percentage:.1f}%)\n\n"
    
    await query.edit_message_text(
        results_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Orqaga", callback_data="back_to_main")
        ]])
    )

# Bosh menyuga qaytish
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📚 Test yechish", callback_data="start_test")],
        [InlineKeyboardButton("📊 Natijalarim", callback_data="my_results")],
    ]
    
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🎓 Bosh menyu\n\nTanlang:",
        reply_markup=reply_markup
    )

# Callback handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "start_test":
        await start_test(update, context)
    elif data.startswith("subject_"):
        await select_subject(update, context)
    elif data.startswith("answer_"):
        await handle_answer(update, context)
    elif data == "admin_panel":
        await admin_panel(update, context)
    elif data == "admin_add_question":
        await admin_add_question(update, context)
    elif data.startswith("add_"):
        await admin_select_subject(update, context)
    elif data.startswith("qtype_"):
        await admin_select_question_type(update, context)
    elif data.startswith("correct_"):
        await admin_select_correct(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)
    elif data == "my_results":
        await my_results(update, context)
    elif data == "back_to_main":
        await back_to_main(update, context)

# Asosiy funksiya
def main():
    # Bot tokeni
    TOKEN = "8568379417:AAE6l3MyBnrb57zdeo3XV4W6rPVE05IIx3w"
    
    application = Application.builder().token(TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.AUDIO, handle_admin_file))
    application.add_handler(MessageHandler(filters.PHOTO, handle_admin_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_answer))
    
    # Botni ishga tushirish
    print("🚀 Bot ishga tushdi!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("✅ Barcha funksiyalar tayyor!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()