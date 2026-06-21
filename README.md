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
- Student Lessons: http://127.0.0.1:8000/lessons

학생용 주소는 `/lessons`, 강사용 주소는 `/admin220380`입니다.
레슨 본문은 Markdown으로 작성할 수 있으며, 표와 코드블럭을 지원합니다.

예:

````markdown
## 옴의 법칙

```python
v = 220
r = 110
print(v / r)
```
````

## OCR

환경변수 `TESSERACT_CMD`가 있으면 해당 경로를 사용합니다.

예:

```powershell
$env:TESSERACT_CMD='G:\Codex\tools\tesseract\Tesseract-OCR\tesseract.exe'
```

강사용 주소는 환경변수 `ADMIN_PREFIX`로 바꿀 수 있습니다.

## 업로드 파일 저장

이미지는 `APP_DATA_DIR/uploads`에 저장되고 `/uploads/...` 공개 URL로 제공됩니다.
로컬에서 G 드라이브에 저장하려면 실행 전에 `APP_DATA_DIR`를 지정합니다.

```powershell
$env:APP_DATA_DIR='G:\Codex\learning_app_data'
```

Coolify에서는 compose volume이 `/data`에 연결되므로 업로드 파일은 컨테이너 재배포 후에도 유지됩니다.
