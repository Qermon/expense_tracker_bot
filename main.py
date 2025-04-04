import asyncio
import logging
import uvicorn
from bot.run import start_bot
from fastapi import FastAPI
from database import SessionLocal, engine, Base

#python main.py старт бота

Base.metadata.create_all(bind=engine)
app = FastAPI()


async def start_fastapi():
    config = uvicorn.Config(app, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    logging.basicConfig(level=logging.INFO)
    await asyncio.gather(
        start_fastapi(),
        start_bot()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Вихід")
