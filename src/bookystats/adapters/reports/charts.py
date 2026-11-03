from __future__ import annotations

from typing import NamedTuple

from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.theme import Theme, paint
from bookystats.domain.reader_report import BarRow, CompareRow, SkylineBar


class LegendEntry(NamedTuple):
    shape: C.RptShape
    tone: C.RptTone
    label: str


def rating_x(value: float, width: float) -> float:
    clamped = min(max(value, C.RPT_RATING_MIN), C.RPT_RATING_MAX)
    inner = width - C.TWO * C.RPT_MARKER
    return (
        C.RPT_MARKER + (clamped - C.RPT_RATING_MIN) / (C.RPT_RATING_MAX - C.RPT_RATING_MIN) * inner
    )


def draw_span(
    canvas: Canvas,
    tone: C.RptTone,
    sparse: bool,
    left: float,
    bottom: float,
    width: float,
    height: float,
) -> None:
    strong = paint(C.RPT_TONE_COLORS[tone])
    canvas.saveState()
    if sparse:
        canvas.setFillColor(paint(S.RPT_HEX_WHITE))
        canvas.setStrokeColor(strong)
        canvas.setLineWidth(C.RPT_OUTLINE)
        canvas.setDash(C.RPT_DASH_ON, C.RPT_DASH_OFF)
        canvas.rect(left, bottom, width, height, stroke=C.ONE, fill=C.ONE)
    else:
        canvas.setFillColor(strong)
        canvas.rect(left, bottom, width, height, stroke=C.ZERO, fill=C.ONE)
    canvas.restoreState()


def draw_hollow(canvas: Canvas, left: float, bottom: float, width: float, height: float) -> None:
    canvas.saveState()
    canvas.setStrokeColor(paint(S.RPT_HEX_GREY))
    canvas.setLineWidth(C.RPT_OUTLINE)
    canvas.setDash(C.RPT_DASH_ON, C.RPT_DASH_OFF)
    canvas.rect(left, bottom, width, height, stroke=C.ONE, fill=C.ZERO)
    canvas.restoreState()


def draw_marker(
    canvas: Canvas, shape: C.RptShape, x: float, y: float, tone: C.RptTone, hollow: bool
) -> None:
    strong = paint(C.RPT_TONE_COLORS[tone])
    canvas.saveState()
    canvas.setStrokeColor(strong)
    canvas.setLineWidth(C.RPT_OUTLINE)
    canvas.setFillColor(paint(S.RPT_HEX_WHITE) if hollow else strong)
    if shape is C.RptShape.CIRCLE:
        canvas.circle(x, y, C.RPT_MARKER, stroke=C.ONE, fill=C.ONE)
    else:
        side = C.RPT_MARKER * C.TWO
        canvas.rect(x - C.RPT_MARKER, y - C.RPT_MARKER, side, side, stroke=C.ONE, fill=C.ONE)
    canvas.restoreState()


def visible(length: float, value: float) -> float:
    return max(length, C.RPT_MIN_FILL) if value else float(C.ZERO)


def split_label(theme: Theme, text: str, limit: float) -> list[str] | None:
    lines: list[str] = []
    current = S.EMPTY
    for word in text.split():
        trial = current + S.SPACE + word if current else word
        if theme.sized(trial, C.RPT_COLUMN_SIZE) <= limit:
            current = trial
        elif current and theme.sized(word, C.RPT_COLUMN_SIZE) <= limit:
            lines.append(current)
            current = word
        else:
            return C.NONE
    if current:
        lines.append(current)
    return lines if len(lines) <= C.RPT_COLUMN_LINES else C.NONE


class Chart(Flowable):
    def __init__(self, height: float) -> None:
        super().__init__()
        self.chart_width = float(C.ZERO)
        self.chart_height = height

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self.chart_width = availWidth
        self.width = availWidth
        self.height = self.chart_height
        return availWidth, self.chart_height


class BarCell(Chart):
    def __init__(self, row: BarRow, style: C.RptBarStyle, maximum: float) -> None:
        super().__init__(C.RPT_BAR_HEIGHT)
        self.row = row
        self.style = style
        self.maximum = maximum

    def draw(self) -> None:
        canvas, width, height = self.canv, self.chart_width, self.chart_height
        value = self.row.value
        if value is C.NONE:
            draw_hollow(canvas, C.ZERO, C.ZERO, width, height)
            return
        canvas.setFillColor(paint(S.RPT_HEX_TRACK))
        canvas.roundRect(C.ZERO, C.ZERO, width, height, C.RPT_RADIUS, stroke=C.ZERO, fill=C.ONE)
        share = min(abs(value) / self.maximum, C.ONE)
        if self.style is C.RptBarStyle.DIVERGING:
            middle = width * C.RPT_HALF
            length = visible(share * middle, value)
            left = middle if value >= C.ZERO else middle - length
            if length:
                draw_span(canvas, self.row.tone, self.row.sparse, left, C.ZERO, length, height)
            canvas.saveState()
            canvas.setStrokeColor(paint(S.RPT_HEX_MUTED))
            canvas.setLineWidth(C.RPT_OUTLINE)
            canvas.line(middle, -C.RPT_AXIS_OVERSHOOT, middle, height + C.RPT_AXIS_OVERSHOOT)
            canvas.restoreState()
            return
        length = visible(share * width, value)
        if length:
            draw_span(canvas, self.row.tone, self.row.sparse, C.ZERO, C.ZERO, length, height)


class ColumnChart(Chart):
    def __init__(self, theme: Theme, rows: tuple[BarRow, ...], maximum: float) -> None:
        super().__init__(C.RPT_COLUMN_PLOT)
        self.theme = theme
        self.rows = rows
        self.maximum = maximum
        self.labels: list[list[str]] = []
        self.rotated = C.FALSE
        self.label_room = float(C.ZERO)

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        slot = availWidth / len(self.rows)
        texts = [self.theme.plain(row.label) for row in self.rows]
        wrapped = [split_label(self.theme, text, slot - C.RPT_COLUMN_GAP) for text in texts]
        self.rotated = any(lines is C.NONE for lines in wrapped)
        if self.rotated:
            self.labels = []
            longest = max(self.theme.sized(text, C.RPT_COLUMN_SIZE) for text in texts)
            self.label_room = longest + C.RPT_COLUMN_GAP * C.TWO
        else:
            self.labels = [lines or [] for lines in wrapped]
            deepest = max(len(lines) for lines in self.labels)
            self.label_room = deepest * C.RPT_COLUMN_LEADING + C.RPT_COLUMN_GAP
        self.chart_height = C.RPT_COLUMN_PLOT + C.RPT_COLUMN_VALUE_ROOM + self.label_room
        return super().wrap(availWidth, availHeight)

    def draw(self) -> None:
        canvas = self.canv
        slot = self.chart_width / len(self.rows)
        column = min(slot * C.RPT_COLUMN_FILL, C.RPT_COLUMN_MAX_WIDTH)
        base = self.label_room
        canvas.saveState()
        canvas.setStrokeColor(paint(S.RPT_HEX_RULE))
        canvas.setLineWidth(C.RPT_HAIRLINE)
        canvas.line(C.ZERO, base, self.chart_width, base)
        canvas.restoreState()
        for index, row in enumerate(self.rows):
            center = slot * (index + C.RPT_HALF)
            top = self._column(row, center - column * C.RPT_HALF, column, base)
            self._value(row, center, slot, top)
            self._label(index, center, base)

    def _column(self, row: BarRow, left: float, column: float, base: float) -> float:
        if row.value is C.NONE:
            stub = C.RPT_COLUMN_PLOT * C.RPT_COLUMN_STUB
            draw_hollow(self.canv, left, base, column, stub)
            return base + stub
        share = min(max(row.value / self.maximum, C.ZERO), C.ONE)
        height = visible(share * C.RPT_COLUMN_PLOT, row.value)
        if height:
            draw_span(self.canv, row.tone, row.sparse, left, base, column, height)
        return base + height

    def _value(self, row: BarRow, center: float, slot: float, top: float) -> None:
        text = self.theme.plain(row.shown)
        size = C.RPT_COLUMN_SIZE
        while size > C.RPT_COLUMN_VALUE_FLOOR and self.theme.sized(text, size) > slot:
            size -= C.RPT_HALF
        if not text or self.theme.sized(text, size) > slot:
            return
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(paint(S.RPT_HEX_INK))
        canvas.setFont(S.PDF_FONT_BOLD, size)
        canvas.drawCentredString(center, top + C.RPT_COLUMN_GAP, text)
        canvas.restoreState()

    def _label(self, index: int, center: float, base: float) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(paint(S.RPT_HEX_MUTED))
        canvas.setFont(S.PDF_FONT, C.RPT_COLUMN_SIZE)
        if self.rotated:
            canvas.translate(
                center + C.RPT_COLUMN_SIZE * C.RPT_BASELINE_SHIFT, base - C.RPT_COLUMN_GAP
            )
            canvas.rotate(-C.RPT_QUARTER_TURN)
            canvas.drawString(C.ZERO, C.ZERO, self.theme.plain(self.rows[index].label))
        else:
            for line, text in enumerate(self.labels[index], start=C.ONE):
                canvas.drawCentredString(center, base - line * C.RPT_COLUMN_LEADING + C.ONE, text)
        canvas.restoreState()


class Skyline(Chart):
    def __init__(self, bars: tuple[SkylineBar, ...]) -> None:
        super().__init__(C.RPT_SKYLINE_HEIGHT)
        self.bars = bars

    def draw(self) -> None:
        canvas = self.canv
        slot = self.chart_width / len(self.bars)
        gap = C.RPT_SKYLINE_GAP if slot >= C.RPT_SKYLINE_GAP_FROM else float(C.ZERO)
        width = slot - gap
        for index, bar in enumerate(self.bars):
            left = index * slot
            if bar.height is C.NONE:
                canvas.saveState()
                canvas.setStrokeColor(paint(S.RPT_HEX_GREY))
                canvas.setLineWidth(min(C.RPT_HAIRLINE, max(width, C.RPT_HAIRLINE)))
                canvas.rect(
                    left,
                    C.ZERO,
                    width,
                    self.chart_height * C.RPT_SKYLINE_STUB,
                    stroke=C.ONE,
                    fill=C.ZERO,
                )
                canvas.restoreState()
            else:
                draw_span(
                    canvas,
                    bar.tone,
                    C.FALSE,
                    left,
                    C.ZERO,
                    width,
                    max(bar.height * self.chart_height, C.RPT_MIN_FILL),
                )
        canvas.saveState()
        canvas.setStrokeColor(paint(S.RPT_HEX_MUTED))
        canvas.setLineWidth(C.RPT_OUTLINE)
        canvas.line(C.ZERO, C.ZERO, self.chart_width, C.ZERO)
        canvas.restoreState()


class RatingScale(Chart):
    def __init__(self) -> None:
        super().__init__(C.RPT_SCALE_HEIGHT)

    def draw(self) -> None:
        canvas = self.canv
        canvas.setFillColor(paint(S.RPT_HEX_MUTED))
        canvas.setFont(S.PDF_FONT, C.RPT_COLUMN_SIZE)
        for tick in C.RPT_TICKS:
            canvas.drawCentredString(rating_x(tick, self.chart_width), C.RPT_COLUMN_GAP, str(tick))


class Dumbbell(Chart):
    def __init__(self, row: CompareRow) -> None:
        super().__init__(C.RPT_DUMBBELL_HEIGHT)
        self.row = row

    def draw(self) -> None:
        canvas, width = self.canv, self.chart_width
        middle = self.chart_height * C.RPT_HALF
        personal = rating_x(self.row.personal, width)
        community = rating_x(self.row.community, width)
        canvas.saveState()
        canvas.setStrokeColor(paint(S.RPT_HEX_RULE))
        canvas.setLineWidth(C.RPT_HAIRLINE)
        canvas.line(
            rating_x(C.RPT_RATING_MIN, width), middle, rating_x(C.RPT_RATING_MAX, width), middle
        )
        for tick in C.RPT_TICKS:
            x = rating_x(tick, width)
            canvas.line(x, middle - C.RPT_COLUMN_GAP, x, middle + C.RPT_COLUMN_GAP)
        canvas.setStrokeColor(paint(S.RPT_HEX_GREY))
        canvas.setLineWidth(C.RPT_LINK_WIDTH)
        canvas.line(personal, middle, community, middle)
        canvas.restoreState()
        draw_marker(canvas, C.RptShape.SQUARE, community, middle, C.RptTone.SLATE, self.row.sparse)
        draw_marker(canvas, C.RptShape.CIRCLE, personal, middle, C.RptTone.TEAL, self.row.sparse)


class Meter(Chart):
    def __init__(self, known: int, total: int) -> None:
        super().__init__(C.RPT_METER_HEIGHT)
        self.known = known
        self.total = total

    def draw(self) -> None:
        canvas, width, height = self.canv, self.chart_width, self.chart_height
        canvas.setFillColor(paint(S.RPT_HEX_TRACK))
        canvas.roundRect(C.ZERO, C.ZERO, width, height, C.RPT_RADIUS, stroke=C.ZERO, fill=C.ONE)
        if self.known:
            length = max(width * min(self.known / self.total, C.ONE), C.RPT_MIN_FILL)
            draw_span(canvas, C.RptTone.TEAL, C.FALSE, C.ZERO, C.ZERO, length, height)


class Badge(Flowable):
    def __init__(self, theme: Theme, label: str) -> None:
        super().__init__()
        self.theme = theme
        self.label = label

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        diameter = C.RPT_BADGE_RADIUS * C.TWO
        self.width = diameter
        self.height = diameter
        return diameter, diameter

    def draw(self) -> None:
        canvas = self.canv
        radius = C.RPT_BADGE_RADIUS
        canvas.setFillColor(paint(S.RPT_HEX_TEAL))
        canvas.circle(radius, radius, radius, stroke=C.ZERO, fill=C.ONE)
        canvas.setFillColor(paint(S.RPT_HEX_WHITE))
        canvas.setFont(S.PDF_FONT_BOLD, C.RPT_BADGE_SIZE)
        canvas.drawCentredString(
            radius, radius - C.RPT_BADGE_SIZE * C.RPT_BASELINE_SHIFT, self.theme.plain(self.label)
        )


class Legend(Flowable):
    def __init__(self, theme: Theme, entries: tuple[LegendEntry, ...]) -> None:
        super().__init__()
        self.theme = theme
        self.entries = entries
        self.placed: list[tuple[float, int, LegendEntry]] = []

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self.placed = []
        left = float(C.ZERO)
        line = C.ZERO
        for entry in self.entries:
            text = self.theme.sized(self.theme.plain(entry.label), C.RPT_LEGEND_SIZE)
            span = C.RPT_MARKER * C.TWO + C.RPT_LEGEND_TEXT_GAP + text
            if left and left + span > availWidth:
                left = float(C.ZERO)
                line += C.ONE
            self.placed.append((left, line, entry))
            left += span + C.RPT_LEGEND_SPACING
        self.width = availWidth
        self.height = (line + C.ONE) * C.RPT_LEGEND_ROW
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        for left, line, entry in self.placed:
            middle = self.height - (line + C.RPT_HALF) * C.RPT_LEGEND_ROW
            draw_marker(canvas, entry.shape, left + C.RPT_MARKER, middle, entry.tone, C.FALSE)
            canvas.setFillColor(paint(S.RPT_HEX_INK))
            canvas.setFont(S.PDF_FONT, C.RPT_LEGEND_SIZE)
            canvas.drawString(
                left + C.RPT_MARKER * C.TWO + C.RPT_LEGEND_TEXT_GAP,
                middle - C.RPT_LEGEND_SIZE * C.RPT_BASELINE_SHIFT,
                self.theme.plain(entry.label),
            )
