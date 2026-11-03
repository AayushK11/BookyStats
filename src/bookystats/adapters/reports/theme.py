from __future__ import annotations

from html import escape
from pathlib import Path
from typing import cast

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

from bookystats import constants as C
from bookystats import strings as S


def register_fonts() -> None:
    root = Path(__file__).parent / S.PDF_FONTS_FOLDER
    for name, filename in C.PDF_FONTS:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(root / filename)))
    pdfmetrics.registerFontFamily(
        S.PDF_FONT,
        normal=S.PDF_FONT,
        bold=S.PDF_FONT_BOLD,
        italic=S.PDF_FONT,
        boldItalic=S.PDF_FONT_BOLD,
    )


def paint(value: str) -> colors.Color:
    return colors.HexColor(value)


def has_glyph(font_name: str, character: str) -> bool:
    font = cast(TTFont, pdfmetrics.getFont(font_name))
    return ord(character) in font.face.charToGlyph


def style_of(spec: C.RptStyle) -> ParagraphStyle:
    return ParagraphStyle(
        name=spec.name.value,
        fontName=S.PDF_FONT_BOLD if spec.bold else S.PDF_FONT,
        fontSize=spec.size,
        leading=spec.leading,
        spaceBefore=spec.before,
        spaceAfter=spec.after,
        textColor=paint(spec.color),
        alignment=TA_RIGHT if spec.right_aligned else TA_LEFT,
        keepWithNext=int(spec.keep),
        leftIndent=spec.indent,
        rightIndent=spec.right,
        bulletIndent=C.ZERO,
        bulletFontName=S.PDF_FONT,
        bulletFontSize=spec.size,
        allowWidows=C.ZERO,
        allowOrphans=C.ZERO,
    )


class Theme:
    def __init__(self) -> None:
        register_fonts()
        self.fallbacks = C.ZERO
        self.styles = {spec.name: style_of(spec) for spec in C.RPT_STYLES}
        self._glyphs: dict[str, tuple[str, bool]] = {}

    def markup(self, text: str) -> str:
        pieces: list[str] = []
        for character in C.PDF_CONTROL_PATTERN.sub(S.SPACE, text):
            fragment, fallback = self._glyph(character)
            pieces.append(fragment)
            self.fallbacks += int(fallback)
        return S.EMPTY.join(pieces)

    def plain(self, text: str) -> str:
        return S.EMPTY.join(
            character
            if has_glyph(S.PDF_FONT, character)
            else S.PDF_UNSUPPORTED_GLYPH.format(code=ord(character))
            for character in C.PDF_CONTROL_PATTERN.sub(S.SPACE, text)
        )

    def paragraph(self, markup: str, name: C.RptText, bullet: str | None = C.NONE) -> Paragraph:
        return Paragraph(markup, self.styles[name], bulletText=bullet)

    def para(self, text: str, name: C.RptText, bullet: str | None = C.NONE) -> Paragraph:
        return self.paragraph(self.markup(text), name, bullet)

    def width(self, text: str, name: C.RptText) -> float:
        style = self.styles[name]
        return float(pdfmetrics.stringWidth(text, style.fontName, style.fontSize))

    def sized(self, text: str, size: float, bold: bool = C.FALSE) -> float:
        return float(pdfmetrics.stringWidth(text, S.PDF_FONT_BOLD if bold else S.PDF_FONT, size))

    def fit(self, text: str, names: tuple[C.RptText, ...], width: float) -> C.RptText:
        for name in names:
            if self.width(self.plain(text), name) <= width:
                return name
        return names[-C.ONE]

    def _glyph(self, character: str) -> tuple[str, bool]:
        known = self._glyphs.get(character)
        if known is not C.NONE:
            return known
        result = (S.PDF_UNSUPPORTED_GLYPH.format(code=ord(character)), C.TRUE)
        for font_name, _ in C.PDF_FONTS:
            if has_glyph(font_name, character):
                fragment = escape(character, quote=C.FALSE)
                primary = font_name in C.PDF_PRIMARY_FONTS
                result = (
                    fragment if primary else S.PDF_FONT_SPAN.format(font=font_name, text=fragment),
                    not primary,
                )
                break
        self._glyphs[character] = result
        return result
