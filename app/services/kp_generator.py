"""
Генератор коммерческого предложения (.docx).

Два режима:
1. Нейтральный (по умолчанию, общедоступный): документ собирается с нуля, данных компании нет,
   вместо них заглушки («ООО «Компания», ИНН …»).
2. Корпоративный: если существует приватный файл бланка (env KP_LETTERHEAD_PATH, по умолчанию
   data/private/kp_letterhead.docx), он используется как основа: сохраняются оформление, логотип,
   реквизиты. В бланке заменяются метки {{OUT_NUM}}, {{DATE}}, {{ADDRESSEE}}, {{SIGNER}},
   {{EXECUTOR}}, а на месте абзаца {{BODY}} вставляется основной текст КП.
   Файл бланка не хранится в репозитории (папка data/private в .gitignore).
"""
import io
import os
from datetime import date as date_cls
from datetime import datetime
from typing import List, Optional

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from app.models import (
    KPPaymentScheme,
    KPPaymentStage,
    KPPriceFormat,
    KPRequest,
    KPStage,
    KPTermUnit,
)
from app.services.money import format_rub, plural_form, rubles_in_words

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_LETTERHEAD = os.path.join(BASE_DIR, "data", "private", "kp_letterhead.docx")

MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
              "сентября", "октября", "ноября", "декабря"]

STAGE_TEXT = {
    KPStage.PD: "разработку проектной документации",
    KPStage.PD_RD: "разработку проектной и рабочей документации",
    KPStage.CHANGES: "внесение изменений в проектную документацию",
}

DEFAULT_PAYMENT_STAGES = [
    KPPaymentStage(percent=40, text="Предоплата - 40% стоимости работ по договору производится в течение "
                                    "5 рабочих дней с момента заключения договора."),
    KPPaymentStage(percent=30, text="Оплата в размере 30% стоимости работ производится в течение 5 рабочих дней "
                                    "с момента передачи полного комплекта документации на согласование."),
    KPPaymentStage(percent=30, text="Оплата в размере 30% стоимости работ производится в течение 5 рабочих дней "
                                    "с момента подписания акта выполненных работ."),
]


def get_letterhead_path() -> Optional[str]:
    path = os.environ.get("KP_LETTERHEAD_PATH") or DEFAULT_LETTERHEAD
    return path if os.path.isfile(path) else None


# ---------------------------------------------------------------- вспомогательное

def _parse_date(value: str) -> date_cls:
    if value:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return date_cls.today()


def format_kp_date(d: date_cls) -> str:
    return f"«{d.day:02d}» {MONTHS_GEN[d.month - 1]} {d.year} г."


def outgoing_number_text(number: str, d: date_cls) -> str:
    """Порядковая часть вписывается пользователем; ММГГ подставляется автоматически."""
    suffix = f"{d.month:02d}{d.year % 100:02d}"
    return f"Исх. № {number.strip() or '____'}/{suffix}"


def term_text(value: int, unit: KPTermUnit) -> str:
    forms = {
        KPTermUnit.MONTHS: ("месяц", "месяца", "месяцев"),
        KPTermUnit.WORKING_DAYS: ("рабочий день", "рабочих дня", "рабочих дней"),
        KPTermUnit.CALENDAR_DAYS: ("календарный день", "календарных дня", "календарных дней"),
    }[unit]
    return f"{value} {plural_form(value, forms)}"


def _vat_info(req: KPRequest):
    cp = req.project.cost_parameters
    if cp and cp.include_vat:
        return True, cp.vat_rate
    return False, 0.0


def _rate_str(rate: float) -> str:
    return f"{rate:g}%"


def _rows_and_totals(req: KPRequest):
    """Возвращает (строки таблицы, итого без НДС, НДС, итого с НДС)."""
    cp = req.project.cost_parameters
    include_vat, rate = _vat_info(req)
    rows = []
    if req.price_format == KPPriceFormat.SECTIONS and cp:
        for it in cp.sections_costs:
            if it.enabled:
                rows.append((it.code_mark, it.title, it.cost_rub))
        net = round(sum(r[2] for r in rows), 2)
    elif req.price_format == KPPriceFormat.WORKS:
        for i, w in enumerate(req.works, 1):
            rows.append((str(i), w.name, w.cost_rub))
        net = round(sum(r[2] for r in rows), 2)
    else:
        net = round(cp.total_cost_net_rub, 2) if cp else 0.0
    vat = round(net * rate / 100.0, 2) if include_vat else 0.0
    return rows, net, vat, round(net + vat, 2)


# ---------------------------------------------------------------- построение текста

def _set_font(run, size=None, bold=None):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def _para(doc, text="", bold=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=12, space_after=6):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if text:
        _set_font(p.add_run(text), size, bold)
    return p


def _cell_text(cell, text, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT, size=11):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    _set_font(p.add_run(text), size, bold)


def _set_borders(table):
    """Границы таблицы вручную (в бланке компании может не быть стиля «Table Grid»)."""
    from docx.oxml import OxmlElement
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tbl_pr.append(borders)


def _price_table(doc, req: KPRequest, rows, net, vat, gross):
    include_vat, rate = _vat_info(req)
    first_col = "Марка" if req.price_format == KPPriceFormat.SECTIONS else "№ п/п"
    table = doc.add_table(rows=1, cols=3)
    _set_borders(table)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = [Cm(2.2), Cm(11.0), Cm(3.8)]
    hdr = table.rows[0].cells
    for c, t in zip(hdr, [first_col, "Наименование работ", "Стоимость, руб."]):
        _cell_text(c, t, True, WD_ALIGN_PARAGRAPH.CENTER)
    for mark, name, cost in rows:
        r = table.add_row().cells
        _cell_text(r[0], mark, align=WD_ALIGN_PARAGRAPH.CENTER)
        _cell_text(r[1], name)
        _cell_text(r[2], format_rub(cost), align=WD_ALIGN_PARAGRAPH.RIGHT)

    def total_row(label, value):
        r = table.add_row().cells
        merged = r[0].merge(r[1])
        _cell_text(merged, label, True, WD_ALIGN_PARAGRAPH.RIGHT)
        _cell_text(r[2], format_rub(value), True, WD_ALIGN_PARAGRAPH.RIGHT)

    if include_vat:
        total_row("ИТОГО без НДС:", net)
        total_row(f"НДС {_rate_str(rate)}:", vat)
        total_row("ИТОГО с НДС:", gross)
    else:
        total_row("ИТОГО (НДС не облагается):", net)
    for row in table.rows:
        for c, w in zip(row.cells, widths):
            c.width = w
    return table


def _build_body(doc, req: KPRequest):
    """Основной текст КП: предмет, стоимость, оговорки, срок, оплата, прочее."""
    include_vat, rate = _vat_info(req)
    rows, net, vat, gross = _rows_and_totals(req)

    _para(doc, "По объекту: «" + req.project.object_name + "»", bold=True, align=WD_ALIGN_PARAGRAPH.LEFT)
    _para(doc, req.salutation, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

    if req.subject_text.strip():
        subject = req.subject_text.strip()
    else:
        ref = f"В ответ на Ваш запрос от {req.request_date}, " if req.request_date else "По Вашему запросу "
        subject = (f"{ref}направляем коммерческое предложение на {STAGE_TEXT[req.stage]} "
                   f"по объекту: «{req.project.object_name}».")
    _para(doc, subject)

    if req.inclusions:
        _para(doc, "В коммерческое предложение входит:", space_after=2)
        for item in req.inclusions:
            _para(doc, "- " + item.rstrip(";."), space_after=2)
        _para(doc, "", space_after=2)

    if req.price_format != KPPriceFormat.TOTAL and rows:
        _price_table(doc, req, rows, net, vat, gross)
        _para(doc, "", space_after=2)

    amount = gross if include_vat else net
    vat_note = f", в т.ч. НДС {_rate_str(rate)}" if include_vat else ", НДС не облагается"
    _para(doc, f"Итого: {rubles_in_words(amount)}{vat_note}.", bold=True)

    if req.exclusions:
        _para(doc, "Стоимость не включает: " + "; ".join(e.rstrip(";.") for e in req.exclusions) + ".")

    _para(doc, "Условия оплаты:", bold=True, space_after=2)
    if req.payment_scheme == KPPaymentScheme.STAGES:
        stages = req.payment_stages or DEFAULT_PAYMENT_STAGES
        _para(doc, "Оплата работ производится поэтапно, с авансированием:", space_after=2)
        for st in stages:
            _para(doc, "- " + st.text, space_after=2)
    else:
        _para(doc, f"Оплата производится на условиях авансирования - {req.advance_percent:g}%.")

    if req.term_value:
        _para(doc, f"Срок выполнения работ - {term_text(req.term_value, req.term_unit)}.")
    if req.note_approval_excluded:
        _para(doc, "*В срок не входит время согласования документации с заказчиком и заинтересованными "
                   "организациями.")

    if req.phrase_help_tz:
        _para(doc, "* Готовы помочь в разработке Технического задания.", align=WD_ALIGN_PARAGRAPH.LEFT,
              space_after=2)
    if req.phrase_counter_offers:
        _para(doc, "* Готовы рассмотреть встречные предложения по срокам и стоимости проектирования.",
              bold=True, align=WD_ALIGN_PARAGRAPH.LEFT)
    _para(doc, f"Коммерческое предложение действительно - {req.validity_days} рабочих дней.",
          align=WD_ALIGN_PARAGRAPH.LEFT)


# ---------------------------------------------------------------- режимы

def _signer_line(req: KPRequest) -> str:
    company = req.company_name.strip() or "ООО «Компания»"
    name = req.signer_name.strip() or "И.О. Фамилия"
    return f"{req.signer_title.strip() or 'Директор'} {company}   ________________   {name}"


def _executor_line(req: KPRequest) -> str:
    return "Исп. " + (req.executor.strip() or "Фамилия И.О. тел. +7 ___ ___ __ __")


def _build_neutral(req: KPRequest, d: date_cls) -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin, sec.right_margin = Cm(2.0), Cm(1.5)
    sec.top_margin, sec.bottom_margin = Cm(1.75), Cm(1.5)
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    company = req.company_name.strip() or "ООО «Компания»"
    _para(doc, "Архитектурно-строительное проектирование", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
          space_after=0)
    _para(doc, f"{company}  ИНН ____  КПП ____  ОГРН ____", align=WD_ALIGN_PARAGRAPH.CENTER, size=10,
          space_after=0)
    _para(doc, "Адрес: ________, тел.: ________, e-mail: ________", align=WD_ALIGN_PARAGRAPH.CENTER, size=10,
          space_after=12)

    t = doc.add_table(rows=1, cols=2)
    _cell_text(t.rows[0].cells[0], outgoing_number_text(req.outgoing_number, d) + "\n" + format_kp_date(d),
               size=12)
    _cell_text(t.rows[0].cells[1], "\n".join(req.addressee_lines) or "Должность\nОрганизация\nФ.И.О.",
               align=WD_ALIGN_PARAGRAPH.RIGHT, size=12)
    _para(doc, "", space_after=6)

    _build_body(doc, req)

    _para(doc, "С уважением,", bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=2)
    _para(doc, _signer_line(req), bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=24)
    _para(doc, _executor_line(req), align=WD_ALIGN_PARAGRAPH.LEFT, size=10)
    return doc


def _replace_in_paragraph(p, mapping: dict) -> bool:
    text = "".join(r.text for r in p.runs)
    if "{{" not in text:
        return False
    changed = False
    for key, val in mapping.items():
        if key in text:
            text = text.replace(key, val)
            changed = True
    if changed and p.runs:
        lines = text.split("\n")
        p.runs[0].text = lines[0]
        for r in p.runs[1:]:
            r.text = ""
        for line in lines[1:]:
            p.runs[0].add_break()
            p.runs[0].add_text(line)
    return changed


def _iter_paragraphs(doc):
    for p in doc.paragraphs:
        yield p
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def _build_corporate(req: KPRequest, d: date_cls, letterhead: str) -> Document:
    doc = Document(letterhead)
    mapping = {
        "{{OUT_NUM}}": outgoing_number_text(req.outgoing_number, d),
        "{{DATE}}": format_kp_date(d),
        "{{ADDRESSEE}}": "\n".join(req.addressee_lines),
        "{{SIGNER}}": _signer_line(req),
        "{{EXECUTOR}}": _executor_line(req),
    }
    anchor = None
    for p in _iter_paragraphs(doc):
        if "{{BODY}}" in p.text:
            anchor = p
        else:
            _replace_in_paragraph(p, mapping)
    if anchor is None:
        raise ValueError("В бланке не найдена метка {{BODY}}")

    body = doc.element.body
    before = list(body)
    _build_body(doc, req)
    new_elements = [el for el in body if el not in before and el.tag != qn("w:sectPr")]
    for el in new_elements:
        anchor._element.addprevious(el)
    anchor._element.getparent().remove(anchor._element)
    return doc


def generate_kp_docx(req: KPRequest) -> io.BytesIO:
    d = _parse_date(req.date)
    letterhead = get_letterhead_path()
    doc = _build_corporate(req, d, letterhead) if letterhead else _build_neutral(req, d)
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
