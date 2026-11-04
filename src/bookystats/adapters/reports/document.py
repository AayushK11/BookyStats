from __future__ import annotations

from typing import BinaryIO

from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Paragraph

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.theme import Theme, paint
from bookystats.domain.reader_report import ReaderReport


class Heading(Paragraph):
    def __init__(
        self,
        document: ReportDocument,
        theme: Theme,
        text: str,
        name: C.RptText,
        level: int,
        listed: bool = C.FALSE,
    ) -> None:
        self.document = document
        self.label = text
        self.level = level
        self.listed = listed
        self.markup_text = theme.markup(text)
        super().__init__(self.markup_text, theme.styles[name])

    def split(self, availWidth: float, availHeight: float) -> list[Flowable]:
        return []

    def draw(self) -> None:
        super().draw()
        self.document.enter(self)


class ReportDocument(BaseDocTemplate):
    def __init__(self, stream: BinaryIO, report: ReaderReport, theme: Theme) -> None:
        super().__init__(
            stream,
            pagesize=C.PDF_PAGE_SIZE,
            leftMargin=C.PDF_MARGIN,
            rightMargin=C.PDF_MARGIN,
            topMargin=C.RPT_MARGIN_TOP,
            bottomMargin=C.RPT_MARGIN_BOTTOM,
            title=report.cover.title,
            author=S.PDF_AUTHOR,
            subject=report.cover.subtitle,
            creator=S.PDF_AUTHOR,
            keywords=[S.RPT_PDF_KEYWORDS],
            lang=S.RPT_PDF_LANGUAGE,
            displayDocTitle=C.ONE,
            pageCompression=C.ONE,
            invariant=C.ONE,
            allowSplitting=C.ONE,
        )
        self.theme = theme
        self.report = report
        self.bookmarks = C.ZERO
        self.page_title = S.EMPTY
        self.page_head = S.EMPTY
        self.cover_text = self._cover_text()
        stack = sum(self._stack_height(paragraph) for paragraph in self.cover_text)
        self.band = max(C.RPT_COVER_BAND, stack + C.TWO * C.RPT_COVER_PAD)
        self.addPageTemplates(
            [
                PageTemplate(
                    id=S.RPT_TEMPLATE_COVER,
                    frames=[self._cover_frame()],
                    onPage=self.paint_cover,
                    pagesize=C.PDF_PAGE_SIZE,
                ),
                PageTemplate(
                    id=S.RPT_TEMPLATE_BODY,
                    frames=[self._body_frame()],
                    onPage=self.begin_page,
                    onPageEnd=self.finish_page,
                    pagesize=C.PDF_PAGE_SIZE,
                ),
            ]
        )

    @property
    def frame_width(self) -> float:
        return C.PDF_PAGE_WIDTH - C.TWO * C.PDF_MARGIN

    @property
    def frame_height(self) -> float:
        return C.PDF_PAGE_HEIGHT - C.RPT_MARGIN_TOP - C.RPT_MARGIN_BOTTOM

    def beforeDocument(self) -> None:
        self.bookmarks = C.ZERO
        self.page_title = S.EMPTY
        self.page_head = S.EMPTY

    def enter(self, heading: Heading) -> None:
        canvas = self.canv
        key = S.PDF_BOOKMARK.format(index=self.bookmarks)
        self.bookmarks += C.ONE
        canvas.bookmarkPage(key)
        canvas.addOutlineEntry(heading.label, key, heading.level, closed=C.FALSE)
        if not heading.listed:
            return
        self.notify(S.PDF_TOC_ENTRY, (heading.level, heading.markup_text, self.page, key))
        self.page_title = heading.label
        _, bottom = canvas.absolutePosition(C.ZERO, C.ZERO)
        near_top = bottom + heading.height >= (
            C.PDF_PAGE_HEIGHT - C.RPT_MARGIN_TOP - C.RPT_HEAD_TOP_ZONE
        )
        if near_top or not self.page_head:
            self.page_head = heading.label

    def paint_cover(self, canvas: Canvas, document: BaseDocTemplate) -> None:
        top = C.PDF_PAGE_HEIGHT
        canvas.saveState()
        self._paper(canvas)
        canvas.setFillColor(paint(S.RPT_HEX_BAND))
        canvas.rect(C.ZERO, top - self.band, C.PDF_PAGE_WIDTH, self.band, stroke=C.ZERO, fill=C.ONE)
        canvas.setFillColor(paint(S.RPT_HEX_AMBER))
        canvas.rect(
            C.ZERO,
            top - self.band - C.RPT_COVER_STRIPE,
            C.PDF_PAGE_WIDTH,
            C.RPT_COVER_STRIPE,
            stroke=C.ZERO,
            fill=C.ONE,
        )
        cursor = top - self.band + C.RPT_COVER_PAD
        cursor += sum(self._stack_height(paragraph) for paragraph in self.cover_text)
        for paragraph in self.cover_text:
            _, height = paragraph.wrap(self.frame_width, top)
            cursor -= height
            paragraph.drawOn(canvas, C.PDF_MARGIN, cursor)
            cursor -= paragraph.style.spaceAfter
        self._bookmark(canvas)
        canvas.restoreState()

    def begin_page(self, canvas: Canvas, document: BaseDocTemplate) -> None:
        self.page_head = self.page_title
        canvas.saveState()
        self._paper(canvas)
        self._bookmark(canvas)
        canvas.restoreState()

    def _paper(self, canvas: Canvas) -> None:
        canvas.setFillColor(paint(S.RPT_HEX_PAPER))
        canvas.rect(C.ZERO, C.ZERO, C.PDF_PAGE_WIDTH, C.PDF_PAGE_HEIGHT, stroke=C.ZERO, fill=C.ONE)

    def _bookmark(self, canvas: Canvas) -> None:
        left = C.PDF_PAGE_WIDTH - C.PDF_MARGIN - C.RPT_BOOKMARK_WIDTH
        right = left + C.RPT_BOOKMARK_WIDTH
        bottom = C.PDF_PAGE_HEIGHT - C.RPT_BOOKMARK_LENGTH
        path = canvas.beginPath()
        path.moveTo(left, C.PDF_PAGE_HEIGHT)
        path.lineTo(right, C.PDF_PAGE_HEIGHT)
        path.lineTo(right, bottom)
        path.lineTo((left + right) / C.TWO, bottom + C.RPT_BOOKMARK_NOTCH)
        path.lineTo(left, bottom)
        path.close()
        canvas.setFillColor(paint(S.RPT_HEX_AMBER))
        canvas.drawPath(path, stroke=C.ZERO, fill=C.ONE)

    def finish_page(self, canvas: Canvas, document: BaseDocTemplate) -> None:
        left = float(C.PDF_MARGIN)
        right = C.PDF_PAGE_WIDTH - C.PDF_MARGIN
        head_y = C.PDF_PAGE_HEIGHT - C.RPT_HEADER_DROP
        foot_y = float(C.RPT_FOOTER_RISE)
        canvas.saveState()
        canvas.setStrokeColor(paint(S.RPT_HEX_RULE))
        canvas.setLineWidth(C.RPT_HAIRLINE)
        canvas.line(left, head_y - C.RPT_RUNNING_RULE_GAP, right, head_y - C.RPT_RUNNING_RULE_GAP)
        rule_y = foot_y + C.RPT_RUNNING_SIZE + C.RPT_RUNNING_RULE_GAP
        canvas.line(left, rule_y, right, rule_y)
        canvas.setFillColor(paint(S.RPT_HEX_MUTED))
        canvas.setFont(S.PDF_FONT, C.RPT_RUNNING_SIZE)
        self._running(canvas, head_y, self.page_head, self.report.cover.title)
        footer = S.RPT_FOOTER.format(
            eyebrow=self.report.cover.eyebrow, as_of=self.report.cover.as_of
        )
        self._running(canvas, foot_y, footer, S.RPT_PAGE_NUMBER.format(page=self.page))
        canvas.restoreState()

    def _running(self, canvas: Canvas, baseline: float, left: str, right: str) -> None:
        left_text = self.theme.plain(left)
        right_text = self.theme.plain(right)
        room = self.frame_width - C.RPT_RUNNING_SIZE * C.TWO
        taken = self.theme.sized(left_text, C.RPT_RUNNING_SIZE)
        taken += self.theme.sized(right_text, C.RPT_RUNNING_SIZE)
        canvas.drawString(C.PDF_MARGIN, baseline, left_text)
        if taken <= room:
            canvas.drawRightString(C.PDF_PAGE_WIDTH - C.PDF_MARGIN, baseline, right_text)

    def _cover_text(self) -> list[Paragraph]:
        cover = self.report.cover
        pieces = (
            (cover.eyebrow, C.RptText.COVER_EYEBROW),
            (cover.title, C.RptText.COVER_TITLE),
            (cover.subtitle, C.RptText.COVER_SUBTITLE),
            (cover.as_of, C.RptText.COVER_ASOF),
        )
        paragraphs = [self.theme.para(text, name) for text, name in pieces if text.strip()]
        return paragraphs

    def _stack_height(self, paragraph: Paragraph) -> float:
        _, height = paragraph.wrap(self.frame_width, C.PDF_PAGE_HEIGHT)
        return float(height + paragraph.style.spaceAfter)

    def _cover_frame(self) -> Frame:
        below = C.PDF_PAGE_HEIGHT - self.band - C.RPT_COVER_STRIPE - C.RPT_COVER_GAP
        return Frame(
            C.PDF_MARGIN,
            C.RPT_MARGIN_BOTTOM,
            self.frame_width,
            below - C.RPT_MARGIN_BOTTOM,
            leftPadding=C.ZERO,
            rightPadding=C.ZERO,
            topPadding=C.ZERO,
            bottomPadding=C.ZERO,
            id=S.RPT_TEMPLATE_COVER,
        )

    def _body_frame(self) -> Frame:
        return Frame(
            C.PDF_MARGIN,
            C.RPT_MARGIN_BOTTOM,
            self.frame_width,
            self.frame_height,
            leftPadding=C.ZERO,
            rightPadding=C.ZERO,
            topPadding=C.ZERO,
            bottomPadding=C.ZERO,
            id=S.RPT_TEMPLATE_BODY,
        )
