# Transformer Learning App MVP

초보자용 전기공학/변압기 수업을 위한 작은 FastAPI MVP입니다.

## 포함된 첫 기능

- 강사용 Admin
  - 레슨 목록/본문 편집
  - OCR 적용 버튼
  - 이미지 삽입
  - YouTube/웹 링크 삽입
  - 문제 만들기: 4지선다, 짧은 답, 긴 답
- 학생용 Preview
  - 강좌/레슨 보기
  - 공개 본문, 이미지, 링크, 문제 표시

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

브라우저:

- Admin: http://127.0.0.1:8000/admin220380
- Student Preview: http://127.0.0.1:8000/preview

## OCR

환경변수 `TESSERACT_CMD`가 있으면 해당 경로를 사용합니다.

예:

```powershell
$env:TESSERACT_CMD='G:\Codex\tools\tesseract\Tesseract-OCR\tesseract.exe'
```

강사용 주소는 환경변수 `ADMIN_PREFIX`로 바꿀 수 있습니다.
