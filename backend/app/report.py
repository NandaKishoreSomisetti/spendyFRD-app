"""Server-side PDF report (fpdf2 + Noto fonts, so Telugu and Hindi render correctly)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from .i18n import category_label, report_text
from .models import Summary, Transaction, TxType

FONT_DIR = Path(__file__).resolve().parent / "fonts"

INK = (17, 24, 39)
MUTED = (100, 116, 139)
ACCENT = (5, 150, 105)
RED = (220, 38, 38)
LINE = (226, 232, 240)
HEAD_BG = (241, 245, 249)


def inr(value: float) -> str:
    """Indian digit grouping: 1234567.5 -> ₹12,34,567.50"""
    sign = "-" if value < 0 else ""
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}₹{whole}.{frac}"


class _Report(FPDF):
    def __init__(self, lang: str):
        super().__init__(format="A4")
        self.lang = lang
        for family, stem in (("Noto", "NotoSans"), ("NotoTe", "NotoSansTelugu"),
                             ("NotoHi", "NotoSansDevanagari")):
            self.add_font(family, "", FONT_DIR / f"{stem}-Regular.ttf")
            self.add_font(family, "B", FONT_DIR / f"{stem}-Bold.ttf")
        # Latin/₹ from Noto Sans; Telugu/Devanagari glyphs fall back to their script fonts.
        self.set_fallback_fonts(["NotoTe", "NotoHi"], exact_match=False)
        self.set_text_shaping(True)
        self.set_auto_page_break(True, margin=18)
        self.set_margins(16, 16, 16)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Noto", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"spendyFRD · {report_text(self.lang, 'page', n=self.page_no())}", align="C")


def build_report(summary: Summary, txs: list[Transaction], lang: str = "en") -> bytes:
    t = lambda key, **kw: report_text(lang, key, **kw)  # noqa: E731
    pdf = _Report(lang)
    pdf.add_page()

    # ---- header --------------------------------------------------------------
    pdf.set_font("Noto", "B", 20)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 10, "spendyFRD", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "B", 14)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, t("title"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 9)
    pdf.set_text_color(*MUTED)
    meta = t("generated", d=date.today().strftime("%d %b %Y"))
    dates = sorted(x.date for x in txs if x.date)
    if dates:
        meta += "   ·   " + t("period", a=dates[0].strftime("%d %b %Y"), b=dates[-1].strftime("%d %b %Y"))
    pdf.cell(0, 6, meta, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ---- KPI tiles -----------------------------------------------------------
    rate = (summary.net / summary.total_credit * 100) if summary.total_credit else 0.0
    tiles = [
        (t("income"), inr(summary.total_credit), ACCENT),
        (t("spent"), inr(summary.total_debit), RED),
        (t("balance"), inr(summary.net), ACCENT if summary.net >= 0 else RED),
        (t("savings_rate"), f"{rate:.1f}%", INK),
    ]
    gap = 4
    width = (pdf.epw - gap * 3) / 4
    top = pdf.get_y()
    for i, (label, value, color) in enumerate(tiles):
        x = pdf.l_margin + i * (width + gap)
        pdf.set_draw_color(*LINE)
        pdf.rect(x, top, width, 20, round_corners=True, corner_radius=2)
        pdf.set_xy(x + 3, top + 3)
        pdf.set_font("Noto", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(width - 6, 5, label)
        pdf.set_xy(x + 3, top + 9)
        pdf.set_font("Noto", "B", 12)
        pdf.set_text_color(*color)
        pdf.cell(width - 6, 8, value)
    pdf.set_y(top + 26)

    if not txs:
        pdf.set_font("Noto", "", 11)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 10, t("empty"))
        return bytes(pdf.output())

    # ---- insights ------------------------------------------------------------
    insights: list[str] = []
    if summary.by_category:
        top_cat = summary.by_category[0]
        insights.append(t("top_category", c=category_label(top_cat.category, lang),
                          a=inr(top_cat.total), p=f"{top_cat.percent:.0f}"))
    if summary.total_credit:
        if summary.net < 0:
            insights.append(t("overspent", a=inr(-summary.net)))
        else:
            insights.append(t("saved_good" if rate >= 20 else "saved_low", p=f"{rate:.0f}"))
    if insights:
        _section(pdf, t("insights"))
        pdf.set_font("Noto", "", 10)
        pdf.set_text_color(*INK)
        for line in insights:
            pdf.multi_cell(0, 6, f"•  {line}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # ---- category table ------------------------------------------------------
    head_style = FontFace(family="Noto", emphasis="BOLD", color=INK, fill_color=HEAD_BG)
    if summary.by_category:
        _section(pdf, t("by_category"))
        pdf.set_font("Noto", "", 9)
        pdf.set_text_color(*INK)
        pdf.set_draw_color(*LINE)
        with pdf.table(col_widths=(50, 15, 22, 13), text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT"),
                       headings_style=head_style, line_height=6.5, borders_layout="HORIZONTAL_LINES") as table:
            table.row([t("category"), t("count"), t("amount"), t("share")])
            for c in summary.by_category:
                table.row([category_label(c.category, lang), str(c.count), inr(c.total), f"{c.percent:.1f}%"])
        pdf.ln(5)

    # ---- transactions --------------------------------------------------------
    _section(pdf, t("transactions"))
    pdf.set_font("Noto", "", 8.5)
    pdf.set_text_color(*INK)
    with pdf.table(col_widths=(16, 48, 24, 18), text_align=("LEFT", "LEFT", "LEFT", "RIGHT"),
                   headings_style=head_style, line_height=5.5, borders_layout="HORIZONTAL_LINES") as table:
        table.row([t("date"), t("description"), t("category"), t("amount")])
        for x in txs:
            sign = "+" if x.type == TxType.CREDIT else "−"
            row = table.row()
            row.cell(x.date.strftime("%d %b %Y") if x.date else "—")
            row.cell(x.description[:80])
            row.cell(category_label(x.category, lang))
            row.cell(f"{sign}{inr(x.amount)}",
                     style=FontFace(color=ACCENT if x.type == TxType.CREDIT else INK))
    return bytes(pdf.output())


def _section(pdf: FPDF, title: str) -> None:
    pdf.set_font("Noto", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
