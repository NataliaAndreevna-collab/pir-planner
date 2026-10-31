import io
from collections import defaultdict
from typing import Dict
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import CalculationMethod, ProjectData, ProjectMode


METHOD_LABELS = {
    CalculationMethod.BY_COLLECTIONS: "По сборникам базовых цен (МНЗ / СБЦП Минстроя РФ)",
    CalculationMethod.LABOR_707: "По трудозатратам специалистов (Форма 3П — по Методике Минстроя РФ № 707/пр)",
    CalculationMethod.LABOR_INTERNAL: "По трудозатратам специалистов (Форма 3П — внутренний справочник ставок)",
    CalculationMethod.FROM_SMR: "От стоимости строительства (СМР) по Таблице 1.5 Приложения № 2 Методики № 707/пр",
    CalculationMethod.PERCENT_SHARE: "По нормативным долям разделов ПП РФ № 87",
    CalculationMethod.LABOR_EFFORT: "По общей трудоёмкости разработки разделов",
}


def generate_estimate_excel(project_data: ProjectData) -> io.BytesIO:
    """
    Формирует официальную детализированную смету на проектно-изыскательские работы
    в формате Excel (.xlsx) на 3 листах:
    1) «Смета ПИР» — расчёт по сборникам МНЗ/СБЦП (по форме Методики № 707/пр), распределение по разделам ПД/РД и сводка с НДС;
    2) «Форма 3П (Трудозатраты)» — калькуляция затрат по категориям специалистов (Методика № 707/пр или внутренний справочник);
    3) «Бюджет по отделам» — распределение трудоёмкости и стоимости по проектным подразделениям.
    """
    cost_params = project_data.cost_parameters
    if not cost_params:
        from app.services.cost_estimator import init_cost_parameters
        cost_params = init_cost_parameters(project_data)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Смета ПИР"
    ws.views.sheetView[0].showGridLines = True

    # Цветовая палитра оформления
    navy_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    steel_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    teal_fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    light_hdr_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    subtle_row_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    total_fill = PatternFill(start_color="EAEEF7", end_color="EAEEF7", fill_type="solid")
    accent_green_fill = PatternFill(start_color="E2F0D9", end_color="E2F0D9", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="1F4E79")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="595959")
    font_section_hdr = Font(name="Calibri", size=11, bold=True, color="1F4E79")
    font_tbl_hdr = Font(name="Calibri", size=9.5, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=9.5, bold=True)
    font_regular = Font(name="Calibri", size=9.5)
    font_small = Font(name="Calibri", size=8.5, italic=True)

    thin_border = Border(
        left=Side(style="thin", color="D3D3D3"),
        right=Side(style="thin", color="D3D3D3"),
        top=Side(style="thin", color="D3D3D3"),
        bottom=Side(style="thin", color="D3D3D3"),
    )
    double_bottom_border = Border(
        left=Side(style="thin", color="B0C4DE"),
        right=Side(style="thin", color="B0C4DE"),
        top=Side(style="thin", color="B0C4DE"),
        bottom=Side(style="double", color="1F4E79"),
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")

    num_format_currency = '#,##0.00\\ "₽"'
    num_format_percent = "0.00%"
    num_format_number = "#,##0.0"

    r = 1

    # 1. Шапка документа
    if project_data.mode == ProjectMode.CONTRACT:
        ws.cell(row=r, column=8, value="Приложение № 3").font = font_small
        ws.cell(
            row=r + 1,
            column=8,
            value=f"к договору № {project_data.contract_number or '______'} от {project_data.contract_date or '______'}",
        ).font = font_small
        r += 3

        ws.cell(row=r, column=2, value="СОГЛАСОВАНО:").font = font_bold
        ws.cell(row=r, column=7, value="УТВЕРЖДАЮ:").font = font_bold
        ws.cell(row=r + 1, column=2, value=project_data.contractor or "Исполнитель").font = font_regular
        ws.cell(row=r + 1, column=7, value=project_data.customer or "Заказчик").font = font_regular
        ws.cell(row=r + 2, column=2, value="________________ / ____________ /").font = font_regular
        ws.cell(row=r + 2, column=7, value="________________ / ____________ /").font = font_regular
        r += 4

        ws.cell(row=r, column=1, value="СМЕТНЫЙ РАСЧЁТ СТОИМОСТИ ПРОЕКТНЫХ И ИЗЫСКАТЕЛЬСКИХ РАБОТ").font = font_title
    else:
        ws.cell(row=r, column=1, value="КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ / РАСЧЁТ СТОИМОСТИ ПИР").font = font_title

    r += 1
    ws.cell(row=r, column=1, value=f"Наименование объекта: {project_data.object_name}").font = font_subtitle
    r += 1
    method_str = METHOD_LABELS.get(cost_params.calculation_method, str(cost_params.calculation_method))
    ws.cell(row=r, column=1, value=f"Методика расчёта: {method_str}").font = font_subtitle
    r += 1
    if project_data.cipher:
        ws.cell(row=r, column=1, value=f"Базовый шифр документации: {project_data.cipher}").font = font_subtitle
        r += 1
    for w_text in (getattr(cost_params, "warnings", None) or []):
        wc = ws.cell(row=r, column=1, value=f"ВНИМАНИЕ: {w_text}")
        wc.font = Font(name="Arial", size=10, bold=True, color="C00000")
        r += 1
    r += 1

    # 2. Таблица 1: Расчёт по сборникам базовых цен МНЗ / СБЦП (по форме Методики № 707/пр)
    active_col_items = [q for q in cost_params.collection_items if q.enabled]
    if active_col_items:
        ws.cell(
            row=r,
            column=1,
            value="1. Сметный расчёт стоимости работ по сборникам базовых цен (МНЗ / СБЦП Минстроя РФ)",
        ).font = font_section_hdr
        r += 1

        col_headers = [
            "№ п/п",
            "Нормативный документ (МНЗ / СБЦП)",
            "Наименование объекта / вида работ",
            "Показатель X",
            "Формула расчёта и коэффициенты",
            "Уровень базовых цен",
            "Базовая цена, руб.",
            "Индекс Минстроя",
            "Стоимость в текущих ценах без НДС, руб.",
        ]
        for c_i, h_text in enumerate(col_headers, 1):
            c = ws.cell(row=r, column=c_i, value=h_text)
            c.fill = teal_fill
            c.font = font_tbl_hdr
            c.alignment = align_center
            c.border = thin_border
        ws.row_dimensions[r].height = 28
        r += 1

        for idx_q, q in enumerate(active_col_items, 1):
            vals = [
                (idx_q, align_center, None),
                (q.collection_code or q.collection_id, align_left, None),
                (q.item_name, align_left, None),
                (f"{q.x_value:g} {q.unit}" if q.x_value > 0 else "НЕ ЗАДАН", align_center, None),
                (q.formula_text, align_left, None),
                (f"01.01.{q.price_level_year}", align_center, None),
                (q.base_cost_rub, align_right, num_format_currency),
                (q.index_applied, align_center, "0.00"),
                (q.current_cost_rub, align_right, num_format_currency),
            ]
            for c_i, (v, al, nf) in enumerate(vals, 1):
                cell = ws.cell(row=r, column=c_i, value=v)
                cell.alignment = al
                cell.border = thin_border
                cell.font = font_bold if c_i == 9 else font_regular
                if nf:
                    cell.number_format = nf
                if idx_q % 2 == 0:
                    cell.fill = subtle_row_fill
            ws.row_dimensions[r].height = 26
            r += 1

        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        c_lbl = ws.cell(row=r, column=1, value="ИТОГО ПО СБОРНИКАМ БАЗОВЫХ ЦЕН (БЕЗ НДС):")
        c_lbl.font = font_bold
        c_lbl.alignment = align_right
        c_sum = ws.cell(row=r, column=9, value=round(sum(q.current_cost_rub for q in active_col_items), 2))
        c_sum.font = font_bold
        c_sum.alignment = align_right
        c_sum.number_format = num_format_currency
        for col_i in range(1, 10):
            ws.cell(row=r, column=col_i).fill = total_fill
            ws.cell(row=r, column=col_i).border = double_bottom_border
        r += 3

    # 3. Таблица распределения стоимости по разделам проекта (ПП РФ № 87 / ГОСТ Р 21.101)
    mode_split_note = (
        "раздельно по стадиям П и Р"
        if cost_params.split_pd_rd_in_cost
        else "единым комплектом по разделам проекта"
    )
    ws.cell(
        row=r,
        column=1,
        value=f"2. Распределение стоимости и трудоёмкости по разделам проекта ({mode_split_note})",
    ).font = font_section_hdr
    r += 1

    headers = [
        ("№ п/п", 6, align_center),
        ("Стадия", 10, align_center),
        ("Шифр / Том", 15, align_center),
        ("Наименование раздела / основного комплекта", 42, align_left),
        ("Ответственное подразделение", 24, align_left),
        ("Доля, %", 10, align_right),
        ("Трудоёмкость, ч-д", 14, align_right),
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
    vat_k = 1.0 + (cost_params.vat_rate / 100.0) if cost_params.include_vat else 1.0

    for item in cost_params.sections_costs:
        if not item.enabled:
            continue

        c1 = ws.cell(row=r, column=1, value=item_num)
        c1.alignment = align_center

        c2 = ws.cell(row=r, column=2, value=getattr(item, "stage", "П+Р"))
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

    table1_end_row = max(r - 1, table1_start_row)

    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    c_tot_label = ws.cell(row=r, column=1, value="ИТОГО ПО РАЗДЕЛАМ ПРОЕКТА (ОСНОВНЫЕ ПИР):")
    c_tot_label.font = font_bold
    c_tot_label.alignment = align_right

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

    # 4. Итоговая сводная ведомость договорной цены (включая дополнительные работы и НДС)
    ws.cell(row=r, column=1, value="3. Итоговая сводная ведомость стоимости работ").font = font_section_hdr
    r += 1

    cost_breakdown_headers = [
        ("№", align_center),
        ("Статья затрат / Вид работ", align_left),
        ("Обоснование / Примечание", align_left),
        ("Сумма без НДС, руб.", align_right),
    ]
    for col_idx, (hdr_text, align) in enumerate(cost_breakdown_headers, start=1):
        c = ws.cell(row=r, column=col_idx, value=hdr_text)
        c.fill = steel_fill
        c.font = font_tbl_hdr
        c.alignment = align
        c.border = thin_border
    ws.row_dimensions[r].height = 24
    r += 1

    cost_items_data = [
        ("1", "Основные проектные работы (ПД / РД)", method_str, cost_params.pir_only_cost_net_rub or cost_params.total_cost_net_rub, True),
    ]

    add_idx = 1
    for aw in cost_params.additional_works:
        if aw.enabled and aw.cost_net_rub > 0:
            cost_items_data.append((f"2.{add_idx}", aw.name, aw.note or "Дополнительный вид работ", aw.cost_net_rub, False))
            add_idx += 1

    cost_items_data.append(("3", "ИТОГО СТОИМОСТЬ РАБОТ БЕЗ НДС", "Договорная цена без налога", cost_params.total_cost_net_rub, True))

    if cost_params.include_vat:
        cost_items_data.append(
            ("4", f"Налог на добавленную стоимость (НДС {cost_params.vat_rate:g}%)", f"Ставка НДС {cost_params.vat_rate:g}%", cost_params.vat_rub, False)
        )
        cost_items_data.append(("5", "ВСЕГО СТОИМОСТЬ С УЧЁТОМ НДС (К ОПЛАТЕ)", "ИТОГО ПО ДОГОВОРУ / КП", cost_params.total_cost_gross_rub, True))
    else:
        cost_items_data.append(("4", "НДС не облагается", "Без НДС", 0.0, False))

    if cost_params.smr_cost_mln_rub > 0:
        cost_items_data.append(
            (
                "Справ.",
                f"Справочно: лимит ПИР от стоимости строительства (СМР = {cost_params.smr_cost_mln_rub:g} млн ₽)",
                f"Табл. 1.5 Прил. 2 Методики № 707/пр ({cost_params.smr_normative_pct:g}%)",
                cost_params.smr_reference_pir_cost_rub,
                False,
            )
        )

    for idx_str, name, desc, amount, is_bold in cost_items_data:
        c1 = ws.cell(row=r, column=1, value=idx_str)
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

    r += 3
    ws.cell(row=r, column=2, value="Главный инженер проекта (ГИП):").font = font_bold
    ws.cell(row=r, column=5, value="____________________ / ____________________ /").font = font_regular
    r += 2
    ws.cell(row=r, column=2, value="Начальник сметно-договорного отдела:").font = font_bold
    ws.cell(row=r, column=5, value="____________________ / ____________________ /").font = font_regular

    for col_idx, (_, col_width, _) in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = col_width

    # =========================================================================
    # ЛИСТ 2: ФОРМА 3П (МЕТОДИКА № 707/пр — ОТ СРЕДНЕМЕСЯЧНОЙ ЗП И ТАБЛ. 1.3)
    # =========================================================================
    ws_707 = wb.create_sheet(title="Форма 3П (Методика 707-пр)")
    ws_707.views.sheetView[0].showGridLines = True

    ws_707.cell(row=1, column=1, value="РАСЧЁТ СТОИМОСТИ ПО ТРУДОЗАТРАТАМ ПО МЕТОДИКЕ МИНСТРОЯ РФ № 707/пр (ФОРМА 3П)").font = font_title
    ws_707.cell(row=2, column=1, value=f"Объект: {project_data.object_name}").font = font_subtitle
    ws_707.cell(
        row=3,
        column=1,
        value=(
            f"п. 143–149, ф. (8.12)–(8.14): ЗП_мес = {cost_params.regional_monthly_salary_707:,.0f} ₽, "
            f"Д_раб = {cost_params.work_days_707:g} дн., К_3 = {cost_params.k3_salary_share_707:g} (Табл. 1.1), "
            f"Р = {cost_params.profitability_707*100:g}% (Табл. 1.2) -> В_ср = {cost_params.v_sr_707_rub:,.2f} ₽/дн."
        ),
    ).font = font_subtitle

    headers_707 = [
        ("№ п/п", 8),
        ("Должность исполнителя (Табл. 1.3 Прил. 2 № 707/пр)", 46),
        ("Подразделение", 28),
        ("Ч_i (кол-во спец.)", 16),
        ("Т_фi (дней на 1 спец.)", 18),
        ("Ч_i × Т_фi, чел.-дн.", 18),
        ("Индекс И_i (Табл. 1.3)", 18),
        ("Привед. чел.-дн. (Ч_i×Т_фi×И_i)", 22),
        ("Стоимость (В_ср×прив.дн.×К), ₽", 24),
    ]
    r7 = 5
    for c_i, (h_txt, w_col) in enumerate(headers_707, 1):
        c = ws_707.cell(row=r7, column=c_i, value=h_txt)
        c.fill = navy_fill
        c.font = font_tbl_hdr
        c.alignment = align_center
        c.border = thin_border
        ws_707.column_dimensions[get_column_letter(c_i)].width = w_col
    ws_707.row_dimensions[r7].height = 28
    r7 += 1

    for idx_7, r_row in enumerate([x for x in cost_params.labor_707_rows if x.enabled], 1):
        row_vals = [
            (idx_7, align_center, None),
            (r_row.role_name, align_left, None),
            (r_row.department, align_left, None),
            (r_row.count, align_center, None),
            (r_row.days, align_right, num_format_number),
            (r_row.total_days, align_right, num_format_number),
            (r_row.index_i, align_center, "0.00"),
            (r_row.weighted_days, align_right, "0.00"),
            (r_row.cost_rub, align_right, num_format_currency),
        ]
        for c_i, (val, al, nf) in enumerate(row_vals, 1):
            c = ws_707.cell(row=r7, column=c_i, value=val)
            c.alignment = al
            c.border = thin_border
            c.font = font_bold if c_i == 9 else font_regular
            if nf:
                c.number_format = nf
        r7 += 1

    r7 += 1
    summary_707 = [
        ("Среднедневная выработка 1 специалиста В_ср, ₽/чел.-дн.:", cost_params.v_sr_707_rub, num_format_currency),
        ("Суммарные трудозатраты ∑(Ч_i × Т_фi), чел.-дн.:", cost_params.labor_707_total_days, num_format_number),
        ("Коэффициент квалификации-участия К_кв-уч = ∑(Ч_i×Т_фi×И_i) / ∑(Ч_i×Т_фi):", cost_params.k_kv_uch_707, "0.0000"),
        ("ИТОГО независимый расчёт по Методике № 707/пр (без НДС), ₽:", cost_params.labor_707_total_net_rub, num_format_currency),
    ]
    for lbl, val, nf_s in summary_707:
        ws_707.merge_cells(start_row=r7, start_column=1, end_row=r7, end_column=8)
        c_l = ws_707.cell(row=r7, column=1, value=lbl)
        c_l.alignment = align_right
        c_l.font = font_bold
        c_v = ws_707.cell(row=r7, column=9, value=val)
        c_v.alignment = align_right
        c_v.font = font_bold
        c_v.number_format = nf_s
        r7 += 1

    # =========================================================================
    # ЛИСТ 3: КАЛЬКУЛЯЦИЯ ПО ТАБЛИЦЕ РЫНОЧНОЙ СТОИМОСТИ СПЕЦИАЛИСТОВ (ТЮМЕНЬ)
    # =========================================================================
    ws_3p = wb.create_sheet(title="Рыночная калькуляция (Тюмень)")
    ws_3p.views.sheetView[0].showGridLines = True

    ws_3p.cell(row=1, column=1, value="КОММЕРЧЕСКАЯ КАЛЬКУЛЯЦИЯ ПО ТАБЛИЦЕ РЫНОЧНОЙ СТОИМОСТИ СПЕЦИАЛИСТОВ (г. ТЮМЕНЬ)").font = font_title
    ws_3p.cell(row=2, column=1, value=f"Объект: {project_data.object_name}").font = font_subtitle
    ws_3p.cell(
        row=3,
        column=1,
        value=f"Независимый коммерческий расчёт от рыночных окладов специалистов (Д_раб = {cost_params.work_days_per_month:g} дн., НР = {cost_params.overhead_percent:g}%, СП = {cost_params.profit_percent:g}%)",
    ).font = font_subtitle

    headers_3p = [
        ("№ п/п", 8),
        ("Должность / категория исполнителя", 44),
        ("Подразделение", 28),
        ("Кол-во спец., чел.", 16),
        ("Трудоёмкость на 1 спец., дн.", 18),
        ("Всего чел.-дней", 16),
        ("Рыночный оклад, ₽/мес.", 20),
        ("Дневная ставка, ₽/дн.", 18),
        ("Прямой ФОТ, ₽", 20),
    ]
    r3 = 5
    for c_i, (h_txt, w_col) in enumerate(headers_3p, 1):
        c = ws_3p.cell(row=r3, column=c_i, value=h_txt)
        c.fill = navy_fill
        c.font = font_tbl_hdr
        c.alignment = align_center
        c.border = thin_border
        ws_3p.column_dimensions[get_column_letter(c_i)].width = w_col
    ws_3p.row_dimensions[r3].height = 28
    r3 += 1

    for idx_s, s_row in enumerate([s for s in cost_params.specialist_rows if s.enabled], 1):
        row_vals = [
            (idx_s, align_center, None),
            (s_row.role_name, align_left, None),
            (s_row.department, align_left, None),
            (s_row.count, align_center, None),
            (s_row.days, align_right, num_format_number),
            (s_row.total_days, align_right, num_format_number),
            (s_row.monthly_salary_rub, align_right, num_format_currency),
            (s_row.daily_rate_rub, align_right, num_format_currency),
            (s_row.total_wage_rub, align_right, num_format_currency),
        ]
        for c_i, (val, al, nf) in enumerate(row_vals, 1):
            c = ws_3p.cell(row=r3, column=c_i, value=val)
            c.alignment = al
            c.border = thin_border
            c.font = font_bold if c_i == 9 else font_regular
            if nf:
                c.number_format = nf
        r3 += 1

    r3 += 1
    summary_3p = [
        ("Прямые затраты на оплату труда исполнителей (ФОТ):", cost_params.labor_market_direct_wage_rub),
        (f"Накладные расходы организации ({cost_params.overhead_percent:g}%):", cost_params.labor_market_overhead_rub),
        (f"Сметная прибыль ({cost_params.profit_percent:g}%):", cost_params.labor_market_profit_rub),
        ("ИТОГО независимый рыночный расчёт по специалистам (без НДС):", cost_params.labor_market_total_net_rub),
    ]
    for lbl, val in summary_3p:
        ws_3p.merge_cells(start_row=r3, start_column=1, end_row=r3, end_column=8)
        c_l = ws_3p.cell(row=r3, column=1, value=lbl)
        c_l.alignment = align_right
        c_l.font = font_bold
        c_v = ws_3p.cell(row=r3, column=9, value=val)
        c_v.alignment = align_right
        c_v.font = font_bold
        c_v.number_format = num_format_currency
        r3 += 1

    # =========================================================================
    # ЛИСТ 3: БЮДЖЕТ ПО ПРОЕКТНЫМ ОТДЕЛАМ
    # =========================================================================
    ws_dep = wb.create_sheet(title="Бюджет по отделам")
    ws_dep.views.sheetView[0].showGridLines = True
    ws_dep.cell(row=1, column=1, value="РАСПРЕДЕЛЕНИЕ ТРУДОЁМКОСТИ И БЮДЖЕТА ПО ПРОЕКТНЫМ ПОДРАЗДЕЛЕНИЯМ").font = font_title

    dep_headers = [
        ("№", 6, align_center),
        ("Подразделение / Отдел", 38, align_left),
        ("Кол-во разделов", 16, align_center),
        ("Трудоёмкость, ч-д", 18, align_right),
        ("Бюджет отдела без НДС, руб.", 22, align_right),
        ("Доля в проекте, %", 16, align_right),
    ]
    r_d = 3
    for col_idx, (hdr_text, w_col, align) in enumerate(dep_headers, start=1):
        c = ws_dep.cell(row=r_d, column=col_idx, value=hdr_text)
        c.fill = steel_fill
        c.font = font_tbl_hdr
        c.alignment = align
        c.border = thin_border
        ws_dep.column_dimensions[get_column_letter(col_idx)].width = w_col
    ws_dep.row_dimensions[r_d].height = 24
    r_d += 1

    dep_summary: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "days": 0.0, "cost": 0.0, "pct": 0.0})
    for it in cost_params.sections_costs:
        if it.enabled:
            dep = it.department or "Проектный отдел"
            dep_summary[dep]["count"] += 1
            dep_summary[dep]["days"] += it.labor_days
            dep_summary[dep]["cost"] += it.cost_rub
            dep_summary[dep]["pct"] += it.relative_share_percent

    for dep_idx, (dep_name, vals) in enumerate(sorted(dep_summary.items(), key=lambda x: x[1]["cost"], reverse=True), 1):
        c1 = ws_dep.cell(row=r_d, column=1, value=dep_idx)
        c1.alignment = align_center
        c2 = ws_dep.cell(row=r_d, column=2, value=dep_name)
        c2.alignment = align_left
        c3 = ws_dep.cell(row=r_d, column=3, value=vals["count"])
        c3.alignment = align_center
        c4 = ws_dep.cell(row=r_d, column=4, value=vals["days"])
        c4.number_format = num_format_number
        c4.alignment = align_right
        c5 = ws_dep.cell(row=r_d, column=5, value=vals["cost"])
        c5.number_format = num_format_currency
        c5.alignment = align_right
        c6 = ws_dep.cell(row=r_d, column=6, value=vals["pct"] / 100.0)
        c6.number_format = num_format_percent
        c6.alignment = align_right
        for c in (c1, c2, c3, c4, c5, c6):
            c.border = thin_border
            c.font = font_regular
        r_d += 1

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
