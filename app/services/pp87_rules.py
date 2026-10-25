import re
from typing import List
from app.models import FacilityType, ProjectData, ProjectMode, SchedulePhase, SectionItem


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


def apply_volume_ciphers(project_data: ProjectData) -> None:
    """
    Обновляет поле full_code у каждого раздела в зависимости от режима:
    - В режиме PRE_CONTRACT: только марка (например, "АР", "КР", "ИОС1")
    - В режиме CONTRACT: {базовый_шифр}-{марка} (например, "12ТПС-26-АР")
    """
    cipher = project_data.cipher.strip() if project_data.cipher else ""
    if not cipher and project_data.contract_number:
        cipher = compute_cipher_from_contract(project_data.contract_number, project_data.contract_date)
        project_data.cipher = cipher

    for sec in project_data.sections:
        if project_data.mode == ProjectMode.CONTRACT and cipher:
            sec.full_code = f"{cipher}-{sec.code_mark}"
        else:
            sec.full_code = sec.code_mark


def get_default_capital_sections() -> List[SectionItem]:
    """
    Базовый состав разделов по Постановлению Правительства РФ № 87
    для объектов капитального строительства (Раздел II).
    """
    return [
        SectionItem(
            id="pz",
            volume_num="1",
            code_mark="ПЗ",
            title="Раздел 1. Пояснительная записка",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="pzu",
            volume_num="2",
            code_mark="ПЗУ",
            title="Раздел 2. Схема планировочной организации земельного участка",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ar",
            volume_num="3",
            code_mark="АР",
            title="Раздел 3. Архитектурные решения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="kr",
            volume_num="4",
            code_mark="КР",
            title="Раздел 4. Конструктивные и объемно-планировочные решения",
            required_by_norm=True,
            enabled=True
        ),
        # Раздел 5: Инженерные сети
        SectionItem(
            id="ios1",
            volume_num="5.1",
            code_mark="ИОС1",
            title="Подраздел 1. Система электроснабжения",
            category_header="Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ios2",
            volume_num="5.2",
            code_mark="ИОС2",
            title="Подраздел 2. Система водоснабжения",
            category_header="Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ios3",
            volume_num="5.3",
            code_mark="ИОС3",
            title="Подраздел 3. Система водоотведения",
            category_header="Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ios4",
            volume_num="5.4",
            code_mark="ИОС4",
            title="Подраздел 4. Отопление, вентиляция и кондиционирование воздуха, тепловые сети",
            category_header="Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ios5_1",
            volume_num="5.5.1",
            code_mark="ИОС5.1",
            title="Подраздел 5. Сети связи. Часть 1. Слаботочные сети",
            category_header="Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ios5_2",
            volume_num="5.5.2",
            code_mark="ИОС5.2",
            title="Подраздел 5. Сети связи. Часть 2. Автоматизация комплексная",
            category_header="Раздел 5. Сведения об инженерном оборудовании, о сетях инженерно-технического обеспечения",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="tx",
            volume_num="6",
            code_mark="ТХ",
            title="Раздел 6. Технологические решения",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="pos",
            volume_num="7",
            code_mark="ПОС",
            title="Раздел 7. Проект организации строительства",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="oos",
            volume_num="8",
            code_mark="ООС",
            title="Раздел 8. Перечень мероприятий по охране окружающей среды",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="pb",
            volume_num="9",
            code_mark="ПБ",
            title="Раздел 9. Мероприятия по обеспечению пожарной безопасности",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="tbe",
            volume_num="10",
            code_mark="ТБЭ",
            title="Раздел 10. Требования к безопасной эксплуатации объекта капитального строительства",
            required_by_norm=True,
            enabled=True
        ),
        # Раздел 12: Сметы
        SectionItem(
            id="sm",
            volume_num="12.1",
            code_mark="СМ",
            title="Часть 1. Сметы",
            category_header="Раздел 12. Смета на строительство, реконструкцию, капитальный ремонт, снос объекта капитального строительства",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="sm_p",
            volume_num="12.2",
            code_mark="СМ.П",
            title="Часть 2. Конъюнктурный анализ. Прайс-листы",
            category_header="Раздел 12. Смета на строительство, реконструкцию, капитальный ремонт, снос объекта капитального строительства",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="sm_vor",
            volume_num="12.3",
            code_mark="СМ.ВОР",
            title="Часть 3. Ведомости объемов работ",
            category_header="Раздел 12. Смета на строительство, реконструкцию, капитальный ремонт, снос объекта капитального строительства",
            required_by_norm=False,
            enabled=True
        ),
        # Раздел 13: Иная документация
        SectionItem(
            id="gochs",
            volume_num="13.1",
            code_mark="ГОЧС",
            title="Подраздел 1. Перечень мероприятий по гражданской обороне, мероприятий по предупреждению чрезвычайных ситуаций природного и техногенного характера",
            category_header="Раздел 13. Иная документация в случаях, предусмотренных законодательными и иными нормативными правовыми актами РФ",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="ots",
            volume_num="13.2",
            code_mark="ОТС",
            title="Подраздел 2. Обследование технического состояния",
            category_header="Раздел 13. Иная документация в случаях, предусмотренных законодательными и иными нормативными правовыми актами РФ",
            required_by_norm=False,
            enabled=True
        ),
    ]


def get_default_linear_sections() -> List[SectionItem]:
    """
    Базовый состав разделов по Постановлению Правительства РФ № 87
    для линейных объектов (Раздел III).
    """
    return [
        SectionItem(
            id="pz",
            volume_num="1",
            code_mark="ПЗ",
            title="Раздел 1. Пояснительная записка",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="ppo",
            volume_num="2",
            code_mark="ППО",
            title="Раздел 2. Проект полосы отвода",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="tkr",
            volume_num="3",
            code_mark="ТКР",
            title="Раздел 3. Технологические и конструктивные решения линейного объекта. Искусственные сооружения",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="lin_infra",
            volume_num="4",
            code_mark="ЗСИ",
            title="Раздел 4. Здания, строения и сооружения, входящие в инфраструктуру линейного объекта",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="pos",
            volume_num="5",
            code_mark="ПОС",
            title="Раздел 5. Проект организации строительства",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="pod",
            volume_num="6",
            code_mark="ПОД",
            title="Раздел 6. Проект организации работ по сносу (демонтажу) линейного объекта",
            required_by_norm=False,
            enabled=False  # По умолчанию выключен, если нет демонтажа
        ),
        SectionItem(
            id="oos",
            volume_num="7",
            code_mark="ООС",
            title="Раздел 7. Мероприятия по охране окружающей среды",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="pb",
            volume_num="8",
            code_mark="ПБ",
            title="Раздел 8. Мероприятия по обеспечению пожарной безопасности",
            required_by_norm=True,
            enabled=True
        ),
        SectionItem(
            id="sm",
            volume_num="9.1",
            code_mark="СМ",
            title="Часть 1. Сводный сметный расчет и сметы",
            category_header="Раздел 9. Смета на строительство",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="sm_vor",
            volume_num="9.2",
            code_mark="СМ.ВОР",
            title="Часть 2. Ведомости объемов работ",
            category_header="Раздел 9. Смета на строительство",
            required_by_norm=False,
            enabled=True
        ),
        SectionItem(
            id="gochs",
            volume_num="10.1",
            code_mark="ГОЧС",
            title="Подраздел 1. Перечень мероприятий по гражданской обороне и предупреждению ЧС",
            category_header="Раздел 10. Иная документация",
            required_by_norm=False,
            enabled=False
        ),
        SectionItem(
            id="rekult",
            volume_num="10.2",
            code_mark="ПРЗ",
            title="Подраздел 2. Проект рекультивации нарушенных земель",
            category_header="Раздел 10. Иная документация",
            required_by_norm=False,
            enabled=True
        ),
    ]


def get_default_schedule(facility_type: FacilityType, has_ots: bool = True) -> List[SchedulePhase]:
    """
    Формирует типовой график работ по этапам жизненного цикла проектирования.
    """
    phases = []
    phase_id = 1

    if has_ots:
        phases.append(
            SchedulePhase(
                id=phase_id,
                name="Обследование, подготовка и согласование отчета обследования",
                start_month=1,
                duration_months=1,
                note="Включает натурное обследование и согласование с Заказчиком",
                category="ПИР"
            )
        )
        phase_id += 1

    # Инженерные изыскания
    izysk_start = 1 if not has_ots else 1
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Выполнение инженерных изысканий (ИГДИ, ИГИ, ИЭИ), подготовка отчетов",
            start_month=izysk_start,
            duration_months=2,
            note="Геодезические, геологические, экологические изыскания",
            category="ПИР"
        )
    )
    phase_id += 1

    # Разработка ПСД и РД
    psd_start = 2 if has_ots else 2
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Разработка проектно-сметной и рабочей документации",
            start_month=psd_start,
            duration_months=4,
            note="Разработка основных разделов проекта (АР, КР, сети, ПОС, сметы)",
            category="ПИР"
        )
    )
    phase_id += 1

    # Согласование проектного решения
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Согласование проектных решений с Заказчиком и эксплуатирующими организациями",
            start_month=psd_start + 3,
            duration_months=1,
            note="Сетевые организации, балансодержатели, архитектура",
            category="ПИР"
        )
    )
    phase_id += 1

    # Внутренняя экспертиза
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Внутренняя экспертиза Заказчика, устранение замечаний",
            start_month=psd_start + 4,
            duration_months=1,
            note="Регламент 30 календарных дней (10+3+10+5 раб. дн.)",
            category="ПИР"
        )
    )
    phase_id += 1

    # Государственная / негосударственная экспертиза
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Государственная / негосударственная экспертиза, в т.ч. проверка сметной стоимости",
            start_month=psd_start + 5,
            duration_months=2,
            note="Сопровождение экспертизы и снятие замечаний",
            category="ПИР"
        )
    )
    phase_id += 1

    # Разрешение на строительство
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Содействие в получении разрешения на строительство / реконструкцию",
            start_month=psd_start + 7,
            duration_months=1,
            note="Подача документов в уполномоченные органы",
            category="ПИР"
        )
    )
    phase_id += 1

    # Подготовка техплана
    phases.append(
        SchedulePhase(
            id=phase_id,
            name="Подготовка технического плана объекта",
            start_month=psd_start + 7,
            duration_months=1,
            note="Кадастровые работы для последующего ввода в эксплуатацию",
            category="ПИР"
        )
    )

    return phases
