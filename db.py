import datetime
import aiosqlite
from pypika import Table, Query, Order
from config import DB_PATH

users = Table("users")
history = Table("history")
watch_later = Table("watch_later")


async def init_db() -> None:
    """Initialize the database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            year INTEGER NOT NULL,
            request_time TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS watch_later (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            year INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        """)
        await db.commit()
        print("База данных инициализирована.")


async def change_db(query: Query) -> None:
    """Execute a database modification query."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(str(query))
        await db.commit()


async def db_add_user(user_id: int) -> None:
    """Add a new user to the database if not exists."""
    if await check_user(user_id):
        return
    query = Query.into(users).insert(user_id)
    await change_db(query)


async def check_user(user_id: int) -> bool:
    """Check if a user exists in the database."""
    query = Query.from_(users).select(users.user_id).where(users.user_id == user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(str(query)) as cursor:
            result = await cursor.fetchone()
            return result is not None


async def save_film_to_history(user_id: int, name: str, year: int) -> None:
    """Save a film to user's history."""
    request_time = datetime.datetime.now()
    query = Query.into(history).columns(
        history.user_id, history.name, history.year, history.request_time
    ).insert(user_id, name, year, request_time)
    await change_db(query)


async def add_watch_later_films(user_id: int, name: str, year: int) -> None:
    """Add a film to user's watch later list."""
    query = Query.into(watch_later).columns(
        watch_later.user_id, watch_later.name, watch_later.year
    ).insert(user_id, name, year)
    await change_db(query)


async def delete_watch_later_film(user_id: int, film_id: int) -> None:
    """Delete a film from user's watch later list by its ID."""
    query = Query.from_(watch_later).delete().where(
        (watch_later.user_id == user_id) & (watch_later.id == film_id)
    )
    await change_db(query)


async def get_history(user_id: int) -> list[dict[str, str | int]]:
    """Retrieve the user's film history."""
    query = Query.from_(history).select(
        history.name, history.year, history.request_time
    ).where(history.user_id == user_id).orderby(history.request_time, order=Order.desc).limit(10)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(str(query)) as cursor:
            rows = await cursor.fetchall()
            return [
                {"name": row[0], "year": row[1], "request_time": row[2]}
                for row in rows
            ]


async def get_watch_later_films(user_id: int) -> list[dict[str, str | int]]:
    """Retrieve the user's watch later list."""
    query = Query.from_(watch_later).select(
        watch_later.id, watch_later.name, watch_later.year
    ).where(watch_later.user_id == user_id).orderby(watch_later.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(str(query)) as cursor:
            rows = await cursor.fetchall()
            return [
                {"id": row[0], "name": row[1], "year": row[2]}
                for row in rows
            ]


async def get_last_film(user_id: int) -> dict[str, str | int] | None:
    """Retrieve the last film from user's history."""
    last_film = await get_history(user_id)
    return last_film[0] if last_film else None
