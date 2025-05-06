from hypercorn.asyncio import serve
from hypercorn.config import Config
from web_app import app

config = Config()
config.bind = ["127.0.0.1:5000"]
config.use_reloader = False
config.install_signal_handlers = True

if __name__ == "__main__":
    import asyncio
    asyncio.run(serve(app, config))
