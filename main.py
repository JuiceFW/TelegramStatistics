from collections import defaultdict
from pathlib import Path
from typing import Tuple
import traceback
import datetime
import logging
import sys
import os

from pyrogram import Client, types, filters
from pyrogram.enums import ParseMode

from config import *


### SCRIPT TelegramChatStats ###
BASE_DIR = Path(sys.argv[0]).parent
LOGS_DIR = BASE_DIR.joinpath("Logs")
os.chdir(BASE_DIR)


os.makedirs(LOGS_DIR, exist_ok=True)
logs_file = LOGS_DIR.joinpath(datetime.datetime.now().strftime("%d_%m_%Y") + ".log")

logs = os.listdir(LOGS_DIR)
if len(logs) > 15:
    for item in reversed(logs):
        if LOGS_DIR.joinpath(item) == logs_file:
            continue

        try:
            os.remove(LOGS_DIR.joinpath(item))
            break
        except:
            print(traceback.format_exc())
            continue
logs = []

logger = logging.getLogger()
logging_format = '%(asctime)s : %(name)s : %(levelname)s : %(message)s' # Можно убрать %(name)s
logging.basicConfig(
    level=logging.INFO,
    format=logging_format
)
try:
    fh = logging.FileHandler(
        logs_file,
        encoding='utf-8'
    )
except:
    try:
        fh = logging.FileHandler(
            logs_file
        )
    except:
        print(traceback.format_exc())
        os._exit(0)
fh.setFormatter(logging.Formatter(logging_format))
logger.addHandler(fh)


# You can change this name
session_name = "my_session"
session_name = session_name.replace(".session", "")

me = None
parsed_app = False
app = Client(session_name, api_hash=API_HASH, api_id=API_ID, hide_password=True)


async def get_messages_top(data_dict: dict, size: int = 5, reverse: bool = False) -> dict:
    sorted_items = sorted(data_dict.items(), key=lambda item: item[1], reverse=(not reverse))
    
    top_n_dict = {}
    for i in range(min(size, len(sorted_items))):
        top_n_dict[i+1] = {"date": sorted_items[i][0], "count": sorted_items[i][1]}

    return top_n_dict


async def _calculate_max_conversation_time(messages: list[types.Message], max_time_limit: int = 5) -> float:
    """
    Calculates the maximum conversation time in hours, considering a max_time_limit hour gap between messages as the end of a conversation.

    Args:
        messages: A list of messages.
        max_time_limit: Max hours of delay between messages

    Returns:
        The maximum conversation time in hours.
    """

    if not messages:
        return 0

    messages.sort(key=lambda msg: msg.date)

    max_duration = datetime.timedelta(0)
    current_start = None # Время начала текущего интервала общения
    last_message_time = None # Время последнего обработанного сообщения
    
    for msg in messages:
        if current_start is None:
            # Если это первое сообщение
            current_start = msg.date

        elif last_message_time is not None and (msg.date - last_message_time) > datetime.timedelta(hours=max_time_limit):
            # Если current_start уже задан, и разница между текущим сообщением и предыдущим больше max_time_limit часов, значит текущий интервал общения окончен.

            duration = last_message_time - current_start
            if duration > max_duration:
                max_duration = duration
            current_start = msg.date
    
        last_message_time = msg.date

    if current_start is not None and last_message_time is not None and (last_message_time - current_start) > max_duration:
        max_duration = last_message_time - current_start

    return max_duration.total_seconds() / 3600


async def get_messages_streak(messages: list[types.Message]) -> int:
    # Извлекаем даты сообщений (удаляем время, оставляем только даты)
    dates = sorted(
        {msg.date.date() for msg in messages}, # Извлечение уникальных дат
        reverse=True # От самой новой к старой
    )

    streak = 1 # Начинаем streak с крайнего дня
    for i, date in enumerate(dates):
        # Проверяем, является ли текущая дата на 1 день старше предыдущей

        try:
            dates[i+1]
        except:
            break

        if date == dates[i+1] or date == dates[i+1] + datetime.timedelta(days=1):
            streak += 1
        else:
            break # Если пропуск в днях, streak прерывается

    return streak


async def get_messages_answ_time(messages: list[types.Message]) -> Tuple[dict[int], dict[list]]:
    start_conv_counts = defaultdict(int)
    response_times = defaultdict(list)

    last_msg_time = None
    last_user_id = None
    last_msg_has_text = None

    last_msg_w_time = None

    messages.sort(key=lambda msg: msg.date)
    for msg in messages:
        user_id = msg.from_user.id

        # Анализ начала диалога
        if not last_user_id is None and user_id != last_user_id:
            # Новый диалог начался после предыдущего, если пауза больше 4 часов
            if msg.date - last_msg_time > datetime.timedelta(hours=4):
                start_conv_counts[user_id] += 1
            else:
                if (msg.text or msg.caption) and last_msg_has_text:
                    # Анализ времени ответа
                    response_time = (msg.date - (last_msg_w_time or last_msg_time)).total_seconds()
                    response_times[(user_id, last_user_id)].append(response_time)
        elif not last_user_id:
            start_conv_counts[user_id] += 1

        if not last_user_id is None and user_id == last_user_id:
            last_msg_w_time = last_msg_time
        else:
            last_msg_w_time = None

        last_user_id = user_id
        last_msg_time = msg.date
        last_msg_has_text = True if (msg.text or msg.caption) else False

    return start_conv_counts, response_times


async def avg_time(pair: tuple, response_times: dict[list]):
    times = response_times.get(pair, [])
    return sum(times) / len(times) if times else None


async def calculate_message_ratio(client: Client, me_id: int, chat_id: int) -> dict:
    """
    Calculates the message ratio between two participants in a chat.

    Args:
        client: The client object for interacting with the chat.
        chat_id: The ID of the chat.

    Returns:
        A dictionary containing the message ratio. Returns None if the chat has fewer than two participants or an error occurs.
        Dictionary keys: "ratio", "total_messages", "user_message_counts".
        If messages from one participant are not found, the corresponding part of the dictionary (e.g., "ratio_B_to_A") will be empty.
    """

    try:
        messages = [] # type: list[types.Message]
        async for msg in client.get_chat_history(chat_id):
            messages.append(msg)
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return None
    logger.info(f"Все сообщения по [{chat_id}] получены!")

    top_messages = defaultdict(int)
    user_message_counts = {}
    user_text_av = {}
    message_count_but_me = 0

    for msg in messages:
        user_id = msg.from_user.id
        if user_id not in user_message_counts:
            user_message_counts[user_id] = 0
        if user_id not in user_text_av:
            user_text_av[user_id] = []

        msg_date = msg.date.strftime("%d_%m_%Y")
        top_messages[msg_date] += 1

        user_message_counts[user_id] += 1
        if user_id != me_id:
            message_count_but_me += 1

        msg_text = msg.text or msg.caption
        if msg_text:
            user_text_av[user_id].append(len(msg_text))

    if len(user_message_counts) < 2:
        return None

    messages_streak = await get_messages_streak(messages)
    messages_top = await get_messages_top(top_messages)
    messages_reverse_top = await get_messages_top(top_messages, reverse=True)

    # Choosing first two users
    _tmp = list(user_message_counts.keys())
    first_user_id = _tmp[0]
    second_user_id = _tmp[1] if len(user_message_counts) > 1 else None

    _tmp = user_text_av.get(first_user_id, []); av_msg_symbols_a = sum(_tmp)/len(_tmp)
    _tmp = user_text_av.get(second_user_id, []); av_msg_symbols_b = sum(_tmp)/len(_tmp)

    messages_a = user_message_counts.get(first_user_id, 0)
    messages_b = user_message_counts.get(second_user_id, 0)

    # If user is not found
    if messages_a == 0 or messages_b == 0:
        return None

    ratio_a_to_b = messages_a / messages_b if messages_b != 0 else 0
    ratio_b_to_a = messages_b / messages_a if messages_a != 0 else 0
    msg_ratio_a_to_b = messages_a / (messages_a+messages_b) if (messages_a and messages_b) else 0
    msg_ratio_b_to_a = messages_b / (messages_a+messages_b) if (messages_a and messages_b) else 0

    # Calculating max conversation time
    max_conversation_time_short = await _calculate_max_conversation_time(messages, max_time_limit = 6)
    max_conversation_time_big = await _calculate_max_conversation_time(messages, max_time_limit = 12)


    start_conv_counts, response_times = await get_messages_answ_time(messages)

    # Start conversation ratio
    start_a = start_conv_counts.get(first_user_id, 0)
    start_b = start_conv_counts.get(second_user_id, 0)
    total_starts = start_a + start_b if (start_a + start_b) > 0 else 1
    start_conv_ratio_a_to_b = start_a / total_starts
    start_conv_ratio_b_to_a = start_b / total_starts

    # Average answer time
    answ_time_a_to_b = await avg_time((first_user_id, second_user_id), response_times)
    answ_time_b_to_a = await avg_time((second_user_id, first_user_id), response_times)


    return {
        "ratio": {
            "user_a": first_user_id,
            "ratio_a_to_b": ratio_a_to_b,
            "msg_ratio_a_to_b": msg_ratio_a_to_b,
            "start_conv_a_to_b": start_conv_ratio_a_to_b,

            "user_b": second_user_id,
            "ratio_b_to_a": ratio_b_to_a,
            "msg_ratio_b_to_a": msg_ratio_b_to_a,
            "start_conv_b_to_a": start_conv_ratio_b_to_a,
        },
        "time": {
            "user_a": first_user_id,
            "answ_time_a_to_b": answ_time_a_to_b,

            "user_b": second_user_id,
            "answ_time_b_to_a": answ_time_b_to_a,
        },
        "total_messages": sum(user_message_counts.values()),
        "max_conversation_time": {
            "short": max_conversation_time_short,
            "big": max_conversation_time_big
        },
        "av_text_symbols": {
            "user_a": first_user_id,
            "val_a": av_msg_symbols_a,
            "user_b": second_user_id,
            "val_b": av_msg_symbols_b,
        },
        "user_message_counts": user_message_counts,
        "messages_streak": messages_streak,
        "messages_top": messages_top,
        "messages_reverse_top": messages_reverse_top,
    }


async def prepare_text(client: Client, history_info: dict[str]) -> str:
    user_message_counts = history_info.get("user_message_counts") # type: dict[int]
    av_text_symbols = history_info.get("av_text_symbols") # type: dict[str, int]
    max_conversation_time = history_info.get("max_conversation_time") # type: int
    messages_streak = history_info.get("messages_streak") # type: int
    total_messages = history_info.get("total_messages") # type: int
    deleted_messages = str(history_info.get("deleted_messages", "-")) # type: str
    messages_top = history_info.get("messages_top") # type: dict
    messages_reverse_top = history_info.get("messages_reverse_top") # type: dict
    ratio = history_info.get("ratio") # type: dict
    timing = history_info.get("time") # type: dict

    if LANGUAGE == "ru":
        stats = "<b>Статистика чата:</b>\n\n"
 
        _tmp =  "\n<b>Написал первым/ой:</b>\n<i>"
        __tmp =  "\n<b>Средний размер текста:</b>\n<i>"
        stats += f"<b>Всего сообщений:</b> {total_messages}\n"
        for user_id, count in user_message_counts.items():
            user = await client.get_users(user_id)

            reply_ratio = ratio.get("ratio_a_to_b") if ratio.get("user_a") == user_id else ratio.get("ratio_b_to_a")
            msg_ratio = ratio.get("msg_ratio_a_to_b") if ratio.get("user_a") == user_id else ratio.get("msg_ratio_b_to_a")
            stats += f"<b>{user.first_name}:</b> {count} сообщений, коэф.о.: {reply_ratio:.2f}, коэф.сообщ.: {msg_ratio:.2f}\n"

            conv_ratio = ratio.get("start_conv_a_to_b") if ratio.get("user_a") == user_id else ratio.get("start_conv_b_to_a")
            timing_ratio = timing.get("answ_time_a_to_b") if timing.get("user_a") == user_id else timing.get("answ_time_b_to_a")
            _tmp += f"<b>{user.first_name}:</b> коэф.: {conv_ratio:.2f}, ср. время ответа.: {timing_ratio:.2f}\n"

            av_msg_symbols = av_text_symbols.get("val_a", 0) if av_text_symbols.get("user_a") == user_id else av_text_symbols.get("val_b", 0)
            __tmp += f"<b>{user.first_name}:</b>: {av_msg_symbols:.2f} симв.\n"

        stats += f"\n<b>Удалено сообщений:</b> <i>{deleted_messages}</i>\n"

        _tmp += "</i>"
        __tmp += "</i>"
        stats += _tmp
        stats += __tmp

        stats += "\n<b>Топ сообщений:</b>\n<i>"
        for place, data in messages_top.items():
            stats += f'{data.get("date").replace("_", ".")} - {data.get("count")}\n'
        stats += f'...\n'
        for place, data in reversed(messages_reverse_top.items()):
            stats += f'{data.get("date").replace("_", ".")} - {data.get("count")}\n'
        stats += "</i>"


        stats += f"""\n<b>Максимальное время общения:</b>\n<i>Подробное: {max_conversation_time["short"]:.2f}ч.\nКраткое: {max_conversation_time["big"]:.2f}ч.</i>"""
        stats += f"""\n\n<b>🔥 Streak:</b> <i>{messages_streak} дней</i>"""
    else:
        stats = "<b>Chat Stats:</b>\n\n"

        _tmp =  "\n<b>Started first:</b>\n<i>"
        __tmp =  "\n<b>Av. text size:</b>\n<i>"
        stats += f"<b>Total Messages:</b> {total_messages}\n"
        for user_id, count in user_message_counts.items():
            user = await client.get_users(user_id)

            reply_ratio = ratio.get("ratio_a_to_b") if ratio.get("user_a") == user_id else ratio.get("ratio_b_to_a")
            msg_ratio = ratio.get("msg_ratio_a_to_b") if ratio.get("user_a") == user_id else ratio.get("msg_ratio_b_to_a")
            stats += f"<b>{user.first_name}:</b> {count} messages, reply ratio: {reply_ratio:.2f}, msgs ratio: {msg_ratio:.2f}\n"

            conv_ratio = ratio.get("start_conv_a_to_b") if ratio.get("user_a") == user_id else ratio.get("start_conv_b_to_a")
            timing_ratio = timing.get("answ_time_a_to_b") if timing.get("user_a") == user_id else timing.get("answ_time_b_to_a")
            _tmp += f"<b>{user.first_name}:</b> ratio.: {conv_ratio:.2f}, av. answer time.: {timing_ratio:.2f}\n"

            av_msg_symbols = av_text_symbols.get("val_a", 0) if av_text_symbols.get("user_a") == user_id else av_text_symbols.get("val_b", 0)
            __tmp += f"<b>{user.first_name}:</b>: {av_msg_symbols:.2f} symb.\n"

        stats += f"\n<b>Deleted messages:</b> <i>{deleted_messages}</i>\n"

        _tmp += "</i>"
        __tmp += "</i>"
        stats += _tmp
        stats += __tmp

        stats += "\n<b>Top Messages:</b>\n<i>"
        for place, data in messages_top.items():
            stats += f'{data.get("date").replace("_", ".")} - {data.get("count")}\n'
        stats += f'...\n'
        for place, data in reversed(messages_reverse_top.items()):
            stats += f'{data.get("date").replace("_", ".")} - {data.get("count")}\n'
        stats += "</i>"


        stats += f"""\n<b>Maximum Conversation Time:</b>\n<i>Detailed: {max_conversation_time["short"]:.2f}h.\nBrief: {max_conversation_time["big"]:.2f}h.</i>"""
        stats += f"""\n\n<b>🔥 Streak:</b> <i>{messages_streak} days</i>"""

    return stats


@app.on_message(filters.private & filters.text & filters.command(["stats"]))
async def stats_command(client: Client, message: types.Message):
    me = await client.get_me()
    if message.from_user.id != me.id:
        return

    chat_id = message.chat.id
    try:
        await client.delete_messages(chat_id, message.id)
    except:
        logger.error(traceback.format_exc())

    logger.info("Creating stats....")
    if SEND_TO_CHAT == True:
        _msg = await message.reply("Creating stats....")
    else:
        _msg = await client.send_message("me", "Creating stats....")


    history_info = await calculate_message_ratio(client, me.id, chat_id) # type: dict
    stats = await prepare_text(history_info)


    await _msg.edit_text(stats, parse_mode=ParseMode.HTML)


if __name__ == "__main__":
    app.run()
