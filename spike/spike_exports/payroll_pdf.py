"""Payroll summary as an A4 landscape PDF with an embedded Traditional Chinese font."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .common import FONT_NAME, FONT_PATH, PayrollRow, format_amount

HEADER = ["員工編號", "姓名", "底薪", "加給", "扣款", "調整", "實發金額"]


def render_payroll_pdf(period: str, rows: list[PayrollRow], generated_at: datetime) -> bytes:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))

    data = [HEADER]
    for r in rows:
        amounts = [r.base_pay, r.allowance, r.deduction, r.adjustment, r.net_pay]
        data.append([r.employee_no, r.name, *amounts])
    data.append(["", "合計", *(sum(row[i] for row in data[1:]) for i in range(2, 7))])

    style = [
        ("FONT", (0, 0), (-1, -1), FONT_NAME, 11),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for y, row in enumerate(data[1:], start=1):
        for x in range(2, 7):
            if row[x] < 0:
                style.append(("TEXTCOLOR", (x, y), (x, y), colors.red))
            row[x] = format_amount(row[x])

    title = ParagraphStyle("title", fontName=FONT_NAME, fontSize=18, leading=24)
    note = ParagraphStyle("note", fontName=FONT_NAME, fontSize=10, leading=14)
    table = Table(data, colWidths=[30 * mm, 45 * mm] + [36 * mm] * 5, repeatRows=1)
    table.setStyle(TableStyle(style))

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=landscape(A4), title=f"{period} 薪資總表",
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
    )
    doc.build([
        Paragraph(f"{period} 薪資總表", title),
        Paragraph(f"製表時間：{generated_at:%Y-%m-%d %H:%M}　幣別：新臺幣（元）", note),
        Spacer(1, 6 * mm),
        table,
    ])
    return out.getvalue()
