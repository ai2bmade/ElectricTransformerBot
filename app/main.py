from __future__ import annotations

import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.openai_service import generate_questions_for_lesson

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "learning_app.sqlite3"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ElectricTransformerBot")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


LESSON_SEED = [
    (1, "전기란 무엇인가 - 전압, 전류, 저항"),
    (2, "전력과 에너지"),
    (3, "자기와 전자기 유도"),
    (4, "직류(DC)와 교류(AC)"),
    (5, "3상 교류와 교류회로 심화"),
    (6, "발전의 원리"),
    (7, "송배전 전력망의 구조"),
    (8, "변압기의 원리"),
    (9, "변압기의 종류와 구조"),
    (10, "전력 변환 - 인버터와 컨버터"),
    (11, "에너지 저장 - 배터리와 ESS"),
    (12, "산업별 적용 - 4대 사업영역"),
]


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def execute_many(db: sqlite3.Connection, statements: Iterable[str]) -> None:
    for statement in statements:
        db.execute(statement)
    db.commit()


def init_db() -> None:
    with connect() as db:
        execute_many(
            db,
            [
                """
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_no INTEGER NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    draft_text TEXT NOT NULL DEFAULT '',
                    published_text TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft'
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lesson_id) REFERENCES lessons(id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_id INTEGER NOT NULL,
                    question_type TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    options_json TEXT NOT NULL DEFAULT '',
                    answer TEXT NOT NULL DEFAULT '',
                    explanation TEXT NOT NULL DEFAULT '',
                    reveal_timing TEXT NOT NULL DEFAULT 'after_submit',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lesson_id) REFERENCES lessons(id)
                )
                """,
            ],
        )
        for lesson_no, title in LESSON_SEED:
            db.execute(
                """
                INSERT OR IGNORE INTO lessons (lesson_no, title, draft_text, published_text)
                VALUES (?, ?, ?, ?)
                """,
                (
                    lesson_no,
                    title,
                    "이곳에 강사용 원문, OCR 결과, 또는 직접 작성한 레슨 내용을 넣으세요.",
                    "",
                ),
            )
        db.commit()


@app.on_event("startup")
def startup() -> None:
    init_db()


def get_lesson(db: sqlite3.Connection, lesson_id: int) -> sqlite3.Row:
    lesson = db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if lesson is None:
        raise ValueError("Lesson not found")
    return lesson


def list_lessons(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM lessons ORDER BY lesson_no").fetchall()


def list_assets(db: sqlite3.Connection, lesson_id: int) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM assets WHERE lesson_id = ? ORDER BY id DESC", (lesson_id,)
    ).fetchall()


def list_questions(db: sqlite3.Connection, lesson_id: int) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM questions WHERE lesson_id = ? ORDER BY id DESC", (lesson_id,)
    ).fetchall()


@app.get("/", response_class=HTMLResponse)
def home() -> RedirectResponse:
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request) -> HTMLResponse:
    with connect() as db:
        lessons = list_lessons(db)
    return templates.TemplateResponse(
        "admin.html", {"request": request, "lessons": lessons}
    )


@app.get("/admin/lessons/{lesson_id}", response_class=HTMLResponse)
def edit_lesson(request: Request, lesson_id: int) -> HTMLResponse:
    with connect() as db:
        lesson = get_lesson(db, lesson_id)
        assets = list_assets(db, lesson_id)
        questions = list_questions(db, lesson_id)
    return templates.TemplateResponse(
        "lesson_edit.html",
        {
            "request": request,
            "lesson": lesson,
            "assets": assets,
            "questions": questions,
        },
    )


@app.post("/admin/lessons/{lesson_id}/save")
def save_lesson(
    lesson_id: int,
    title: str = Form(...),
    draft_text: str = Form(""),
    published_text: str = Form(""),
    status: str = Form("draft"),
) -> RedirectResponse:
    with connect() as db:
        db.execute(
            """
            UPDATE lessons
            SET title = ?, draft_text = ?, published_text = ?, status = ?
            WHERE id = ?
            """,
            (title, draft_text, published_text, status, lesson_id),
        )
        db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}", status_code=303)


@app.post("/admin/lessons/{lesson_id}/ocr")
async def apply_ocr(lesson_id: int, image: UploadFile = File(...)) -> RedirectResponse:
    suffix = Path(image.filename or "upload.png").suffix or ".png"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    with stored_path.open("wb") as target:
        shutil.copyfileobj(image.file, target)

    ocr_text = run_ocr(stored_path)
    with connect() as db:
        lesson = get_lesson(db, lesson_id)
        new_text = f"{lesson['draft_text']}\n\n[OCR 결과: {image.filename}]\n{ocr_text}".strip()
        db.execute(
            "UPDATE lessons SET draft_text = ? WHERE id = ?", (new_text, lesson_id)
        )
        db.execute(
            "INSERT INTO assets (lesson_id, kind, title, url) VALUES (?, ?, ?, ?)",
            (lesson_id, "image", image.filename or "OCR image", f"/uploads/{stored_name}"),
        )
        db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}", status_code=303)


def run_ocr(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image

        tesseract_cmd = os.getenv("TESSERACT_CMD")
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        return pytesseract.image_to_string(Image.open(image_path), lang=os.getenv("OCR_LANG", "kor+eng")).strip()
    except Exception as exc:
        return f"OCR 실행 실패: {exc}"


@app.post("/admin/lessons/{lesson_id}/assets/image")
async def add_image(
    lesson_id: int,
    title: str = Form(...),
    image: UploadFile = File(...),
) -> RedirectResponse:
    suffix = Path(image.filename or "image.png").suffix or ".png"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    with stored_path.open("wb") as target:
        shutil.copyfileobj(image.file, target)
    with connect() as db:
        db.execute(
            "INSERT INTO assets (lesson_id, kind, title, url) VALUES (?, ?, ?, ?)",
            (lesson_id, "image", title, f"/uploads/{stored_name}"),
        )
        db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}", status_code=303)


@app.post("/admin/lessons/{lesson_id}/assets/link")
def add_link(
    lesson_id: int,
    title: str = Form(...),
    url: str = Form(...),
) -> RedirectResponse:
    with connect() as db:
        db.execute(
            "INSERT INTO assets (lesson_id, kind, title, url) VALUES (?, ?, ?, ?)",
            (lesson_id, "link", title, url),
        )
        db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}", status_code=303)


@app.post("/admin/lessons/{lesson_id}/questions")
def add_question(
    lesson_id: int,
    question_type: str = Form(...),
    prompt: str = Form(...),
    option_a: str = Form(""),
    option_b: str = Form(""),
    option_c: str = Form(""),
    option_d: str = Form(""),
    answer: str = Form(""),
    explanation: str = Form(""),
    reveal_timing: str = Form("after_submit"),
) -> RedirectResponse:
    options = "\n".join(
        option for option in [option_a, option_b, option_c, option_d] if option.strip()
    )
    with connect() as db:
        db.execute(
            """
            INSERT INTO questions (
                lesson_id, question_type, prompt, options_json, answer, explanation, reveal_timing
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (lesson_id, question_type, prompt, options, answer, explanation, reveal_timing),
        )
        db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}", status_code=303)


@app.post("/admin/lessons/{lesson_id}/questions/generate")
def generate_questions(
    lesson_id: int,
    multiple_choice_count: int = Form(3),
    short_answer_count: int = Form(2),
    long_answer_count: int = Form(1),
) -> RedirectResponse:
    with connect() as db:
        lesson = get_lesson(db, lesson_id)
        lesson_text = lesson["published_text"] or lesson["draft_text"]
        questions = generate_questions_for_lesson(
            lesson["title"],
            lesson_text,
            multiple_choice_count,
            short_answer_count,
            long_answer_count,
        )
        for question in questions:
            db.execute(
                """
                INSERT INTO questions (
                    lesson_id, question_type, prompt, options_json, answer, explanation, reveal_timing
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lesson_id,
                    question["question_type"],
                    question["prompt"],
                    "\n".join(question["options"]),
                    question["answer"],
                    question["explanation"],
                    "after_submit",
                ),
            )
        db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}", status_code=303)


@app.get("/preview", response_class=HTMLResponse)
def preview(request: Request) -> HTMLResponse:
    with connect() as db:
        lessons = db.execute(
            "SELECT * FROM lessons WHERE status = 'published' ORDER BY lesson_no"
        ).fetchall()
        if not lessons:
            lessons = list_lessons(db)
    return templates.TemplateResponse(
        "preview.html", {"request": request, "lessons": lessons}
    )


@app.get("/preview/lessons/{lesson_id}", response_class=HTMLResponse)
def preview_lesson(request: Request, lesson_id: int) -> HTMLResponse:
    with connect() as db:
        lesson = get_lesson(db, lesson_id)
        assets = list_assets(db, lesson_id)
        questions = list_questions(db, lesson_id)
    return templates.TemplateResponse(
        "lesson_preview.html",
        {
            "request": request,
            "lesson": lesson,
            "assets": assets,
            "questions": questions,
        },
    )
