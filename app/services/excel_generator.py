import datetime
import io
from typing import List
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from app.models import ProjectData, ProjectMode, SchedulePhase


def generate_excel_schedule(project_data: ProjectData) -> io.BytesIO:
    """
    Генерирует профессиональный Календарный график выполнения работ в Excel (.xlsx)
    с визуализацией диаграммы Ганта по месяцам.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "График работ"

    # Включаем сетку
    ws.views.sheetView[0].showGridLines = True

    # Цветовая палитра
    navy_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    steel_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    light_hdr_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    gantt_bar_fill = PatternFill(start_color="41719C", end_color="41719C", fill_type="solid")
    gantt_accent_fill = PatternFill(start_color="5B9BD5", end_color="5B9BD5", fill_type="solid")
    category_fill = PatternFill(start_color="F2F4F7", end_color="F2F4F7", fill_type="solid")

    font_title = Font(name="Calibri", size=13, bold=True, color="1F4E79")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_regular = Font(name="Calibri", size=9.5)
    font_small = Font(name="Calibri", size=8.5, italic=True)
    font_white_bold = Font(name="Calibri", size=9.5, bold=True, color="FFFFFF")
    font_bar = Font(name="Calibri", size=9, bold=True, color="FFFFFF")

    thin_border = Border(
        left=Side(style="thin", color="B0C4DE"),
        right=Side(style="thin", color="B0C4DE"),
        top=Side(style="thin", color="B0C4DE"),
        bottom=Side(style="thin", color="B0C4DE")
    )
    thick_bottom = Border(bottom=Side(style="medium", color="1F4E79"))

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # Определяем общее количество месяцев (длительность)
    max_month = max((p.start_month + p.duration_months - 1 for p in project_data.schedule_phases), default=8)
    num_months = max(max_month, project_data.total_months, 8)

    current_row = 1

    # 1. Шапка документа
    if project_data.mode == ProjectMode.CONTRACT:
        # Режим договора
        ws.cell(row=current_row, column=num_months + 3, value=f"Приложение № 2").font = font_small
        ws.cell(row=current_row + 1, column=num_months + 3, value=f"к договору {project_data.contract_number or '____'} от {project_data.contract_date or '___'}").font = font_small
        current_row += 3

        # Блок подписей
        ws.cell(row=current_row, column=2, value="СОГЛАСОВАНО:").font = font_bold
        ws.cell(row=current_row, column=num_months + 1, value="УТВЕРЖДАЮ:").font = font_bold

        sub_name = project_data.subcontractor or "Проектная организация"
        contr_name = project_data.contractor or "Заказчик"

        ws.cell(row=current_row + 1, column=2, value=f"Руководитель {sub_name}").font = font_regular
        ws.cell(row=current_row + 1, column=num_months + 1, value=f"Руководитель {contr_name}").font = font_regular

        ws.cell(row=current_row + 2, column=2, value="________________ / ___________ /").font = font_regular
        ws.cell(row=current_row + 2, column=num_months + 1, value="________________ / ___________ /").font = font_regular
        current_row += 4
    else:
        # Режим КП
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_months + 3)
        c_title = ws.cell(row=current_row, column=1, value="ПРОЕКТ КАЛЕНДАРНОГО ГРАФИКА ВЫПОЛНЕНИЯ РАБОТ")
        c_title.font = font_title
        c_title.alignment = align_center
        current_row += 2

    # Заголовок графика и объект
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_months + 3)
    c_obj = ws.cell(row=current_row, column=1, value=f"Объект: {project_data.object_name}")
    c_obj.font = Font(name="Calibri", size=11, bold=True, color="2F5597")
    c_obj.alignment = align_left
    current_row += 2

    # 2. Табличная шапка графика (Двухуровневая)
    tbl_start_row = current_row

    # Ячейка № (строки tbl_start_row и tbl_start_row + 1)
    ws.merge_cells(start_row=tbl_start_row, start_column=1, end_row=tbl_start_row + 1, end_column=1)
    c_num = ws.cell(row=tbl_start_row, column=1, value="№ п/п")
    c_num.fill = steel_fill
    c_num.font = font_white_bold
    c_num.alignment = align_center

    # Ячейка Наименование
    ws.merge_cells(start_row=tbl_start_row, start_column=2, end_row=tbl_start_row + 1, end_column=2)
    c_name = ws.cell(row=tbl_start_row, column=2, value="Наименование мероприятия (этапа работ)")
    c_name.fill = steel_fill
    c_name.font = font_white_bold
    c_name.alignment = align_center

    # Блок месяцев
    ws.merge_cells(start_row=tbl_start_row, start_column=3, end_row=tbl_start_row, end_column=num_months + 2)
    c_period = ws.cell(row=tbl_start_row, column=3, value="Сроки выполнения (месяцы с момента начала работ)")
    c_period.fill = steel_fill
    c_period.font = font_white_bold
    c_period.alignment = align_center

    # Ячейка Примечание
    ws.merge_cells(start_row=tbl_start_row, start_column=num_months + 3, end_row=tbl_start_row + 1, end_column=num_months + 3)
    c_note = ws.cell(row=tbl_start_row, column=num_months + 3, value="Примечание")
    c_note.fill = steel_fill
    c_note.font = font_white_bold
    c_note.alignment = align_center

    # Подшапка для каждого месяца
    sub_row = tbl_start_row + 1
    for m in range(1, num_months + 1):
        col_idx = m + 2
        col_cell = ws.cell(row=sub_row, column=col_idx)
        if project_data.mode == ProjectMode.CONTRACT and project_data.start_date:
            try:
                # Рассчитываем примерную дату окончания месяца (например 31.10, 30.11...)
                dt = datetime.datetime.strptime(project_data.start_date, "%Y-%m-%d")
                month_dt = dt + datetime.timedelta(days=(m - 1) * 30.5)
                col_cell.value = f"{m} мес\n({month_dt.strftime('%m.%y')})"
            except Exception:
                col_cell.value = f"М{m}"
        else:
            col_cell.value = f"{m} мес"

        col_cell.fill = light_hdr_fill
        col_cell.font = font_bold
        col_cell.alignment = align_center

    # Оформляем границы шапки
    for r in range(tbl_start_row, tbl_start_row + 2):
        for col in range(1, num_months + 4):
            ws.cell(row=r, column=col).border = thin_border

    current_row = tbl_start_row + 2

    # 3. Раздел "ПИР (Проектно-изыскательские работы)"
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=num_months + 3)
    c_sec = ws.cell(row=current_row, column=1, value="ПИР (Проектно-изыскательские работы)")
    c_sec.fill = category_fill
    c_sec.font = Font(name="Calibri", size=10, bold=True, color="1F4E79")
    c_sec.alignment = align_left
    for col in range(1, num_months + 4):
        ws.cell(row=current_row, column=col).border = thin_border
    current_row += 1

    # 4. Вывод этапов работ
    for idx, phase in enumerate(project_data.schedule_phases, start=1):
        # Номер
        c_i = ws.cell(row=current_row, column=1, value=idx)
        c_i.alignment = align_center
        c_i.font = font_regular
        c_i.border = thin_border

        # Название этапа
        c_n = ws.cell(row=current_row, column=2, value=phase.name)
        c_n.alignment = align_left
        c_n.font = font_regular
        c_n.border = thin_border

        # Отрисовка полосы Ганта по месяцам
        phase_start = phase.start_month
        phase_end = phase.start_month + phase.duration_months - 1

        for m in range(1, num_months + 1):
            col_idx = m + 2
            cell_m = ws.cell(row=current_row, column=col_idx)
            cell_m.border = thin_border

            if phase_start <= m <= phase_end:
                cell_m.fill = gantt_bar_fill
                # В первом месяце полосы можно поставить индикатор длительности
                if m == phase_start:
                    cell_m.value = f"●"
                    cell_m.alignment = align_center
                    cell_m.font = font_bar

        # Примечание
        c_nt = ws.cell(row=current_row, column=num_months + 3, value=phase.note)
        c_nt.alignment = align_left
        c_nt.font = font_small
        c_nt.border = thin_border

        current_row += 1

    # Настройка ширины колонок
    ws.column_dimensions["A"].width = 7
    ws.column_dimensions["B"].width = 52
    for m in range(1, num_months + 1):
        col_letter = get_column_letter(m + 2)
        ws.column_dimensions[col_letter].width = 9.5
    note_col = get_column_letter(num_months + 3)
    ws.column_dimensions[note_col].width = 38

    # Настройка высоты строк шапки
    ws.row_dimensions[tbl_start_row].height = 24
    ws.row_dimensions[tbl_start_row + 1].height = 24

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
