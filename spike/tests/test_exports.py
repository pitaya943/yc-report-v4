"""Read the text back out of the generated files and compare it with what went in.

Expected strings are written out by hand, not produced by the code under test.
"""
import io
import zipfile
from datetime import date

import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.shared import RGBColor
from pypdf import PdfReader

from spike_exports.bank_docx import render_bank_transfer_docx
from spike_exports.make_samples import PAYROLL, TRANSFERS
from spike_exports.payroll_pdf import render_payroll_pdf
from spike_jobs.clock import FixedClock


@pytest.fixture(scope="module")
def pdf():
    data = render_payroll_pdf("2026 年 11 月", PAYROLL, FixedClock("2026-11-30T23:59:00").now())
    return PdfReader(io.BytesIO(data))


def _words(pdf):
    """All text in reading order; pypdf returns each table cell on its own line."""
    return " ".join(page.extract_text() for page in pdf.pages).split()


def test_pdf_text_read_back_matches_the_chinese_and_the_amounts(pdf):
    assert _words(pdf) == " ".join([
        "2026 年 11 月 薪資總表",
        "製表時間：2026-11-30 23:59 幣別：新臺幣（元）",
        "員工編號 姓名 底薪 加給 扣款 調整 實發金額",
        "E001 王小明 45,000 3,000 2,180 0 45,820",
        "E002 陳美玲 52,000 0 2,560 -1,200 48,240",
        "E003 林志豪 38,500 1,500 1,890 0 38,110",
        "E004 張堃喆 0 0 1,200 0 -1,200",
        "合計 135,500 4,500 7,830 -1,200 130,970",
    ]).split()


def test_pdf_is_one_a4_landscape_page(pdf):
    assert len(pdf.pages) == 1
    page = pdf.pages[0]
    width_mm = float(page.mediabox.width) / 72 * 25.4
    height_mm = float(page.mediabox.height) / 72 * 25.4
    assert (round(width_mm), round(height_mm)) == (297, 210)
    assert page.get("/Rotate", 0) == 0


def test_pdf_carries_its_own_chinese_font(pdf):
    """Every font is either embedded or one of the 14 fonts every PDF reader has."""
    fonts = pdf.pages[0]["/Resources"]["/Font"]
    embedded = []
    for font in fonts.values():
        font = font.get_object()
        descriptor = font.get("/FontDescriptor")
        if descriptor is not None and "/FontFile2" in descriptor.get_object():
            embedded.append(str(font["/BaseFont"]))
        else:
            assert font["/BaseFont"] in ("/Helvetica", "/Helvetica-Bold")
    assert len(embedded) >= 1
    assert all(name.endswith("+NotoSansTC-Regular") for name in embedded)


@pytest.fixture(scope="module")
def docx_bytes():
    return render_bank_transfer_docx("範例工程行", "00400000000001", date(2026, 12, 5), TRANSFERS)


def test_docx_text_read_back_matches_the_chinese_and_the_amounts(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    assert [p.text for p in doc.paragraphs if p.text] == [
        "薪資轉帳明細表",
        "委託單位：範例工程行",
        "扣款帳號：00400000000001",
        "轉帳日期：民國 115 年 12 月 5 日",
        "委託單位簽章：＿＿＿＿＿＿＿＿　　銀行收件章：＿＿＿＿＿＿＿＿",
    ]
    (table,) = doc.tables
    assert [[cell.text for cell in row.cells] for row in table.rows] == [
        ["序號", "收款帳號", "戶名", "轉帳金額"],
        ["1", "00412345678901", "王小明", "45,820"],
        ["2", "00498765432109", "陳美玲", "48,240"],
        ["3", "01200011122233", "林志豪", "38,110"],
        ["4", "01255566677788", "張堃喆", "-1,200"],
        ["合計", "共 4 筆", "", "130,970"],
    ]


def test_docx_xml_itself_contains_the_chinese_text(docx_bytes):
    """Independent of python-docx: unzip and look at the document part."""
    xml = zipfile.ZipFile(io.BytesIO(docx_bytes)).read("word/document.xml").decode("utf-8")
    for expected in ("薪資轉帳明細表", "王小明", "陳美玲", "張堃喆", "00412345678901", "130,970"):
        assert expected in xml


def test_docx_asks_for_a_chinese_font_on_every_run_and_marks_negatives_red(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    table = doc.tables[0]
    runs = [r for p in doc.paragraphs for r in p.runs]
    runs += [r for row in table.rows for cell in row.cells for p in cell.paragraphs for r in p.runs]
    assert len(runs) > 20
    assert {r._element.rPr.rFonts.get(qn("w:eastAsia")) for r in runs} == {"標楷體"}

    red = [r.text for r in runs if r.font.color.rgb == RGBColor(0xFF, 0, 0)]
    assert red == ["-1,200"]


def test_docx_page_is_a4_portrait(docx_bytes):
    section = Document(io.BytesIO(docx_bytes)).sections[0]
    assert (round(section.page_width.mm), round(section.page_height.mm)) == (210, 297)
