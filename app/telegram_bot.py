from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.main import DB_PATH, init_db

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def telegram_call(method: str, payload: dict) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(f"{API_BASE}/{method}", data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id: int, text: str, reply_markup=None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    telegram_call("sendMessage", payload)


def lesson_keyboard() -> dict:
    with connect() as db:
        lessons = db.execute("SELECT id, lesson_no, title FROM lessons ORDER BY lesson_no").fetchall()
    rows = []
    for lesson in lessons:
        rows.append(
            [
                {
                    "text": f"{lesson['lesson_no']}. {lesson['title'][:24]}",
                    "callback_data": f"lesson:{lesson['id']}",
                }
            ]
        )
    return {"inline_keyboard": rows}


def handle_message(message: dict) -> None:
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text == "/start":
        send_message(
            chat_id,
            "전기공학 기초와 변압기 학습 봇입니다. 학습할 레슨을 선택하세요.",
            lesson_keyboard(),
        )
        return
    send_message(chat_id, "먼저 /start 를 누르고 레슨을 선택해 주세요.")


def handle_callback(callback: dict) -> None:
    chat_id = callback["message"]["chat"]["id"]
    data = callback.get("data", "")
    if not data.startswith("lesson:"):
        return
    lesson_id = int(data.split(":", 1)[1])
    with connect() as db:
        lesson = db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        questions = db.execute(
            "SELECT question_type, prompt FROM questions WHERE lesson_id = ? ORDER BY id DESC LIMIT 3",
            (lesson_id,),
        ).fetchall()
    if not lesson:
        send_message(chat_id, "레슨을 찾지 못했습니다.")
        return

    body = lesson["published_text"] or lesson["draft_text"]
    preview = body[:1300] + ("..." if len(body) > 1300 else "")
    question_text = ""
    if questions:
        question_text = "\n\n문제 예시:\n" + "\n".join(
            f"- {row['prompt']}" for row in questions
        )
    send_message(chat_id, f"[Lesson {lesson['lesson_no']}] {lesson['title']}\n\n{preview}{question_text}")


def poll_updates() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    init_db()
    offset = 0
    while True:
        try:
            result = telegram_call("getUpdates", {"timeout": 25, "offset": offset})
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
                if "callback_query" in update:
                    handle_callback(update["callback_query"])
        except Exception as exc:
            print(f"Telegram polling error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    poll_updates()
