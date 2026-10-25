import io
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor
from app.models import ProjectData, ProjectMode


def set_cell_background(cell, fill_hex: str):
    """Устанавливает цвет фона ячейки."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)


def set_table_borders(table):
    """Устанавливает тонкие аккуратные рамки таблицы по ГОСТ."""
    tbl_pr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="888888"/>'
        f'  <w:left w:val="single" w:sz="4" w:space="0" w:color="888888"/>'
        f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="888888"/>'
        f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="888888"/>'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
        f'  <w:insideV w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
        f'</w:tblBorders>'
    )
    tbl_pr.append(borders)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Устанавливает внутренние отступы ячейки."""
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="{top}" w:type="dxa"/>'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'  <w:left w:w="{left}" w:type="dxa"/>'
        f'  <w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tc_pr.append(tc_mar)


def generate_docx_sostav(project_data: ProjectData) -> io.BytesIO:
    """
    Генерирует документ Word 'Состав проектной документации'
    в точном соответствии с образцом.
    """
    doc = Document()

    # Настройка полей страницы (20 мм со всех сторон)
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # 1. Шапка документа
    if project_data.mode == ProjectMode.CONTRACT:
        # Режим договора: официальная шапка согласования
        p_app = doc.add_paragraph()
        p_app.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_app = p_app.add_run(
            f"Приложение № 1\nк Договору № {project_data.contract_number or '_______'} "
            f"от {project_data.contract_date or '«____» ___________ 2026 г.'}\n"
        )
        r_app.font.name = "Calibri"
        r_app.font.size = Pt(10)
        r_app.font.italic = True

        # Таблица согласования (2 колонки)
        table_sig = doc.add_table(rows=1, cols=2)
        table_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
        table_sig.autofit = False

        left_cell = table_sig.rows[0].cells[0]
        right_cell = table_sig.rows[0].cells[1]
        left_cell.width = Inches(3.2)
        right_cell.width = Inches(3.2)

        sub_name = project_data.subcontractor or "Проектная организация"
        contr_name = project_data.contractor or "Заказчик"

        p_left = left_cell.paragraphs[0]
        p_left.add_run(f"СОГЛАСОВАНО:\nРуководитель\n{sub_name}\n\n________________ / ___________ /\n«____» ___________ 20__г.").font.name = "Calibri"
        p_left.runs[0].font.size = Pt(9.5)

        p_right = right_cell.paragraphs[0]
        p_right.add_run(f"УТВЕРЖДАЮ:\nРуководитель\n{contr_name}\n\n________________ / ___________ /\n«____» ___________ 20__г.").font.name = "Calibri"
        p_right.runs[0].font.size = Pt(9.5)

        doc.add_paragraph()  # Отступ
    else:
        # Режим предварительной оценки / КП (без шифра договора)
        p_pre = doc.add_paragraph()
        p_pre.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_pre = p_pre.add_run("ПРЕДВАРИТЕЛЬНЫЙ СОСТАВ ПРОЕКТНОЙ ДОКУМЕНТАЦИИ\n(проект для коммерческого предложения)")
        r_pre.font.name = "Calibri"
        r_pre.font.size = Pt(13)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(30, 60, 110)

        p_meta = doc.add_paragraph()
        p_meta.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r_meta = p_meta.add_run(
            f"Заказчик: {project_data.customer}\n"
            f"Проектная организация: {project_data.subcontractor}\n"
            f"Статус: Проработка технического задания (до заключения договора)"
        )
        r_meta.font.name = "Calibri"
        r_meta.font.size = Pt(10)
        r_meta.font.italic = True

    # 2. Заголовок состава
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r_title_1 = p_title.add_run("Состав Проектной документации:\n")
    r_title_1.font.name = "Calibri"
    r_title_1.font.size = Pt(12)
    r_title_1.font.bold = True

    r_title_2 = p_title.add_run(project_data.object_name)
    r_title_2.font.name = "Calibri"
    r_title_2.font.size = Pt(12)
    r_title_2.font.bold = True
    r_title_2.font.color.rgb = RGBColor(20, 40, 80)

    # 3. Таблица томов
    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)

    # Ширина колонок
    col_widths = [Inches(0.9), Inches(1.5), Inches(3.6), Inches(1.2)]

    # Заголовок таблицы
    hdr_cells = table.rows[0].cells
    headers = ["№ тома", "Обозначение", "Наименование", "Примечание"]
    for i, title in enumerate(headers):
        hdr_cells[i].width = col_widths[i]
        set_cell_background(hdr_cells[i], "EAECEE")
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(title)
        run.font.name = "Calibri"
        run.font.size = Pt(10)
        run.font.bold = True

    # Наполнение таблицы
    last_header = None
    enabled_sections = [s for s in project_data.sections if s.enabled]

    for sec in enabled_sections:
        # Если есть группирующий заголовок (например, Раздел 5 или Раздел 12), выводим его объединенной строкой
        if sec.category_header and sec.category_header != last_header:
            last_header = sec.category_header
            cat_row = table.add_row()
            merged_cell = cat_row.cells[0]
            for c in cat_row.cells[1:]:
                merged_cell.merge(c)
            set_cell_background(merged_cell, "F2F4F4")
            set_cell_margins(merged_cell, top=100, bottom=100, left=140, right=140)
            p_cat = merged_cell.paragraphs[0]
            p_cat.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r_cat = p_cat.add_run(sec.category_header)
            r_cat.font.name = "Calibri"
            r_cat.font.size = Pt(9.5)
            r_cat.font.bold = True

        # Строка тома
        row = table.add_row()
        for idx, w in enumerate(col_widths):
            row.cells[idx].width = w
            set_cell_margins(row.cells[idx], top=80, bottom=80, left=120, right=120)
            row.cells[idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        # № тома
        p0 = row.cells[0].paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0 = p0.add_run(sec.volume_num)
        r0.font.name = "Calibri"
        r0.font.size = Pt(9.5)

        # Обозначение (в режиме КП - марка, в режиме Договор - полный шифр)
        p1 = row.cells[1].paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p1.add_run(sec.full_code or sec.code_mark)
        r1.font.name = "Calibri"
        r1.font.size = Pt(9.5)
        r1.font.bold = True

        # Наименование
        p2 = row.cells[2].paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r2 = p2.add_run(sec.title)
        r2.font.name = "Calibri"
        r2.font.size = Pt(9.5)

        # Примечание
        p3 = row.cells[3].paragraphs[0]
        p3.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r3 = p3.add_run(sec.note)
        r3.font.name = "Calibri"
        r3.font.size = Pt(9)
        r3.font.italic = True

    # Сохранение в буфер памяти
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
