"""Database CRUD operatsiyalari."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import Question, User, UserAnswer


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    full_name: str | None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.username = username
        user.full_name = full_name
        await session.commit()
        return user

    user = User(telegram_id=telegram_id, username=username, full_name=full_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def count_user_answers(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count(UserAnswer.id)).where(UserAnswer.user_id == user_id)
    )
    return int(result.scalar() or 0)


async def get_unanswered_question(session: AsyncSession, user_id: int) -> Question | None:
    answered_count = await count_user_answers(session, user_id)
    if answered_count >= settings.questions_per_user:
        return None

    answered_subq = select(UserAnswer.question_id).where(UserAnswer.user_id == user_id)
    result = await session.execute(
        select(Question)
        .where(Question.is_active.is_(True))
        .where(Question.id.not_in(answered_subq))
        .order_by(func.random())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_question_by_id(session: AsyncSession, question_id: int) -> Question | None:
    result = await session.execute(select(Question).where(Question.id == question_id))
    return result.scalar_one_or_none()


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
) -> bool:
    if await has_answered_question(session, user.id, question.id):
        raise ValueError("Bu savolga allaqachon javob berilgan")

    selected = selected.upper()
    is_correct = selected == question.correct_option.upper()

    session.add(
        UserAnswer(
            user_id=user.id,
            question_id=question.id,
            selected_option=selected,
            is_correct=is_correct,
        )
    )
    await session.commit()
    return is_correct


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    username = username.lstrip("@").lower()
    result = await session.execute(
        select(User).where(func.lower(User.username) == username)
    )
    return result.scalar_one_or_none()


async def get_user_stats(session: AsyncSession, user_id: int) -> dict:
    total_res = await session.execute(
        select(func.count(UserAnswer.id)).where(UserAnswer.user_id == user_id)
    )
    correct_res = await session.execute(
        select(func.count(UserAnswer.id)).where(
            UserAnswer.user_id == user_id, UserAnswer.is_correct.is_(True)
        )
    )
    last_res = await session.execute(
        select(func.max(UserAnswer.answered_at)).where(UserAnswer.user_id == user_id)
    )
    total_n = int(total_res.scalar() or 0)
    correct_n = int(correct_res.scalar() or 0)
    return {
        "total_answers": total_n,
        "correct_answers": correct_n,
        "wrong_answers": total_n - correct_n,
        "last_answered_at": last_res.scalar(),
    }


async def list_users_with_stats(
    session: AsyncSession, limit: int = 50
) -> list[tuple[User, dict]]:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(limit)
    )
    users = list(result.scalars().all())
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


async def get_user_with_stats(
    session: AsyncSession, query: str
) -> tuple[User, dict] | None:
    query = query.strip()
    if query.startswith("@") or not query.lstrip("-").isdigit():
        user = await get_user_by_username(session, query)
    else:
        user = await get_user_by_telegram_id(session, int(query))
    if not user:
        return None
    stats = await get_user_stats(session, user.id)
    return user, stats
