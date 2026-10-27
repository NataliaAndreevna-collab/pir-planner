import datetime
import io
import math
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from app.models import ProjectData, ProjectMode
from app.services.pp87_rules import GROUPS, GROUP_COLORS, resolve_schedule, total_weeks

MONTH_NAMES_RU = [
    "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
]

GROUP_EXCEL_COLORS = {
    "survey": "10B981",     # Изумрудный (Изыскания)
    "pd": "3B82F6",         # Синий (ПД)
    "approval": "F59E0B",   # Янтарный (Согласования)
    "expertise": "8B5CF6",  # Фиолетовый (Экспертиза)
    "rd": "06B6D4",         # Бирюзовый (РД)
    "other": "64748B",      # Сланцевый (Прочее)
}


def generate_excel_schedule(project_data: ProjectData) -> io.BytesIO:
    """
    Генерирует профессиональный Календарный график выполнения работ в Excel (.xlsx)
    с двухуровневой шкалой (Месяцы + Недели), связями этапов, группами и вехами.
    """
    resolve_schedule(project_data.schedule_phases)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Календарный график"
    ws.views.sheetView[0].showGridLines = True

    steel_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    sub_hdr_fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
    week_hdr_fill = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
    group_row_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    milestone_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    font_title = Font(name="Calibri", size=13, bold=True, color="1E3A8A")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_regular = Font(name="Calibri", size=9.5)
    font_small = Font(name="Calibri", size=8.5, italic=True)
    font_white_bold = Font(name="Calibri", size=9.5, bold=True, color="FFFFFF")
    font_week = Font(name="Calibri", size=8, bold=True, color="1E3A8A")
    font_bar = Font(name="Calibri", size=8.5, bold=True, color="FFFFFF")
    font_milestone = Font(name="Calibri", size=10, bold=True, color="B45309")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    num_weeks = max(total_weeks(project_data.schedule_phases), 8)
    # Округляем до кратного 4 для аккуратных месячных блоков
    num_months = math.ceil(num_weeks / 4)
    num_weeks = num_months * 4

    # Колонки:
    # 1: №
    # 2: Наименование этапа / раздела
    # 3: После №
    # 4: Старт (нед.)
    # 5: Длит. (нед.)
    # 6: Финиш (нед.)
    # 7 .. 6 + num_weeks: Недели Н1..НN
    # 7 + num_weeks: Примечание
    first_week_col = 7
    note_col = first_week_col + num_weeks

    current_row = 1

    # 1. Шапка документа
    if project_data.mode == ProjectMode.CONTRACT:
        ws.cell(row=current_row, column=note_col, value="Приложение № 2").font = font_small
        ws.cell(
            row=current_row + 1,
            column=note_col,
            value=f"к договору № {project_data.contract_number or '____'} от {project_data.contract_date or '___'}"
        ).font = font_small
        current_row += 3

        ws.cell(row=current_row, column=2, value="ИСПОЛНИТЕЛЬ:").font = font_bold
        ws.cell(row=current_row, column=first_week_col, value="ЗАКАЗЧИК:").font = font_bold

        contr_name = project_data.contractor or project_data.customer or "Заказчик"
        ws.cell(row=current_row + 1, column=2, value="________________ / ___________ /").font = font_regular
        ws.cell(row=current_row + 1, column=first_week_col, value=f"{contr_name}").font = font_regular
        ws.cell(row=current_row + 2, column=first_week_col, value="________________ / ___________ /").font = font_regular
        current_row += 4
    else:
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=note_col)
        c_title = ws.cell(row=current_row, column=1, value="КАЛЕНДАРНЫЙ ГРАФИК ВЫПОЛНЕНИЯ ПРОЕКТНО-ИЗЫСКАТЕЛЬСКИХ РАБОТ")
        c_title.font = font_title
        c_title.alignment = align_center
        current_row += 2

    # Объект и сводка сроков
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=note_col)
    actual_weeks = total_weeks(project_data.schedule_phases)
    actual_months = round(actual_weeks / 4.33, 1)
    summary_str = f"Объект: {project_data.object_name}   |   Общий срок: {actual_weeks} нед. (~{actual_months} мес.)"
    if project_data.customer:
        summary_str += f"   |   Заказчик: {project_data.customer}"
    if project_data.contractor:
        summary_str += f"   |   Генпроектировщик: {project_data.contractor}"
    c_obj = ws.cell(row=current_row, column=1, value=summary_str)
    c_obj.font = Font(name="Calibri", size=10.5, bold=True, color="1E3A8A")
    c_obj.alignment = align_left
    current_row += 2

    # 2. Двухуровневая шапка таблицы
    tbl_start_row = current_row
    sub_row = tbl_start_row + 1

    fixed_headers = [
        (1, "№\nэтапа"),
        (2, "Наименование этапа / раздела"),
        (3, "Старт после\nэтапа №"),
        (4, "Начало,\nнед."),
        (5, "Длительность,\nнед."),
        (6, "Окончание,\nнед."),
    ]
    for col_idx, text in fixed_headers:
        ws.merge_cells(start_row=tbl_start_row, start_column=col_idx, end_row=sub_row, end_column=col_idx)
        c = ws.cell(row=tbl_start_row, column=col_idx, value=text)
        c.fill = steel_fill
        c.font = font_white_bold
        c.alignment = align_center

    # Верхний уровень шкалы: Месяцы (по 4 недели)
    start_dt = None
    if project_data.start_date:
        try:
            start_dt = datetime.datetime.strptime(project_data.start_date[:10], "%Y-%m-%d")
        except Exception:
            start_dt = None

    for m_idx in range(num_months):
        w_start_col = first_week_col + m_idx * 4
        w_end_col = w_start_col + 3
        ws.merge_cells(start_row=tbl_start_row, start_column=w_start_col, end_row=tbl_start_row, end_column=w_end_col)
        if start_dt:
            m_dt = start_dt + datetime.timedelta(days=m_idx * 30.4375)
            m_label = f"Месяц {m_idx + 1} ({MONTH_NAMES_RU[m_dt.month - 1]} {m_dt.year})"
        else:
            m_label = f"Месяц {m_idx + 1}"
        cm = ws.cell(row=tbl_start_row, column=w_start_col, value=m_label)
        cm.fill = sub_hdr_fill
        cm.font = Font(name="Calibri", size=9, bold=True, color="1E3A8A")
        cm.alignment = align_center

    # Нижний уровень шкалы: Недели Н1..НN
    for w in range(1, num_weeks + 1):
        col_idx = first_week_col + w - 1
        cw = ws.cell(row=sub_row, column=col_idx, value=f"Н{w}")
        cw.fill = week_hdr_fill
        cw.font = font_week
        cw.alignment = align_center

    # Колонка Примечание
    ws.merge_cells(start_row=tbl_start_row, start_column=note_col, end_row=sub_row, end_column=note_col)
    c_note = ws.cell(row=tbl_start_row, column=note_col, value="Примечание")
    c_note.fill = steel_fill
    c_note.font = font_white_bold
    c_note.alignment = align_center

    for r in (tbl_start_row, sub_row):
        for col in range(1, note_col + 1):
            ws.cell(row=r, column=col).border = thin_border

    current_row = sub_row + 1

    # 3. Вывод строк графика с группировкой по блокам
    last_group = None
    for idx, phase in enumerate(project_data.schedule_phases, start=1):
        grp = phase.group or "pd"
        if grp != last_group:
            last_group = grp
            grp_title = GROUPS.get(grp, "Этапы работ")
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=note_col)
            cg = ws.cell(row=current_row, column=1, value=grp_title.upper())
            cg.fill = group_row_fill
            cg.font = Font(name="Calibri", size=9.5, bold=True, color="1E3A8A")
            cg.alignment = align_left
            for col in range(1, note_col + 1):
                ws.cell(row=current_row, column=col).border = thin_border
            current_row += 1

        finish_week = phase.start_week if phase.milestone else (phase.start_week + max(1, phase.duration_weeks) - 1)
        deps_str = ", ".join(str(d) for d in phase.depends_on) if phase.depends_on else "—"
        if phase.depends_on and phase.lag_weeks:
            sign = "+" if phase.lag_weeks > 0 else ""
            deps_str += f" ({sign}{phase.lag_weeks}н)"

        row_vals = [
            (1, phase.id or idx, align_center, font_bold if phase.milestone else font_regular),
            (2, f"◆ {phase.name}" if phase.milestone else phase.name, align_left, font_bold if phase.milestone else font_regular),
            (3, deps_str, align_center, font_regular),
            (4, f"Н{phase.start_week}", align_center, font_regular),
            (5, "Веха" if phase.milestone else f"{phase.duration_weeks} нед.", align_center, font_regular),
            (6, f"Н{finish_week}", align_center, font_regular),
        ]
        for col_idx, val, al, fnt in row_vals:
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.alignment = al
            cell.font = fnt
            cell.border = thin_border
            if phase.milestone:
                cell.fill = milestone_fill

        bar_hex = GROUP_EXCEL_COLORS.get(grp, "3B82F6")
        bar_fill = PatternFill(start_color=bar_hex, end_color=bar_hex, fill_type="solid")

        for w in range(1, num_weeks + 1):
            col_idx = first_week_col + w - 1
            cw = ws.cell(row=current_row, column=col_idx)
            cw.border = thin_border
            if phase.milestone:
                cw.fill = milestone_fill
                if w == phase.start_week:
                    cw.value = "◆"
                    cw.alignment = align_center
                    cw.font = font_milestone
            else:
                if phase.start_week <= w <= finish_week:
                    cw.fill = bar_fill
                    if w == phase.start_week:
                        cw.value = f"{phase.duration_weeks}н"
                        cw.alignment = align_center
                        cw.font = font_bar

        c_nt = ws.cell(row=current_row, column=note_col, value=phase.note)
        c_nt.alignment = align_left
        c_nt.font = font_small
        c_nt.border = thin_border
        if phase.milestone:
            c_nt.fill = milestone_fill

        current_row += 1

    # Настройка ширины колонок
    ws.column_dimensions["A"].width = 7.0
    ws.column_dimensions["B"].width = 48
    ws.column_dimensions["C"].width = 13
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 13
    ws.column_dimensions["F"].width = 11
    for w in range(1, num_weeks + 1):
        col_letter = get_column_letter(first_week_col + w - 1)
        ws.column_dimensions[col_letter].width = 4.2
    ws.column_dimensions[get_column_letter(note_col)].width = 32

    ws.row_dimensions[tbl_start_row].height = 22
    ws.row_dimensions[sub_row].height = 20

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
