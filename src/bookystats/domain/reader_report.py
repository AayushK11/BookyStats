from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import Field

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisManifest
from bookystats.domain.models import canonical_json


def manifest_digest(manifest: AnalysisManifest) -> str:
    payload = canonical_json(manifest.model_dump(mode=S.JSON))
    return hashlib.sha256(payload.encode(S.UTF_8)).hexdigest()


class Link(C.Model):
    label: str = Field(min_length=C.ONE)
    url: str = Field(min_length=C.ONE)


class Stat(C.Model):
    label: str
    value: str
    detail: str = S.EMPTY
    tone: C.RptTone = C.RptTone.INK


class Fact(C.Model):
    headline: str
    body: str
    tone: C.RptTone = C.RptTone.TEAL


class BarRow(C.Model):
    label: str
    value: float | None = C.NONE
    shown: str = S.EMPTY
    caption: str = S.EMPTY
    tone: C.RptTone = C.RptTone.TEAL
    sparse: bool = C.FALSE


class Quote(C.Model):
    text: str
    cue: str
    title: str
    byline: str
    link: Link | None = C.NONE


class BookItem(C.Model):
    title: str
    byline: str = S.EMPTY
    detail: str = S.EMPTY
    marker: str = S.EMPTY
    lines: tuple[str, ...] = ()


class BookGroup(C.Model):
    heading: str
    books: tuple[BookItem, ...]


class CompareRow(C.Model):
    title: str
    byline: str
    personal: float
    community: float
    personal_text: str
    community_text: str
    delta: str
    sample: str
    sparse: bool = C.FALSE


class CoverageRow(C.Model):
    label: str
    read_known: int = Field(ge=C.ZERO)
    read_total: int = Field(ge=C.ZERO)
    watch_known: int = Field(ge=C.ZERO)
    watch_total: int = Field(ge=C.ZERO)


class ProseBlock(C.Model):
    kind: Literal[C.RptKind.PROSE] = C.RptKind.PROSE
    heading: str = S.EMPTY
    paragraphs: tuple[str, ...]


class TilesBlock(C.Model):
    kind: Literal[C.RptKind.TILES] = C.RptKind.TILES
    heading: str = S.EMPTY
    tiles: tuple[Stat, ...]
    note: str = S.EMPTY


class FactsBlock(C.Model):
    kind: Literal[C.RptKind.FACTS] = C.RptKind.FACTS
    heading: str = S.EMPTY
    facts: tuple[Fact, ...]
    note: str = S.EMPTY


class BarsBlock(C.Model):
    kind: Literal[C.RptKind.BARS] = C.RptKind.BARS
    heading: str = S.EMPTY
    style: C.RptBarStyle = C.RptBarStyle.HORIZONTAL
    rows: tuple[BarRow, ...]
    note: str = S.EMPTY
    axis: str = S.EMPTY
    maximum: float | None = Field(default=C.NONE, gt=C.ZERO)


class QuotesBlock(C.Model):
    kind: Literal[C.RptKind.QUOTES] = C.RptKind.QUOTES
    heading: str = S.EMPTY
    quotes: tuple[Quote, ...]
    note: str = S.EMPTY


class BooksBlock(C.Model):
    kind: Literal[C.RptKind.BOOKS] = C.RptKind.BOOKS
    heading: str = S.EMPTY
    groups: tuple[BookGroup, ...]
    note: str = S.EMPTY


class CompareBlock(C.Model):
    kind: Literal[C.RptKind.COMPARE] = C.RptKind.COMPARE
    heading: str = S.EMPTY
    rows: tuple[CompareRow, ...]
    note: str = S.EMPTY


class CoverageBlock(C.Model):
    kind: Literal[C.RptKind.COVERAGE] = C.RptKind.COVERAGE
    heading: str = S.EMPTY
    rows: tuple[CoverageRow, ...]
    note: str = S.EMPTY


class CalloutBlock(C.Model):
    kind: Literal[C.RptKind.CALLOUT] = C.RptKind.CALLOUT
    heading: str = S.EMPTY
    paragraphs: tuple[str, ...]
    tone: C.RptTone = C.RptTone.AMBER


Block = Annotated[
    ProseBlock
    | TilesBlock
    | FactsBlock
    | BarsBlock
    | QuotesBlock
    | BooksBlock
    | CompareBlock
    | CoverageBlock
    | CalloutBlock,
    Field(discriminator=S.RPT_KIND),
]


class Chapter(C.Model):
    key: str = Field(min_length=C.ONE)
    title: str = Field(min_length=C.ONE)
    kicker: str = S.EMPTY
    intro: str = S.EMPTY
    blocks: tuple[Block, ...]


class SkylineBar(C.Model):
    height: float | None = Field(default=C.NONE, ge=C.ZERO, le=C.ONE)
    tone: C.RptTone


class Swatch(C.Model):
    label: str
    tone: C.RptTone


class Cover(C.Model):
    eyebrow: str
    title: str
    subtitle: str
    as_of: str
    heroes: tuple[Stat, ...]
    skyline: tuple[SkylineBar, ...] = ()
    skyline_caption: str = S.EMPTY
    legend: tuple[Swatch, ...] = ()


class ReaderReport(C.Model):
    model_version: int = Field(ge=C.ONE, le=C.RPT_MODEL_VERSION)
    analysis_report_id: int | None = C.NONE
    as_of: str
    manifest_digest: str = Field(min_length=C.RPT_DIGEST_LENGTH, max_length=C.RPT_DIGEST_LENGTH)
    calculation_version: str
    cover: Cover
    chapters: tuple[Chapter, ...]
    fine_print: tuple[str, ...] = ()
    technical_notes: tuple[str, ...] = ()

    @C.AFTER_MODEL_VALIDATOR
    def unique_chapters(self) -> ReaderReport:
        keys = tuple(chapter.key for chapter in self.chapters)
        if len(set(keys)) != len(keys):
            raise ValueError(S.RPT_DUPLICATE_CHAPTER)
        return self
