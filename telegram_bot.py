import asyncio
import datetime
import functools
import logging
import db
import utils

from aiogram.exceptions import TelegramBadRequest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from config import BOT_TOKEN


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def generate_keyboard(urls_dict: dict[str, str]) -> InlineKeyboardMarkup:
    """Generate a keyboard.."""
    buttons = [
        InlineKeyboardButton(text=name, url=url) for name, url in urls_dict.items() if url
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def command_handler(command_name: str, loading_text: str):
    """Decorator for handling errors and animations in commands.."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            if not await db.check_user(message.from_user.id):
                await db.db_add_user(message.from_user.id)
            message_animation = await bot.send_message(message.chat.id, loading_text)
            asyncio.create_task(
                loading_animation(message.chat.id, message_animation.message_id, loading_text)
            )
            try:
                await func(message, message_animation.message_id, *args, **kwargs)
            except Exception as e:
                logging.error(f"Ошибка в команде {command_name}: {e}")
                await message.answer(
                    "\U0001F6AB Произошла ошибка. Попробуйте позже."
                )

        return wrapper

    return decorator


async def loading_animation(chat_id: int, message_id: int, text: str) -> None:
    """Show a loading animation while processing."""
    states = [1, 2, 3, 2]
    for i in range(100):
        try:
            await asyncio.sleep(0.1)
            new_text = f"{text}{' ' * states[i % 4]}{'\U0001F50D'}"
            await bot.edit_message_text(text=new_text, chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest:
            break


async def film_info_message(message: Message, film: utils.FilmInfo, lordfilm: str, zona: str) -> None:
    """Send a message with information about a film."""
    rating_kp = film.rating.get("kp")
    votes_kp = film.votes.get("kp")
    rating_info = f"\u2B50 Рейтинг Кинопоиска: <b>{rating_kp}/10</b> ({votes_kp} голосов)\n" \
        if rating_kp and votes_kp else "\u2B50 Рейтинг не найден\n"
    film_description = film.description if film.description else "Описание отсутствует \u2639"
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=film.poster,
        caption=(
            f"<b>{film.name}</b> ({film.year})\n\n"
            f"{film_description}\n\n"
            f"{rating_info}\n"
            f"<i>{'\U0001F517 Ссылки для просмотра:' if lordfilm or zona else ''}</i>"
        ),
        reply_markup=generate_keyboard(
            {"Lordfilm": lordfilm, "Zona": zona}
        )
    )


async def update(film: utils.FilmInfo, user_id: int) -> None:
    """Update user's film history with current film."""
    if await db.check_user(user_id):
        await db.save_film_to_history(user_id, film.name, int(film.year))


async def set_default_commands():
    """Set default bot commands."""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Помощь и описание команд"),
        BotCommand(command="random", description="Случайный фильм"),
        BotCommand(command="history", description="История поиска фильмов"),
        BotCommand(command="watch_later", description="Просмотр списка 'Посмотреть позже'"),
        BotCommand(command="add_to_watch_later",
                   description="Добавить последний найденный фильм в 'Посмотреть позже'"),
        BotCommand(command="delete_from_watch_later",
                   description="Удалить фильм из 'Посмотреть позже' по номеру"),
    ]
    await bot.set_my_commands(commands)


@dp.message(CommandStart())
async def start_command(message: Message) -> None:
    """Handle the start command."""
    await db.db_add_user(message.from_user.id)
    await message.answer(
        "\U0001F44B Привет! Я помогу тебе найти фильмы. Просто отправь название фильма или воспользуйся командами.\n\n"
        "Для списка команд используй /help"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Handle the help command."""
    await message.answer(
        "\U0001F4D6 <b>Справочник команд:</b>\n\n"
        "/start - Запустить бота\n\n"
        "/help - Помощь\n\n"
        "/random - Случайный фильм\n\n"
        "/history - История поиска фильмов\n\n"
        "/watch_later - Просмотр списка 'Посмотреть позже'\n\n"
        "/add_to_watch_later - Добавить последний найденный фильм в 'Посмотреть позже'\n\n"
        "/delete_from_watch_later - Удалить фильм из 'Посмотреть позже' по номеру\n\n"
    )


@dp.message(Command("random"))
@command_handler("random", "\U0001F4E1 Ищу случайный фильм")
async def random_handler(message: Message, loading_id: int) -> None:
    """Handle the random film command."""
    film: utils.FilmInfo = await utils.get_random_film()
    if film:
        lordfilm, zona = await asyncio.gather(
            utils.find_lordfilm(film),
            utils.find_zona(film),
        )
        await update(film, message.from_user.id)
        await bot.delete_message(message.chat.id, loading_id)
        await film_info_message(message, film, lordfilm, zona)
    else:
        await bot.delete_message(message.chat.id, loading_id)
        await message.answer("\U0001F6AB Не удалось найти случайный фильм. Попробуйте снова!")


@dp.message(Command("history"))
async def history_handler(message: Message) -> None:
    """Handle the history command."""
    films = await db.get_history(message.from_user.id)
    if films:
        formatted_history = "\n".join(
            [
                f"<b>{i + 1}. {film['name']}</b> ({film['year']}) — "
                f"{datetime.datetime.fromisoformat(film['request_time']).strftime('%d.%m.%Y %H:%M')}"
                for i, film in enumerate(films)
            ]
        )
        await message.answer(
            f"\U0001F4D6 <b>История поиска фильмов:</b>\n\n{formatted_history}"
        )
    else:
        await message.answer("\U0001F625 История пуста.")


@dp.message(Command("watch_later"))
async def watch_later_handler(message: Message) -> None:
    """Handle the watch later command."""
    films = await db.get_watch_later_films(message.from_user.id)
    if films:
        formatted_watch_later = "\n".join(
            [
                f"<b>{i + 1}. {film['name']}</b> ({film['year']})"
                for i, film in enumerate(films)
            ]
        )
        await message.answer(
            f"\U0001F4CC <b>Список 'Посмотреть позже':</b>\n\n{formatted_watch_later}"
        )
    else:
        await message.answer("\U0001F625 Список пуст.")


@dp.message(Command("add_to_watch_later"))
async def add_to_watch_later_handler(message: Message) -> None:
    """Handle the command to add a film to the watch later list."""
    film = await db.get_last_film(message.from_user.id)
    if film:
        await db.add_watch_later_films(message.from_user.id, film["name"], film["year"])
        await message.answer(
            f"\U00002705 Фильм <b>{film['name']}</b> ({film['year']}) добавлен в список Посмотреть позже."
        )
    else:
        await message.answer("\U0001F625 Не найдено последних фильмов для добавления.")


@dp.message(Command("delete_from_watch_later"))
async def delete_from_watch_later_handler(message: Message) -> None:
    """Handle the command to delete a film from the watch later list."""
    try:
        _, film_number = message.text.split()
        film_number = int(film_number) - 1
        films = await db.get_watch_later_films(message.from_user.id)

        if 0 <= film_number < len(films):
            film_id = films[film_number]["id"]
            await db.delete_watch_later_film(message.from_user.id, film_id)
            await message.answer(
                f"\U00002705 Фильм <b>{films[film_number]['name']}</b> удален из списка 'Посмотреть позже'."
            )
        else:
            await message.answer("\U000026A0 Неверный номер фильма. Попробуйте снова.")
    except (ValueError, IndexError):
        await message.answer(
            "\U000026A0 Пожалуйста, укажите корректный номер фильма после команды. Пример: /delete_from_watch_later 1")


@dp.message()
@command_handler("search", "Ищу фильм")
async def search_handler(message: Message, loading_id: int) -> None:
    """Handle the search command."""
    film: utils.FilmInfo = await utils.get_film_by_name(message.text)
    if film:
        lordfilm, zona = await asyncio.gather(
            utils.find_lordfilm(film),
            utils.find_zona(film),
        )
        await update(film, message.from_user.id)
        await bot.delete_message(message.chat.id, loading_id)
        await film_info_message(message, film, lordfilm, zona)
    else:
        await bot.delete_message(message.chat.id, loading_id)
        await message.answer(
            "\U0001F625 К сожалению мне не удалось найти этот фильм."
        )


async def start_bot() -> None:
    """Main entry point for the bot."""
    try:
        await db.init_db()
        await utils.init_session()
        await set_default_commands()
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Critical error while starting the bot: {e}")
