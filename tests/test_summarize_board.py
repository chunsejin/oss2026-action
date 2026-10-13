import argparse
import unittest
from unittest.mock import patch
from urllib.error import URLError

from summarize_board import (
    BOARD_URL, BoardRedirectHandler, extract_content, generate_report,
    main, Notice, parse_notices, positive_int, summarize,
)


class BoardSummaryTests(unittest.TestCase):
    def test_notice_links_dates_duplicates_and_limit(self):
        page = """
        <a href="https://example.com/?mode=view">외부 링크</a>
        <table><tr><td><a href="?mode=view&amp;board_seq=1">장학 신청</a></td>
        <td>2026.10.13</td></tr>
        <tr><td><a href="?mode=view&amp;board_seq=1&amp;page=2">중복</a></td></tr>
        <tr><td><a href="?mode=view&amp;board_seq=2">수강 안내</a></td></tr></table>
        """
        notices = parse_notices(page, 10)
        self.assertEqual([notice.title for notice in notices], ["장학 신청", "수강 안내"])
        self.assertEqual(notices[0].date, "2026-10-13")
        self.assertEqual(len(parse_notices(page, 1)), 1)

    def test_empty_or_changed_board_fails(self):
        with self.assertRaises(ValueError):
            parse_notices("<html>서비스 점검 중</html>", 10)

    def test_extract_content_excludes_navigation_and_scripts(self):
        page = """<nav>메뉴</nav><div class="board-view-contents">
        <p>장학금 안내</p><p>신청 기간: 10월 20일까지<br>대상: 재학생</p>
        <script>malicious()</script></div><footer>푸터</footer>"""
        text = extract_content(page)
        self.assertNotIn("메뉴", text)
        self.assertNotIn("malicious", text)
        self.assertEqual(summarize(text), ["장학금 안내", "신청 기간: 10월 20일까지", "대상: 재학생"])

    def test_content_fallback_and_missing_body(self):
        self.assertEqual(extract_content('<table><td colspan="3">본문</td></table>'), "본문")
        self.assertEqual(extract_content("<html><nav>메뉴</nav></html>"), "")

    def test_summary_prioritizes_important_lines_and_limits_length(self):
        points = summarize("소개\n일반 문장\n신청 마감: 내일\n대상: 학생\n장소: 강의실")
        self.assertEqual(points, ["소개", "신청 마감: 내일", "대상: 학생"])
        self.assertEqual(len(summarize("가" * 300)[0]), 240)
        self.assertEqual(summarize(""), [])

    def test_report_escapes_untrusted_markup(self):
        report = generate_report(
            [Notice('<img src=x> [제목]', BOARD_URL + "&mode=view&board_seq=1")],
            lambda url: '<div class="board-view-contents">&lt;script&gt;본문&lt;/script&gt;</div>',
        )
        self.assertNotIn("<img", report)
        self.assertNotIn("<script>", report)
        self.assertIn(r"\[제목\]", report)
        self.assertIn("KST", report)

    def test_detail_failure_keeps_notice_link(self):
        def fail(url):
            raise URLError("offline")
        report = generate_report([Notice("공지", BOARD_URL)], fail)
        self.assertIn("본문을 가져오지 못했습니다", report)
        self.assertIn(BOARD_URL, report)

    def test_external_redirect_is_rejected(self):
        with self.assertRaises(URLError):
            BoardRedirectHandler().redirect_request(None, None, 302, "", {}, "https://example.com/")

    def test_invalid_limit(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")

    def test_list_failure_returns_nonzero(self):
        with patch("sys.argv", ["summarize_board.py"]), patch("summarize_board.fetch_page", side_effect=URLError("offline")):
            self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()
