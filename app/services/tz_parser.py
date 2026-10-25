import io
import re
from typing import List, Tuple
from app.models import FacilityType, ProjectData, ProjectMode
from app.services.pp87_rules import (
    apply_volume_ciphers,
    compute_cipher_from_contract,
    get_default_capital_sections,
    get_default_linear_sections,
    get_default_schedule,
)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Извлекает текст из docx (абзацы и таблицы)."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        full_text = []
        for p in doc.paragraphs:
            if p.text.strip():
                full_text.append(p.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    full_text.append(" | ".join(row_text))
        return "\n".join(full_text)
    except Exception as e:
        return f"Ошибка чтения docx: {e}"


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Извлекает текст из pdf с помощью pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        full_text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text.append(t)
        return "\n".join(full_text)
    except Exception as e:
        return f"Ошибка чтения pdf: {e}"


def parse_tz_content(raw_text: str) -> Tuple[ProjectData, List[str]]:
    """
    Анализирует текст ТЗ, извлекает параметры объекта,
    определяет тип объекта и активирует нужные разделы.
    """
    detected_features = []

    # 1. Извлечение наименования объекта
    object_name = "Строительство объекта"
    match_obj = re.search(
        r"(?:по объекту|наименование объекта|объект строительства)[\s:]*([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if match_obj:
        val = match_obj.group(1).strip()
        val = re.sub(r"^[«\"']|[»\"']$", "", val).strip()
        if len(val) > 4:
            object_name = val
    else:
        # Проверяем типовые строки вида "Строительство объекта..."
        match_constr = re.search(
            r"((?:Строительство|Реконструкция|Капитальный ремонт)\s+[^\n\r\|]{5,80})",
            raw_text,
            re.IGNORECASE,
        )
        if match_constr:
            object_name = match_constr.group(1).strip()

    # 2. Заказчик, Подрядчик, Субподрядчик
    customer = ""
    match_cust = re.search(
        r"(?:Заказчик|Заказчик-Застройщик)[\s:\|]+([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if match_cust:
        customer = clean_extracted_entity(match_cust.group(1))

    contractor = ""
    match_contr = re.search(
        r"(?:Подрядчик|Генподрядчик)[\s:\|]+([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if match_contr:
        contractor = clean_extracted_entity(match_contr.group(1))

    subcontractor = ""
    match_sub = re.search(
        r"(?:Субподрядчик|Проектная организация)[\s:\|]+([^\n\r]+)",
        raw_text,
        re.IGNORECASE,
    )
    if match_sub:
        subcontractor = clean_extracted_entity(match_sub.group(1))

    # 3. Договор и дата (если уже есть)
    contract_number = ""
    contract_date = ""
    match_contract = re.search(
        r"(?:Договор[а-я\s]*|контракт[а-я\s]*)№\s*([0-9А-Яа-яA-Za-z\/\-]+)(?:\s+от\s+([0-9\.\s\w«»г]+))?",
        raw_text,
        re.IGNORECASE,
    )
    if match_contract:
        contract_number = match_contract.group(1).strip()
        if match_contract.group(2):
            contract_date = match_contract.group(2).strip()

    # 4. Определение типа объекта (Капитальный vs Линейный vs Комплексный)
    text_lower = raw_text.lower()

    linear_keywords = [
        "линейный объект", "полоса отвода", "протяженность трассы",
        "трасса водопровода", "коллектор", "кабельная линия",
        "наружные сети водоснабжения протяженностью", "вдоль трассы"
    ]
    capital_keywords = [
        "сооружение водоподготовки", "станция", "здание", "блок-бокс",
        "площадка", "резервуар", "цех", "вос", "кос", "сооружение", "спозу"
    ]

    has_linear_markers = any(k in text_lower for k in linear_keywords)
    has_capital_markers = any(k in text_lower for k in capital_keywords)

    if has_capital_markers and has_linear_markers:
        facility_type = FacilityType.CAPITAL  # Площадка с прилегающими сетями (комплекс)
        detected_features.append("Комплексный объект: площадочные сооружения + прилегающие линейные сети")
    elif has_linear_markers and not has_capital_markers:
        facility_type = FacilityType.LINEAR
        detected_features.append("Линейный объект (сети / трасса)")
    else:
        facility_type = FacilityType.CAPITAL
        detected_features.append("Объект капитального строительства (площадочный)")

    # 5. Выбор разделов и триггеров
    if facility_type == FacilityType.LINEAR:
        sections = get_default_linear_sections()
    else:
        sections = get_default_capital_sections()

    # Проверка специфических триггеров:
    # 5.1 Обследование технического состояния (ОТС)
    has_ots = bool(re.search(r"(?:обследование|гост 31937|техническ\w+ состояни\w+|отс)", text_lower))
    if has_ots:
        detected_features.append("Обнаружено требование обследования (ГОСТ 31937 / существующие сети/сооружения) -> включен том 13.2 ОТС")
    for s in sections:
        if s.id == "ots":
            s.enabled = has_ots

    # 5.2 Гражданская оборона и ЧС (ГОЧС)
    has_gochs = bool(re.search(r"(?:гочс|го и чс|гражданск\w+ оборон\w+|чрезвычайн\w+ ситуац|гост р 22\.2\.13)", text_lower))
    if has_gochs:
        detected_features.append("Обнаружено требование ГОЧС (ГОСТ Р 22.2.13) -> включен раздел ГОЧС")
    for s in sections:
        if s.id == "gochs":
            s.enabled = has_gochs

    # 5.3 Снос / Демонтаж (ПОД)
    has_pod = bool(re.search(r"(?:снос|демонтаж|ликвидаци\w+ сооружен)", text_lower))
    if has_pod:
        detected_features.append("Обнаружена необходимость сноса/демонтажа -> включен раздел ПОД")
    for s in sections:
        if s.id == "pod":
            s.enabled = has_pod

    # 5.4 Автоматизация комплексная (АК / АСУ)
    has_automation = bool(re.search(r"(?:автоматизац|диспетчеризац|кип|асу)", text_lower))
    if has_automation:
        detected_features.append("Обнаружена автоматизация/диспетчеризация -> выделен подраздел ИОС5.2")
    for s in sections:
        if s.id == "ios5_2":
            s.enabled = has_automation

    # 5.5 Технология (ТХ)
    has_tx = bool(re.search(r"(?:технологическ\w+ схем|водоподготовк|очистк\w+ вод|уфо|фильтр|насосн\w+|технологическ\w+ регламент)", text_lower))
    if has_tx:
        detected_features.append("Обнаружены технологические процессы/оборудование -> включен Раздел 6 (ТХ)")
    for s in sections:
        if s.id == "tx":
            s.enabled = has_tx

    # 5.6 Сметная документация
    has_sm = bool(re.search(r"(?:смет|фснб|проверк\w+ достоверност|гранд-смет)", text_lower))
    if has_sm:
        detected_features.append("Обнаружены требования к сметам (ФСНБ-2022 / экспертиза смет) -> включен Раздел 12 (СМ, СМ.П, СМ.ВОР)")

    # 5.7 ЦУС (Цифровое управление строительством)
    if "цус" in text_lower or "цифровое управление строительством" in text_lower:
        detected_features.append("Требование Заказчика: документооборот через ЦУС с усиленной ЭЦП")

    # Формируем график
    schedule = get_default_schedule(facility_type=facility_type, has_ots=has_ots)

    # Режим по умолчанию: PRE_CONTRACT (Предварительная оценка / КП)
    project_mode = ProjectMode.PRE_CONTRACT
    cipher = ""

    # Если уже был найден явный договор, рассчитываем потенциальный шифр
    if contract_number:
        cipher = compute_cipher_from_contract(contract_number, contract_date)

    project_data = ProjectData(
        mode=project_mode,
        object_name=object_name,
        customer=customer or "",
        contractor=contractor or "",
        subcontractor=subcontractor or "",
        contract_number=contract_number,
        contract_date=contract_date,
        cipher=cipher,
        facility_type=facility_type,
        start_date="2026-10-01",
        total_months=len(schedule) + 1,
        sections=sections,
        schedule_phases=schedule,
    )

    # Применяем шифры (в режиме PRE_CONTRACT останутся чистые марки ГОСТ)
    apply_volume_ciphers(project_data)

    return project_data, detected_features


def clean_extracted_entity(raw: str) -> str:
    """Очищает название организации от лишних разделителей."""
    cleaned = raw.strip()
    # Убираем хвосты после разделителей
    parts = re.split(r"[\n\r\|]", cleaned)
    first_part = parts[0].strip()
    # Убираем лишние точки или двоеточия в начале/конце
    first_part = re.sub(r"^[:\s\-]+|[:\s\-]+$", "", first_part)
    return first_part
