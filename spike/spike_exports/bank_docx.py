"""Salary-transfer slip as a Word .docx.

The layout is a plausible stand-in. The real bank sample was not available;
the product must match the bank's own form before this is used.
"""
import io
from datetime import date

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from .common import TransferRow, format_amount

EAST_ASIAN_FONT = "標楷體"  # not embedded: Word uses the reader's own copy
HEADER = ["序號", "收款帳號", "戶名", "轉帳金額"]


def _write(paragraph, text, size=12, bold=False, red=False):
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), EAST_ASIAN_FONT)
    if red:
        run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
    return run


def render_bank_transfer_docx(
    company: str, payer_account: str, transfer_date: date, rows: list[TransferRow]
) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)

    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _write(heading, "薪資轉帳明細表", size=18, bold=True)

    _write(doc.add_paragraph(), f"委託單位：{company}")
    _write(doc.add_paragraph(), f"扣款帳號：{payer_account}")
    _write(
        doc.add_paragraph(),
        f"轉帳日期：民國 {transfer_date.year - 1911} 年 {transfer_date.month} 月 {transfer_date.day} 日",
    )

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, text in zip(table.rows[0].cells, HEADER):
        _write(cell.paragraphs[0], text, bold=True)

    def add_row(values, amount):
        cells = table.add_row().cells
        for cell, text in zip(cells, values):
            _write(cell.paragraphs[0], text)
        cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _write(cells[3].paragraphs[0], format_amount(amount), red=amount < 0)

    for n, row in enumerate(rows, start=1):
        add_row([str(n), row.account_no, row.name], row.amount)
    add_row(["合計", f"共 {len(rows)} 筆", ""], sum(r.amount for r in rows))

    doc.add_paragraph()
    _write(doc.add_paragraph(), "委託單位簽章：＿＿＿＿＿＿＿＿　　銀行收件章：＿＿＿＿＿＿＿＿")

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
