from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectMode(str, Enum):
    PRE_CONTRACT = "pre_contract"  # Предварительная оценка / КП (без шифра, марки по ГОСТ, месяцы 1..N)
    CONTRACT = "contract"          # Выход на договор (с шифром {номер}ТПС-{ГГ}, календарные даты)


class FacilityType(str, Enum):
    CAPITAL = "capital"  # Раздел II ПП 87: Капитальные объекты (здания, сооружения, площадки)
    LINEAR = "linear"    # Раздел III ПП 87: Линейные объекты (сети, водоводы, трубопроводы, дороги)
    COMPLEX = "complex"  # Комплексный объект (сочетание площадочной части и внеплощадочных сетей)


class CalculationMethod(str, Enum):
    BY_COLLECTIONS = "by_collections"  # 1. По сборникам базовых цен (МНЗ / СБЦП)
    LABOR_707 = "labor_707"            # 2 (В1). По трудозатратам (Форма 3П — строго по Методике № 707/пр)
    LABOR_INTERNAL = "labor_internal"  # 2 (В2). По трудозатратам (Форма 3П — внутренний справочник ставок)
    FROM_SMR = "from_smr"              # 3. От стоимости строительства (СМР) по табл. 1.5 Методики № 707/пр
    PERCENT_SHARE = "percent_share"    # Обратная совместимость: от целевой суммы по долям разделов
    LABOR_EFFORT = "labor_effort"      # Обратная совместимость: общая оценка по ч-д


class CollectionQuoteItem(BaseModel):
    """Отдельная расценка (позиция) из сборника МНЗ / СБЦП в сметном расчёте."""
    row_id: str = "item_1"
    collection_id: str = "mnz_53"      # ID сборника из normative_catalog
    item_id: str = "53_t1_p1"          # ID расценки в сборнике
    custom_name: str = ""              # Уточнение наименования (необязательно)
    x_value: float = 0.0               # Значение основного показателя X (м3/сут, км, м2, м3 и т.д.) — вводится вручную; 0 = не задан
    stage_mode: str = "pd_rd"          # "pd" (только П), "rd" (только Р), "pd_rd" (П + Р вместе)
    completeness_pct: float = 100.0    # Доля разрабатываемых разделов от полного комплекса по сборнику (К_разд), %
    k_coeff: float = 1.0               # Поправочный коэффициент (реконструкция, сейсмика, условия и т.д.)
    enabled: bool = True

    # Специальные поля для сборника № 8 (МНЗ № 283/пр — Обследование сетей ИТО)
    adverse_period: bool = True        # Неблагоприятный период года для Тюменской области (+19% к полевым работам)

    # Специальные поля для сборника № 9 (СБЦП № 270/пр — Обмерные работы и обследование зданий)
    height_group: str = "h_up_to_6"    # Высотная группа здания (h_up_to_4 .. h_over_21)
    building_category: str = "II"      # Категория сложности здания: "I", "II", "III"
    work_complexity: str = "II"        # Категория сложности работ: "I", "II", "III"
    work_type: str = "obmer_plus_obsled"  # "obmer", "obsled", "obmer_plus_obsled"
    small_volume_auto: bool = True     # Автоматический повышающий коэф. табл. 11 при V <= 5000 м3

    # Происхождение позиции и значения X (этап Б: подбор через ИИ с проверкой человеком)
    source_description: str = ""       # Объект/сооружение из ТЗ, для которого подобрана позиция
    ai_reason: str = ""                # Пояснение ИИ, почему выбрана позиция
    x_source: str = ""                 # "" (не задан) | "manual" | "ai" | "min_default"
    x_note: str = ""                   # Как получено X: цитата, перевод единиц или пометка «не указано в ТЗ»
    needs_ai: bool = False             # Требуется (повторный) точечный запрос X: новая строка или изменён сборник/таблица

    # Вычисляемые выходные поля расценки
    warning: str = ""                  # Предупреждение по строке (не задан X, не найден сборник/таблица и т.п.)
    collection_code: str = ""
    item_name: str = ""
    unit: str = ""
    calc_type: str = "ab"              # "ab" | "survey_283" | "obmer_270"
    price_level_year: int = 2024
    index_type: str = "pir"            # "pir" | "survey"
    index_applied: float = 1.0
    formula_text: str = ""             # Строка формулы с подставленными числами и коэффициентами
    base_cost_rub: float = 0.0         # Стоимость в базовом уровне цен, руб.
    current_cost_rub: float = 0.0      # Стоимость в текущем уровне цен без НДС, руб.


class Labor707Row(BaseModel):
    """Строка нормативного расчёта по трудозатратам строго по Методике Минстроя РФ № 707/пр (п. 143–149, Табл. 1.3 Прил. 2, Форма 3П)."""
    row_id: str = "l707_1"
    role_id: str = "lead"
    role_name: str = "Ведущий специалист (инженер, архитектор, экономист, сметчик)"
    department: str = "Проектный отдел"
    count: int = 1                     # Численность исполнителей Ч_i
    days: float = 10.0                 # Трудозатраты 1 исполнителя Т_фi, раб. дн.
    index_i: float = 1.00              # Индекс среднемесячной ЗП И_i по Табл. 1.3 Прил. 2 Методики № 707/пр
    total_days: float = 0.0            # Ч_i * Т_фi, чел.-дн.
    weighted_days: float = 0.0         # Ч_i * Т_фi * И_i, приведённых чел.-дн.
    cost_rub: float = 0.0              # Стоимость по позиции (В_ср * Ч_i * Т_фi * И_i), руб. без НДС
    enabled: bool = True


class SpecialistLaborRow(BaseModel):
    """Строка коммерческой калькуляции трудозатрат по рыночной стоимости специалистов в г. Тюмени."""
    row_id: str = "spec_1"
    role_id: str = "lead"
    role_name: str = "Ведущий инженер-проектировщик"
    department: str = "Проектный отдел"
    count: int = 1                     # Количество специалистов данной категории
    days: float = 10.0                 # Трудозатраты на 1 специалиста, чел.-дней
    monthly_salary_rub: float = 115000.0  # Рыночный оклад из справочника Тюмени (для В2)
    qual_coeff_707: float = 1.00       # Совместимость со старым полем
    daily_rate_rub: float = 0.0        # Вычисленная дневная ставка ЗП, руб./день
    total_days: float = 0.0            # Всего чел.-дней по строке (count * days)
    total_wage_rub: float = 0.0        # Прямой ФОТ по строке, руб.
    enabled: bool = True


class AdditionalWorkItem(BaseModel):
    """Дополнительный вид работ (обследование, изыскания, экспертиза / достоверность)."""
    work_id: str                       # "inspection" | "surveys" | "expertise"
    name: str
    enabled: bool = False
    cost_net_rub: float = 0.0          # Стоимость без НДС, руб.
    note: str = ""


class SectionCostItem(BaseModel):
    section_id: str
    stage: str = "П+Р"                 # "П+Р" (единый расчёт), "П" или "Р" (при раздельном расчёте)
    volume_num: str
    code_mark: str
    full_code: str = ""
    title: str
    relative_share_percent: float = 0.0  # Доля тома в проекте, %
    labor_days: float = 0.0              # Трудоемкость в человеко-днях
    cost_rub: float = 0.0                # Стоимость разработки без НДС, руб.
    cost_pd_rub: float = 0.0             # В т.ч. стадия П, руб. (справочно или при раздельном расчёте)
    cost_rd_rub: float = 0.0             # В т.ч. стадия Р, руб. (справочно или при раздельном расчёте)
    department: str = ""                 # Проектный отдел / подразделение
    lead_specialist: str = ""            # Ответственный специалист
    enabled: bool = True


class CostParameters(BaseModel):
    calculation_method: CalculationMethod = CalculationMethod.BY_COLLECTIONS
    target_total_cost_net: float = 0.0        # Целевая стоимость ПИР без НДС, руб. (только для метода «по долям»; скрытой суммы по умолчанию нет)
    include_vat: bool = True                  # Учитывать НДС
    vat_rate: float = 5.0                     # Ставка НДС, % (0, 5 или 22; с 01.01.2026 общая ставка 22%)
    average_daily_rate_rub: float = 12000.0   # Средняя дневная ставка специалиста, руб./день
    overhead_percent: float = 60.0            # Накладные расходы, %
    profit_percent: float = 20.0              # Сметная прибыль, %
    complexity_factor: float = 1.0            # Коэффициент сложности
    is_reconstruction: bool = False           # Реконструкция (К=1.20)
    use_bim: bool = False                     # Применение ТИМ/BIM технологий (К=1.15)
    urgency_factor: float = 1.0               # Коэффициент срочности

    # Настройка объединения / разделения стадий П и Р в расчёте стоимости
    # По умолчанию False: П и Р считаются вместе (без дублирования строк), галочкой можно разделить
    split_pd_rd_in_cost: bool = False
    pd_stage_share_pct: float = 40.0          # Доля стадии П (%), по умолчанию 40%
    rd_stage_share_pct: float = 60.0          # Доля стадии Р (%), по умолчанию 60%

    # 1. Позиции расчёта по сборникам МНЗ / СБЦП (Форма 2П)
    collection_items: List[CollectionQuoteItem] = Field(default_factory=list)
    collections_total_net_rub: float = 0.0    # Независимый итог по сборникам МНЗ/СБЦП без НДС, руб.

    # 2А (В1). Независимый нормативный расчёт по трудозатратам строго по Методике № 707/пр (п. 143–149, ф. 8.12–8.14, Табл. 1.1–1.3)
    regional_monthly_salary_707: float = 95000.0  # ЗП_мес по региону (Тюменская обл.) для Методики № 707/пр
    work_days_707: float = 20.6                   # Д_раб по Табл. 1.1 Прил. 2 Методики № 707/пр
    k3_salary_share_707: float = 0.4006           # К_3 — доля прямой ЗП в себестоимости (40,06% по Табл. 1.1 Прил. 2 № 707/пр)
    profitability_707: float = 0.10               # Р — уровень рентабельности (10% по Табл. 1.2 Прил. 2 № 707/пр)
    v_sr_707_rub: float = 0.0                     # Среднедневная выработка В_ср = (ЗП_мес / Д_раб) * (1 + Р) / К_3, руб./чел.-дн.
    k_kv_uch_707: float = 1.0                     # Коэффициент квалификации-участия К_кв-уч = sum(Ч_i * Т_фi * И_i) / sum(Ч_i * Т_фi)
    labor_707_total_days: float = 0.0             # Суммарные трудозатраты sum(Ч_i * Т_фi) по расчёту 707/пр, чел.-дн.
    labor_707_weighted_days: float = 0.0          # Приведённые трудозатраты sum(Ч_i * Т_фi * И_i), чел.-дн.
    labor_707_total_net_rub: float = 0.0          # Независимый итог по Методике № 707/пр без НДС, руб.
    labor_707_formula_text: str = ""              # Строка расчёта по ф. (8.12)–(8.14) Методики № 707/пр
    labor_707_rows: List[Labor707Row] = Field(default_factory=list)
    labor_rows_auto: bool = True                  # Таблицы трудозатрат строятся по составу разделов; False после ручной правки
    labor_norms_approved: bool = False            # Нормы чел.-дн. по разделам утверждены пользователем (data/labor_norms.json)
    labor_total_days_norm: float = 0.0            # Всего чел.-дн. по нормам для выбранных разделов

    # 2Б (В2). Независимый коммерческий расчёт по таблице рыночной стоимости специалистов (г. Тюмень)
    work_days_per_month: float = 21.0             # Среднемесячное число рабочих дней для рыночного расчёта
    specialist_rows: List[SpecialistLaborRow] = Field(default_factory=list)
    labor_market_total_days: float = 0.0          # Суммарные трудозатраты по рыночной таблице, чел.-дн.
    labor_market_direct_wage_rub: float = 0.0     # Прямой ФОТ по рыночным окладам Тюмени, руб.
    labor_market_overhead_rub: float = 0.0        # Накладные расходы рыночного расчёта, руб.
    labor_market_profit_rub: float = 0.0          # Прибыль рыночного расчёта, руб.
    labor_market_total_net_rub: float = 0.0       # Независимый итог по таблице рыночной стоимости без НДС, руб.
    labor_market_formula_text: str = ""           # Строка пояснения рыночного расчёта

    # 3. Параметры расчёта от стоимости строительства (СМР) по Методике № 707/пр (Табл. 1.5 Прил. 2)
    smr_cost_mln_rub: float = 0.0             # Ориентировочная стоимость строительства (СМР), млн руб. без НДС
    smr_object_category: str = "other"        # "industrial" | "civil" | "utilities" | "roads" | "other"
    smr_normative_pct: float = 0.0            # Вычисленный норматив % ПИР от СМР
    smr_reference_pir_cost_rub: float = 0.0   # Справочная стоимость ПИР от СМР без НДС, руб.
    smr_detected_from_tz: bool = False        # Была ли стоимость СМР найдена автоматически в ТЗ

    # 4. Дополнительные виды работ (обследование, ИИ, экспертиза/достоверность)
    additional_works: List[AdditionalWorkItem] = Field(default_factory=list)
    additional_works_total_net_rub: float = 0.0

    # Предупреждения расчёта (показываются в интерфейсе и в тексте сметы)
    warnings: List[str] = Field(default_factory=list)
    ai_notes: List[str] = Field(default_factory=list)  # Заметки последнего ИИ-подбора (нет позиции в справочнике, X не найден и т.п.)

    # Распределение по разделам проекта
    sections_costs: List[SectionCostItem] = Field(default_factory=list)

    # Итоговые расчетные показатели
    pir_only_cost_net_rub: float = 0.0        # Стоимость основных проектных работ (ПД/РД) без доп. работ, руб.
    total_labor_days: float = 0.0             # Всего человеко-дней
    direct_labor_cost_rub: float = 0.0        # Прямые затраты на ФОТ
    overhead_rub: float = 0.0                 # Накладные расходы, руб.
    profit_rub: float = 0.0                   # Сметная прибыль, руб.
    total_cost_net_rub: float = 0.0           # Итого без НДС (включая включенные доп. работы), руб.
    vat_rub: float = 0.0                      # Сумма НДС, руб.
    total_cost_gross_rub: float = 0.0         # Итого с НДС, руб.


class SectionItem(BaseModel):
    id: str
    stage: str = "П"                 # "П" - проектная документация, "Р" - рабочая документация
    volume_num: str = ""             # Номер тома: "1", "5.1", "12.3", "13.1" (для РД - порядковый номер)
    code_mark: str                   # Базовая марка: "ПЗ", "АР", "ИОС1", "СМ.П", для РД "КЖ", "НВК"
    full_code: str = ""              # Полный шифр тома: "12ТПС-26-АР" или "АР" в режиме КП
    title: str                       # Наименование тома/раздела
    note: str = ""                   # Примечание
    category_header: Optional[str] = None  # Заголовок группирующего раздела (например, "Раздел 5. Сведения об...")
    enabled: bool = True             # Включен ли том в проект
    required_by_norm: bool = False   # Является ли строго обязательным по ПП 87
    source: str = "default"          # Откуда взят: tz (явно указан в ТЗ), trigger (по признакам ТЗ), default, user


class SchedulePhase(BaseModel):
    id: int
    name: str
    group: str = "pd"                # precontract | survey | tx_concept | pd | approval | internal_rvk | expertise | rd | other
    start_week: int = 1              # Неделя / период начала
    duration_weeks: int = 4          # Длительность в неделях (для обратной совместимости)
    duration_days: int = 28          # Длительность в календарных днях (0 для вехи)
    start_date: str = ""             # Календарная дата начала (ГГГГ-ММ-ДД)
    finish_date: str = ""            # Календарная дата окончания (ГГГГ-ММ-ДД)
    depends_on: List[int] = Field(default_factory=list)  # id этапов-предшественников
    lag_weeks: int = 0               # Сдвиг в неделях
    lag_days: int = 0                # Сдвиг в календарных днях
    milestone: bool = False          # Веха (контрольная точка)
    note: str = ""
    status: str = "В работе"         # "В работе", "На согласовании", "Согласовано", "Замечания", "Завершено"
    resp_party: str = "Проектировщик" # "Проектировщик", "Заказчик", "Экспертиза", "Подрядчик"
    enabled: bool = True             # Флаг включения этапа в график (пользователь может отключить ненужные)

    # Поля фиксации документооборота и согласований с Заказчиком:
    sent_to_client_date: str = ""    # Дата отправки Заказчику (например, "2026-09-24")
    client_remarks_1_date: str = ""  # Замечания 1 от Заказчика
    designer_answers_1_date: str = "" # Ответы 1 / снятие замечаний проектировщиком
    client_remarks_2_date: str = ""  # Повторные замечания 2
    designer_answers_2_date: str = "" # Финальные ответы 2 / протокол согласования
    approval_result: str = ""        # Результат: "Согласовано без замечаний", "Замечания сняты", "В рассмотрении Заказчиком"


class ProjectData(BaseModel):
    mode: ProjectMode = ProjectMode.PRE_CONTRACT
    object_name: str = "Строительство объекта"
    customer: str = ""
    contractor: str = ""             # Генпроектировщик - заполняется только если явно указан в ТЗ
    contract_number: str = ""
    contract_date: str = ""
    cipher: str = ""                 # Базовый шифр, например 12ТПС-26
    facility_type: FacilityType = FacilityType.CAPITAL
    start_date: str = ""             # Например "2026-10-01"
    has_pd: bool = True              # Стадия П (проектная документация) входит в работу
    has_rd: bool = False             # Стадия Р (рабочая документация) входит в работу
    composition_preset: str = "permit"  # tz | permit | expertise
    schedule_flags: Dict[str, Any] = Field(default_factory=dict)  # Признаки из ТЗ для построения графика
    schedule_detail: str = "sections"  # sections - по разделам, stages - укрупненно
    tz_text: str = ""                # Исходный текст ТЗ (для пересборки состава при смене типа объекта)
    sections: List[SectionItem] = Field(default_factory=list)
    schedule_phases: List[SchedulePhase] = Field(default_factory=list)
    cost_parameters: Optional[CostParameters] = None


class ParseTZRequest(BaseModel):
    text: str = ""
    file_name: Optional[str] = None


class ParseTZResponse(BaseModel):
    project_data: ProjectData
    detected_features: List[str] = Field(default_factory=list)


class KPPriceFormat(str, Enum):
    TOTAL = "total"        # Одна сумма без таблицы
    SECTIONS = "sections"  # Таблица по разделам (томам)
    WORKS = "works"        # Таблица по видам работ без указания разделов


class KPStage(str, Enum):
    PD = "pd"                # Проектная документация (ПД)
    RD = "rd"                # Рабочая документация (РД)
    PD_RD = "pd_rd"          # Проектная и рабочая документация
    CHANGES = "changes"      # Внесение изменений в проектную документацию


class KPTermUnit(str, Enum):
    MONTHS = "months"
    WORKING_DAYS = "working_days"
    CALENDAR_DAYS = "calendar_days"


class KPPaymentScheme(str, Enum):
    ADVANCE = "advance"  # Аванс N% одной строкой
    STAGES = "stages"    # Поэтапная оплата


class KPWorkItem(BaseModel):
    name: str
    cost_rub: float = 0.0  # Стоимость без НДС


class KPPaymentStage(BaseModel):
    percent: float
    text: str


class KPRequest(BaseModel):
    """Данные для формирования коммерческого предложения (вводятся пользователем)."""
    project: ProjectData

    # Шапка
    outgoing_number: str = ""          # Порядковая часть исх. номера - пользователь вписывает при отправке
    date: str = ""                     # ISO ГГГГ-ММ-ДД, пусто = сегодня
    addressee_lines: List[str] = Field(default_factory=list)  # Должность, организация, ФИО
    salutation: str = "Уважаемый Заказчик!"

    # Предмет
    request_date: str = ""             # Дата запроса заказчика, строкой ДД.ММ.ГГГГ
    stage: KPStage = KPStage.PD
    subject_text: str = ""             # Свой текст предмета (если пусто - формируется автоматически)
    inclusions: List[str] = Field(default_factory=list)   # "В коммерческое предложение входит"
    exclusions: List[str] = Field(default_factory=list)   # "В стоимость не входит"

    # Стоимость
    price_format: KPPriceFormat = KPPriceFormat.TOTAL
    works: List[KPWorkItem] = Field(default_factory=list)  # Для формата WORKS

    # Срок
    term_value: int = 0
    term_unit: KPTermUnit = KPTermUnit.CALENDAR_DAYS
    note_approval_excluded: bool = True   # «В срок не входит время согласования...»

    # Оплата
    payment_scheme: KPPaymentScheme = KPPaymentScheme.ADVANCE
    advance_percent: float = 50.0
    payment_stages: List[KPPaymentStage] = Field(default_factory=list)

    # Прочее
    validity_days: int = 15
    phrase_counter_offers: bool = True    # «Готовы рассмотреть встречные предложения...»
    phrase_help_tz: bool = False          # «Готовы помочь в разработке Технического задания»

    # Подпись (вводит пользователь; в общедоступной версии - заглушки)
    signer_title: str = "Директор"
    signer_name: str = ""
    company_name: str = ""
    executor: str = ""                    # «Исп. Фамилия И.О. тел.»