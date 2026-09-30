from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent

from app.config import load_settings
from app.database import create_engine, create_sessionmaker, init_db
from app.handlers import admin, parent
from app.middleware import DbSessionMiddleware
from app.scheduler import build_scheduler

log = logging.getLogger("edu_memory")

PARENT_COMMANDS = [
    BotCommand(command="start", description="Boshlash"),
    BotCommand(command="stats", description="Farzand davomati"),
    BotCommand(command="link", description="Farzand qo‘shish"),
    BotCommand(command="help", description="Yordam"),
]
ADMIN_COMMANDS = [
    BotCommand(command="davomat", description="Bugungi davomat"),
    BotCommand(command="add_student", description="O‘quvchi qo‘shish"),
    BotCommand(command="students", description="O‘quvchilar ro‘yxati"),
    BotCommand(command="cancel", description="Bekor qilish"),
    BotCommand(command="link", description="Ota-ona sifatida bog‘lanish"),
    BotCommand(command="help", description="Yordam"),
]


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = load_settings()

    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    await init_db(engine)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))

    # Tartib muhim: avval admin, keyin ota-ona router'i
    dp.include_router(admin.build_router(settings))
    dp.include_router(parent.build_router(settings))

    @dp.error()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Handlerda xatolik: %s", event.exception)
        return True

    scheduler = build_scheduler(bot, sessionmaker, settings)

    async def on_startup() -> None:
        scheduler.start()  # bot restart bo'lganda scheduler avtomatik qayta ishga tushadi
        await bot.set_my_commands(PARENT_COMMANDS, scope=BotCommandScopeDefault())
        for admin_id in settings.admin_ids:
            try:
                await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception:  # admin hali botga /start bosmagan bo'lishi mumkin
                log.warning("Admin %s uchun buyruqlar menyusi o'rnatilmadi", admin_id)
        me = await bot.get_me()
        log.info("EDU MEMORY ishga tushdi: @%s | vaqt zonasi: %s", me.username, settings.timezone)

    async def on_shutdown() -> None:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await engine.dispose()
        log.info("EDU MEMORY to'xtatildi")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
