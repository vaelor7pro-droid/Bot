"""Database CRUD operatsiyalari."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from database.models import Question, User, UserAnswer

settings = get_settings()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
    referrer_telegram_id: int | None = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.username = username
        user.full_name = full_name
        return user

    referrer_db_id = None
    if referrer_telegram_id and referrer_telegram_id != telegram_id:
        ref = await session.execute(
            select(User).where(User.telegram_id == referrer_telegram_id)
        )
        referrer = ref.scalar_one_or_none()
        if referrer:
            referrer_db_id = referrer.id

    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        balance=0,
        referred_by_id=referrer_db_id,
    )
    session.add(user)
    await session.flush()
    return user


async def count_user_answers(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(UserAnswer.id)).where(UserAnswer.user_id == user_id)
    )
    return int(result.scalar() or 0)


async def get_unanswered_questions(
    session: AsyncSession, user_id: int, limit: int = 1
) -> list[Question]:
    answered_count = await count_user_answers(session, user_id)
    if answered_count >= settings.questions_per_user:
        return []

    remaining_quota = settings.questions_per_user - answered_count
    fetch_limit = min(limit, remaining_quota)

    answered_subq = select(UserAnswer.question_id).where(UserAnswer.user_id == user_id)
    result = await session.execute(
        select(Question)
        .where(Question.is_active.is_(True))
        .where(Question.id.not_in(answered_subq))
        .order_by(func.random())
        .limit(fetch_limit)
    )
    return list(result.scalars().all())


async def has_answered_question(
    session: AsyncSession, user_id: int, question_id: int
) -> bool:
    result = await session.execute(
        select(UserAnswer.id).where(
            UserAnswer.user_id == user_id,
            UserAnswer.question_id == question_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def submit_answer(
    session: AsyncSession,
    user: User,
    question: Question,
    selected: str,
) -> tuple[bool, int]:
    if await has_answered_question(session, user.id, question.id):
        raise ValueError("Bu savolga allaqachon javob berilgan")

    selected = selected.upper()
    is_correct = selected == question.correct_option.upper()

    answer = UserAnswer(
        user_id=user.id,
        question_id=question.id,
        selected_option=selected,
        is_correct=is_correct,
        reward_amount=0,
    )
    session.add(answer)
    await session.flush()
    return is_correct, 0


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_stats(session: AsyncSession, user_id: int) -> dict:
    total = await session.execute(
        select(func.count(UserAnswer.id)).where(UserAnswer.user_id == user_id)
    )
    correct = await session.execute(
        select(func.count(UserAnswer.id)).where(
            UserAnswer.user_id == user_id, UserAnswer.is_correct.is_(True)
        )
    )
    last_answer = await session.execute(
        select(func.max(UserAnswer.answered_at)).where(UserAnswer.user_id == user_id)
    )
    total_n = int(total.scalar() or 0)
    correct_n = int(correct.scalar() or 0)
    return {
        "total_answers": total_n,
        "correct_answers": correct_n,
        "wrong_answers": total_n - correct_n,
        "last_answered_at": last_answer.scalar(),
    }


async def list_all_users(session: AsyncSession, limit: int = 50) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def list_users_with_stats(
    session: AsyncSession, limit: int = 50
) -> list[tuple[User, dict]]:
    users = await list_all_users(session, limit)
    return [(u, await get_user_stats(session, u.id)) for u in users]


async def get_top_players(
    session: AsyncSession, limit: int = 10
) -> list[tuple[User, dict]]:
    correct_count = (
        select(
            UserAnswer.user_id.label("uid"),
            func.count(UserAnswer.id).label("correct_n"),
        )
        .where(UserAnswer.is_correct.is_(True))
        .group_by(UserAnswer.user_id)
        .subquery()
    )
    result = await session.execute(
        select(User, func.coalesce(correct_count.c.correct_n, 0).label("correct_n"))
        .outerjoin(correct_count, User.id == correct_count.c.uid)
        .order_by(
            func.coalesce(correct_count.c.correct_n, 0).desc(),
            User.id.asc(),
        )
        .limit(limit)
    )
    rows = result.all()
    out: list[tuple[User, dict]] = []
    for user, _correct_n in rows:
        stats = await get_user_stats(session, user.id)
        out.append((user, stats))
    return out


async def get_user_with_stats_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> tuple[User, dict] | None:
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    stats = await get_user_stats(session, user.id)
    return user, stats


async def get_user_with_stats_by_username(
    session: AsyncSession, username: str
) -> tuple[User, dict] | None:
    username = username.lstrip("@").lower()
    result = await session.execute(
        select(User).where(func.lower(User.username) == username)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    stats = await get_user_stats(session, user.id)
    return user, stats
