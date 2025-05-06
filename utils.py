import asyncio
import dataclasses
import aiohttp
import typing as tp
import logging

from config import TOKEN_KINOPOISK, ZONA_URL
from bs4 import BeautifulSoup

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants.

HEADERS_KINOPOISK = {'X-API-KEY': TOKEN_KINOPOISK}
USER_AGENT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                  ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
    'Accept-Encoding': "utf-8",
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
}


# Data structure for storing movie information
@dataclasses.dataclass()
class FilmInfo:
    id: tp.Optional[int]
    name: tp.Optional[str]
    alternative_name: tp.Optional[str]
    year: tp.Optional[str]
    rating: tp.Optional[dict[str, tp.Optional[float]]]
    votes: tp.Optional[dict[str, tp.Optional[int]]]
    description: tp.Optional[str]
    poster: tp.Optional[str]


# Helper function to extract movie information from a page response
def film_info_from_page(page: dict) -> FilmInfo:
    poster = page.get("poster")
    poster_url = poster.get("url") if poster.get("url", None) else "https://imgur.com/eEmOQBt"
    return FilmInfo(
        id=page.get("id"),
        name=page.get("name"),
        alternative_name=page.get("alternativeName"),
        year=page.get("year"),
        rating=page.get("rating"),
        votes=page.get("votes"),
        description=page.get("description"),
        poster=poster_url,
    )


session: aiohttp.ClientSession | None = None


# Initialize an aiohttp session
async def init_session():
    global session
    session = aiohttp.ClientSession()


# Retrieve a random movie
async def get_random_film() -> tp.Optional[FilmInfo]:
    url = "https://api.kinopoisk.dev/v1.4/movie/random"
    params = {
        "votes.kp": "2000-6666666",
        "notNullFields": ["description"]
    }
    try:
        async with session.get(url, headers=HEADERS_KINOPOISK, params=params) as response:
            if response.status == 200:
                logger.info(f"✅ Request status: {response.status}")
                page = await response.json()
                return film_info_from_page(page)
            else:
                logger.warning(f"⚠️ Failed to retrieve a movie. Status code: {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"❌ Connection error: {e}")
    return None


# Search for a movie by name
async def get_film_by_name(name: str) -> tp.Optional[FilmInfo]:
    url = "https://api.kinopoisk.dev/v1.4/movie/search"
    try:
        async with session.get(url, headers=HEADERS_KINOPOISK, params={"query": name}) as response:
            if response.status == 200:
                logger.info(f"✅ Request status: {response.status}")
                src = await response.json()
                if not src.get("docs"):
                    logger.warning("⚠️ Movie not found")
                    return None
                page = src.get("docs", [None])[0]
                return film_info_from_page(page)
            else:
                logger.warning(f"⚠️ Error during movie search. Status code: {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"❌ Connection error: {e}")
    return None


# Helper function for requesting data by URL
async def _async_request(url: str, params: dict = None) -> tp.Tuple[tp.Optional[int], tp.Optional[str]]:
    try:
        async with session.get(url=url, params=params, headers=USER_AGENT_HEADERS, timeout=1) as response:
            if response.status == 200:
                text = await response.text()
                return response.status, text
            else:
                logger.warning(f"⚠️ Request error: {response.status}")
                return response.status, None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"❌ Connection error: {e}")
        return None, None


async def _check_url(url: str) -> bool:
    try:
        async with session.head(url, headers=USER_AGENT_HEADERS, timeout=1) as response:
            return response.status == 200
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"❌ Connection error: {e}")
        return False


# ---------LORDFILM----------
# Search for a movie link on the LordFilm website
async def find_lordfilm(film: FilmInfo) -> tp.Optional[str]:
    query = f"{film.name} {film.year} lordfilm"
    status, text = await _async_request("https://www.google.com/search", params={"q": query})
    try:
        soup = BeautifulSoup(text, "html.parser")
        all_links = [item.get("href") for item in soup.find_all(attrs={"jsname": "UWckNb"})[:3]]
        links = [link for link in all_links if "lordfilm" in link and link.startswith("https:/")]
        tasks = [asyncio.create_task(_check_url(link)) for link in links]
        results = await asyncio.gather(*tasks)

        for status, link in zip(results, links):
            if status:
                logger.info(f"✅ Found LordFilm link: {link}")
                return link
    except Exception as e:
        logger.error(f"❌ Error while processing LordFilm: {e}")

    return None


# ----------ZONA-----------
# Search for a movie link on the Zona website
async def find_zona(film: FilmInfo) -> tp.Optional[str]:
    search_url = f"{ZONA_URL}/search/{film.name}%20"
    status, text = await _async_request(search_url)
    if not text:
        return None
    try:
        soup = BeautifulSoup(text, "html.parser")
        for item in soup.find_all(attrs={"class": "results-item-wrap"}):
            item_year = item.find(attrs={"class": "results-item-year"}).text
            if int(item_year) == film.year:
                link = item.find("a").get("href")
                logger.info(f"✅ Found Zona link: {ZONA_URL}{link}")
                return f"{ZONA_URL}{link}"
    except Exception as e:
        logger.error(f"❌ Error while processing Zona: {e}")
    return None
