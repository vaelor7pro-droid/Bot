"""data/Tarix_250_test.json fayldagi savollarni bazaga yuklaydi.

Ishga tushirish:
    PYTHONPATH=. python -m scripts.load_questions
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from database.models import Question
from database.session import async_session, init_db

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "Tarix_250_test.json"

LETTER_TO_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3}


async def load_questions() -> None:
    await init_db()

    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    added = 0
    skipped = 0

    async with async_session() as session:
        for item in raw:
            text = item["question"].strip()

            # Bazada bir xil matnli savol borligini tekshiramiz (qayta yuklashda dublikat bo'lmasin)
            existing = await session.execute(
                select(Question.id).where(Question.text == text)
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

            options = item["options"]
            correct_letter = item["answer"].strip().upper()

            question = Question(
                text=text,
                option_a=options[0],
                option_b=options[1],
                option_c=options[2],
                option_d=options[3],
                correct_option=correct_letter,
                is_active=True,
            )
            session.add(question)
            added += 1

        await session.commit()

    print(f"✅ Yuklandi: {added} ta yangi savol. O'tkazib yuborildi (dublikat): {skipped} ta.")


if __name__ == "__main__":
    asyncio.run(load_questions())
