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
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback_questions(title)

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = build_prompt(
        title,
        lesson_text,
        multiple_choice_count,
        short_answer_count,
        long_answer_count,
    )
    payload = {
        "model": model,
        "input": prompt,
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
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "question_type": {
                                        "type": "string",
                                        "enum": [
                                            "multiple_choice",
                                            "short_answer",
                                            "long_answer",
                                        ],
                                    },
                                    "prompt": {"type": "string"},
                                    "options": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
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
                            },
                        }
                    },
                    "required": ["questions"],
                },
            }
        },
    }
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
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error: {exc.code} {detail}") from exc

    content = extract_response_text(raw)
    parsed = json.loads(content)
    return normalize_questions(parsed.get("questions", []))


def build_prompt(
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
