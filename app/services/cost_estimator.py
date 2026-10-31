import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from app.models import (
    AdditionalWorkItem,
    CalculationMethod,
    CollectionQuoteItem,
    CostParameters,
    FacilityType,
    Labor707Row,
    ProjectData,
    SectionCostItem,
    SpecialistLaborRow,
)
from app.services.normative_catalog import ensure_catalog_file


# Нормативные базовые доли распределения стоимости разработки разделов (по СБЦ и Методике № 707/пр Минстроя РФ)
VAT_RATES_ALLOWED = (0.0, 5.0, 22.0)

DEFAULT_CAPITAL_SHARES: Dict[str, float] = {
    "pz": 3.0,       # Раздел 1. Пояснительная записка
    "pzu": 5.0,      # Раздел 2. Схема планировочной организации земельного участка
    "ar": 13.0,      # Раздел 3. Архитектурные решения
    "kr": 18.0,      # Раздел 4. Конструктивные решения
    "ios1": 7.0,     # Раздел 5.1. Электроснабжение
    "ios2": 4.0,     # Раздел 5.2. Водоснабжение
    "ios3": 4.0,     # Раздел 5.3. Водоотведение
    "ios4": 8.0,     # Раздел 5.4. ОВК, тепловые сети
    "ios5_1": 4.0,   # Раздел 5.5.1. Сети связи
    "ios5_2": 4.0,   # Раздел 5.5.2. Автоматизация комплексная
    "ios6": 4.0,     # Раздел 5.6. Газоснабжение
    "tx": 10.0,      # Раздел 6. Технологические решения
    "pos": 5.0,      # Раздел 7. Проект организации строительства
    "oos": 3.0,      # Раздел 8. Охрана окружающей среды
    "pb": 3.0,       # Раздел 9. Пожарная безопасность
    "tbe": 1.0,      # Раздел 10. Требования к безопасной эксплуатации
    "sm": 4.0,       # Раздел 12.1. Сметы
    "sm_p": 1.5,     # Раздел 12.2. Конъюнктурный анализ
    "sm_vor": 1.5,   # Раздел 12.3. Ведомости объемов работ
    "gochs": 1.0,    # Раздел 13.1. Мероприятия ГОЧС
    "ots": 1.0,      # Раздел 13.2. Обследование техсостояния
    "odi": 2.0,      # Раздел 11. Доступ инвалидов
    "ee": 2.0,       # Энергоэффективность
    "pod": 3.0,      # Снос / демонтаж
    # Марки рабочей документации (РД)
    "rd_gp": 4.0,
    "rd_ar": 12.0,
    "rd_as": 15.0,
    "rd_kzh": 18.0,
    "rd_km": 14.0,
    "rd_kd": 8.0,
    "rd_eom": 8.0,
    "rd_es": 6.0,
    "rd_vk": 6.0,
    "rd_nvk": 7.0,
    "rd_ov": 10.0,
    "rd_ts": 6.0,
    "rd_ss": 5.0,
    "rd_ak": 6.0,
    "rd_gsn": 6.0,
    "rd_tx": 12.0,
    "rd_aps": 4.0,
    "rd_ad": 6.0,
    "rd_sm": 5.0,
}

DEFAULT_LINEAR_SHARES: Dict[str, float] = {
    "pz": 4.0,         # Раздел 1. Пояснительная записка
    "ppo": 14.0,       # Раздел 2. Проект полосы отвода
    "tkr": 36.0,       # Раздел 3. Технологические и конструктивные решения
    "lin_infra": 10.0, # Раздел 4. Здания и сооружения инфраструктуры
    "pos": 8.0,        # Раздел 5. Проект организации строительства
    "pod": 4.0,        # Раздел 6. Проект сноса / демонтажа
    "oos": 6.0,        # Раздел 7. Охрана окружающей среды
    "pb": 4.0,         # Раздел 8. Пожарная безопасность
    "sm": 5.0,         # Раздел 9.1. Сметная документация
    "sm_vor": 3.0,     # Раздел 9.2. Ведомости объемов работ
    "gochs": 2.0,      # Раздел 10.1. Мероприятия ГОЧС
    "rekult": 4.0,     # Раздел 10.2. Рекультивация земель
    "ots": 3.0,        # Раздел 10.3. Обследование техсостояния
    # Марки РД
    "rd_gp": 6.0,
    "rd_nvk": 25.0,
    "rd_ts": 20.0,
    "rd_es": 20.0,
    "rd_gsn": 20.0,
    "rd_ad": 20.0,
    "rd_sm": 6.0,
}

# Распределение разделов по проектным отделам
DEFAULT_DEPARTMENTS: Dict[str, str] = {
    "pz": "ГИП / Руководство проекта",
    "pzu": "Отдел генерального плана (ГП)",
    "ar": "Архитектурный отдел (АСО)",
    "kr": "Конструкторский отдел (КО)",
    "ios1": "Электротехнический отдел (ЭТО)",
    "ios2": "Отдел водоснабжения и канализации (ВК)",
    "ios3": "Отдел водоснабжения и канализации (ВК)",
    "ios4": "Отдел отопления и вентиляции (ОВ)",
    "ios5_1": "Отдел систем связи (СС)",
    "ios5_2": "Отдел автоматизации и КИПиА",
    "ios6": "Отдел газоснабжения (ГС)",
    "tx": "Технологический отдел (ТО)",
    "pos": "Отдел организации строительства (ПОС)",
    "oos": "Отдел охраны окружающей среды (ООС)",
    "pb": "Отдел пожарной безопасности (ПБ)",
    "tbe": "ГИП / Служба безопасности",
    "odi": "Архитектурный отдел (АСО)",
    "ee": "Отдел отопления и вентиляции (ОВ)",
    "sm": "Сметно-договорной отдел (СДО)",
    "sm_p": "Сметно-договорной отдел (СДО)",
    "sm_vor": "Сметно-договорной отдел (СДО)",
    "gochs": "Отдел спецмероприятий (ГОЧС)",
    "ots": "Отдел обследований и изысканий",
    "ppo": "Отдел генплана и землеустройства",
    "tkr": "Линейно-дорожный отдел",
    "lin_infra": "Архитектурно-строительный отдел",
    "pod": "Отдел организации строительства (ПОС)",
    "rekult": "Отдел охраны окружающей среды",
    # Отделы для РД
    "rd_gp": "Отдел генерального плана (ГП)",
    "rd_ar": "Архитектурный отдел (АСО)",
    "rd_as": "Архитектурный отдел (АСО)",
    "rd_kzh": "Конструкторский отдел (КО)",
    "rd_km": "Конструкторский отдел (КО)",
    "rd_kd": "Конструкторский отдел (КО)",
    "rd_eom": "Электротехнический отдел (ЭТО)",
    "rd_es": "Электротехнический отдел (ЭТО)",
    "rd_vk": "Отдел водоснабжения и канализации (ВК)",
    "rd_nvk": "Отдел водоснабжения и канализации (ВК)",
    "rd_ov": "Отдел отопления и вентиляции (ОВ)",
    "rd_ts": "Отдел отопления и вентиляции (ОВ)",
    "rd_ss": "Отдел систем связи (СС)",
    "rd_ak": "Отдел автоматизации и КИПиА",
    "rd_gsn": "Отдел газоснабжения (ГС)",
    "rd_tx": "Технологический отдел (ТО)",
    "rd_aps": "Отдел пожарной безопасности (ПБ)",
    "rd_ad": "Линейно-дорожный отдел",
    "rd_sm": "Сметно-договорной отдел (СДО)",
}


def get_default_department(section_id: str) -> str:
    """Возвращает наименование профильного подразделения-исполнителя."""
    return DEFAULT_DEPARTMENTS.get(section_id, "Комплексный проектный отдел")


def normalize_active_shares(items: List[SectionCostItem]) -> None:
    """
    Нормализует проценты активных (enabled=True) томов,
    чтобы их сумма строго равнялась 100.0%.
    """
    active_items = [it for it in items if it.enabled]
    if not active_items:
        return

    current_sum = sum(it.relative_share_percent for it in active_items)
    if current_sum <= 0:
        even_share = round(100.0 / len(active_items), 2)
        for it in active_items:
            it.relative_share_percent = even_share
    else:
        for it in active_items:
            it.relative_share_percent = round((it.relative_share_percent / current_sum) * 100.0, 2)

    new_sum = sum(it.relative_share_percent for it in active_items)
    diff = round(100.0 - new_sum, 2)
    if abs(diff) > 0.001:
        largest = max(active_items, key=lambda x: x.relative_share_percent)
        largest.relative_share_percent = round(largest.relative_share_percent + diff, 2)

    for it in items:
        if not it.enabled:
            it.relative_share_percent = 0.0


# ---------------------------------------------------------------------------
# ЯДРО РАСЧЁТА ПО 15 СБОРНИКАМ МНЗ / СБЦП (3 АЛГОРИТМА)
# ---------------------------------------------------------------------------

def _eval_ab_intervals(intervals: List[Dict[str, Any]], x_val: float) -> Tuple[float, float, float, str]:
    """
    Вычисляет базовую стоимость по таблице интервалов (a, b) с учётом правил
    интерполяции и экстраполяции (Методика Минстроя РФ № 707/пр):
    - Внутри интервала [x_min, x_max]: C = a + b * X
    - Ниже минимального показателя (X < X_min): C = a + b * (0.4 * X_min + 0.6 * X)
      (а если b == 0: C = a * (0.4 + 0.6 * X / X_min))
    - Выше максимального показателя (X > X_max): C = a + b * (0.4 * X_max + 0.6 * X)
    Возвращает (цена_табл, a, b, пояснение_формулы).
    """
    if not intervals:
        return 0.0, 0.0, 0.0, "0"

    x = max(float(x_val), 0.001)
    first = intervals[0]
    last = intervals[-1]

    if x < float(first["x_min"]):
        x_min = max(float(first["x_min"]), 0.001)
        a = float(first["a"])
        b = float(first["b"])
        if b > 0:
            x_eff = 0.4 * x_min + 0.6 * x
            val = a + b * x_eff
            expr = f"({a:g} + {b:g} × (0,4×{x_min:g} + 0,6×{x:g})) [экстрап. X < {x_min:g}]"
        else:
            k_ext = max(0.4 + 0.6 * (x / x_min), 0.2)
            val = a * k_ext
            expr = f"({a:g} × (0,4 + 0,6×{x:g}/{x_min:g})) [экстрап. X < {x_min:g}]"
        return val, a, b, expr

    if x > float(last["x_max"]):
        x_max = max(float(last["x_max"]), 0.001)
        a = float(last["a"])
        b = float(last["b"])
        if b > 0:
            x_eff = 0.4 * x_max + 0.6 * x
            val = a + b * x_eff
            expr = f"({a:g} + {b:g} × (0,4×{x_max:g} + 0,6×{x:g})) [экстрап. X > {x_max:g}]"
        else:
            k_ext = 0.4 + 0.6 * (x / x_max)
            val = a * k_ext
            expr = f"({a:g} × (0,4 + 0,6×{x:g}/{x_max:g})) [экстрап. X > {x_max:g}]"
        return val, a, b, expr

    # Внутри одного из интервалов
    chosen = last
    for iv in intervals:
        if float(iv["x_min"]) <= x <= float(iv["x_max"]):
            chosen = iv
            break

    a = float(chosen["a"])
    b = float(chosen["b"])
    val = a + b * x
    if b > 0:
        expr = f"({a:g} + {b:g} × {x:g})"
    else:
        expr = f"{a:g}"
    return val, a, b, expr


def _parse_height_meters(height_group: str) -> int:
    """Преобразует строковый код высоты ('h_up_to_6', '8', '12' и т.д.) в число метров (4..21)."""
    if not height_group:
        return 6
    m = re.search(r"(\d+)", str(height_group))
    if m:
        h = int(m.group(1))
        return max(4, min(21, h))
    return 6


def _lookup_obmer_270_rate(
    tables_1_4: Dict[str, Any],
    table_key: str,
    work_comp: str,
    bldg_cat: str,
    height_m: int,
    is_obsled: bool = False,
) -> float:
    """Извлекает базовую цену (руб. на 100 м3 в ценах 2001 г.) из Таблиц 1-4 СБЦП № 270/пр."""
    w_map = {"I": "w1", "II": "w2", "III": "w3", "1": "w1", "2": "w2", "3": "w3"}
    b_map = {"I": "b1", "II": "b2", "III": "b3", "1": "b1", "2": "b2", "3": "b3"}
    w_code = w_map.get(str(work_comp).upper(), "w2")
    b_code = b_map.get(str(bldg_cat).upper(), "b2")
    row_key = f"{w_code}_{b_code}"

    t_data = tables_1_4.get(table_key, {})
    arr = t_data.get(row_key, [])
    if not arr:
        return 300.0

    heights = tables_1_4.get("heights_16" if is_obsled else "heights_18", [])
    if not heights:
        return float(arr[0])

    idx = 0
    for i, h_val in enumerate(heights):
        if height_m <= int(h_val):
            idx = i
            break
    else:
        idx = len(arr) - 1

    idx = min(idx, len(arr) - 1)
    return float(arr[idx])


def calculate_single_collection_item(
    quote_item: CollectionQuoteItem,
    catalog: Dict[str, Any],
    global_k_mult: float = 1.0,
) -> CollectionQuoteItem:
    """
    Рассчитывает одну позицию сметы по выбранному сборнику из базы (МНЗ / СБЦП)
    по одному из 3 алгоритмов:
    1) 'ab' — стандартная формула (a + b * X) с интерполяцией/экстраполяцией;
    2) 'survey_283' — Приказ Минстроя № 283/пр (обследование сетей ИТО: полевые + 19% НП для Тюмени + тех. отчёт);
    3) 'obmer_270' — Приказ Минстроя № 270/пр / СБЦП 81-2001-25 (обмерные и обследовательские работы по строительному объёму V).
    """
    collections = catalog.get("collections", [])
    col_map = {c["id"]: c for c in collections}

    # Поддержка коротких алиасов id сборников
    col = col_map.get(quote_item.collection_id)
    if not col:
        for c in collections:
            if c["id"].startswith(quote_item.collection_id) or quote_item.collection_id.startswith(c["id"]):
                col = c
                break
    if not col:
        quote_item.warning = f"Сборник «{quote_item.collection_id}» не найден в справочнике — выберите сборник вручную"
        quote_item.formula_text = quote_item.warning
        quote_item.base_cost_rub = 0.0
        quote_item.current_cost_rub = 0.0
        return quote_item

    quote_item.warning = ""
    quote_item.collection_id = col["id"]
    quote_item.collection_code = col.get("code", "")
    calc_type = col.get("calc_type", "ab")
    quote_item.calc_type = calc_type
    base_year = str(col.get("base_year", "2021"))
    quote_item.price_level_year = int(base_year) if base_year.isdigit() else 2021
    index_type = col.get("index_type", "pir")
    quote_item.index_type = index_type

    indices_block = catalog.get("indices", {})
    idx_dict = indices_block.get(index_type, indices_block.get("pir", {}))
    index_val = float(idx_dict.get(base_year, 1.0))
    quote_item.index_applied = index_val

    items = col.get("items", [])
    matched_item = next((it for it in items if it["id"] == quote_item.item_id), None)
    if not matched_item:
        quote_item.warning = f"Таблица «{quote_item.item_id}» не найдена в сборнике {col.get('code', '')} — выберите таблицу вручную"
        quote_item.formula_text = quote_item.warning
        quote_item.base_cost_rub = 0.0
        quote_item.current_cost_rub = 0.0
        return quote_item

    quote_item.item_name = quote_item.custom_name.strip() or matched_item.get("name", "")
    quote_item.unit = matched_item.get("unit", "ед.")
    if float(quote_item.x_value or 0.0) <= 0.0:
        quote_item.warning = (
            f"Не задан показатель X ({quote_item.unit}) — укажите значение вручную; "
            "позиция не включена в сумму"
        )
        quote_item.formula_text = quote_item.warning
        quote_item.base_cost_rub = 0.0
        quote_item.current_cost_rub = 0.0
        return quote_item
    x_val = float(quote_item.x_value)
    k_total = round(max(float(quote_item.k_coeff), 0.01) * global_k_mult, 4)

    # Доля стадийности (П, Р, П+Р)
    pd_share = float(col.get("pd_share", 40.0)) / 100.0
    rd_share = float(col.get("rd_share", 60.0)) / 100.0
    if quote_item.stage_mode == "pd":
        stage_k = pd_share
        stage_label = f"К_ст(П)={pd_share:g}"
    elif quote_item.stage_mode == "rd":
        stage_k = rd_share
        stage_label = f"К_ст(Р)={rd_share:g}"
    else:
        stage_k = 1.0
        stage_label = "К_ст(П+Р)=1,0"

    # Коэффициент полноты разрабатываемых разделов (К_разд = completeness_pct / 100)
    comp_pct = max(min(float(getattr(quote_item, "completeness_pct", 100.0) or 100.0), 100.0), 1.0)
    quote_item.completeness_pct = round(comp_pct, 1)
    comp_k = round(comp_pct / 100.0, 4)
    comp_label = f" × К_разд={comp_k:g} ({comp_pct:g}%)" if comp_pct < 99.95 else " × К_разд=1,0 (100%)"

    # АЛГОРИТМ 2: Приказ № 283/пр (Обследование сетей ИТО неразрушающими методами, цены 01.01.2024 в руб.)
    if calc_type == "survey_283":
        field_rate = float(matched_item.get("field_rate_per_unit", 15000.0))
        so_pz = round(field_rate * x_val, 2)
        adv_pct = float(col.get("adverse_period_tyumen_percent", 19.0)) if quote_item.adverse_period else 0.0
        dzo_np = round(so_pz * (adv_pct / 100.0), 2)
        rep_val, _, _, rep_expr = _eval_ab_intervals(matched_item.get("report_intervals", []), x_val)
        spo = round(rep_val, 2)

        base_rub = round((so_pz + dzo_np + spo) * comp_k * k_total, 2)
        curr_rub = round(base_rub * index_val, 2)

        quote_item.base_cost_rub = base_rub
        quote_item.current_cost_rub = curr_rub
        np_str = f" + ДЗ_НП({adv_pct:g}% Тюмень)={dzo_np:,.0f}" if adv_pct > 0 else ""
        quote_item.formula_text = (
            f"[СО_пз({field_rate:g}×{x_val:g}={so_pz:,.0f} ₽){np_str} + СПО{rep_expr}={spo:,.0f} ₽]"
            f"{comp_label} × К={k_total:g} × I_ИИ({base_year})={index_val}"
        )
        return quote_item

    # АЛГОРИТМ 3: Приказ № 270/пр / СБЦП 81-2001-25 (Обмерные и обследовательские работы, цены 01.01.2001 в руб. на 100 м3)
    if calc_type == "obmer_270":
        tables_1_4 = col.get("tables_1_4", {})
        h_m = _parse_height_meters(quote_item.height_group)
        is_single = "single" in str(quote_item.work_type).lower()
        t_obmer_key = "t1_obmer_single" if is_single else "t2_obmer_multi"
        t_obsled_key = "t3_obsled_single" if is_single else "t4_obsled_multi"

        p_obmer = _lookup_obmer_270_rate(
            tables_1_4, t_obmer_key, quote_item.work_complexity, quote_item.building_category, h_m, is_obsled=False
        )
        p_obsled = _lookup_obmer_270_rate(
            tables_1_4, t_obsled_key, quote_item.work_complexity, quote_item.building_category, h_m, is_obsled=True
        )

        wt = str(quote_item.work_type).lower()
        if wt == "obmer":
            rate_100m3 = p_obmer
            rate_desc = f"Р_обм={p_obmer:g} ₽/100м³"
        elif wt == "obsled":
            rate_100m3 = p_obsled
            rate_desc = f"Р_обсл={p_obsled:g} ₽/100м³"
        else:
            rate_100m3 = round(p_obmer + p_obsled, 2)
            rate_desc = f"(Р_обм={p_obmer:g} + Р_обсл={p_obsled:g} = {rate_100m3:g} ₽/100м³)"

        # Таблица 11: Повышающий коэффициент при малом строительном объёме V <= 5000 м3
        k_vol = 1.0
        if quote_item.small_volume_auto:
            for row_v in col.get("small_volume_table_11", []):
                if x_val <= float(row_v["v_max"]):
                    k_vol = float(row_v["k"])
                    break

        units_100 = x_val / 100.0
        base_rub = round(rate_100m3 * units_100 * k_vol * comp_k * k_total, 2)
        curr_rub = round(base_rub * index_val, 2)

        quote_item.base_cost_rub = base_rub
        quote_item.current_cost_rub = curr_rub
        quote_item.formula_text = (
            f"{rate_desc} × ({x_val:g}/100 м³) × К_объёма(Табл.11)={k_vol:g}{comp_label} × К={k_total:g} "
            f"× I_ПИР({base_year})={index_val}"
        )
        return quote_item

    # АЛГОРИТМ 1: Стандартная формула (a + b * X) для сборников № 1–7 и № 10–15
    raw_val, _, _, expr = _eval_ab_intervals(matched_item.get("intervals", []), x_val)
    unit_mult = 1000.0 if col.get("price_unit", "thousand_rub") == "thousand_rub" else 1.0
    unit_Note = " тыс.₽" if unit_mult == 1000.0 else " ₽"

    base_rub = round(raw_val * unit_mult * stage_k * comp_k * k_total, 2)
    curr_rub = round(base_rub * index_val, 2)

    quote_item.base_cost_rub = base_rub
    quote_item.current_cost_rub = curr_rub
    quote_item.formula_text = (
        f"{expr}{unit_Note} × {stage_label}{comp_label} × К={k_total:g} × I_ПИР({base_year})={index_val}"
    )
    return quote_item


# ---------------------------------------------------------------------------
# РАСЧЁТ ОТ СТОИМОСТИ СТРОИТЕЛЬСТВА (СМР) ПО ТАБЛ. 1.5 МЕТОДИКИ № 707/пр
# ---------------------------------------------------------------------------

def calculate_pir_from_smr_707(
    smr_current_mln_rub: float,
    catalog: Dict[str, Any],
    has_pd: bool = True,
    has_rd: bool = True,
    k_multipliers: float = 1.0,
) -> Tuple[float, float]:
    """
    Вычисляет нормативный процент (alpha, %) и справочную стоимость ПИР (руб. без НДС)
    от ориентировочной стоимости строительства (СМР) согласно Таблице 1.5 Приложения № 2
    Методики Минстроя РФ № 707/пр:
    1) Переводит текущую стоимость СМР (млн руб.) в базовый уровень цен 01.01.2001 г. через индекс СМР.
    2) Линейно интерполирует норматив alpha (%) по Таблице 1.5 Методики № 707/пр.
    3) Учитывает стадийность (ПД 40%, РД 60%, ПД+РД 100%) и коэффициенты усложнения.
    Возвращает (alpha_percent, pir_cost_rub).
    """
    if smr_current_mln_rub <= 0:
        return 0.0, 0.0

    indices = catalog.get("indices", {})
    smr_idx_2001 = float(indices.get("smr_to_2001_index", 11.45)) or 11.45
    smr_2001_mln = smr_current_mln_rub / smr_idx_2001

    table = catalog.get("method_707_smr_table", [])
    if not table:
        alpha = 6.5
    elif smr_2001_mln <= float(table[0]["smr_2001_mln"]):
        alpha = float(table[0]["alpha_percent"])
    elif smr_2001_mln >= float(table[-1]["smr_2001_mln"]):
        alpha = float(table[-1]["alpha_percent"])
    else:
        alpha = float(table[-1]["alpha_percent"])
        for i in range(len(table) - 1):
            x0 = float(table[i]["smr_2001_mln"])
            x1 = float(table[i + 1]["smr_2001_mln"])
            if x0 <= smr_2001_mln <= x1:
                y0 = float(table[i]["alpha_percent"])
                y1 = float(table[i + 1]["alpha_percent"])
                t = (smr_2001_mln - x0) / max(x1 - x0, 0.0001)
                alpha = y0 + t * (y1 - y0)
                break

    stage_share = 1.0
    if has_pd and not has_rd:
        stage_share = 0.40
    elif has_rd and not has_pd:
        stage_share = 0.60

    effective_pct = round(alpha * stage_share * k_multipliers, 2)
    pir_cost_rub = round(smr_current_mln_rub * 1_000_000.0 * (effective_pct / 100.0), 2)
    return effective_pct, pir_cost_rub


# ---------------------------------------------------------------------------
# АВТОПОДБОР СБОРНИКОВ И ПАРАМЕТРОВ ИЗ ТЕКСТА ТЗ
# ---------------------------------------------------------------------------

def extract_smr_from_tz_text(tz_text: str) -> float:
    """
    Ищет в тексте ТЗ упоминание предельной / ориентировочной стоимости строительства (СМР)
    и возвращает значение в млн руб. (или 0.0, если в ТЗ стоимость строительства не указана).
    """
    if not tz_text:
        return 0.0
    text_lower = tz_text.lower()
    patterns = [
        r"(?:предельн\w+|ориентировочн\w+|сметн\w+|предполагаем\w+)\s+стоимост\w+\s+(?:строительств\w+|смр)[^\d\n]{0,40}(\d+(?:[\.,]\d+)?)\s*(млрд|млн|тыс)?",
        r"стоимост\w+\s+строительств\w+\s*\(\s*смр\s*\)[^\d\n]{0,30}(\d+(?:[\.,]\d+)?)\s*(млрд|млн|тыс)?",
    ]
    for pat in patterns:
        m = re.search(pat, text_lower)
        if m:
            val = float(m.group(1).replace(",", "."))
            unit = (m.group(2) or "млн").strip()
            if unit == "млрд":
                return round(val * 1000.0, 2)
            if unit == "тыс":
                return round(val / 1000.0, 3)
            if val > 100_000:
                return round(val / 1_000_000.0, 2)
            return round(val, 2)
    return 0.0


def compute_sections_completeness_pct(project_data: ProjectData) -> float:
    """
    Определяет долю полноты разрабатываемых разделов (К_разд в %) относительно полного комплекса (100%):
    - Если выбран режим «Только по ТЗ» (composition_preset == 'tz') или отключена существенная часть базовых разделов,
      суммирует нормативные доли включённых разделов ПД (или РД, если разрабатывается только РД).
    - Если включён полный базовый комплекс (для разрешения на строительство / экспертизы >= 85%), возвращает 100.0%.
    """
    is_linear = project_data.facility_type == FacilityType.LINEAR
    shares_map = DEFAULT_LINEAR_SHARES if is_linear else DEFAULT_CAPITAL_SHARES

    # Оцениваем по разделам основной стадии (ПД, либо РД если ПД отключена)
    target_stage = "П" if project_data.has_pd else "Р"
    stage_sections = [s for s in project_data.sections if getattr(s, "stage", "П") == target_stage]
    if not stage_sections:
        return 100.0

    enabled_sum = sum(shares_map.get(s.id, 2.0) for s in stage_sections if s.enabled)
    total_possible = sum(shares_map.get(s.id, 2.0) for s in stage_sections)
    if total_possible <= 0:
        return 100.0

    # Для полного пресета ("permit" или "expertise"), если пользователь не отключал разделы вручную до узкого набора
    ratio_pct = round(min((enabled_sum / total_possible) * 100.0, 100.0), 1)
    if project_data.composition_preset in ("permit", "expertise") and ratio_pct >= 75.0:
        return 100.0
    return max(ratio_pct, 5.0)


def suggest_initial_collection_items(project_data: ProjectData, catalog: Dict[str, Any]) -> List[CollectionQuoteItem]:
    """
    Стартовый список позиций по сборникам МНЗ/СБЦП ПУСТ намеренно.

    Раньше сборник и значение X подбирались по ключевым словам ТЗ, и при отсутствии совпадения
    подставлялся случайный сборник с выдуманным X — итоговая сумма выглядела достоверно, но не имела
    отношения к объекту. Теперь позиции добавляет и параметр X вводит специалист вручную.
    """
    return []


def load_labor_norms() -> Dict[str, Any]:
    """Читает data/labor_norms.json (черновые нормы чел.-дн. по разделам, см. поле approved)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "labor_norms.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"approved": False, "default_days_per_section": 8.0, "days_per_section": {}, "role_split_707": {}, "role_split_market": {}}


def norm_total_days(project_data: Optional[ProjectData], norms: Dict[str, Any]) -> float:
    """Сумма норм чел.-дн. по включённым разделам проекта. Без проекта/разделов возвращает 0."""
    if project_data is None:
        return 0.0
    table = norms.get("days_per_section", {})
    default = float(norms.get("default_days_per_section", 8.0))
    return round(sum(float(table.get(sec.id, default)) for sec in project_data.sections if sec.enabled), 1)


def build_default_labor_707_rows(catalog: Dict[str, Any], project_data: Optional[ProjectData] = None) -> List[Labor707Row]:
    """
    Стартовые строки расчёта В1 (Методика № 707/пр, п. 143–149, Табл. 1.3 Прил. 2: индексы И_i).
    Дни определяются составом проекта: сумма норм по включённым разделам × доля роли.
    Нормы черновые (data/labor_norms.json, approved=false). Без включённых разделов дни = 0.
    """
    norms = load_labor_norms()
    total = norm_total_days(project_data, norms)
    split = norms.get("role_split_707", {})
    t13_map = {r["id"]: r for r in catalog.get("method_707_table_1_3", [])}
    rows: List[Labor707Row] = []
    for idx, (role_id, share) in enumerate(split.items(), 1):
        info = t13_map.get(role_id, {})
        rows.append(
            Labor707Row(
                row_id=f"l707_{idx}",
                role_id=role_id,
                role_name=info.get("role", "Ведущий специалист: инженер, архитектор, экономист, сметчик (Табл. 1.3 п. 7)"),
                department=info.get("department", "Профильные отделы"),
                count=1,
                days=round(total * float(share), 1),
                index_i=float(info.get("index_i", 1.00)),
                enabled=True,
            )
        )
    return rows


def build_default_specialist_rows(catalog: Dict[str, Any], project_data: Optional[ProjectData] = None) -> List[SpecialistLaborRow]:
    """
    Стартовые строки расчёта В2 (рыночные оклады специалистов, г. Тюмень).
    Дни определяются составом проекта так же, как в build_default_labor_707_rows.
    """
    norms = load_labor_norms()
    total = norm_total_days(project_data, norms)
    split = norms.get("role_split_market", {})
    spec_map = {s["id"]: s for s in catalog.get("specialists_directory", [])}
    rows: List[SpecialistLaborRow] = []
    for idx, (role_id, share) in enumerate(split.items(), 1):
        info = spec_map.get(role_id, {})
        rows.append(
            SpecialistLaborRow(
                row_id=f"spec_{idx}",
                role_id=role_id,
                role_name=info.get("role", "Инженер-проектировщик"),
                department=info.get("department", "Проектный отдел"),
                count=1,
                days=round(total * float(share), 1),
                monthly_salary_rub=float(info.get("monthly_salary_rub", 95000.0)),
                qual_coeff_707=float(info.get("k_qual_707", 1.0)),
                enabled=True,
            )
        )
    return rows


def build_default_additional_works(project_data: ProjectData) -> List[AdditionalWorkItem]:
    """
    Формирует список дополнительных видов работ (обследование, ИИ, экспертиза).
    Суммы по умолчанию НЕ задаются (0 ₽): стоимость вводит специалист. Раньше здесь были зашитые
    суммы, которые молча попадали в итог при включении изысканий.
    """
    return [
        AdditionalWorkItem(
            work_id="inspection",
            name="Техническое обследование зданий, сооружений и сетей",
            enabled=False,
            cost_net_rub=0.0,
            note="Включается отдельно, если не учтено в таблицах сборников № 270/пр или № 283/пр",
        ),
        AdditionalWorkItem(
            work_id="surveys",
            name="Комплексные инженерные изыскания (ИГДИ, ИГИ, ИЭИ)",
            enabled=False,
            cost_net_rub=0.0,
            note="Геодезические, геологические и экологические изыскания",
        ),
        AdditionalWorkItem(
            work_id="expertise",
            name="Сопровождение в экспертизе и проверка достоверности определения сметной стоимости",
            enabled=False,
            cost_net_rub=0.0,
            note="Подача и сопровождение документации в ГАУ ТО «УГЭПД» / негосударственной экспертизе",
        ),
    ]


# ---------------------------------------------------------------------------
# ПОСТРОЕНИЕ СПИСКА РАЗДЕЛОВ В РАСЧЁТЕ СТОИМОСТИ (ВМЕСТЕ ИЛИ РАЗДЕЛЬНО П и Р)
# ---------------------------------------------------------------------------

def _build_section_cost_items(
    project_data: ProjectData,
    split_pd_rd: bool = False,
    existing_items: Optional[List[SectionCostItem]] = None,
) -> List[SectionCostItem]:
    """
    Формирует строки таблицы разделов для сметы:
    - Если split_pd_rd == False (по умолчанию, как согласовано с пользователем):
      Если в проекте включены только ПД или только РД, выводятся активные разделы.
      Если включены и ПД, и РД, расчёт по умолчанию ведется без деления на отдельные таблицы П и Р
      (по основным разделам проекта со стадией «П+Р», либо с сохранением выбранных разделов в едином списке).
    - Если split_pd_rd == True (включена галочка «Разделить расчёт отдельно на стадию П и стадию Р»):
      Отдельно выводятся разделы стадии «П» и отдельно марки стадии «Р».
    """
    is_linear = project_data.facility_type == FacilityType.LINEAR
    shares_map = DEFAULT_LINEAR_SHARES if is_linear else DEFAULT_CAPITAL_SHARES
    existing_map = {it.section_id: it for it in (existing_items or [])}

    both_stages_active = project_data.has_pd and project_data.has_rd
    cost_items: List[SectionCostItem] = []

    for sec in project_data.sections:
        is_rd = getattr(sec, "stage", "П") == "Р"

        # В режиме по умолчанию (split_pd_rd=False), когда в проекте есть и ПД, и РД,
        # не дублируем отдельно строки РД поверх разделов ПД, а считаем П+Р вместе по разделам проекта
        if both_stages_active and not split_pd_rd and is_rd:
            continue

        base_share = shares_map.get(sec.id, 2.0)
        if both_stages_active and not split_pd_rd:
            stage_label = "П+Р"
            vol_label = sec.volume_num
            title_label = sec.title
        else:
            stage_label = "Р" if is_rd else "П"
            vol_label = (f"РД-{sec.volume_num}" if sec.volume_num else "РД") if is_rd else sec.volume_num
            title_label = f"[РД] {sec.title}" if is_rd and not sec.title.startswith("[РД]") else sec.title

        prev = existing_map.get(sec.id)
        if prev:
            share_val = prev.relative_share_percent if (sec.enabled and prev.relative_share_percent > 0) else (base_share if sec.enabled else 0.0)
            item = SectionCostItem(
                section_id=sec.id,
                stage=stage_label,
                volume_num=vol_label,
                code_mark=sec.code_mark,
                full_code=sec.full_code or sec.code_mark,
                title=title_label,
                relative_share_percent=share_val,
                labor_days=prev.labor_days,
                department=prev.department or get_default_department(sec.id),
                lead_specialist=prev.lead_specialist,
                enabled=sec.enabled,
            )
        else:
            item = SectionCostItem(
                section_id=sec.id,
                stage=stage_label,
                volume_num=vol_label,
                code_mark=sec.code_mark,
                full_code=sec.full_code or sec.code_mark,
                title=title_label,
                relative_share_percent=base_share if sec.enabled else 0.0,
                department=get_default_department(sec.id),
                enabled=sec.enabled,
            )
        cost_items.append(item)

    normalize_active_shares(cost_items)
    return cost_items


def init_cost_parameters(project_data: ProjectData) -> CostParameters:
    """
    Создает и рассчитывает начальную структуру стоимости и трудоемкости
    на основе состава разделов проекта, текста ТЗ и базы нормативов.
    """
    catalog = ensure_catalog_file()
    norm_707 = catalog.get("method_707_normatives", {})
    detected_smr = extract_smr_from_tz_text(project_data.tz_text or "")
    initial_collections = suggest_initial_collection_items(project_data, catalog)
    initial_labor_707 = build_default_labor_707_rows(catalog, project_data)
    initial_specialists = build_default_specialist_rows(catalog, project_data)
    initial_add_works = build_default_additional_works(project_data)
    cost_items = _build_section_cost_items(project_data, split_pd_rd=False)

    cost_params = CostParameters(
        calculation_method=CalculationMethod.BY_COLLECTIONS,
        target_total_cost_net=0.0,
        include_vat=True,
        vat_rate=5.0,
        average_daily_rate_rub=12000.0,
        overhead_percent=60.0,
        profit_percent=20.0,
        complexity_factor=1.0,
        is_reconstruction=False,
        use_bim=False,
        urgency_factor=1.0,
        split_pd_rd_in_cost=False,
        pd_stage_share_pct=40.0,
        rd_stage_share_pct=60.0,
        collection_items=initial_collections,
        regional_monthly_salary_707=float(catalog.get("regional_salary_707_rub", 95000.0)),
        work_days_707=float(norm_707.get("work_days_month", 20.6)),
        k3_salary_share_707=float(norm_707.get("k3_salary_share", 0.4006)),
        profitability_707=float(norm_707.get("p_profitability", 0.10)),
        labor_707_rows=initial_labor_707,
        work_days_per_month=float(catalog.get("working_days_per_month", 21.0)),
        specialist_rows=initial_specialists,
        smr_cost_mln_rub=detected_smr,
        smr_detected_from_tz=(detected_smr > 0),
        additional_works=initial_add_works,
        sections_costs=cost_items,
    )

    recalculate_cost_parameters(cost_params, has_pd=project_data.has_pd, has_rd=project_data.has_rd)
    return cost_params


def sync_cost_with_sections(project_data: ProjectData) -> None:
    """
    Синхронизирует состав стоимостного модуля при изменении
    состава разделов (включение/отключение, смена шифров или типа объекта).
    """
    if not project_data.cost_parameters:
        project_data.cost_parameters = init_cost_parameters(project_data)
        return

    cost_params = project_data.cost_parameters
    catalog = ensure_catalog_file()

    if not cost_params.collection_items:
        cost_params.collection_items = suggest_initial_collection_items(project_data, catalog)

    if cost_params.labor_rows_auto or not cost_params.labor_707_rows:
        cost_params.labor_707_rows = build_default_labor_707_rows(catalog, project_data)
    if cost_params.labor_rows_auto or not cost_params.specialist_rows:
        cost_params.specialist_rows = build_default_specialist_rows(catalog, project_data)
    if not cost_params.additional_works:
        cost_params.additional_works = build_default_additional_works(project_data)

    cost_params.sections_costs = _build_section_cost_items(
        project_data,
        split_pd_rd=cost_params.split_pd_rd_in_cost,
        existing_items=cost_params.sections_costs,
    )
    recalculate_cost_parameters(cost_params, has_pd=project_data.has_pd, has_rd=project_data.has_rd)


def recalculate_cost_parameters(
    cost_params: CostParameters,
    has_pd: bool = True,
    has_rd: bool = True,
) -> CostParameters:
    """
    Выполняет НЕЗАВИСИМЫЙ математический расчёт всех 4 методов определения стоимости ПИР
    без какой-либо взаимной подгонки:
    1) BY_COLLECTIONS — по сборникам базовых цен МНЗ / СБЦП (Форма 2П, с учётом полноты разделов К_разд);
    2) LABOR_707 (Расчёт В1) — строго по Методике Минстроя РФ № 707/пр (п. 143–149, ф. 8.12–8.14,
       Табл. 1.1 К_3=0.4006, Табл. 1.2 Р=10%, Табл. 1.3 индексы И_i, от ЗП_мес = 95 000 руб.);
    3) LABOR_INTERNAL (Расчёт В2) — коммерческий расчёт по таблице рыночной стоимости специалистов в г. Тюмени;
    4) FROM_SMR — справочный расчёт от стоимости строительства (СМР) по Таблице 1.5 Приложения № 2 Методики № 707/пр.
    """
    catalog = ensure_catalog_file()
    warnings: List[str] = []

    # Строки трудозатрат строит init/sync по составу разделов; здесь только предупреждение о черновых нормах
    norms = load_labor_norms()
    cost_params.labor_norms_approved = bool(norms.get("approved", False))
    cost_params.labor_total_days_norm = round(
        sum(max(float(r.days), 0.0) * max(int(r.count), 1) for r in cost_params.labor_707_rows if r.enabled), 1
    )
    if cost_params.labor_rows_auto and not cost_params.labor_norms_approved:
        warnings.append(
            "Трудозатраты (методы 2А и 2Б) рассчитаны по ориентировочным нормам человеко-дней на раздел "
            "(data/labor_norms.json), они не утверждены: замените своими данными или отредактируйте таблицу вручную."
        )

    # Общие мультипликаторы условий проектирования
    reconstr_k = 1.20 if cost_params.is_reconstruction else 1.0
    bim_k = 1.15 if cost_params.use_bim else 1.0
    k_multipliers = round(cost_params.complexity_factor * reconstr_k * bim_k * cost_params.urgency_factor, 4)

    # =========================================================================
    # НЕЗАВИСИМЫЙ РАСЧЁТ № 1: По сборникам базовых цен МНЗ / СБЦП (Форма 2П)
    # =========================================================================
    collections_sum_rub = 0.0
    for q_item in cost_params.collection_items:
        calculate_single_collection_item(q_item, catalog, global_k_mult=k_multipliers)
        if q_item.enabled:
            collections_sum_rub += q_item.current_cost_rub
            if q_item.warning:
                warnings.append(f"Позиция «{q_item.item_name or q_item.item_id}»: {q_item.warning}")
            if q_item.x_source == "min_default" and not q_item.warning:
                warnings.append(
                    f"Позиция «{q_item.source_description or q_item.item_name or q_item.item_id}»: данные не указаны в ТЗ, "
                    f"взято минимальное значение X = {q_item.x_value:g} {q_item.unit} — уточните у заказчика."
                )
            if q_item.needs_ai and q_item.x_source != "manual":
                warnings.append(
                    f"Позиция «{q_item.source_description or q_item.item_name or q_item.item_id}»: значение X ещё не определено — "
                    "нажмите «Найти X в ТЗ (ИИ)» или введите вручную."
                )
    collections_sum_rub = round(collections_sum_rub, 2)
    cost_params.collections_total_net_rub = collections_sum_rub

    # =========================================================================
    # НЕЗАВИСИМЫЙ РАСЧЁТ № 2А (В1): По трудозатратам строго по Методике № 707/пр
    # п. 143–149, формулы (8.12)–(8.14), Приложение № 2 Таблицы 1.1, 1.2, 1.3
    # =========================================================================
    zp_707 = max(float(cost_params.regional_monthly_salary_707 or 95000.0), 10000.0)
    d_rab_707 = max(float(cost_params.work_days_707 or 20.6), 15.0)
    k3_707 = max(min(float(cost_params.k3_salary_share_707 or 0.4006), 0.95), 0.10)
    p_707 = max(float(cost_params.profitability_707 if cost_params.profitability_707 is not None else 0.10), 0.0)

    # Среднедневная выработка 1 специалиста: В_ср = ((ЗП_мес / Д_раб) * (1 + Р)) / К_3
    v_sr_707 = round(((zp_707 / d_rab_707) * (1.0 + p_707)) / k3_707, 2)
    cost_params.v_sr_707_rub = v_sr_707

    sum_t_707 = 0.0
    sum_weighted_707 = 0.0
    for r707 in cost_params.labor_707_rows:
        if not r707.enabled:
            r707.total_days = 0.0
            r707.weighted_days = 0.0
            r707.cost_rub = 0.0
            continue
        cnt = max(int(r707.count), 1)
        days_val = max(float(r707.days), 0.0)
        idx_i = max(float(r707.index_i), 0.1)
        r707.total_days = round(cnt * days_val, 1)
        r707.weighted_days = round(r707.total_days * idx_i, 3)
        r707.cost_rub = round(v_sr_707 * r707.weighted_days * k_multipliers, 2)
        sum_t_707 += r707.total_days
        sum_weighted_707 += r707.weighted_days

    k_kv_uch = round(sum_weighted_707 / sum_t_707, 4) if sum_t_707 > 0 else 1.0
    labor_707_net = round(v_sr_707 * sum_weighted_707 * k_multipliers, 2)

    cost_params.k_kv_uch_707 = k_kv_uch
    cost_params.labor_707_total_days = round(sum_t_707, 1)
    cost_params.labor_707_weighted_days = round(sum_weighted_707, 2)
    cost_params.labor_707_total_net_rub = labor_707_net
    cost_params.labor_707_formula_text = (
        f"В_ср = ({zp_707:,.0f} / {d_rab_707:g}) × (1 + {p_707:g}) / {k3_707:g} = {v_sr_707:,.2f} ₽/дн.; "
        f"∑(Ч_i×Т_фi) = {sum_t_707:g} чел.-дн.; К_кв-уч = {sum_weighted_707:g}/{sum_t_707 or 1:g} = {k_kv_uch:.4f}; "
        f"Ц_пр(707/пр) = {v_sr_707:,.2f} × {sum_t_707:g} × {k_kv_uch:.4f} × К={k_multipliers:g} = {labor_707_net:,.2f} ₽"
    )

    # =========================================================================
    # НЕЗАВИСИМЫЙ РАСЧЁТ № 2Б (В2): По таблице рыночной стоимости специалистов (Тюмень)
    # =========================================================================
    work_days_mkt = max(float(cost_params.work_days_per_month or 21.0), 15.0)
    mkt_total_days = 0.0
    mkt_direct_wage = 0.0
    for s_row in cost_params.specialist_rows:
        if not s_row.enabled:
            s_row.total_days = 0.0
            s_row.total_wage_rub = 0.0
            continue
        monthly_eff = max(float(s_row.monthly_salary_rub), 10000.0)
        s_row.daily_rate_rub = round(monthly_eff / work_days_mkt, 2)
        s_row.total_days = round(max(int(s_row.count), 1) * max(float(s_row.days), 0.0), 1)
        s_row.total_wage_rub = round(s_row.total_days * s_row.daily_rate_rub, 2)
        mkt_total_days += s_row.total_days
        mkt_direct_wage += s_row.total_wage_rub

    mkt_direct_wage = round(mkt_direct_wage, 2)
    mkt_overhead = round(mkt_direct_wage * (cost_params.overhead_percent / 100.0), 2)
    mkt_profit = round((mkt_direct_wage + mkt_overhead) * (cost_params.profit_percent / 100.0), 2)
    mkt_net = round((mkt_direct_wage + mkt_overhead + mkt_profit) * k_multipliers, 2)

    cost_params.labor_market_total_days = round(mkt_total_days, 1)
    cost_params.labor_market_direct_wage_rub = mkt_direct_wage
    cost_params.labor_market_overhead_rub = mkt_overhead
    cost_params.labor_market_profit_rub = mkt_profit
    cost_params.labor_market_total_net_rub = mkt_net
    cost_params.labor_market_formula_text = (
        f"ФОТ_прям = {mkt_direct_wage:,.2f} ₽ ({mkt_total_days:g} чел.-дн.) + "
        f"НР({cost_params.overhead_percent:g}%) = {mkt_overhead:,.2f} ₽ + "
        f"СП({cost_params.profit_percent:g}%) = {mkt_profit:,.2f} ₽ × К={k_multipliers:g} = {mkt_net:,.2f} ₽"
    )

    # =========================================================================
    # НЕЗАВИСИМЫЙ РАСЧЁТ № 3: От стоимости строительства (СМР) по Табл. 1.5 № 707/пр
    # =========================================================================
    smr_pct, smr_pir_rub = calculate_pir_from_smr_707(
        cost_params.smr_cost_mln_rub,
        catalog,
        has_pd=has_pd,
        has_rd=has_rd,
        k_multipliers=k_multipliers,
    )
    cost_params.smr_normative_pct = smr_pct
    cost_params.smr_reference_pir_cost_rub = smr_pir_rub

    # =========================================================================
    # Дополнительные виды работ (обследование, изыскания, экспертиза)
    # =========================================================================
    add_works_sum = round(
        sum(max(float(w.cost_net_rub), 0.0) for w in cost_params.additional_works if w.enabled),
        2,
    )
    cost_params.additional_works_total_net_rub = add_works_sum
    for w in cost_params.additional_works:
        if w.enabled and float(w.cost_net_rub) <= 0:
            warnings.append(f"Дополнительная работа «{w.name}» включена, но стоимость не указана — введите сумму вручную.")

    # =========================================================================
    # Выбор активного расчёта, который пойдёт в итоговую смету и КП
    # (без подгонки остальных независимых расчётов!)
    # =========================================================================
    method = cost_params.calculation_method
    normalize_active_shares(cost_params.sections_costs)

    if method == CalculationMethod.BY_COLLECTIONS:
        pir_net = collections_sum_rub
        if pir_net <= 0:
            warnings.append("Расчёт по сборникам: ни одной позиции с заданным X — стоимость не рассчитана. Добавьте позиции и введите X вручную.")
        cost_params.pir_only_cost_net_rub = pir_net
        cost_params.target_total_cost_net = round(pir_net / max(k_multipliers, 0.01), 2)

        # Трудозатраты НЕ подгоняются делением рублей сборника на ставку, а берутся из независимого расчёта трудозатрат
        ref_days = sum_t_707 if sum_t_707 > 0 else mkt_total_days
        cost_params.total_labor_days = round(ref_days, 1)
        cost_params.direct_labor_cost_rub = mkt_direct_wage
        cost_params.overhead_rub = mkt_overhead
        cost_params.profit_rub = mkt_profit

        for it in cost_params.sections_costs:
            if it.enabled:
                it.cost_rub = round(pir_net * (it.relative_share_percent / 100.0), 2)
                it.labor_days = round(ref_days * (it.relative_share_percent / 100.0), 1)
            else:
                it.cost_rub = 0.0
                it.labor_days = 0.0

    elif method == CalculationMethod.LABOR_707:
        # Выбран нормативный расчёт В1 строго по Методике № 707/пр (п. 143–149, ф. 8.12–8.14)
        pir_net = labor_707_net
        # В структуре 707/пр: себестоимость = Ц / (1 + Р), прямая ЗП = себестоимость * К_3
        cost_price_707 = round(pir_net / (1.0 + p_707), 2)
        direct_zp_707 = round(cost_price_707 * k3_707, 2)
        overhead_707 = round(cost_price_707 - direct_zp_707, 2)
        profit_707 = round(pir_net - cost_price_707, 2)

        cost_params.total_labor_days = round(sum_t_707, 1)
        cost_params.direct_labor_cost_rub = direct_zp_707
        cost_params.overhead_rub = overhead_707
        cost_params.profit_rub = profit_707
        cost_params.pir_only_cost_net_rub = pir_net
        cost_params.target_total_cost_net = round(pir_net / max(k_multipliers, 0.01), 2)

        for it in cost_params.sections_costs:
            if it.enabled:
                it.cost_rub = round(pir_net * (it.relative_share_percent / 100.0), 2)
                it.labor_days = round(sum_t_707 * (it.relative_share_percent / 100.0), 1)
            else:
                it.cost_rub = 0.0
                it.labor_days = 0.0

    elif method == CalculationMethod.LABOR_INTERNAL:
        # Выбран коммерческий расчёт В2 по таблице рыночной стоимости специалистов (Тюмень)
        pir_net = mkt_net
        cost_params.total_labor_days = round(mkt_total_days, 1)
        cost_params.direct_labor_cost_rub = mkt_direct_wage
        cost_params.overhead_rub = mkt_overhead
        cost_params.profit_rub = mkt_profit
        cost_params.pir_only_cost_net_rub = pir_net
        cost_params.target_total_cost_net = round(pir_net / max(k_multipliers, 0.01), 2)
        if mkt_total_days > 0:
            cost_params.average_daily_rate_rub = round(mkt_direct_wage / mkt_total_days, 2)

        for it in cost_params.sections_costs:
            if it.enabled:
                it.cost_rub = round(pir_net * (it.relative_share_percent / 100.0), 2)
                it.labor_days = round(mkt_total_days * (it.relative_share_percent / 100.0), 1)
            else:
                it.cost_rub = 0.0
                it.labor_days = 0.0

    elif method == CalculationMethod.FROM_SMR:
        pir_net = smr_pir_rub
        if pir_net <= 0:
            warnings.append("Расчёт от СМР: не задана стоимость строительства (СМР) — стоимость не рассчитана.")
        cost_params.pir_only_cost_net_rub = pir_net
        cost_params.target_total_cost_net = round(pir_net / max(k_multipliers, 0.01), 2)

        ref_days = sum_t_707 if sum_t_707 > 0 else mkt_total_days
        cost_params.total_labor_days = round(ref_days, 1)
        cost_params.direct_labor_cost_rub = mkt_direct_wage
        cost_params.overhead_rub = mkt_overhead
        cost_params.profit_rub = mkt_profit

        for it in cost_params.sections_costs:
            if it.enabled:
                it.cost_rub = round(pir_net * (it.relative_share_percent / 100.0), 2)
                it.labor_days = round(ref_days * (it.relative_share_percent / 100.0), 1)
            else:
                it.cost_rub = 0.0
                it.labor_days = 0.0

    elif method == CalculationMethod.PERCENT_SHARE:
        effective_net = round(cost_params.target_total_cost_net * k_multipliers, 2)
        if effective_net <= 0:
            warnings.append("Расчёт по долям: не задана целевая стоимость ПИР — стоимость не рассчитана.")
        cost_params.pir_only_cost_net_rub = effective_net
        ref_days = sum_t_707 if sum_t_707 > 0 else mkt_total_days
        cost_params.total_labor_days = round(ref_days, 1)
        cost_params.direct_labor_cost_rub = mkt_direct_wage
        cost_params.overhead_rub = mkt_overhead
        cost_params.profit_rub = mkt_profit

        for it in cost_params.sections_costs:
            if it.enabled:
                it.cost_rub = round(effective_net * (it.relative_share_percent / 100.0), 2)
                it.labor_days = round(ref_days * (it.relative_share_percent / 100.0), 1)
            else:
                it.cost_rub = 0.0
                it.labor_days = 0.0

    else:
        # LABOR_EFFORT (обратная совместимость)
        daily_rate = max(cost_params.average_daily_rate_rub, 100.0)
        active_items = [it for it in cost_params.sections_costs if it.enabled]
        total_days = sum(it.labor_days for it in active_items)
        if total_days <= 0:
            total_days = max(len(active_items) * 10.0, 10.0)
            even_days = round(total_days / len(active_items), 1) if active_items else 10.0
            for it in active_items:
                it.labor_days = even_days

        cost_params.total_labor_days = round(total_days, 1)
        direct_labor = round(total_days * daily_rate, 2)
        overhead = round(direct_labor * (cost_params.overhead_percent / 100.0), 2)
        cost_price = direct_labor + overhead
        profit = round(cost_price * (cost_params.profit_percent / 100.0), 2)
        base_net = cost_price + profit
        effective_net = round(base_net * k_multipliers, 2)

        cost_params.direct_labor_cost_rub = direct_labor
        cost_params.overhead_rub = overhead
        cost_params.profit_rub = profit
        cost_params.pir_only_cost_net_rub = effective_net
        cost_params.target_total_cost_net = round(effective_net / max(k_multipliers, 0.01), 2)

        for it in cost_params.sections_costs:
            if it.enabled and total_days > 0:
                share = round((it.labor_days / total_days) * 100.0, 2)
                it.relative_share_percent = share
                it.cost_rub = round(effective_net * (it.labor_days / total_days), 2)
            else:
                it.relative_share_percent = 0.0
                it.cost_rub = 0.0

    # Заполняем разбивку cost_pd_rub / cost_rd_rub внутри каждого раздела
    pd_part = max(min(cost_params.pd_stage_share_pct, 100.0), 0.0) / 100.0
    rd_part = round(1.0 - pd_part, 4)
    for it in cost_params.sections_costs:
        if not it.enabled:
            it.cost_pd_rub = 0.0
            it.cost_rd_rub = 0.0
        elif it.stage == "П":
            it.cost_pd_rub = it.cost_rub
            it.cost_rd_rub = 0.0
        elif it.stage == "Р":
            it.cost_pd_rub = 0.0
            it.cost_rd_rub = it.cost_rub
        else:
            it.cost_pd_rub = round(it.cost_rub * pd_part, 2)
            it.cost_rd_rub = round(it.cost_rub * rd_part, 2)

    # Итоговая стоимость без НДС = основные ПИР + включенные дополнительные работы
    cost_params.total_cost_net_rub = round(cost_params.pir_only_cost_net_rub + add_works_sum, 2)

    # Расчёт НДС: 0%, 5% или 22% (с 01.01.2026 общая ставка 22%); «без НДС» = include_vat=False
    if cost_params.vat_rate not in VAT_RATES_ALLOWED:
        warnings.append(f"Ставка НДС {cost_params.vat_rate:g}% не из списка 0/5/22% — проверьте")
    if cost_params.include_vat:
        cost_params.vat_rub = round(cost_params.total_cost_net_rub * (cost_params.vat_rate / 100.0), 2)
        cost_params.total_cost_gross_rub = round(cost_params.total_cost_net_rub + cost_params.vat_rub, 2)
    else:
        cost_params.vat_rub = 0.0
        cost_params.total_cost_gross_rub = cost_params.total_cost_net_rub

    cost_params.warnings = warnings
    return cost_params
