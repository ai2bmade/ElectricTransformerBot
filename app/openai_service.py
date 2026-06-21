from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def generate_questions_for_lesson(
    title: str,
    lesson_text: str,
    multiple_choice_count: int = 3,
    short_answer_count: int = 2,
    long_answer_count: int = 1,
) -> list[dict]:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return fallback_questions(title)

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": build_question_prompt(
            title,
            lesson_text,
            multiple_choice_count,
            short_answer_count,
            long_answer_count,
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "lesson_questions",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "questions": {
                            "type": "array",
                            "items": question_schema(),
                        }
                    },
                    "required": ["questions"],
                },
            }
        },
    }
    parsed = json.loads(extract_response_text(call_openai(payload)))
    return normalize_questions(parsed.get("questions", []))


def generate_lesson_guide(title: str, lesson_text: str) -> dict:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return fallback_lesson_guide(title)

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": build_guide_prompt(title, lesson_text),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "lesson_guide",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "terms_markdown": {"type": "string"},
                        "faq_markdown": {"type": "string"},
                        "anticipated_questions_markdown": {"type": "string"},
                        "teacher_review_notes": {"type": "string"},
                    },
                    "required": [
                        "terms_markdown",
                        "faq_markdown",
                        "anticipated_questions_markdown",
                        "teacher_review_notes",
                    ],
                },
            }
        },
    }
    parsed = json.loads(extract_response_text(call_openai(payload)))
    return {
        "terms_markdown": parsed.get("terms_markdown", "").strip(),
        "faq_markdown": parsed.get("faq_markdown", "").strip(),
        "anticipated_questions_markdown": parsed.get(
            "anticipated_questions_markdown", ""
        ).strip(),
        "teacher_review_notes": parsed.get("teacher_review_notes", "").strip(),
    }


def answer_student_question(
    title: str,
    lesson_text: str,
    guide: dict,
    question: str,
) -> str:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return (
            "OPENAI_API_KEY가 아직 설정되지 않았습니다. "
            "이 답변 기능은 강사가 검수한 용어/FAQ/예상질문 자료와 레슨 본문을 함께 참고하도록 설계되어 있습니다."
        )

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "input": build_student_answer_prompt(title, lesson_text, guide, question),
    }
    return extract_response_text(call_openai(payload)).strip()


def call_openai(payload: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error: {exc.code} {detail}") from exc


def question_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "question_type": {
                "type": "string",
                "enum": ["multiple_choice", "short_answer", "long_answer"],
            },
            "prompt": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": [
            "question_type",
            "prompt",
            "options",
            "answer",
            "explanation",
        ],
    }


def build_question_prompt(
    title: str,
    lesson_text: str,
    multiple_choice_count: int,
    short_answer_count: int,
    long_answer_count: int,
) -> str:
    return f"""
너는 전기공학 기초와 변압기 수업을 돕는 문제 출제자다.
아래 레슨 내용만 근거로 학생용 학습 문제를 만들어라.

레슨 제목:
{title}

레슨 내용:
{lesson_text[:12000]}

출제 수량:
- 4지선다: {multiple_choice_count}개
- 짧은 답: {short_answer_count}개
- 긴 답: {long_answer_count}개

규칙:
- 완전 초보자도 이해할 수 있는 표현을 사용한다.
- 4지선다는 options를 정확히 4개 만든다.
- 짧은 답과 긴 답은 options를 빈 배열로 둔다.
- answer에는 정답 또는 모범답안을 쓴다.
- explanation에는 왜 그 답인지 짧게 설명한다.
- 레슨 내용 밖의 지식은 억지로 끌어오지 않는다.
""".strip()


def build_guide_prompt(title: str, lesson_text: str) -> str:
    return f"""
너는 전기공학 기초/변압기 수업을 준비하는 강사용 AI 조교다.
아래 레슨을 읽고, 학생 질문에 멍청하게 답하지 않도록 사전 지식 자료를 만든다.

레슨 제목:
{title}

레슨 내용:
{lesson_text[:14000]}

작성할 것:
1. terms_markdown: 핵심 용어 표. 열은 용어, 쉬운 설명, 학생이 헷갈릴 점.
2. faq_markdown: 학생이 바로 물어볼 만한 FAQ와 답변.
3. anticipated_questions_markdown: 잠재 질문 리스트와 근거 있는 답변. 가능하면 "근거: 레슨의 어떤 부분"을 붙인다.
4. teacher_review_notes: 강사가 검수할 때 봐야 할 주의점.

규칙:
- Markdown으로 작성한다.
- 레슨 밖 지식은 보충 수준으로만 쓰고, 추측이면 추측이라고 표시한다.
- 정답/퀴즈 해설은 학생에게 너무 빨리 노출될 수 있으니 주의 문구를 남긴다.
""".strip()


def build_student_answer_prompt(
    title: str, lesson_text: str, guide: dict, question: str
) -> str:
    return f"""
너는 학생용 전기공학 학습 도우미다.
반드시 강사가 준비/검수할 수 있는 자료와 레슨 내용을 우선 근거로 답한다.
모르면 모른다고 말하고, 레슨 어디를 다시 보면 좋은지 안내한다.
관리자 경로, 원본 파일 경로, OCR 품질 문제 같은 내부 정보는 말하지 않는다.

레슨 제목:
{title}

레슨 본문:
{lesson_text[:10000]}

강사용 사전 용어 자료:
{guide.get("terms_markdown", "")[:5000]}

강사용 FAQ:
{guide.get("faq_markdown", "")[:5000]}

예상 질문과 답:
{guide.get("anticipated_questions_markdown", "")[:7000]}

학생 질문:
{question}

답변 형식:
- 먼저 쉬운 답을 3~6문장으로 설명한다.
- 필요하면 짧은 예시를 든다.
- 마지막에 "근거"를 한 줄로 적는다.
""".strip()


def extract_response_text(response: dict) -> str:
    if response.get("output_text"):
        return response["output_text"]
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    raise RuntimeError("OpenAI response did not include text output")


def normalize_questions(questions: list[dict]) -> list[dict]:
    normalized = []
    for question in questions:
        question_type = question.get("question_type", "short_answer")
        options = question.get("options") or []
        if question_type == "multiple_choice":
            options = (options + ["", "", "", ""])[:4]
        else:
            options = []
        normalized.append(
            {
                "question_type": question_type,
                "prompt": question.get("prompt", "").strip(),
                "options": [str(option).strip() for option in options],
                "answer": question.get("answer", "").strip(),
                "explanation": question.get("explanation", "").strip(),
            }
        )
    return [question for question in normalized if question["prompt"]]


def fallback_questions(title: str) -> list[dict]:
    return [
        {
            "question_type": "multiple_choice",
            "prompt": f"{title}에서 가장 핵심이 되는 개념은 무엇인가요?",
            "options": ["전압", "전류", "저항", "레슨 본문을 보고 선택"],
            "answer": "레슨 본문을 보고 선택",
            "explanation": "OPENAI_API_KEY가 없어서 샘플 문제가 생성되었습니다.",
        },
        {
            "question_type": "short_answer",
            "prompt": "이 레슨에서 처음 배운 용어 하나를 고르고, 쉬운 말로 설명해보세요.",
            "options": [],
            "answer": "본문의 핵심 용어를 학생이 자기 말로 설명하면 됩니다.",
            "explanation": "짧은 답 문제의 예시입니다.",
        },
        {
            "question_type": "long_answer",
            "prompt": "이 레슨의 내용을 실제 전기 설비나 변압기와 연결해서 설명해보세요.",
            "options": [],
            "answer": "개념, 이유, 실제 연결 사례가 포함되면 좋은 답입니다.",
            "explanation": "긴 답 문제의 예시입니다.",
        },
    ]


def fallback_lesson_guide(title: str) -> dict:
    return {
        "terms_markdown": (
            "| 용어 | 쉬운 설명 | 학생이 헷갈릴 점 |\n"
            "|---|---|---|\n"
            f"| {title} | 이 레슨의 핵심 개념 | OPENAI_API_KEY 설정 후 실제 용어 분석을 생성하세요 |\n"
        ),
        "faq_markdown": (
            "### FAQ 샘플\n\n"
            "- **Q. 이 레슨에서 가장 먼저 이해해야 할 것은 무엇인가요?**\n"
            "  - A. 레슨 본문에서 반복되는 핵심 용어와 공식의 의미입니다.\n"
        ),
        "anticipated_questions_markdown": (
            "### 예상 질문 샘플\n\n"
            "- **질문:** 이 개념이 변압기와 어떻게 연결되나요?\n"
            "  - **답:** 레슨 본문을 기준으로 전기 기초 개념이 변압기 원리로 이어지는 지점을 설명합니다.\n"
        ),
        "teacher_review_notes": "OPENAI_API_KEY가 없어 샘플 가이드가 저장되었습니다.",
    }
