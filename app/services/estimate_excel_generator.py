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
    Формирует официальную смету на проектно-изыскательские работы в формате Excel (.xlsx)
    в строгом соответствии с унифицированной Формой № 2п (Приложение № 7 к Методике Минстроя РФ № 707/пр).
    
    Листы:
    1) «Смета ПИР (Форма 2п)» — 5-графная форма по Приложению № 7 к Методике № 707/пр (в тыс. руб. с 3 знаками);
    2) «Форма 3П (Трудозатраты)» — калькуляция затрат по категориям специалистов по Методике № 707/пр;
    3) «Бюджет по отделам» — распределение трудоёмкости и стоимости по проектным подразделениям.
    """
    cost_params = project_data.cost_parameters
    if not cost_params:
        from app.services.cost_estimator import init_cost_parameters
        cost_params = init_cost_parameters(project_data)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Смета ПИР (Форма 2п)"
    ws.views.sheetView[0].showGridLines = True

    # Стили оформления
    font_small = Font(name="Calibri", size=8.5, italic=True)
    font_title = Font(name="Calibri", size=12, bold=True)
    font_bold = Font(name="Calibri", size=9.5, bold=True)
    font_regular = Font(name="Calibri", size=9.5)
    font_tbl_hdr = Font(name="Calibri", size=9.5, bold=True)
    font_section = Font(name="Calibri", size=10, bold=True)

    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    section_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    total_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    thin_side = Side(style="thin", color="000000")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    double_bottom_border = Border(
        left=thin_side, right=thin_side, top=thin_side, bottom=Side(style="double", color="000000")
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")
    align_top_left = Alignment(horizontal="left", vertical="top", wrap_text=True)
    align_top_center = Alignment(horizontal="center", vertical="top", wrap_text=True)
    align_top_right = Alignment(horizontal="right", vertical="top")

    # Формат в тыс. руб. с 3 знаками после запятой: #,##0.000
    num_format_thous = "#,##0.000"

    r = 1

    # 1. Шапка документа: Ссылка на норматив
    ws.cell(row=r, column=4, value="Форма № 2п").font = font_bold
    ws.cell(row=r, column=4).alignment = align_right
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    r += 1

    ws.cell(row=r, column=4, value="Приложение № 7 к Методике определения стоимости работ").font = font_small
    ws.cell(row=r, column=4).alignment = align_right
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    r += 1

    ws.cell(row=r, column=4, value="по подготовке проектной документации, утв. приказом").font = font_small
    ws.cell(row=r, column=4).alignment = align_right
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    r += 1

    ws.cell(row=r, column=4, value="Минстроя России от 01.10.2021 № 707/пр").font = font_small
    ws.cell(row=r, column=4).alignment = align_right
    ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=5)
    r += 2

    # Грифы согласования и утверждения
    ws.cell(row=r, column=2, value="СОГЛАСОВАНО:").font = font_bold
    ws.cell(row=r, column=4, value="УТВЕРЖДАЮ:").font = font_bold
    r += 1

    ws.cell(row=r, column=2, value=project_data.contractor or "Исполнитель").font = font_regular
    ws.cell(row=r, column=4, value=project_data.customer or "Заказчик").font = font_regular
    r += 1

    ws.cell(row=r, column=2, value="________________ / ____________ /").font = font_regular
    ws.cell(row=r, column=4, value="________________ / ____________ /").font = font_regular
    r += 1

    ws.cell(row=r, column=2, value='"____" _______________ 20___ г.').font = font_small
    ws.cell(row=r, column=4, value='"____" _______________ 20___ г.').font = font_small
    r += 2

    # Заголовок сметы
    smeta_no = project_data.contract_number or "1"
    c_title = ws.cell(row=r, column=1, value=f"СМЕТА № {smeta_no}")
    c_title.font = font_title
    c_title.alignment = align_center
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    r += 1

    c_sub = ws.cell(row=r, column=1, value="на проектные и изыскательские работы")
    c_sub.font = font_bold
    c_sub.alignment = align_center
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    r += 2

    # Реквизиты объекта
    ws.cell(row=r, column=1, value="Наименование предприятия, здания, сооружения, стадии, вида работ:").font = font_bold
    ws.cell(row=r, column=2, value=project_data.object_name).font = font_regular
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    r += 1

    ws.cell(row=r, column=1, value="Наименование проектной (изыскательской) организации:").font = font_bold
    ws.cell(row=r, column=2, value=project_data.contractor or "—").font = font_regular
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    r += 1

    ws.cell(row=r, column=1, value="Наименование организации заказчика:").font = font_bold
    ws.cell(row=r, column=2, value=project_data.customer or "—").font = font_regular
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=5)
    r += 1

    warnings_list = getattr(cost_params, "warnings", None) or []
    if warnings_list:
        r += 1
        for w_text in warnings_list:
            wc = ws.cell(row=r, column=1, value=f"ВНИМАНИЕ: {w_text}")
            wc.font = Font(name="Calibri", size=9, bold=True, color="C00000")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
            r += 1
    r += 1

    # 2. Табличная часть Формы № 2п (5 граф)
    headers_2p = [
        ("№\nпп", 8, align_center),
        ("Характеристика предприятия,\nздания, сооружения или вид работ", 42, align_center),
        (
            "Номер частей, глав, таблиц, параграфов и пунктов\n"
            "указаний к разделу справочника базовых цен на\n"
            "проектные и изыскательские работы для строителей",
            36,
            align_center,
        ),
        (
            "Расчет стоимости: (a+bx)*Кj или\n"
            "(стоимость строительно-монтажных\n"
            "работ)*проц./ 100 или количество * цена,\n"
            "руб.",
            36,
            align_center,
        ),
        ("Стоимость\nработ, тыс.\nруб.", 20, align_center),
    ]

    for col_i, (h_text, _, al) in enumerate(headers_2p, start=1):
        cell = ws.cell(row=r, column=col_i, value=h_text.replace("\\n", "\n"))
        cell.font = font_tbl_hdr
        cell.alignment = al
        cell.border = thin_border
        cell.fill = header_fill
    ws.row_dimensions[r].height = 55
    r += 1

    # Строка с номерами граф 1 - 5
    for col_i in range(1, 6):
        cell = ws.cell(row=r, column=col_i, value=col_i)
        cell.font = font_bold
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = header_fill
    ws.row_dimensions[r].height = 20
    r += 1

    # 3. Раздел 1. Проектные работы
    ws.cell(row=r, column=1, value="Раздел 1. Проектные работы").font = font_section
    for col_i in range(1, 6):
        ws.cell(row=r, column=col_i).border = thin_border
        ws.cell(row=r, column=col_i).fill = section_fill
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    ws.row_dimensions[r].height = 22
    r += 1

    active_col_items = [q for q in cost_params.collection_items if q.enabled]
    item_idx = 1
    sum_pir_rub = 0.0

    for q in active_col_items:
        c1 = ws.cell(row=r, column=1, value=item_idx)
        c1.alignment = align_top_center

        name_lines = [q.source_description or q.custom_name or q.item_name]
        if q.x_value > 0:
            name_lines.append(f"Показатель X = {q.x_value:g} {q.unit}")
        c2 = ws.cell(row=r, column=2, value="\n".join(name_lines))
        c2.alignment = align_top_left

        norm_lines = [f"{q.collection_code or q.collection_id}, {q.item_name}"]
        if q.x_source == "min_default":
            norm_lines.append(f"(в ТЗ не указан, принят минимум X={q.x_value:g} {q.unit})")
        if q.stage_mode == "pd":
            norm_lines.append("Кстад = 0,40 (Стадия П)")
        elif q.stage_mode == "rd":
            norm_lines.append("Кстад = 0,60 (Стадия Р)")
        else:
            norm_lines.append("Кстад = 1,00 (Стадия П+Р)")
        if q.completeness_pct < 100.0:
            norm_lines.append(f"Кразд = {q.completeness_pct/100.0:g} (Полнота разделов {q.completeness_pct:g}%)")
        if q.k_coeff != 1.0:
            norm_lines.append(f"К1 = {q.k_coeff:g}")
        norm_lines.append(f"Кинф = {q.index_applied:g} (Индекс Минстроя РФ, цены 01.01.{q.price_level_year})")
        c3 = ws.cell(row=r, column=3, value="\n".join(norm_lines))
        c3.alignment = align_top_left

        calc_lines = []
        if q.formula_text and q.formula_text != q.warning:
            calc_lines.append(q.formula_text)
        else:
            calc_lines.append(f"Базовая цена: {q.base_cost_rub:,.2f} руб. × {q.index_applied:g}")
        calc_lines.append("(A + B*X) * Кстад * Кразд * Кинф")
        c4 = ws.cell(row=r, column=4, value="\n".join(calc_lines))
        c4.alignment = align_top_left

        cost_thous = round(q.current_cost_rub / 1000.0, 3)
        sum_pir_rub += q.current_cost_rub
        c5 = ws.cell(row=r, column=5, value=cost_thous)
        c5.number_format = num_format_thous
        c5.alignment = align_top_right
        c5.font = font_bold

        for c in (c1, c2, c3, c4, c5):
            c.border = thin_border
            if c != c5:
                c.font = font_regular

        ws.row_dimensions[r].height = max(50, 16 * max(len(name_lines), len(norm_lines), len(calc_lines)))
        item_idx += 1
        r += 1

    active_add_works = [aw for aw in cost_params.additional_works if aw.enabled and aw.cost_net_rub > 0]
    sum_add_rub = 0.0

    if active_add_works:
        ws.cell(row=r, column=1, value="Раздел 2. Дополнительные проектно-изыскательские работы").font = font_section
        for col_i in range(1, 6):
            ws.cell(row=r, column=col_i).border = thin_border
            ws.cell(row=r, column=col_i).fill = section_fill
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        ws.row_dimensions[r].height = 22
        r += 1

        for aw in active_add_works:
            c1 = ws.cell(row=r, column=1, value=item_idx)
            c1.alignment = align_top_center

            c2 = ws.cell(row=r, column=2, value=aw.name)
            c2.alignment = align_top_left

            c3 = ws.cell(row=r, column=3, value=aw.note or "Методика Минстроя РФ № 707/пр")
            c3.alignment = align_top_left

            c4 = ws.cell(row=r, column=4, value="По сметному расчету (калькуляции затрат)")
            c4.alignment = align_top_left

            cost_thous = round(aw.cost_net_rub / 1000.0, 3)
            sum_add_rub += aw.cost_net_rub
            c5 = ws.cell(row=r, column=5, value=cost_thous)
            c5.number_format = num_format_thous
            c5.alignment = align_top_right
            c5.font = font_bold

            for c in (c1, c2, c3, c4, c5):
                c.border = thin_border
                if c != c5:
                    c.font = font_regular

            ws.row_dimensions[r].height = 30
            item_idx += 1
            r += 1

    # 4. ИТОГИ ПО СМЕТЕ
    ws.cell(row=r, column=1, value="Итоги по смете").font = font_bold
    for col_i in range(1, 6):
        ws.cell(row=r, column=col_i).border = thin_border
        ws.cell(row=r, column=col_i).fill = header_fill
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    r += 1

    ws.cell(row=r, column=1, value="")
    ws.cell(row=r, column=2, value=f"Проектные работы: {project_data.object_name}").font = font_regular
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c_p_sum = ws.cell(row=r, column=5, value=round(sum_pir_rub / 1000.0, 3))
    c_p_sum.number_format = num_format_thous
    c_p_sum.alignment = align_right
    c_p_sum.font = font_bold
    for col_i in range(1, 6):
        ws.cell(row=r, column=col_i).border = thin_border
    r += 1

    if sum_add_rub > 0:
        ws.cell(row=r, column=1, value="")
        ws.cell(row=r, column=2, value="Дополнительные виды работ").font = font_regular
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        c_a_sum = ws.cell(row=r, column=5, value=round(sum_add_rub / 1000.0, 3))
        c_a_sum.number_format = num_format_thous
        c_a_sum.alignment = align_right
        c_a_sum.font = font_bold
        for col_i in range(1, 6):
            ws.cell(row=r, column=col_i).border = thin_border
        r += 1

    total_net_rub = sum_pir_rub + sum_add_rub
    ws.cell(row=r, column=1, value="")
    ws.cell(row=r, column=2, value="Итого").font = font_bold
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c_tot = ws.cell(row=r, column=5, value=round(total_net_rub / 1000.0, 3))
    c_tot.number_format = num_format_thous
    c_tot.alignment = align_right
    c_tot.font = font_bold
    for col_i in range(1, 6):
        ws.cell(row=r, column=col_i).border = thin_border
        ws.cell(row=r, column=col_i).fill = total_fill
    r += 1

    if cost_params.include_vat:
        vat_rub = round(total_net_rub * (cost_params.vat_rate / 100.0), 2)
        total_gross_rub = total_net_rub + vat_rub
        vat_label = f"НДС {cost_params.vat_rate:g}%"
    else:
        vat_rub = 0.0
        total_gross_rub = total_net_rub
        vat_label = "Без НДС"

    ws.cell(row=r, column=1, value="")
    ws.cell(row=r, column=2, value=vat_label).font = font_regular
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c_vat = ws.cell(row=r, column=5, value=round(vat_rub / 1000.0, 3))
    c_vat.number_format = num_format_thous
    c_vat.alignment = align_right
    c_vat.font = font_regular
    for col_i in range(1, 6):
        ws.cell(row=r, column=col_i).border = thin_border
    r += 1

    ws.cell(row=r, column=1, value="")
    ws.cell(row=r, column=2, value="Всего").font = font_bold
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
    c_gross = ws.cell(row=r, column=5, value=round(total_gross_rub / 1000.0, 3))
    c_gross.number_format = num_format_thous
    c_gross.alignment = align_right
    c_gross.font = font_bold
    for col_i in range(1, 6):
        ws.cell(row=r, column=col_i).border = double_bottom_border
        ws.cell(row=r, column=col_i).fill = total_fill
    r += 3

    ws.cell(row=r, column=2, value="Составил:").font = font_bold
    ws.cell(row=r, column=3, value="____________________ / ____________________ /").font = font_regular
    r += 2

    ws.cell(row=r, column=2, value="Проверил (ГИП):").font = font_bold
    ws.cell(row=r, column=3, value="____________________ / ____________________ /").font = font_regular

    for col_i, (_, col_w, _) in enumerate(headers_2p, start=1):
        col_letter = get_column_letter(col_i)
        ws.column_dimensions[col_letter].width = col_w

    # =========================================================================
    # ЛИСТ 2: ФОРМА 3П (МЕТОДИКА № 707/пр — ОТ СРЕДНЕМЕСЯЧНОЙ ЗП И ТАБЛ. 1.3)
    # =========================================================================
    ws_707 = wb.create_sheet(title="Форма 3П (Трудозатраты)")
    ws_707.views.sheetView[0].showGridLines = True

    ws_707.cell(row=1, column=1, value="РАСЧЁТ СТОИМОСТИ ПО ТРУДОЗАТРАТАМ ПО МЕТОДИКЕ МИНСТРОЯ РФ № 707/пр (ФОРМА 3П)").font = font_title
    ws_707.cell(row=2, column=1, value=f"Объект: {project_data.object_name}").font = font_section
    ws_707.cell(
        row=3,
        column=1,
        value=(
            f"п. 143–149, ф. (8.12)–(8.14): ЗП_мес = {cost_params.regional_monthly_salary_707:,.0f} ₽, "
            f"Д_раб = {cost_params.work_days_707:g} дн., К_3 = {cost_params.k3_salary_share_707:g} (Табл. 1.1), "
            f"Р = {cost_params.profitability_707*100:g}% (Табл. 1.2) -> В_ср = {cost_params.v_sr_707_rub:,.2f} ₽/дн."
        ),
    ).font = font_small

    headers_707 = [
        ("№ п/п", 8),
        ("Категория исполнителя / Должность", 36),
        ("Подразделение", 26),
        ("Индекс И_i (Табл. 1.3)", 15),
        ("Кол-во чел.", 12),
        ("Трудоёмкость, дн.", 16),
        ("Всего чел.-дней (Т_i)", 16),
        ("Взвешенная трудоёмк. (Т_i × И_i)", 22),
        ("Себестоимость ЗП, руб.", 18),
    ]

    for col_i, (h_text, col_w) in enumerate(headers_707, start=1):
        c = ws_707.cell(row=5, column=col_i, value=h_text)
        c.font = font_tbl_hdr
        c.alignment = align_center
        c.fill = header_fill
        c.border = thin_border
        ws_707.column_dimensions[get_column_letter(col_i)].width = col_w
    ws_707.row_dimensions[5].height = 28

    r_707 = 6
    zp_dnevn = (cost_params.regional_monthly_salary_707 or 95000.0) / (cost_params.work_days_707 or 20.6)
    for idx_r, r_it in enumerate(cost_params.labor_707_rows, start=1):
        if not r_it.enabled:
            continue
        c1 = ws_707.cell(row=r_707, column=1, value=idx_r)
        c1.alignment = align_center
        c2 = ws_707.cell(row=r_707, column=2, value=getattr(r_it, "role_name", "") or getattr(r_it, "category", ""))
        c2.alignment = align_left
        c3 = ws_707.cell(row=r_707, column=3, value=r_it.department or "—")
        c3.alignment = align_left
        c4 = ws_707.cell(row=r_707, column=4, value=r_it.index_i)
        c4.alignment = align_center
        c4.number_format = "0.00"
        c5 = ws_707.cell(row=r_707, column=5, value=r_it.count)
        c5.alignment = align_center
        c6 = ws_707.cell(row=r_707, column=6, value=r_it.days)
        c6.alignment = align_right
        c6.number_format = "#,##0.0"
        c7 = ws_707.cell(row=r_707, column=7, value=r_it.total_days)
        c7.alignment = align_right
        c7.number_format = "#,##0.0"
        c8 = ws_707.cell(row=r_707, column=8, value=r_it.weighted_days)
        c8.alignment = align_right
        c8.number_format = "#,##0.0"
        c9 = ws_707.cell(row=r_707, column=9, value=round(r_it.weighted_days * zp_dnevn, 2))
        c9.alignment = align_right
        c9.number_format = '#,##0.00\\ \"₽\"'

        for c in (c1, c2, c3, c4, c5, c6, c7, c8, c9):
            c.border = thin_border
            c.font = font_regular
        r_707 += 1

    # Итог по 707
    ws_707.merge_cells(start_row=r_707, start_column=1, end_row=r_707, end_column=6)
    ws_707.cell(row=r_707, column=1, value="ИТОГО ПО МЕТОДИКЕ № 707/пр (БЕЗ НДС):").font = font_bold
    ws_707.cell(row=r_707, column=1).alignment = align_right
    c_tot_707 = ws_707.cell(row=r_707, column=9, value=cost_params.labor_707_total_net_rub)
    c_tot_707.number_format = '#,##0.00\\ \"₽\"'
    c_tot_707.font = font_bold
    c_tot_707.alignment = align_right
    for col_i in range(1, 10):
        ws_707.cell(row=r_707, column=col_i).fill = total_fill
        ws_707.cell(row=r_707, column=col_i).border = double_bottom_border

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
