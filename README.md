# oss2026-action

동아대학교 컴퓨터공학과 [공지 게시판](https://computer.donga.ac.kr/computer/CMS/Board/Board.do?robot=Y&mCode=MN044)의 최근 공지를 Python으로 수집하고 Markdown으로 발췌 요약합니다.

## 실행

Python 3.12 이상에서 저장소 루트를 작업 디렉터리로 사용합니다.

```sh
python -m pip install -r requirements.txt
python summarize_board.py --limit 10 --output board-summary.md
```

- 게시판 첫 페이지의 표시 순서(상단 고정 공지 포함)대로 최대 10개를 수집합니다. `--limit`으로 수를 줄일 수 있으며, 다음 페이지까지 탐색하지 않습니다.
- 제목, 게시일(목록에 표시된 경우), 원문 링크와 본문 요약을 저장합니다.
- 외부 AI 서비스나 API 키 없이 본문 첫 문장과 신청·접수·마감·기간·장소·대상·제출·장학·문의 등 주요 키워드가 있는 문장을 최대 3개, 각 240자까지 발췌합니다. 중요도를 판정하거나 사실을 추론하는 AI 요약은 아닙니다.
- 이미지, 첨부파일, JavaScript로만 표시되는 내용은 분석하지 않습니다. 일정과 신청 조건은 반드시 원문에서 확인하세요.
- 목록 수집 실패 또는 게시판 구조 변경으로 게시글을 찾을 수 없으면 실패 상태로 종료합니다. 개별 본문 수집·추출 실패는 요약에 안내하고 표준 오류에 기록하며, 나머지 게시글은 계속 처리합니다.

## 매일 오전 9시 자동 실행

`.github/workflows/board-summary.yml`은 **한국 시간(Asia/Seoul) 매일 오전 9시**에 실행되도록 예약되어 있습니다. GitHub Actions의 cron은 UTC 기준이므로 `0 0 * * *`를 사용합니다.

1. 기본 브랜치에 워크플로가 반영되어 있고 저장소의 Actions가 활성화되어 있어야 합니다.
2. **Actions → Daily board summary → Run workflow**에서 수동 실행도 가능합니다.
3. 실행 결과 페이지의 **Summary**에서 요약을 읽거나 **Artifacts → board-summary**에서 Markdown 파일을 내려받습니다. 파일 보관 기간은 14일이며 저장소에 자동 커밋하지 않습니다.

GitHub의 예약 작업은 부하에 따라 지연될 수 있어 정확한 9시 실행을 보장하지 않습니다. 비활성 공개 저장소에서는 예약 작업이 중지될 수 있습니다.

## 테스트 및 제한

```sh
python -m unittest discover -s tests -v
```

테스트는 네트워크 없이 HTML 예제로 링크·날짜·중복 처리, 본문 추출, 요약, 실패 처리 및 출력 이스케이프를 검증합니다. 개발 환경에서 대상 도메인의 DNS 조회가 실패하여 실제 게시판 HTML과의 호환성은 확인하지 못했습니다. 실제 실행에서 추출 실패가 발생하면 `summarize_board.py`의 게시글 링크 처리와 `CONTENT_SELECTORS`를 현재 게시판 구조에 맞게 확인하세요.