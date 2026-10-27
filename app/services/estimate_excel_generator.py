import datetime
import io
from collections import defaultdict
from typing import Dict, List
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import CalculationMethod, CostParameters, ProjectData, ProjectMode, SectionCostItem


def generate_estimate_excel(project_data: ProjectData) -> io.BytesIO:
    """
    Формирует официальную детализированную смету на проектно-изыскательские работы
    в формате Excel (.xlsx) с калькуляцией затрат, долями разделов и трудоемкостью.
    """
    cost_params = project_data.cost_parameters
    if not cost_params:
        from app.services.cost_estimator import init_cost_parameters
        cost_params = init_cost_parameters(project_data)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Смета ПИР"

    # Включаем сетку
    ws.views.sheetView[0].showGridLines = True

    # Цветовая палитра оформления
    navy_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    steel_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    light_hdr_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    subtle_row_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    total_fill = PatternFill(start_color="EAEEF7", end_color="EAEEF7", fill_type="solid")
    accent_green_fill = PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="595959")
    font_section_hdr = Font(name="Calibri", size=11, bold=True, color="1F4E79")
    font_tbl_hdr = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=9.5, bold=True)
    font_regular = Font(name="Calibri", size=9.5)
    font_small = Font(name="Calibri", size=8.5, italic=True)

    thin_border = Border(
        left=Side(style="thin", color="D3D3D3"),
        right=Side(style="thin", color="D3D3D3"),
        top=Side(style="thin", color="D3D3D3"),
        bottom=Side(style="thin", color="D3D3D3")
    )
    double_bottom_border = Border(
        left=Side(style="thin", color="B0C4DE"),
        right=Side(style="thin", color="B0C4DE"),
        top=Side(style="thin", color="B0C4DE"),
        bottom=Side(style="double", color="1F4E79")
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")

    num_format_currency = '#,##0.00\\ "₽"'
    num_format_percent = '0.00%'
    num_format_number = '#,##0.0'

    r = 1

    # 1. Шапка документа
    if project_data.mode == ProjectMode.CONTRACT:
        ws.cell(row=r, column=7, value="Приложение № 3").font = font_small
        ws.cell(
            row=r + 1,
            column=7,
            value=f"к договору № {project_data.contract_number or '______'} от {project_data.contract_date or '______'}"
        ).font = font_small
        r += 3

        # Блоки согласования
        ws.cell(row=r, column=2, value="СОГЛАСОВАНО:").font = font_bold
        ws.cell(row=r, column=7, value="УТВЕРЖДАЮ:").font = font_bold
        ws.cell(row=r + 1, column=2, value="Исполнитель").font = font_regular
        ws.cell(row=r + 1, column=7, value=project_data.contractor or project_data.customer or "Заказчик").font = font_regular
        ws.cell(row=r + 2, column=2, value="________________ / ____________ /").font = font_regular
        ws.cell(row=r + 2, column=7, value="________________ / ____________ /").font = font_regular
        r += 4

        ws.cell(row=r, column=1, value="СМЕТНЫЙ РАСЧЕТ СТОИМОСТИ ПРОЕКТНЫХ РАБОТ").font = font_title
    else:
        ws.cell(row=r, column=1, value="КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ / РАСЧЕТ СТОИМОСТИ ПИР").font = font_title

    r += 1
    ws.cell(row=r, column=1, value=f"Объект: {project_data.object_name}").font = font_subtitle
    r += 1
    if project_data.cipher:
        ws.cell(row=r, column=1, value=f"Базовый шифр документации: {project_data.cipher}").font = font_subtitle
        r += 1

    r += 1

    # 2. Таблица 1: Сводная смета по томам и разделам
    ws.cell(row=r, column=1, value="1. Сводный расчет распределения стоимости по разделам (ПП РФ № 87)").font = font_section_hdr
    r += 1

    headers = [
        ("№ п/п", 6, align_center),
        ("№ тома", 9, align_center),
        ("Шифр", 14, align_center),
        ("Наименование раздела / подраздела", 42, align_left),
        ("Ответственное подразделение", 24, align_left),
        ("Доля, %", 10, align_right),
        ("Трудоемкость, ч-д", 14, align_right),
        ("Стоимость без НДС", 18, align_right),
        ("Стоимость с НДС", 18, align_right),
    ]

    for col_idx, (hdr_text, _, align) in enumerate(headers, start=1):
        c = ws.cell(row=r, column=col_idx, value=hdr_text)
        c.fill = navy_fill
        c.font = font_tbl_hdr
        c.alignment = align
        c.border = thin_border
    ws.row_dimensions[r].height = 28
    r += 1

    table1_start_row = r
    item_num = 1

    # Сортируем тома: сначала активные
    for item in cost_params.sections_costs:
        if not item.enabled:
            continue

        c1 = ws.cell(row=r, column=1, value=item_num)
        c1.alignment = align_center

        c2 = ws.cell(row=r, column=2, value=item.volume_num)
        c2.alignment = align_center

        c3 = ws.cell(row=r, column=3, value=item.full_code or item.code_mark)
        c3.alignment = align_center
        c3.font = font_bold

        c4 = ws.cell(row=r, column=4, value=item.title)
        c4.alignment = align_left

        c5 = ws.cell(row=r, column=5, value=item.department)
        c5.alignment = align_left

        c6 = ws.cell(row=r, column=6, value=item.relative_share_percent / 100.0)
        c6.number_format = num_format_percent
        c6.alignment = align_right

        c7 = ws.cell(row=r, column=7, value=item.labor_days)
        c7.number_format = num_format_number
        c7.alignment = align_right

        c8 = ws.cell(row=r, column=8, value=item.cost_rub)
        c8.number_format = num_format_currency
        c8.alignment = align_right

        vat_k = 1.0 + (cost_params.vat_rate / 100.0) if cost_params.include_vat else 1.0
        c9 = ws.cell(row=r, column=9, value=round(item.cost_rub * vat_k, 2))
        c9.number_format = num_format_currency
        c9.alignment = align_right

        for c in (c1, c2, c3, c4, c5, c6, c7, c8, c9):
            c.border = thin_border
            c.font = font_regular if c not in (c3,) else font_bold
            if item_num % 2 == 0:
                c.fill = subtle_row_fill

        item_num += 1
        r += 1

    table1_end_row = r - 1

    # Строка ИТОГО ПО РАЗДЕЛАМ
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c_tot_label = ws.cell(row=r, column=1, value="ИТОГО ПО ВСЕМ РАЗДЕЛАМ ПРОЕКТА:")
    c_tot_label.font = font_bold
    c_tot_label.alignment = Alignment(horizontal="right", vertical="center")

    c_tot_pct = ws.cell(row=r, column=6, value=f"=SUM(F{table1_start_row}:F{table1_end_row})")
    c_tot_pct.number_format = num_format_percent
    c_tot_pct.alignment = align_right
    c_tot_pct.font = font_bold

    c_tot_days = ws.cell(row=r, column=7, value=f"=SUM(G{table1_start_row}:G{table1_end_row})")
    c_tot_days.number_format = num_format_number
    c_tot_days.alignment = align_right
    c_tot_days.font = font_bold

    c_tot_net = ws.cell(row=r, column=8, value=f"=SUM(H{table1_start_row}:H{table1_end_row})")
    c_tot_net.number_format = num_format_currency
    c_tot_net.alignment = align_right
    c_tot_net.font = font_bold

    c_tot_gross = ws.cell(row=r, column=9, value=f"=SUM(I{table1_start_row}:I{table1_end_row})")
    c_tot_gross.number_format = num_format_currency
    c_tot_gross.alignment = align_right
    c_tot_gross.font = font_bold

    for col_i in range(1, 10):
        cell_i = ws.cell(row=r, column=col_i)
        cell_i.fill = total_fill
        cell_i.border = double_bottom_border

    r += 3

    # 3. Таблица 2: Структура ценообразования и себестоимости (Калькуляция затрат)
    ws.cell(row=r, column=1, value="2. Экономическая структура затрат и расчет договорной цены").font = font_section_hdr
    r += 1

    cost_breakdown_headers = [
        ("№", 6, align_center),
        ("Статья затрат / Элемент ценообразования", 52, align_left),
        ("База / Параметр", 24, align_left),
        ("Сумма без НДС, руб.", 18, align_right),
    ]

    for col_idx, (hdr_text, _, align) in enumerate(cost_breakdown_headers, start=1):
        c = ws.cell(row=r, column=col_idx, value=hdr_text)
        c.fill = steel_fill
        c.font = font_tbl_hdr
        c.alignment = align
        c.border = thin_border
    ws.row_dimensions[r].height = 24
    r += 1

    cost_items_data = [
        ("1", "Прямые затраты на оплату труда специалистов (ФОТ)", f"{cost_params.total_labor_days} ч-д @ {cost_params.average_daily_rate_rub:,.0f} ₽/д", cost_params.direct_labor_cost_rub, False),
        ("2", f"Накладные расходы организации ({cost_params.overhead_percent}%)", "Аренда, ПО, CAD/BIM лицензии, ЕСН", cost_params.overhead_rub, False),
        ("3", "Полная производственная себестоимость", "Статьи (1 + 2)", cost_params.direct_labor_cost_rub + cost_params.overhead_rub, True),
        ("4", f"Сметная нормативная прибыль ({cost_params.profit_percent}%)", "Развитие производства, резервы", cost_params.profit_rub, False),
    ]

    if cost_params.is_reconstruction:
        cost_items_data.append(("5.1", "Коэффициент реконструкции / стесненности", "К = 1.20 (по нормативам)", cost_params.total_cost_net_rub * 0.20, False))

    if cost_params.use_bim:
        cost_items_data.append(("5.2", "Коэффициент применения ТИМ/BIM технологий", "К = 1.15 (цифровая модель)", cost_params.total_cost_net_rub * 0.15, False))

    cost_items_data.append(("6", "ИТОГО СТОИМОСТЬ ПРОЕКТНЫХ РАБОТ БЕЗ НДС", "Базовая цена договора", cost_params.total_cost_net_rub, True))

    if cost_params.include_vat:
        cost_items_data.append(("7", f"Налог на добавленную стоимость (НДС {cost_params.vat_rate}%)", f"Налоговая ставка {cost_params.vat_rate:g}%", cost_params.vat_rub, False))
        cost_items_data.append(("8", "ВСЕГО СТОИМОСТЬ С УЧЕТОМ НДС (К ОПЛАТЕ)", "ИТОГО ПО ДОГОВОРУ", cost_params.total_cost_gross_rub, True))
    else:
        cost_items_data.append(("7", "НДС не облагается (УСН)", "Без налога", 0.0, False))

    for idx, name, desc, amount, is_bold in cost_items_data:
        c1 = ws.cell(row=r, column=1, value=idx)
        c1.alignment = align_center

        c2 = ws.cell(row=r, column=2, value=name)
        c2.alignment = align_left

        c3 = ws.cell(row=r, column=3, value=desc)
        c3.alignment = align_left

        c4 = ws.cell(row=r, column=4, value=amount)
        c4.number_format = num_format_currency
        c4.alignment = align_right

        for c in (c1, c2, c3, c4):
            c.border = thin_border
            if is_bold:
                c.font = font_bold
                c.fill = accent_green_fill if "ВСЕГО" in name or "ИТОГО" in name else light_hdr_fill
            else:
                c.font = font_regular

        r += 1

    r += 2

    # 4. Таблица 3: Сводка по отделам-исполнителям
    ws.cell(row=r, column=1, value="3. Распределение трудоемкости и бюджета по проектным подразделениям").font = font_section_hdr
    r += 1

    dep_headers = [
        ("№", 6, align_center),
        ("Подразделение / Отдел", 36, align_left),
        ("Кол-во томов", 14, align_center),
        ("Трудоемкость, ч-д", 16, align_right),
        ("Бюджет отдела, руб.", 20, align_right),
        ("Доля в проекте, %", 16, align_right),
    ]

    for col_idx, (hdr_text, _, align) in enumerate(dep_headers, start=1):
        c = ws.cell(row=r, column=col_idx, value=hdr_text)
        c.fill = steel_fill
        c.font = font_tbl_hdr
        c.alignment = align
        c.border = thin_border
    ws.row_dimensions[r].height = 24
    r += 1

    # Группируем по отделам
    dep_summary: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "days": 0.0, "cost": 0.0, "pct": 0.0})
    for it in cost_params.sections_costs:
        if it.enabled:
            dep = it.department or "Проектный отдел"
            dep_summary[dep]["count"] += 1
            dep_summary[dep]["days"] += it.labor_days
            dep_summary[dep]["cost"] += it.cost_rub
            dep_summary[dep]["pct"] += it.relative_share_percent

    dep_idx = 1
    for dep_name, vals in sorted(dep_summary.items(), key=lambda x: x[1]["cost"], reverse=True):
        c1 = ws.cell(row=r, column=1, value=dep_idx)
        c1.alignment = align_center

        c2 = ws.cell(row=r, column=2, value=dep_name)
        c2.alignment = align_left

        c3 = ws.cell(row=r, column=3, value=vals["count"])
        c3.alignment = align_center

        c4 = ws.cell(row=r, column=4, value=vals["days"])
        c4.number_format = num_format_number
        c4.alignment = align_right

        c5 = ws.cell(row=r, column=5, value=vals["cost"])
        c5.number_format = num_format_currency
        c5.alignment = align_right

        c6 = ws.cell(row=r, column=6, value=vals["pct"] / 100.0)
        c6.number_format = num_format_percent
        c6.alignment = align_right

        for c in (c1, c2, c3, c4, c5, c6):
            c.border = thin_border
            c.font = font_regular

        dep_idx += 1
        r += 1

    r += 3

    # Подписи
    ws.cell(row=r, column=2, value="Главный инженер проекта (ГИП):").font = font_bold
    ws.cell(row=r, column=5, value="____________________ / ____________________ /").font = font_regular
    r += 2
    ws.cell(row=r, column=2, value="Начальник сметно-договорного отдела:").font = font_bold
    ws.cell(row=r, column=5, value="____________________ / ____________________ /").font = font_regular
    r += 2

    # Настройка ширины колонок
    for col_idx, (_, col_width, _) in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = col_width

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
