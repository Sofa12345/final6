import os.path
import telebot
from telebot import types
from validatot import *  
from gpt import *  
from config import *
from database import *
from speech import *
from creds import get_bot_token  

bot = telebot.TeleBot(get_bot_token())

logging.basicConfig(
    filename=LOGS,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s", filemode="w"
)


def menu_keyboard(options):
    buttons = (types.KeyboardButton(text=option) for option in options)
    keyboard = types.ReplyKeyboardMarkup(
        row_width=2,
        resize_keyboard=True,
        one_time_keyboard=True
    )
    keyboard.add(*buttons)
    return keyboard


@bot.message_handler(commands=['debug'])
def send_logs(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Вы не являетесь администратором этого бота.")
        return

    if os.path.exists(LOGS):
        with open(LOGS, 'rb') as lg:
            bot.send_document(message.chat.id, lg)
    else:
        bot.send_message(message.chat.id, "Файл не найден.")


@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.from_user.id, "Чтобы приступить к общению, отправь мне голосовое сообщение или текст\n"
                                           "Так же ты можешь сделать проверку:\n"
                                           "/stt - проверка синтеза речи\n"
                                           "/tts - проверка распознавания речи",
                     reply_markup=menu_keyboard(["/stt, /tts"]))


@bot.message_handler(commands=['start'])
def start(message):
    user_name = message.from_user.first_name
    bot.send_message(message.chat.id, f"Привет, {user_name}! Я твой личный психолог,"
                                      f" который поможет тебе решить твои вопросы.\n"
                                      "Напиши или запиши мне голосовое сообщение, чтобы начать.\n"
                                      "Либо нажми --> /help <-- чтобы узнать дополнительную информацию")


@bot.message_handler(commands=['tts'])
def tts_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь следующим сообщеним текст, чтобы я его озвучил!')
    bot.register_next_step_handler(message, tts)


def tts(message):
    user_id = message.from_user.id
    text = message.text

    if message.content_type != 'text':
        bot.send_message(user_id, 'Отправь текстовое сообщение')
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: пользователь отправил не текстовое сообщение")
        return
    
    status_check_users, error_message = check_number_of_users(user_id)
    if not status_check_users:
        bot.send_message(user_id, error_message)  # мест нет =(
        return

    full_user_message = [message.text, 'user', 0, 0, 0]
    add_message(user_id=user_id, full_message=full_user_message)

    last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)

    total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
    if error_message:
        bot.send_message(user_id, error_message)
        return

    status, content = text_to_speech(text)

    if status:
        bot.send_voice(user_id, content)
    else:
        bot.send_message(user_id, content)
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: При запросе в SpeechKit возникла ошибка")


def is_tts_symbol_limit(message, text):
    user_id = message.from_user.id
    text_symbols = len(text)

    all_symbols = count_all_symbol(user_id) + text_symbols

    if all_symbols >= MAX_USER_TTS_SYMBOLS:
        msg = (f"Превышен общий лимит SpeechKit TTS {MAX_USER_TTS_SYMBOLS}. "
               f"Использовано: {all_symbols} символов. Доступно: {MAX_USER_TTS_SYMBOLS - all_symbols}")
        bot.send_message(user_id, msg)
        return None

    if text_symbols >= MAX_TTS_SYMBOLS:
        msg = f"Превышен лимит SpeechKit TTS на запрос {MAX_TTS_SYMBOLS}, в сообщении {text_symbols} символов"
        bot.send_message(user_id, msg)
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: Превышен лимит SpeechKit TTS на запрос")
        return None
    return len(text)


@bot.message_handler(commands=['stt'])
def stt_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь голосовое сообщение, чтобы я его распознал!')
    bot.register_next_step_handler(message, stt)

def stt(message):
    user_id = message.from_user.id

    if not message.voice:
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: пользователь отправил не голосовое сообщение")
        return

    stt_blocks = is_stt_block_limit(message, message.voice.duration)
    if not stt_blocks:
        return

    file_id = message.voice.file_id  
    file_info = bot.get_file(file_id)  
    file = bot.download_file(file_info.file_path)  

    status, text = speech_to_text(file)  

    if status:
        bot.send_message(user_id, text, reply_to_message_id=message.id)
    else:
        bot.send_message(user_id, text)
        logging.info(f"TELEGRAM BOT: Input: {message.text}\nOutput: Error: При запросе в SpeechKit возникла ошибка")

    add_message(user_id=user_id, full_message=[text, 'user', 0, 0, stt_blocks])

    last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
    total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
    if error_message:
        bot.send_message(user_id, error_message)
        return


@bot.message_handler(content_types=['text'])
def handle_text(message):
    try:
        user_id = message.from_user.id

        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)  
            return

        full_user_message = [message.text, 'user', 0, 0, 0]
        add_message(user_id=user_id, full_message=full_user_message)

        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        full_gpt_message = [answer_gpt, 'assistant', total_gpt_tokens, 0, 0]
        add_message(user_id=user_id, full_message=full_gpt_message)

        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)  
    except Exception as e:
        logging.error(e) 
        bot.send_message(message.from_user.id, "Не получилось ответить. Попробуй написать другое сообщение")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    try:
        user_id = message.from_user.id 
        file_id = message.voice.file_id  
        file_info = bot.get_file(file_id)  
        file = bot.download_file(file_info.file_path)  

        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)

        status_stt, stt_text = speech_to_text(file)  
        if not status_stt:
            bot.send_message(user_id, stt_text)
            return
        
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        status_tts, voice_response = text_to_speech(
            answer_gpt)  
        if not status_tts:
            bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)
        else:
            bot.send_voice(user_id, voice_response, reply_to_message_id=message.id)

    except Exception as e:
        logging.error(e)
        bot.send_message(user_id, "Не получилось ответить. Попробуй записать другое сообщение")

@bot.message_handler(func=lambda: True)
def handler(message):
    bot.send_message(message.from_user.id, "Отправь мне голосовое или текстовое сообщение, и я тебе отвечу")


bot.polling()