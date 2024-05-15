import logging
import math 
from config import LOGS, MAX_USERS, MAX_USER_GPT_TOKENS, MAX_USER_STT_BLOCKS, MAX_USER_TTS_SYMBOLS, MAX_TTS_SYMBOLS
from database import *
from gpt import count_gpt_tokens

logging.basicConfig(filename=LOGS,
                    level=logging.ERROR,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s",
                    filemode="w")


def check_number_of_users(user_id):
    count = count_users(user_id)
    if count is None:
        return None, "Ошибка при работе с БД"
    if count > MAX_USERS:
        return None, "Превышено максимальное количество пользователей"
    return True, ""


def is_gpt_token_limit(messages, total_spent_tokens):
    all_tokens = count_gpt_tokens(messages) + total_spent_tokens
    if all_tokens > MAX_USER_GPT_TOKENS:
        return None, f"Превышен общий лимит GPT-токенов {MAX_USER_GPT_TOKENS}"
    return all_tokens, ""


def is_stt_block_limit(user_id, duration):
    audio_blocks = math.ceil(duration / 15) 
    all_blocks = count_all_limits(user_id) + audio_blocks

    if duration >= 30:
        return None, "SpeechKit STT работает с голосовыми сообщениями меньше 30 секунд"

    if all_blocks >= MAX_USER_STT_BLOCKS:
        return None, (f"Превышен общий лимит SpeechKit STT {MAX_USER_STT_BLOCKS}. Использовано {all_blocks} блоков."
                      f"Доступно: {MAX_USER_STT_BLOCKS - all_blocks}")

    return audio_blocks

def is_tts_symbol_limit(user_id, text):
    text_symbols = len(text)
    all_symbols = count_all_limits(user_id) + text_symbols

    if all_symbols >= MAX_USER_TTS_SYMBOLS:
        return None, (f"Превышен общий лимит SpeechKit TTS {MAX_USER_TTS_SYMBOLS}. Использовано: {all_symbols} символов."
                      f"Доступно: {MAX_USER_TTS_SYMBOLS - all_symbols}")

    if text_symbols >= MAX_TTS_SYMBOLS:
        return None, f"Превышен лимит SpeechKit TTS на запрос {MAX_TTS_SYMBOLS}, в сообщении {text_symbols} символов"

    return len(text)