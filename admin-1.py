from aiogram.types import User as TgUser

from bot.config import get_settings

settings = get_settings()


def is_admin(user: TgUser) -> bool:
    if user.id in settings.admin_ids:
        return True
    if user.username and user.username.lower() in settings.admin_usernames:
        return True
    return False


async def get_admin_notify_ids(session) -> set[int]:
    from database.crud import get_user_with_stats_by_username

    ids = set(settings.admin_ids)
    for username in settings.admin_usernames:
        data = await get_user_with_stats_by_username(session, username)
        if data:
            ids.add(data[0].telegram_id)
    return ids
