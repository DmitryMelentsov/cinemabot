from quart import Quart, render_template, request, redirect, url_for, session
from quart_auth import (
    AuthUser,
    login_user,
    logout_user,
    current_user,
    login_required,
    Unauthorized,
    QuartAuth
)
import hashlib, hmac
import asyncio
import utils
import db
from config import BOT_TOKEN, SECRET_KEY

app = Quart(__name__)
app.secret_key = SECRET_KEY
QuartAuth(app)

@app.errorhandler(Unauthorized)
async def redirect_to_login(*_):
    return redirect(url_for("login_page"))

def check_telegram_auth(data: dict) -> bool:
    hash_to_check = data.pop("hash", "")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, hash_to_check)

@app.before_serving
async def startup():
    await utils.init_session()
    await db.init_db()

@app.route("/auth", methods=["GET", "POST"])
async def telegram_auth():
    if request.method == "GET":
        data = request.args
    else:
        data = await request.form

    data_dict = dict(data)
    if not check_telegram_auth(data_dict.copy()):
        return "Unauthorized", 401

    user = AuthUser(data_dict["id"])
    login_user(user)

    return redirect(url_for("index"))

@app.get("/login_page")
async def login_page():
    return await render_template("login.html")

@app.route("/logout")
@login_required
async def logout():
    logout_user()
    return redirect(url_for("login_page"))

@app.route("/", methods=["GET", "POST"])
@login_required
async def index():
    if request.method == "POST":
        form = await request.form
        film_name = form.get("film_name")
        return redirect(url_for("search_result", query=film_name))
    return await render_template("index.html")

@app.route("/search")
@login_required
async def search_result():
    query = request.args.get("query", "")
    film = await utils.get_film_by_name(query)
    if film:
        lordfilm, zona = await asyncio.gather(
            utils.find_lordfilm(film),
            utils.find_zona(film)
        )
        user_id = int(current_user.auth_id)
        await db.save_film_to_history(user_id, film.name, int(film.year))
        return await render_template("result.html",
                                     film=film,
                                     lordfilm=lordfilm,
                                     zona=zona)
    else:
        return await render_template("result.html", film=None)

@app.route("/add_watch_later/<name>/<int:year>")
@login_required
async def add_watch_later(name: str, year: int):
    user_id = int(current_user.auth_id)
    await db.add_watch_later_films(user_id, name, year)
    return redirect(url_for("watch_later"))

@app.route("/delete_watch_later/<int:film_id>")
@login_required
async def delete_watch_later(film_id: int):
    user_id = int(current_user.auth_id)
    await db.delete_watch_later_film(user_id, film_id)
    return redirect(url_for("watch_later"))

@app.route("/history")
@login_required
async def history():
    user_id = int(current_user.auth_id)
    records = await db.get_history(user_id)
    return await render_template("history.html", history=records)

@app.route("/watch_later")
@login_required
async def watch_later():
    user_id = int(current_user.auth_id)
    films = await db.get_watch_later_films(user_id)
    return await render_template("watch_later.html", films=films)

