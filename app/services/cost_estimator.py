from typing import Dict, List, Optional
from app.models import CalculationMethod, CostParameters, FacilityType, ProjectData, SectionCostItem


# Нормативные базовые доли распределения стоимости разработки разделов (по СБЦ и Методике № 707/пр Минстроя РФ)
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
        # Если все доли были нулями, распределяем равномерно
        even_share = round(100.0 / len(active_items), 2)
        for it in active_items:
            it.relative_share_percent = even_share
    else:
        for it in active_items:
            it.relative_share_percent = round((it.relative_share_percent / current_sum) * 100.0, 2)

    # Корректировка разницы округления (наибольшему активному разделу)
    new_sum = sum(it.relative_share_percent for it in active_items)
    diff = round(100.0 - new_sum, 2)
    if abs(diff) > 0.001:
        largest = max(active_items, key=lambda x: x.relative_share_percent)
        largest.relative_share_percent = round(largest.relative_share_percent + diff, 2)

    # Неактивные разделы обнуляем
    for it in items:
        if not it.enabled:
            it.relative_share_percent = 0.0


def init_cost_parameters(project_data: ProjectData) -> CostParameters:
    """
    Создает и рассчитывает структуру стоимости и трудоемкости
    на основе состава разделов проекта.
    """
    is_linear = project_data.facility_type == FacilityType.LINEAR
    shares_map = DEFAULT_LINEAR_SHARES if is_linear else DEFAULT_CAPITAL_SHARES

    cost_items: List[SectionCostItem] = []
    for sec in project_data.sections:
        base_share = shares_map.get(sec.id, 2.0)
        is_rd = getattr(sec, "stage", "П") == "Р"
        vol_label = (f"РД-{sec.volume_num}" if sec.volume_num else "РД") if is_rd else sec.volume_num
        title_label = f"[РД] {sec.title}" if is_rd and not sec.title.startswith("[РД]") else sec.title
        item = SectionCostItem(
            section_id=sec.id,
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

    cost_params = CostParameters(
        calculation_method=CalculationMethod.PERCENT_SHARE,
        target_total_cost_net=3000000.0,
        include_vat=True,
        vat_rate=5.0,
        average_daily_rate_rub=12000.0,
        overhead_percent=60.0,
        profit_percent=20.0,
        complexity_factor=1.0,
        is_reconstruction=False,
        use_bim=False,
        urgency_factor=1.0,
        sections_costs=cost_items,
    )

    recalculate_cost_parameters(cost_params)
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
    existing_map = {item.section_id: item for item in cost_params.sections_costs}
    is_linear = project_data.facility_type == FacilityType.LINEAR
    shares_map = DEFAULT_LINEAR_SHARES if is_linear else DEFAULT_CAPITAL_SHARES

    new_items: List[SectionCostItem] = []
    for sec in project_data.sections:
        is_rd = getattr(sec, "stage", "П") == "Р"
        vol_label = (f"РД-{sec.volume_num}" if sec.volume_num else "РД") if is_rd else sec.volume_num
        title_label = f"[РД] {sec.title}" if is_rd and not sec.title.startswith("[РД]") else sec.title
        if sec.id in existing_map:
            item = existing_map[sec.id]
            item.volume_num = vol_label
            item.code_mark = sec.code_mark
            item.full_code = sec.full_code or sec.code_mark
            item.title = title_label
            item.enabled = sec.enabled
            if not sec.enabled:
                item.relative_share_percent = 0.0
            elif item.relative_share_percent == 0.0:
                item.relative_share_percent = shares_map.get(sec.id, 2.0)
            new_items.append(item)
        else:
            base_share = shares_map.get(sec.id, 2.0)
            item = SectionCostItem(
                section_id=sec.id,
                volume_num=vol_label,
                code_mark=sec.code_mark,
                full_code=sec.full_code or sec.code_mark,
                title=title_label,
                relative_share_percent=base_share if sec.enabled else 0.0,
                department=get_default_department(sec.id),
                enabled=sec.enabled,
            )
            new_items.append(item)

    cost_params.sections_costs = new_items
    normalize_active_shares(cost_params.sections_costs)
    recalculate_cost_parameters(cost_params)


def recalculate_cost_parameters(cost_params: CostParameters) -> CostParameters:
    """
    Выполняет математический расчет стоимостных и трудовых показателей
    в зависимости от выбранного метода (PERCENT_SHARE или LABOR_EFFORT).
    """
    # Мультипликаторы условий проектирования
    reconstr_k = 1.20 if cost_params.is_reconstruction else 1.0
    bim_k = 1.15 if cost_params.use_bim else 1.0
    k_multipliers = round(cost_params.complexity_factor * reconstr_k * bim_k * cost_params.urgency_factor, 4)

    active_items = [it for it in cost_params.sections_costs if it.enabled]

    # Эффективная себестоимость одного дня работы с накладными и плановой прибылью
    daily_rate = max(cost_params.average_daily_rate_rub, 100.0)
    overhead_k = 1.0 + (cost_params.overhead_percent / 100.0)
    profit_k = 1.0 + (cost_params.profit_percent / 100.0)
    effective_daily_cost = daily_rate * overhead_k * profit_k

    if cost_params.calculation_method == CalculationMethod.PERCENT_SHARE:
        # МЕТОД 1: Расчет от целевой стоимости договора по долям СБЦ
        normalize_active_shares(cost_params.sections_costs)

        effective_net = round(cost_params.target_total_cost_net * k_multipliers, 2)
        total_days = 0.0

        for it in cost_params.sections_costs:
            if it.enabled:
                sec_cost = round(effective_net * (it.relative_share_percent / 100.0), 2)
                it.cost_rub = sec_cost
                # Оценка трудоемкости в днях
                days = round(sec_cost / effective_daily_cost, 1) if effective_daily_cost > 0 else 1.0
                it.labor_days = max(days, 0.5)
                total_days += it.labor_days
            else:
                it.cost_rub = 0.0
                it.labor_days = 0.0

        cost_params.total_labor_days = round(total_days, 1)
        cost_params.direct_labor_cost_rub = round(total_days * daily_rate, 2)
        cost_params.overhead_rub = round(cost_params.direct_labor_cost_rub * (cost_params.overhead_percent / 100.0), 2)
        cost_params.profit_rub = round(
            (cost_params.direct_labor_cost_rub + cost_params.overhead_rub) * (cost_params.profit_percent / 100.0), 2
        )
        cost_params.total_cost_net_rub = effective_net

    else:
        # МЕТОД 2: Расчет по трудозатратам специалистов (Форма 3П)
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
        cost_params.total_cost_net_rub = effective_net
        cost_params.target_total_cost_net = round(effective_net / k_multipliers, 2)

        # Распределяем доли и стоимость по разделам пропорционально трудоемкости
        for it in cost_params.sections_costs:
            if it.enabled and total_days > 0:
                share = round((it.labor_days / total_days) * 100.0, 2)
                it.relative_share_percent = share
                it.cost_rub = round(effective_net * (it.labor_days / total_days), 2)
            else:
                it.relative_share_percent = 0.0
                it.cost_rub = 0.0

    # Расчет НДС
    if cost_params.include_vat:
        cost_params.vat_rub = round(cost_params.total_cost_net_rub * (cost_params.vat_rate / 100.0), 2)
        cost_params.total_cost_gross_rub = round(cost_params.total_cost_net_rub + cost_params.vat_rub, 2)
    else:
        cost_params.vat_rub = 0.0
        cost_params.total_cost_gross_rub = cost_params.total_cost_net_rub

    return cost_params
