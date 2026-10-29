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
    PERCENT_SHARE = "percent_share"  # По долям разделов (СБЦ / Методика 707/пр)
    LABOR_EFFORT = "labor_effort"    # По трудозатратам специалистов (Форма 3П)


class SectionCostItem(BaseModel):
    section_id: str
    volume_num: str
    code_mark: str
    full_code: str = ""
    title: str
    relative_share_percent: float = 0.0  # Доля тома в проекте, %
    labor_days: float = 0.0              # Трудоемкость в человеко-днях
    cost_rub: float = 0.0                # Стоимость разработки без НДС, руб.
    department: str = ""                 # Проектный отдел / подразделение
    lead_specialist: str = ""            # Ответственный специалист
    enabled: bool = True


class CostParameters(BaseModel):
    calculation_method: CalculationMethod = CalculationMethod.PERCENT_SHARE
    target_total_cost_net: float = 3000000.0  # Базовая целевая стоимость ПИР без НДС, руб.
    include_vat: bool = True                  # Учитывать НДС
    vat_rate: float = 5.0                     # Ставка НДС, % (5 или 20; без НДС - include_vat=False)
    average_daily_rate_rub: float = 12000.0   # Средняя дневная ставка специалиста, руб./день
    overhead_percent: float = 60.0            # Накладные расходы, %
    profit_percent: float = 20.0              # Сметная прибыль, %
    complexity_factor: float = 1.0            # Коэффициент сложности
    is_reconstruction: bool = False           # Реконструкция (К=1.20)
    use_bim: bool = False                     # Применение ТИМ/BIM технологий (К=1.15)
    urgency_factor: float = 1.0               # Коэффициент срочности
    sections_costs: List[SectionCostItem] = Field(default_factory=list)

    # Итоговые расчетные показатели
    total_labor_days: float = 0.0             # Всего человеко-дней
    direct_labor_cost_rub: float = 0.0        # Прямые затраты на ФОТ
    overhead_rub: float = 0.0                 # Накладные расходы, руб.
    profit_rub: float = 0.0                   # Сметная прибыль, руб.
    total_cost_net_rub: float = 0.0           # Итого без НДС, руб.
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
    group: str = "pd"                # precontract | survey | tx_concept | pd | approval | expertise | rd | other
    start_week: int = 1              # Неделя начала (1..N) - для этапов без зависимостей задается вручную
    duration_weeks: int = 4          # Длительность в неделях (0 - веха)
    depends_on: List[int] = Field(default_factory=list)  # id этапов-предшественников (начало после их окончания)
    lag_weeks: int = 0               # Сдвиг относительно окончания предшественников (может быть < 0 - нахлест)
    milestone: bool = False          # Веха (контрольная точка)
    note: str = ""
    status: str = "В работе"         # "В работе", "На согласовании", "Согласовано", "Замечания", "Завершено"
    resp_party: str = "Проектировщик" # "Проектировщик", "Заказчик", "Экспертиза", "Подрядчик"
    enabled: bool = True             # Флаг включения этапа в график (пользователь может отключить ненужные)


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
    PD = "pd"                # Проектная документация
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