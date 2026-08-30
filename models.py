"""Ma'lumotlar bazasi modellari, ulanish (engine/session) va boshlang'ich sozlash."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    answers: Mapped[list["UserAnswer"]] = relationship(back_populates="user")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(String(512), nullable=False)
    option_b: Mapped[str] = mapped_column(String(512), nullable=False)
    option_c: Mapped[str] = mapped_column(String(512), nullable=False)
    option_d: Mapped[str] = mapped_column(String(512), nullable=False)
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    answers: Mapped[list["UserAnswer"]] = relationship(back_populates="question")


class UserAnswer(Base):
    __tablename__ = "user_answers"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_user_question"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    selected_option: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship(back_populates="answers")


class RuntimeSetting(Base):
    """Ish vaqtida o'zgaradigan sozlamalar (masalan majburiy kanal), DB ichida
    saqlanadi — shu sababli Railow qayta ishga tushirilganda ham yo'qolmaydi."""

    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False, default="")


engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _seed_questions(session: AsyncSession) -> None:
    result = await session.execute(select(func.count(Question.id)))
    if (result.scalar() or 0) > 0:
        return

    if not settings.questions_file.exists():
        logger.warning("Savollar fayli topilmadi: %s", settings.questions_file)
        return

    with settings.questions_file.open("r", encoding="utf-8") as f:
        raw_questions = json.load(f)

    for item in raw_questions:
        options = item.get("options", [])
        if len(options) != 4:
            continue
        answer = str(item.get("answer", "")).strip().upper()
        if answer not in {"A", "B", "C", "D"}:
            continue
        session.add(
            Question(
                text=str(item.get("question", "")).strip(),
                option_a=options[0],
                option_b=options[1],
                option_c=options[2],
                option_d=options[3],
                correct_option=answer,
                is_active=True,
            )
        )
    await session.commit()
    logger.info("Savollar bazaga yuklandi: %d ta", len(raw_questions))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await _seed_questions(session)


async def get_channel_username() -> str:
    async with async_session() as session:
        result = await session.execute(
            select(RuntimeSetting).where(RuntimeSetting.key == "channel_username")
        )
        row = result.scalar_one_or_none()
        if row and row.value:
            return row.value
    return settings.channel_username


async def set_channel_username(username: str) -> str:
    clean = username.strip().lstrip("@")
    async with async_session() as session:
        result = await session.execute(
            select(RuntimeSetting).where(RuntimeSetting.key == "channel_username")
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = clean
        else:
            session.add(RuntimeSetting(key="channel_username", value=clean))
        await session.commit()
    return clean
