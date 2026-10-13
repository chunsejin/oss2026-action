"""동아대학교 컴퓨터공학과 게시판의 최근 공지를 발췌 요약합니다."""

import argparse
from dataclasses import dataclass
from datetime import datetime
import html
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


BOARD_URL = "https://computer.donga.ac.kr/computer/CMS/Board/Board.do?robot=Y&mCode=MN044"
IMPORTANT_WORDS = ("신청", "접수", "마감", "기간", "일시", "장소", "대상", "제출", "장학", "필수", "문의")
CONTENT_SELECTORS = (
    ".board-view-contents", ".board-view-content", ".board_view_con",
    ".board_view_content", ".view_content", ".view_cont", ".view-con",
    ".board_view .cont", ".board-view .contents", "#boardContent",
)


@dataclass
class Notice:
    title: str
    url: str
    date: str = ""


def same_board(url):
    target, source = urlsplit(url), urlsplit(BOARD_URL)
    return (
        target.scheme == source.scheme
        and target.netloc == source.netloc
        and target.path == source.path
    )


class BoardRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not same_board(newurl):
            raise URLError("게시판 외부로의 리디렉션을 거부했습니다.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url):
    if not same_board(url):
        raise ValueError("허용되지 않은 게시판 주소입니다.")
    request = Request(url, headers={"User-Agent": "DongaBoardSummary/1.0"})
    opener = build_opener(BoardRedirectHandler())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise ValueError("게시판 응답이 너무 큽니다.")
                charset = response.headers.get_content_charset()
                if charset:
                    return raw.decode(charset)
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    return raw.decode("euc-kr")
        except (HTTPError, URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def parse_notices(page, limit):
    soup = BeautifulSoup(page, "html.parser")
    notices, seen = [], set()
    for anchor in soup.select("a[href]"):
        url = urljoin(BOARD_URL, anchor["href"])
        if not same_board(url):
            continue
        query = parse_qs(urlsplit(url).query)
        if query.get("mode", [""])[0].lower() != "view":
            continue
        title = " ".join(anchor.stripped_strings) or anchor.get("title", "").strip()
        if not title:
            continue
        # 페이지 번호 등 부가 쿼리가 달라도 같은 게시글은 한 번만 수집합니다.
        identity = query.get("board_seq", query.get("boardSeq", [url]))[0]
        if identity in seen:
            continue
        seen.add(identity)
        row = anchor.find_parent("tr") or anchor.find_parent("li")
        date = ""
        if row:
            match = re.search(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", row.get_text(" ", strip=True))
            if match:
                date = f"{match[1]}-{int(match[2]):02d}-{int(match[3]):02d}"
        parts = urlsplit(url)
        safe_url = urlunsplit((
            parts.scheme, parts.netloc, quote(parts.path, safe="/%"),
            quote(parts.query, safe="=&%"), "",
        ))
        notices.append(Notice(title, safe_url, date))
        if len(notices) >= limit:
            break
    if not notices:
        raise ValueError("게시글 링크를 찾지 못했습니다. 게시판 구조 또는 응답 내용을 확인하세요.")
    return notices


def extract_content(page):
    soup = BeautifulSoup(page, "html.parser")
    for element in soup.select("script, style, noscript"):
        element.decompose()
    content = next((soup.select_one(selector) for selector in CONTENT_SELECTORS
                    if soup.select_one(selector) is not None), None)
    if content is None:
        # 일부 CMS 템플릿은 본문을 표의 병합 셀에 넣습니다.
        candidates = soup.select("td[colspan]")
        content = max(candidates, key=lambda cell: len(cell.get_text(strip=True)), default=None)
    if content is None:
        return ""
    for br in content.find_all("br"):
        br.replace_with("\n")
    return content.get_text("\n", strip=True)


def summarize(text, max_points=3):
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    lines = list(dict.fromkeys(lines))
    important = [line for line in lines if any(word in line for word in IMPORTANT_WORDS)]
    chosen = list(dict.fromkeys(lines[:1] + important + lines))[:max_points]
    return [line if len(line) <= 240 else line[:239] + "…" for line in chosen]


def markdown_text(text):
    text = html.escape(" ".join(text.split()), quote=False)
    return re.sub(r"([\\`*_\[\]{}()#+.!|>-])", r"\\\1", text)


def generate_report(notices, fetcher=fetch_page):
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M KST")
    report = [
        "# 동아대학교 컴퓨터공학과 주요 공지 요약", "",
        f"생성 시각: {now}", "", f"[게시판 원문](<{BOARD_URL}>)", "",
        "> 게시판 첫 페이지의 공지를 표시 순서대로 발췌합니다. "
        "신청·마감·기간·장소·대상 등의 문장을 우선하며, 정확한 내용과 첨부파일은 원문을 확인하세요.", "",
    ]
    for index, notice in enumerate(notices, 1):
        report += [f"## {index}. {markdown_text(notice.title)}", ""]
        if notice.date:
            report += [f"- 게시일: {notice.date}"]
        report += [f"- 원문: [게시글 보기](<{notice.url}>)"]
        try:
            content = extract_content(fetcher(notice.url))
            points = summarize(content)
            if not points:
                points = ["본문을 추출하지 못했습니다. 이미지·첨부파일 또는 원문을 확인하세요."]
                print(f"본문 추출 실패: {notice.url}", file=sys.stderr)
        except (URLError, TimeoutError, ValueError, LookupError, OSError) as exc:
            print(f"게시글 수집 실패: {notice.url}: {exc}", file=sys.stderr)
            points = ["본문을 가져오지 못했습니다. 원문을 확인하세요."]
        report += [f"- {markdown_text(point)}" for point in points]
        report += [""]
    return "\n".join(report)


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요.")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=positive_int, default=10, help="수집할 최대 게시글 수 (기본: 10)")
    parser.add_argument("--output", type=Path, default=Path("board-summary.md"), help="Markdown 저장 경로")
    args = parser.parse_args()
    try:
        notices = parse_notices(fetch_page(BOARD_URL), args.limit)
        report = generate_report(notices)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (URLError, TimeoutError, ValueError, LookupError, OSError) as exc:
        print(f"요약 생성 실패: {exc}", file=sys.stderr)
        return 1
    print(f"{len(notices)}개 공지 요약 저장: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
