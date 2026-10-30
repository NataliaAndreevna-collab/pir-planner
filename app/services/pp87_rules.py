"""
Справочники разделов ПД (ПП РФ № 87), марок РД (ГОСТ Р 21.101) и построение календарного графика.
"""
import calendar
import datetime
import re
from typing import Dict, List, Optional, Tuple

from app.models import FacilityType, ProjectData, ProjectMode, SchedulePhase, SectionItem


# ---------------------------------------------------------------------------
# Шифры
# ---------------------------------------------------------------------------

def compute_cipher_from_contract(contract_number: str, contract_date: str = "") -> str:
    """
    Формирует базовый шифр проекта по стандарту:
    {Номер договора}ТПС-{ГГ}
    Например: "12ТПС/0926" от "23.09.2026" -> "12ТПС-26"
    """
    if not contract_number:
        return ""

    # Извлекаем ведущий номер договора (например, 12 из 12ТПС/0926)
    match_num = re.search(r"^(\d+)", contract_number.strip())
    prefix = match_num.group(1) if match_num else "01"

    # Извлекаем год из даты или из самого номера (например, 2026 -> 26 или /0926 -> 26)
    year_suffix = "26"
    if contract_date:
        match_year = re.search(r"20(\d{2})", contract_date)
        if match_year:
            year_suffix = match_year.group(1)
    else:
        match_year_in_num = re.search(r"(\d{2})$", contract_number.strip())
        if match_year_in_num:
            year_suffix = match_year_in_num.group(1)

    return f"{prefix}ТПС-{year_suffix}"


def renumber_sections(project_data: ProjectData) -> None:
    """
    Перенумерация:
    - подразделы «Иной документации» (Раздел 13 / Раздел 10) идут подряд только по включенным томам;
    - тома РД нумеруются по порядку включенных марок.
    """
    other_prefix = {"13": 0, "10": 0}
    rd_counter = 0
    for sec in project_data.sections:
        if sec.stage == "Р":
            if sec.enabled:
                rd_counter += 1
                sec.volume_num = str(rd_counter)
            else:
                sec.volume_num = ""
            continue
        header = sec.category_header or ""
        m = re.match(r"Раздел (13|10)\. Иная", header)
        if m and sec.enabled:
            key = m.group(1)
            other_prefix[key] += 1
            sec.volume_num = f"{key}.{other_prefix[key]}"


def apply_volume_ciphers(project_data: ProjectData) -> None:
    """
    Обновляет номера томов и поле full_code у каждого раздела в зависимости от режима:
    - В режиме PRE_CONTRACT: только марка (например, "АР", "КР", "ИОС1")
    - В режиме CONTRACT: {базовый_шифр}-{марка} (например, "12ТПС-26-АР")
    """
    cipher = project_data.cipher.strip() if project_data.cipher else ""
    if not cipher and project_data.contract_number:
        cipher = compute_cipher_from_contract(project_data.contract_number, project_data.contract_date)
        project_data.cipher = cipher

    renumber_sections(project_data)

    for sec in project_data.sections:
        if project_data.mode == ProjectMode.CONTRACT and cipher:
            sec.full_code = f"{cipher}-{sec.code_mark}"
        else:
            sec.full_code = sec.code_mark


# ---------------------------------------------------------------------------
# Справочник разделов проектной документации (ПП РФ № 87)
# ---------------------------------------------------------------------------

SEC5 = "Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения"
SEC12 = "Раздел 12. Смета на строительство, реконструкцию, капитальный ремонт, снос объекта капитального строительства"
SEC13 = "Раздел 13. Иная документация в случаях, предусмотренных законодательными и иными нормативными правовыми актами РФ"
LIN9 = "Раздел 9. Смета на строительство"
LIN10 = "Раздел 10. Иная документация"

# (id, № тома, марка, наименование, группирующий заголовок, обязателен по ПП 87, включен по умолчанию)
_CAPITAL = [
    ("pz", "1", "ПЗ", "Раздел 1. Пояснительная записка", None, True, True),
    ("pzu", "2", "ПЗУ", "Раздел 2. Схема планировочной организации земельного участка", None, True, True),
    ("ar", "3", "АР", "Раздел 3. Архитектурные решения", None, True, True),
    ("kr", "4", "КР", "Раздел 4. Конструктивные и объемно-планировочные решения", None, True, True),
    ("ios1", "5.1", "ИОС1", "Подраздел 1. Система электроснабжения", SEC5, True, True),
    ("ios2", "5.2", "ИОС2", "Подраздел 2. Система водоснабжения", SEC5, True, True),
    ("ios3", "5.3", "ИОС3", "Подраздел 3. Система водоотведения", SEC5, True, True),
    ("ios4", "5.4", "ИОС4", "Подраздел 4. Отопление, вентиляция и кондиционирование воздуха, тепловые сети", SEC5, True, True),
    ("ios5_1", "5.5.1", "ИОС5.1", "Подраздел 5. Сети связи. Часть 1. Слаботочные сети", SEC5, True, True),
    ("ios5_2", "5.5.2", "ИОС5.2", "Подраздел 5. Сети связи. Часть 2. Автоматизация комплексная", SEC5, False, False),
    ("ios6", "5.6", "ИОС6", "Подраздел 6. Система газоснабжения", SEC5, False, False),
    ("tx", "6", "ТХ", "Раздел 6. Технологические решения", None, False, False),
    ("pos", "7", "ПОС", "Раздел 7. Проект организации строительства", None, True, True),
    ("oos", "8", "ООС", "Раздел 8. Перечень мероприятий по охране окружающей среды", None, True, True),
    ("pb", "9", "ПБ", "Раздел 9. Мероприятия по обеспечению пожарной безопасности", None, True, True),
    ("tbe", "10", "ТБЭ", "Раздел 10. Требования к безопасной эксплуатации объекта капитального строительства", None, True, True),
    ("odi", "11", "ОДИ", "Раздел 11. Мероприятия по обеспечению доступа инвалидов", None, False, False),
    ("sm", "12.1", "СМ", "Часть 1. Сметы", SEC12, False, False),
    ("sm_p", "12.2", "СМ.П", "Часть 2. Конъюнктурный анализ. Прайс-листы", SEC12, False, False),
    ("sm_vor", "12.3", "СМ.ВОР", "Часть 3. Ведомости объемов работ", SEC12, False, False),
    ("gochs", "13.1", "ГОЧС", "Перечень мероприятий по гражданской обороне, мероприятий по предупреждению чрезвычайных ситуаций природного и техногенного характера", SEC13, False, False),
    ("ots", "13.2", "ОТС", "Обследование технического состояния", SEC13, False, False),
    ("ee", "13.3", "ЭЭ", "Мероприятия по обеспечению соблюдения требований энергетической эффективности", SEC13, False, False),
    ("pod", "13.4", "ПОД", "Проект организации работ по сносу (демонтажу)", SEC13, False, False),
]

_LINEAR = [
    ("pz", "1", "ПЗ", "Раздел 1. Пояснительная записка", None, True, True),
    ("ppo", "2", "ППО", "Раздел 2. Проект полосы отвода", None, True, True),
    ("tkr", "3", "ТКР", "Раздел 3. Технологические и конструктивные решения линейного объекта. Искусственные сооружения", None, True, True),
    ("lin_infra", "4", "ИЛО", "Раздел 4. Здания, строения и сооружения, входящие в инфраструктуру линейного объекта", None, False, False),
    ("pos", "5", "ПОС", "Раздел 5. Проект организации строительства", None, True, True),
    ("pod", "6", "ПОД", "Раздел 6. Проект организации работ по сносу (демонтажу) линейного объекта", None, False, False),
    ("oos", "7", "ООС", "Раздел 7. Мероприятия по охране окружающей среды", None, True, True),
    ("pb", "8", "ПБ", "Раздел 8. Мероприятия по обеспечению пожарной безопасности", None, True, True),
    ("sm", "9.1", "СМ", "Часть 1. Сводный сметный расчет и сметы", LIN9, False, False),
    ("sm_vor", "9.2", "СМ.ВОР", "Часть 2. Ведомости объемов работ", LIN9, False, False),
    ("gochs", "10.1", "ГОЧС", "Перечень мероприятий по гражданской обороне и предупреждению ЧС", LIN10, False, False),
    ("rekult", "10.2", "ПРЗ", "Проект рекультивации нарушенных земель", LIN10, False, False),
    ("ots", "10.3", "ОТС", "Обследование технического состояния", LIN10, False, False),
]


def _make_pd(rows) -> List[SectionItem]:
    return [
        SectionItem(id=i, stage="П", volume_num=v, code_mark=m, title=t, category_header=h,
                    required_by_norm=req, enabled=on, source="default")
        for (i, v, m, t, h, req, on) in rows
    ]


def get_default_capital_sections() -> List[SectionItem]:
    """Базовый состав разделов ПД для объектов капитального строительства (Раздел II ПП 87)."""
    return _make_pd(_CAPITAL)


def get_default_linear_sections() -> List[SectionItem]:
    """Базовый состав разделов ПД для линейных объектов (Раздел III ПП 87)."""
    return _make_pd(_LINEAR)


# ---------------------------------------------------------------------------
# Справочник марок рабочей документации (ГОСТ Р 21.101)
# ---------------------------------------------------------------------------

# (id, марка, наименование, связанные разделы ПД, включать по умолчанию при наличии связанного раздела)
RD_CATALOG = [
    ("rd_gp", "ГП", "Генеральный план", ["pzu"], True),
    ("rd_ar", "АР", "Архитектурные решения", ["ar"], True),
    ("rd_as", "АС", "Архитектурно-строительные решения", [], False),
    ("rd_kzh", "КЖ", "Конструкции железобетонные", ["kr"], True),
    ("rd_km", "КМ", "Конструкции металлические", ["kr"], True),
    ("rd_kd", "КД", "Конструкции деревянные", [], False),
    ("rd_eom", "ЭОМ", "Силовое электрооборудование и электрическое освещение", ["ios1"], True),
    ("rd_es", "ЭС", "Наружные сети электроснабжения", [], False),
    ("rd_vk", "ВК", "Внутренние системы водоснабжения и канализации", ["ios2", "ios3"], True),
    ("rd_nvk", "НВК", "Наружные сети водоснабжения и канализации", ["ios2", "ios3"], True),
    ("rd_ov", "ОВ", "Отопление, вентиляция и кондиционирование", ["ios4"], True),
    ("rd_ts", "ТС", "Тепловые сети", [], False),
    ("rd_ss", "СС", "Системы связи", ["ios5_1"], True),
    ("rd_ak", "АК", "Автоматизация комплексная", ["ios5_2"], True),
    ("rd_gsn", "ГСН", "Наружные сети газоснабжения", ["ios6"], True),
    ("rd_tx", "ТХ", "Технологические решения", ["tx"], True),
    ("rd_aps", "АПС", "Автоматическая пожарная сигнализация и СОУЭ", [], False),
    ("rd_ad", "АД", "Автомобильные дороги", [], False),
    ("rd_sm", "СМ", "Сметная документация", ["sm"], True),
]

# Для линейных объектов марки РД выбираются по виду сети, упомянутой в ТЗ
LINEAR_RD_BY_NETWORK = [
    ("rd_nvk", r"водоснабжени|водоотведени|канализаци|водопровод|водовод|коллектор"),
    ("rd_ts", r"теплоснабжени|теплов\w*\s+сет|теплотрасс"),
    ("rd_es", r"электроснабжени|кабельн\w*\s+лини|\bвл\b|\bкл\b|лэп"),
    ("rd_gsn", r"газоснабжени|газопровод"),
    ("rd_ad", r"автомобильн\w*\s+дорог|проезд"),
]


def build_rd_sections(facility: FacilityType, pd_sections: List[SectionItem], text_lower: str = "") -> List[SectionItem]:
    """Формирует список марок РД; включение по умолчанию - по связанным включенным разделам ПД."""
    enabled_pd = {s.id for s in pd_sections if s.enabled}
    linear_on = set()
    if facility == FacilityType.LINEAR:
        for rid, pattern in LINEAR_RD_BY_NETWORK:
            if re.search(pattern, text_lower):
                linear_on.add(rid)
        if not linear_on:
            linear_on.add("rd_nvk")
    result = []
    for rid, mark, title, linked, default_on in RD_CATALOG:
        if facility == FacilityType.LINEAR:
            on = rid in linear_on or (rid == "rd_sm" and "sm" in enabled_pd)
        else:
            on = default_on and any(l in enabled_pd for l in linked)
        result.append(SectionItem(id=rid, stage="Р", code_mark=mark, title=title, enabled=on, source="default"))
    return result


# ---------------------------------------------------------------------------
# Календарный график
# ---------------------------------------------------------------------------

GROUPS: Dict[str, str] = {
    "precontract": "Организационно-договорной этап",
    "survey": "Сбор ИД и инженерные изыскания",
    "tx_concept": "Согласование технологии и концепции",
    "pd": "Проектная документация (стадия ПД)",
    "approval": "Согласование проектных решений с Заказчиком",
    "internal_rvk": "Внутренняя экспертиза ООО «Тюмень Водоканал» (до 30 дн.)",
    "expertise": "Государственная / негосударственная экспертиза (ПД + РИИ + Сметы)",
    "rd": "Рабочая документация (стадия РД)",
    "other": "Прочие согласования и завершение",
}

# Цвета групп (hex без #) - используются в Excel и в интерфейсе
GROUP_COLORS: Dict[str, str] = {
    "precontract": "475569", # Тёмно-серый / сланец (Договор)
    "survey": "10B981",      # Изумрудный (Изыскания)
    "tx_concept": "F97316",  # Оранжевый (Технология)
    "pd": "2563EB",          # Синий (ПД)
    "approval": "D97706",    # Янтарный (Согласования)
    "internal_rvk": "0284C7",# Сине-голубой / морской (Внутренняя экспертиза РВК)
    "expertise": "9333EA",   # Пурпурный (Госэкспертиза)
    "rd": "0D9488",          # Бирюзовый (РД)
    "other": "64748B",       # Серо-голубой (Прочее)
}

# Типовые длительности разработки разделов ПД, в календарных днях (и неделях)
PD_DURATION_DAYS = {
    "pz": 14, "pzu": 28, "ar": 42, "kr": 56, "ios1": 42, "ios2": 42, "ios3": 42, "ios4": 42,
    "ios5_1": 35, "ios5_2": 42, "ios6": 35, "tx": 49, "pos": 28, "pod": 21, "oos": 35, "pb": 28,
    "tbe": 14, "odi": 14, "sm": 28, "sm_p": 21, "sm_vor": 21, "gochs": 21, "ee": 14,
    "ppo": 28, "tkr": 56, "lin_infra": 42, "rekult": 21,
}
PD_DURATION = {k: v // 7 for k, v in PD_DURATION_DAYS.items()}
RD_DURATION_DAYS = {"rd_kzh": 56, "rd_tx": 49, "rd_gp": 28, "rd_sm": 28}
RD_DURATION = {"rd_kzh": 8, "rd_tx": 7, "rd_gp": 4, "rd_sm": 4}

# Очередность разработки разделов ПД (волны)
PD_WAVES = [
    {"pzu", "ar", "kr", "ios1", "ios2", "ios3", "ios4", "ios5_1", "ios5_2", "ios6", "tx", "ppo", "tkr", "lin_infra"},
    {"pos", "pod", "oos", "pb", "tbe", "odi", "gochs", "ee", "rekult"},
    {"sm", "sm_p", "sm_vor"},
    {"pz"},
]


def short_title(title: str) -> str:
    t = re.sub(r"^(?:Раздел|Подраздел|Часть)\s*\d+(?:\.\d+)*\.?\s*", "", title or "").strip()
    return t[:90]


def parse_date(date_str: str) -> Optional[datetime.date]:
    """Парсит строку даты вида ГГГГ-ММ-ДД или ДД.ММ.ГГГГ."""
    if not date_str:
        return None
    s = date_str.strip()[:10]
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def format_date_iso(dt: Optional[datetime.date]) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def format_date_ru(dt: Optional[datetime.date]) -> str:
    return dt.strftime("%d.%m.%Y") if dt else ""


def date_to_decade_index(dt: datetime.date, base_y: int, base_m: int) -> int:
    """
    Возвращает 0-based индекс декады относительно года и месяца базового старта проекта.
    Декада 0: 1-10 число, 1: 11-20 число, 2: 21-конец месяца.
    """
    month_offset = (dt.year - base_y) * 12 + (dt.month - base_m)
    dec = 0 if dt.day <= 10 else (1 if dt.day <= 20 else 2)
    return month_offset * 3 + dec


def phase_end_excl(p: SchedulePhase) -> int:
    """Неделя, следующая за окончанием этапа (для вехи - следующая за неделей вехи)."""
    if p.milestone:
        return p.start_week + 1
    return p.start_week + max(p.duration_weeks, 1)


def resolve_schedule(phases: List[SchedulePhase], base_start_date_str: str = "") -> None:
    """
    Пересчет начала и окончания этапов по зависимостям:
    - Расчет ведется в точных календарных днях и датах.
    - Начало этапа = max(окончание активных предшественников + 1 день) + lag_days.
    - При отключении предшественников активные зависимости ищутся транзитивно.
    - Если минимальный старт среди включенных этапов сдвинут, график автоматически нормализуется
      к базовой дате проекта (start_date).
    - Также заполняются start_week и duration_weeks для обратной совместимости.
    """
    base_dt = parse_date(base_start_date_str) or datetime.date.today()
    by_id = {p.id: p for p in phases}

    def get_active_ancestors(pid: int, visited: Optional[set] = None) -> List[SchedulePhase]:
        """Рекурсивно находит ближайших включенных (enabled) предшественников."""
        if visited is None:
            visited = set()
        if pid in visited or pid not in by_id:
            return []
        visited.add(pid)
        parent = by_id[pid]
        if getattr(parent, "enabled", True):
            return [parent]
        result = []
        for grand_id in parent.depends_on:
            result.extend(get_active_ancestors(grand_id, visited))
        return result

    # 1. Топологический расчет дат старта и окончания в днях
    for _ in range(len(phases) + 2):
        changed = False
        for p in phases:
            if not getattr(p, "enabled", True):
                continue
            deps = []
            for d in p.depends_on:
                deps.extend(get_active_ancestors(d))
            deps = [d for d in {d.id: d for d in deps}.values() if d.id != p.id]

            # Длительность в днях
            dur_days = 0 if p.milestone else max(1, getattr(p, "duration_days", 0) or (p.duration_weeks * 7 if p.duration_weeks else 14))
            p.duration_days = 0 if p.milestone else dur_days
            lag_d = getattr(p, "lag_days", 0) or (p.lag_weeks * 7)

            if deps:
                # Финиш предшественников
                dep_end_dates = []
                for d in deps:
                    d_finish = parse_date(d.finish_date)
                    if not d_finish:
                        d_start = parse_date(d.start_date) or base_dt
                        d_dur = 0 if d.milestone else max(1, getattr(d, "duration_days", 14))
                        d_finish = d_start if d.milestone else d_start + datetime.timedelta(days=max(0, d_dur - 1))
                    dep_end_dates.append(d_finish)

                max_dep_finish = max(dep_end_dates)
                if p.milestone:
                    calc_start = max_dep_finish + datetime.timedelta(days=lag_d)
                else:
                    calc_start = max_dep_finish + datetime.timedelta(days=1 + lag_d)
                new_start_dt = max(base_dt, calc_start)
            else:
                new_start_dt = base_dt

            curr_start_dt = parse_date(p.start_date)
            if curr_start_dt != new_start_dt:
                p.start_date = format_date_iso(new_start_dt)
                changed = True

            # Вычисляем finish_date
            if p.milestone:
                new_finish_dt = new_start_dt
            else:
                new_finish_dt = new_start_dt + datetime.timedelta(days=max(0, p.duration_days - 1))
            if parse_date(p.finish_date) != new_finish_dt:
                p.finish_date = format_date_iso(new_finish_dt)
                changed = True

        if not changed:
            break

    # 2. Нормализация к базовой дате: если все активные этапы начинаются позже base_dt
    enabled_phases = [p for p in phases if getattr(p, "enabled", True)]
    if enabled_phases:
        earliest_start = min(parse_date(p.start_date) or base_dt for p in enabled_phases)
        if earliest_start > base_dt:
            shift_days = (earliest_start - base_dt).days
            for p in enabled_phases:
                p_st = parse_date(p.start_date) or base_dt
                new_st = p_st - datetime.timedelta(days=shift_days)
                p.start_date = format_date_iso(new_st)
                if p.milestone:
                    p.finish_date = p.start_date
                else:
                    p.finish_date = format_date_iso(new_st + datetime.timedelta(days=max(0, p.duration_days - 1)))

    # 3. Синхронизируем start_week и duration_weeks для совместимости со старыми вызовами
    for p in enabled_phases:
        p_st = parse_date(p.start_date) or base_dt
        day_offset = max(0, (p_st - base_dt).days)
        p.start_week = max(1, (day_offset // 7) + 1)
        p.duration_weeks = 0 if p.milestone else max(1, int(round(p.duration_days / 7.0)))


def total_calendar_days(phases: List[SchedulePhase], base_start_date_str: str = "") -> int:
    """Вычисляет суммарную продолжительность проекта в календарных днях."""
    enabled_phases = [p for p in phases if getattr(p, "enabled", True)]
    if not enabled_phases:
        return 0
    base_dt = parse_date(base_start_date_str) or parse_date(enabled_phases[0].start_date) or datetime.date.today()
    max_finish = base_dt
    for p in enabled_phases:
        f_dt = parse_date(p.finish_date)
        if f_dt and f_dt > max_finish:
            max_finish = f_dt
    return max(1, (max_finish - base_dt).days + 1)


def total_weeks(phases: List[SchedulePhase]) -> int:
    enabled_phases = [p for p in phases if getattr(p, "enabled", True)]
    return max((phase_end_excl(p) - 1 for p in enabled_phases), default=0)


def build_schedule(project: ProjectData, detail: Optional[str] = None) -> List[SchedulePhase]:
    """
    Строит календарный график по составу проекта и признакам ТЗ в точных календарных днях.
    detail = "sections" - по разделам/маркам, "stages" - укрупненно по стадиям.
    Учитывает преддоговорной этап (Этап 0), передачу ИД Заказчиком (Этап 1),
    согласование технологии/концепции, экспертизу и вехи К0-К5.
    """
    detail = detail or project.schedule_detail or "sections"
    flags = project.schedule_flags or {}
    phases: List[SchedulePhase] = []
    counter = [0]

    def add(name, group, dur_days, deps=None, lag_days=0, milestone=False, note="", resp_party="Проектировщик", status="В работе", enabled=True) -> int:
        counter[0] += 1
        d_days = 0 if milestone else max(1, int(dur_days))
        d_weeks = 0 if milestone else max(1, int(round(d_days / 7.0)))
        lag_d = int(lag_days)
        lag_w = int(round(lag_d / 7.0))
        phases.append(SchedulePhase(
            id=counter[0], name=name, group=group, start_week=1,
            duration_weeks=d_weeks, duration_days=d_days,
            depends_on=list(deps or []), lag_weeks=lag_w, lag_days=lag_d,
            milestone=milestone, note=note,
            resp_party=resp_party, status=status, enabled=enabled,
        ))
        return counter[0]

    # -----------------------------------------------------------------------
    # Этап 0. Организационно-договорной этап (Pre-Contract)
    # -----------------------------------------------------------------------
    contract_phase_id = add(
        "Согласование существенных условий, заключение договора на ПИР",
        "precontract",
        14,  # 14 календарных дней
        note="Согласование сметы ПИР, порядка приемки и платежей",
        resp_party="Заказчик / Проектировщик",
        status="Согласовано",
    )
    gip_appoint_id = add(
        "Назначение ГИПа и формирование рабочей группы проектировщика",
        "precontract",
        7,
        [contract_phase_id],
        lag_days=-7,
        note="Приказ о назначении ГИПа, фиксация каналов связи",
        resp_party="Проектировщик",
        status="Завершено",
    )
    curator_appoint_id = add(
        "Запрос и назначение куратора проекта со стороны Заказчика",
        "precontract",
        7,
        [contract_phase_id],
        note="Официальное письмо, регламент совещаний и обмена данными",
        resp_party="Заказчик",
        status="Завершено",
    )
    k0_milestone = add(
        "Контрольная точка К0: Договор подписан, ГИП и куратор закреплены",
        "precontract",
        0,
        [gip_appoint_id, curator_appoint_id],
        milestone=True,
        note="Юридический старт проекта",
        resp_party="Заказчик / Проектировщик",
        status="Завершено",
    )

    # -----------------------------------------------------------------------
    # Этап 1. Сбор исходных данных (ИД) и обследование
    # -----------------------------------------------------------------------
    id_collection_id = add(
        "Запрос и сбор исходных данных Заказчиком (ГПЗУ, ТУ, справки, анализ воды)",
        "survey",
        21,  # 21 календарный день
        [k0_milestone],
        note="Обязанность Заказчика; передача паспортов, техусловий, выписок ЕГРН",
        resp_party="Заказчик",
        status="В работе",
    )

    ots_on = any(s.id == "ots" and s.enabled for s in project.sections if s.stage == "П") or flags.get("ots")
    surveys_phases: List[int] = [id_collection_id]

    if ots_on:
        ots_phase = add(
            "Обследование технического состояния строительных конструкций",
            "survey",
            21,
            [id_collection_id],
            lag_days=-7,
            note="ГОСТ 31937-2011; выезд на объект, инструментальный контроль, отчет",
            resp_party="Проектировщик",
            status="В работе",
        )
        surveys_phases.append(ots_phase)

    if flags.get("surveys", True):
        types = flags.get("survey_types") or "ИГДИ, ИГИ, ИЭИ"
        surv_phase = add(
            f"Инженерные изыскания ({types})",
            "survey",
            42,  # 42 календарных дня (~6 недель)
            [id_collection_id],
            lag_days=-7,
            note="Топосъемка, бурение скважин, лаборатория, согласование с сетями",
            resp_party="Проектировщик",
            status="В работе",
        )
        surveys_phases.append(surv_phase)

    k1_milestone = add(
        "Контрольная точка К1: Полный комплект исходных данных и отчетов передан ГИПу",
        "survey",
        0,
        surveys_phases,
        milestone=True,
        note="Разрешение на старт полномасштабного проектирования",
        resp_party="Заказчик",
        status="В работе",
    )

    # -----------------------------------------------------------------------
    # Этап 2. Согласование концепции технологии и генерального плана
    # -----------------------------------------------------------------------
    tx_concept_id = add(
        "Разработка и согласование принципиальной технологии (ТХ) и компоновки",
        "tx_concept",
        14,
        [k1_milestone],
        note="Опросные листы оборудования, технологическая схема, нагрузки для смежников",
        resp_party="Проектировщик / Заказчик",
        status="В работе",
    )
    pzu_agree_id = add(
        "Предварительное согласование схемы генплана (посадка сооружений и сетей)",
        "tx_concept",
        14,
        [tx_concept_id],
        note="Увязка санитарно-защитных зон, подъездов, точек врезки в сети Заказчика",
        resp_party="Заказчик",
        status="В работе",
    )
    k2_milestone = add(
        "Контрольная точка К2: Технологическая схема и генеральный план утверждены",
        "tx_concept",
        0,
        [pzu_agree_id],
        milestone=True,
        note="Фиксация габаритов, весов и мощностей для смежных отделов",
        resp_party="Заказчик / Проектировщик",
        status="В работе",
    )

    pd_secs = [s for s in project.sections if s.stage == "П" and s.enabled and s.id != "ots"] if project.has_pd else []
    rd_secs = [s for s in project.sections if s.stage == "Р" and s.enabled] if project.has_rd else []

    def dev_block(items: List[SectionItem], group: str, deps: List[int], lag_days: int,
                  durations: Dict[str, int], default_dur: int, waves: List[set],
                  stage_name: str, release_name: str) -> int:
        """Блок разработки: волны разделов + веха выпуска. Возвращает id вехи."""
        if detail == "stages":
            total = 0
            prev_exists = False
            for wave in waves + [None]:
                w_items = [s for s in items if (wave is None and not any(s.id in w for w in waves)) or (wave is not None and s.id in wave)]
                if not w_items:
                    continue
                d = max(durations.get(s.id, default_dur) for s in w_items)
                total += d - (14 if prev_exists else 0)
                prev_exists = True
            marks = ", ".join(s.code_mark for s in items)
            dev = add(stage_name, group, max(total, 14), deps, lag_days, note=marks)
            return add(release_name, group, 0, [dev], milestone=True)

        all_ids: List[int] = []
        prev_ids: List[int] = []
        placed = set()
        wave_list = list(waves)
        for wave in wave_list + [None]:
            if wave is None:
                w_items = [s for s in items if s.id not in placed]
            else:
                w_items = [s for s in items if s.id in wave and s.id not in placed]
            if not w_items:
                continue
            if prev_ids:
                w_deps, w_lag = prev_ids, -14 if wave != {"pz"} else -7
            else:
                w_deps, w_lag = deps, lag_days
            ids = []
            for s in w_items:
                placed.add(s.id)
                ids.append(add(f"{s.code_mark} — {short_title(s.title)}", group,
                               durations.get(s.id, default_dur), w_deps, w_lag))
            all_ids.extend(ids)
            prev_ids = ids
        return add(release_name, group, 0, all_ids, milestone=True)

    after_expertise: List[int] = []
    pd_release: Optional[int] = None
    last: List[int] = []  # цепочка последних этапов стадии П; пусто, если ПД не разрабатывается (только РД)

    # -----------------------------------------------------------------------
    # Этап 3. Разработка проектной документации (стадия ПД)
    # -----------------------------------------------------------------------
    if pd_secs:
        pd_release = dev_block(
            pd_secs, "pd", [k2_milestone], 0, PD_DURATION_DAYS, 28, PD_WAVES,
            "Разработка проектной документации (ПП РФ № 87)", "Выпуск проектной документации",
        )

        # 3.1. Согласование с Заказчиком
        # 5 раб. дней рассмотрение Заказчиком (7 кал. дн.) + 7 раб. дней устранение (10 кал. дн.)
        appr_client_exam = add(
            "Рассмотрение проектных решений Заказчиком (5 раб. дней)",
            "approval",
            7,
            [pd_release],
            note="Проверка комплектности и соответствия ТЗ (план Заказчика: 5 раб. дней)",
            resp_party="Заказчик",
            status="На согласовании",
        )
        appr_client_corr = add(
            "Корректировка ПД по замечаниям Заказчика (7 раб. дней)",
            "approval",
            10,
            [appr_client_exam],
            note="Устранение замечаний проектировщиком и повторная передача Заказчику",
            resp_party="Проектировщик",
            status="В работе",
        )
        k3_milestone = add(
            "Контрольная точка К3: Проектная документация согласована Заказчиком",
            "approval",
            0,
            [appr_client_corr],
            milestone=True,
            note="Подписание протокола согласования проектных решений с Заказчиком",
            resp_party="Заказчик / Проектировщик",
            status="В работе",
        )
        last = [k3_milestone]

        # 3.2. Внутренняя экспертиза «Росводоканал» (РВК)
        # Регламент: 1-3 (направление, экспертиза, замечания) = 14 кал. дн.
        # 4 (устранение) = 10 кал. дн., 5 (повторная) = 6 кал. дн. Общий срок строго = 30 кал. дн.
        if flags.get("internal_expertise", True):
            rvk_exam = add(
                "Внутренняя экспертиза РВК (направление, проверка 10 раб. дн., выдача замечаний)",
                "internal_rvk",
                14,
                last,
                note="Процедура управления проектированием объектов ГК Росводоканал (3 кал. дн. передача + 10 раб. дн. проверка)",
                resp_party="Заказчик (РВК)",
                status="В работе",
            )
            rvk_corr = add(
                "Устранение замечаний внутренней экспертизы РВК (10 раб. дней)",
                "internal_rvk",
                10,
                [rvk_exam],
                note="Корректировка документации проектировщиком в регламентный срок (10 раб. дней)",
                resp_party="Проектировщик",
                status="В работе",
            )
            rvk_recheck = add(
                "Повторная проверка внутренней экспертизы РВК и получение заключения (5 раб. дней)",
                "internal_rvk",
                6,
                [rvk_corr],
                note="Контрольный суммарный срок внутренней экспертизы РВК не превышает 30 календарных дней (14 + 10 + 6 = 30 дн.)",
                resp_party="Заказчик (РВК)",
                status="В работе",
            )
            ms_rvk = add(
                "Контрольная точка: Положительное заключение внутренней экспертизы РВК получено",
                "internal_rvk",
                0,
                [rvk_recheck],
                milestone=True,
                note="Официальное согласование РВК для передачи в госэкспертизу или в производство",
                resp_party="Заказчик (РВК)",
                status="В работе",
            )
            last = [ms_rvk]

        # 3.3. Государственная / негосударственная экспертиза (ПД + ИИ + Достоверность смет)
        if flags.get("expertise", True):
            ex_intake = add(
                "Загрузка в Главгосэкспертизу, проверка комплектности и регистрация (3-5 раб. дней)",
                "expertise",
                5,
                last,
                note="Входной контроль, подписание договора и выставление счета на экспертизу",
                resp_party="Экспертиза / Проектировщик",
                status="В работе",
            )
            ex_ii = add(
                "Экспертиза результатов инженерных изысканий (РИИ)",
                "expertise",
                30,
                [ex_intake],
                note="Проверка отчетов ИГДИ, ИГИ, ИЭИ экспертами",
                resp_party="Экспертиза",
                status="В работе",
            )
            ex_pd = add(
                "Экспертиза проектной документации и проверка достоверности сметной стоимости",
                "expertise",
                42,
                [ex_ii],
                lag_days=-14,
                note="Нормативный срок 42 раб. дня + сметная экспертиза 30 раб. дней (совмещено)",
                resp_party="Экспертиза",
                status="В работе",
            )
            ex_buffer = add(
                "Устранение замечаний экспертов (дополнительный срок / продление экспертизы)",
                "expertise",
                21,
                [ex_pd],
                note="Реалистичный буфер ГИПа: нормативное продление экспертизы по ст. 49 ГрК РФ",
                resp_party="Проектировщик / Экспертиза",
                status="В работе",
            )
            ms_exp = add(
                "Контрольная точка К4: Положительное заключение государственной / негос. экспертизы получено",
                "expertise",
                0,
                [ex_buffer],
                milestone=True,
                note="Регистрация положительного заключения в ЕГРЗ Минстроя РФ",
                resp_party="Экспертиза",
                status="В работе",
            )
            last = [ms_exp]

        after_expertise = last

    # -----------------------------------------------------------------------
    # Этап 4. Рабочая документация (стадия РД)
    # -----------------------------------------------------------------------
    rd_release: Optional[int] = None
    if rd_secs:
        if last:
            rd_deps, rd_lag = last, 0
        elif k1_milestone:
            rd_deps, rd_lag = [k1_milestone], 0
        else:
            rd_deps, rd_lag = [], 0

        rd_waves = [set(s.id for s in rd_secs if s.id != "rd_sm"), {"rd_sm"}]
        rd_release = dev_block(
            rd_secs, "rd", rd_deps, rd_lag, RD_DURATION_DAYS, 42, rd_waves,
            "Разработка рабочей документации (ГОСТ Р 21.101)", "Выпуск комплектов рабочей документации",
        )
        rd_appr = add(
            "Согласование комплектов рабочей документации и передача в производство работ",
            "approval",
            14,
            [rd_release],
            note="Штамп «В производство работ»",
            resp_party="Заказчик",
            status="В работе",
        )
        k5_milestone = add(
            "Контрольная точка К5: Рабочая документация утверждена и передана на объект",
            "rd",
            0,
            [rd_appr],
            milestone=True,
            note="Готовность к СМР",
            resp_party="Заказчик / Проектировщик",
            status="В работе",
        )
        if not pd_secs:
            after_expertise = [k5_milestone]

    tail = after_expertise or ([rd_release] if rd_release else [k1_milestone])
    if flags.get("techplan"):
        add(
            "Подготовка технического плана здания / сооружения",
            "other",
            21,
            tail,
            note="Кадастровый инженер, постановка на кадастровый учет",
            resp_party="Проектировщик",
            status="В работе",
        )

    resolve_schedule(phases, project.start_date)
    return phases
