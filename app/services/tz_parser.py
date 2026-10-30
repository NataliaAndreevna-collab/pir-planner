import datetime
import io
import os
import re
from typing import Dict, List, Optional, Set, Tuple
from fastapi import HTTPException
from app.models import FacilityType, ProjectData, ProjectMode, SectionItem
from app.services.llm_parser import query_llm_tz_analysis
from app.services.pp87_rules import (
    RD_CATALOG,
    apply_volume_ciphers,
    build_rd_sections,
    build_schedule,
    compute_cipher_from_contract,
    get_default_capital_sections,
    get_default_linear_sections,
)


# ---------------------------------------------------------------------------
# Разбор ТЗ, оформленного таблицей «№ | Поле | Значение»
# (текст, скопированный из Word с табуляцией, либо результат extract_text_from_docx со знаком « | »)
# ---------------------------------------------------------------------------

_ROW_START_RE = re.compile(
    r"^[ \t]*(\d{1,2})[ \t]*(?:\t|[ ]\|[ ])[ \t]*([^\t|\n]{2,120}?)[ \t]*(?:\t|[ ]\|[ ])[ \t]*(.*)$"
)

_ROW_NONUM_RE = re.compile(r"^[ \t]*([^\t|\n]{2,120}?)[ \t]*(?:\t|[ ]\|[ ])[ \t]*(.*)$")

_TZ_KEY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "customer": ("заказчик",),
    "contractor": ("подрядчик", "исполнитель", "генпроектировщик", "генеральный проектировщик"),
    "object": ("объект", "наименование объекта", "объект проектирования", "объект строительства"),
    "stage": ("стадийность", "стадия проектирования", "стадии проектирования"),
    "basis": ("основание для проектирования", "основание"),
}


def _alias_name(key: str) -> str:
    """Возвращает внутреннее имя поля ТЗ-таблицы по её названию или пустую строку."""
    k = (key or "").lower().strip(" :.")
    for name, aliases in _TZ_KEY_ALIASES.items():
        if any(k == a or k.startswith(a + " ") for a in aliases):
            return name
    return ""


def parse_tz_table_fields(raw_text: str) -> Dict[str, str]:
    """
    Разбирает ТЗ, оформленное таблицей «№ | Поле | Значение», и возвращает словарь
    {customer, contractor, object, stage, basis} (только найденные поля).
    Строки без номера в начале считаются продолжением значения предыдущей строки таблицы.
    Если таблицы в тексте нет — возвращается пустой словарь.
    """
    rows: List[List[str]] = []
    for line in (raw_text or "").splitlines():
        m = _ROW_START_RE.match(line)
        if m:
            rows.append([m.group(2).strip(), m.group(3).strip()])
            continue
        # Строка без номера (номер мог потеряться при копировании из Word): принимаем,
        # только если название поля совпадает с известным ключом.
        m2 = _ROW_NONUM_RE.match(line)
        if m2 and _alias_name(m2.group(1)):
            rows.append([m2.group(1).strip(), m2.group(2).strip()])
        elif rows and line.strip():
            rows[-1][1] = (rows[-1][1] + "\n" + line.strip()).strip()

    fields: Dict[str, str] = {}
    for key, value in rows:
        name = _alias_name(key)
        if name and name not in fields:
            fields[name] = value
    return fields


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
                seen = []
                for cell in row.cells:
                    t = cell.text.strip()
                    if t and (not seen or seen[-1] != t):
                        seen.append(t)
                if seen:
                    full_text.append(" | ".join(seen))
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


# ---------------------------------------------------------------------------
# Словари распознавания разделов ПД (ПП РФ № 87) и марок РД (ГОСТ Р 21.101)
# Поддерживают как официальные названия по ПП 87, так и живые инженерные формулировки из ТЗ
# ---------------------------------------------------------------------------

PD_CODE_PATTERNS: Dict[str, List[str]] = {
    "pz": [
        r"(?<![а-яёa-z0-9])пз(?![а-яёa-z0-9])",
        r"пояснительн\w+\s+записк\w*",
    ],
    "pzu": [
        r"(?<![а-яёa-z0-9])(?:пзу|спозу)(?![а-яёa-z0-9])",
        r"схем\w+\s+планировочн\w+\s+организац\w+",
        r"планировочн\w+\s+организац\w+\s+земельн\w+\s+участк\w*",
        r"благоустройств\w+\s+(?:и\s+озеленени\w+\s+)?территори\w*",
        r"генеральн\w+\s+план\w*",
    ],
    "ar": [
        r"(?<![а-яёa-z0-9])ар(?![а-яёa-z0-9])",
        r"архитектурн\w+\s+решени\w*",
        r"архитектурно[\-\s]строительн\w+",
    ],
    "kr": [
        r"(?<![а-яёa-z0-9])кр(?![а-яёa-z0-9])",
        r"конструктивн\w+\s+(?:и\s+объемно[\-\s]планировочн\w+\s+)?решени\w*",
        r"объемно[\-\s]планировочн\w+\s+и\s+конструктивн\w+\s+решени\w*",
        r"строительн\w+\s+част[ьию]\b",
        r"строительн\w+\s+конструкци\w*",
        r"фундамент\w*\s+под\s+оборудован",
    ],
    "ios1": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*1(?![0-9])",
        r"раздел\s*№?\s*5\.1(?![0-9])",
        r"подраздел\s*№?\s*1\b[^\n]{0,40}электро",
        r"электроснабжени[еяюем]\b",
        r"силов\w+\s+электрооборудовани\w*",
        r"электроосвещени[еяюем]\b",
    ],
    "ios2": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*2(?![0-9])",
        r"раздел\s*№?\s*5\.2(?![0-9])",
        r"подраздел\s*№?\s*2\b[^\n]{0,40}водоснабж",
        r"водоснабжени[еяюем]\b",
        r"участк\w+\s+водопровод\w*",
        r"сет[иейям]\s+водопровод\w*",
        r"реконструируем\w+\s+водопровод\w*",
    ],
    "ios3": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*3(?![0-9])",
        r"раздел\s*№?\s*5\.3(?![0-9])",
        r"подраздел\s*№?\s*3\b[^\n]{0,40}водоотвед",
        r"водоотведени[еяюем]\b",
        r"канализаци[ияюей]\b",
    ],
    "ios4": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*4(?![0-9])",
        r"раздел\s*№?\s*5\.4(?![0-9])",
        r"подраздел\s*№?\s*4\b[^\n]{0,40}(?:отоплен|вентиляц|теплов)",
        r"отоплени[еяюем]\s+и\s+вентиляци\w*",
        r"отоплени[еяю]\s*,?\s*вентиляци\w*",
        r"вентиляци\w*\s+и\s+кондиционировани\w*",
        r"теплоснабжени[еяюем]\b",
    ],
    "ios5_1": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*5(?:\.1)?(?![0-9\.]|\.\d)",
        r"раздел\s*№?\s*5\.5(?:\.1)?(?![0-9])",
        r"подраздел\s*№?\s*5\b[^\n]{0,40}связ",
        r"сет[иейям]\s+связи",
        r"канал\w*\s+связи",
        r"средств\w*\s+связи",
        r"видеонаблюдени[еяюем]\b",
        r"слаботочн\w+\s+(?:сет\w*|систем\w*)",
        r"структурированн\w+\s+кабельн\w+\s+систем\w*",
    ],
    "ios5_2": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*5\.2(?![0-9])",
        r"раздел\s*№?\s*5\.5\.2(?![0-9])",
        r"(?<![а-яёa-z0-9])(?:кипиа|кип|асутп|асу\s*тп)(?![а-яёa-z0-9])",
        r"автоматизац\w+\s+комплексн\w*",
        r"автоматизац\w+\s+и\s+диспетчеризац\w*",
        r"диспетчеризац\w+",
        r"автоматизац\w+\s+технологическ\w+",
    ],
    "ios6": [
        r"(?<![а-яёa-z0-9])иос\s*[\-\.]?\s*6(?![0-9])",
        r"раздел\s*№?\s*5\.6(?![0-9])",
        r"подраздел\s*№?\s*6\b[^\n]{0,40}газоснабж",
        r"газоснабжени[еяюем]\b",
        r"газопотреблени\w*",
    ],
    "tx": [
        r"(?<![а-яёa-z0-9])(?:тх|иос\s*[\-\.]?\s*7)(?![а-яёa-z0-9])",
        r"раздел\s*№?\s*6(?:\b|\.)[^\n]{0,40}технолог",
        r"подраздел\s*№?\s*7\b[^\n]{0,40}технолог",
        r"технологическ\w+\s+решени\w*",
        r"технологическ\w+\s+схем\w*",
        r"технологическ\w+\s+част[ьию]\b",
        r"очистк\w+\s+вод\w*",
        r"станци\w+\s+водоочистк\w*",
        r"водоподготовк\w*",
    ],
    "pos": [
        r"(?<![а-яёa-z0-9])пос(?![а-яёa-z0-9])",
        r"проект\w*\s+организац\w+\s+строительств\w*",
        r"организац\w+\s+строительств\w*",
    ],
    "pod": [
        r"(?<![а-яёa-z0-9])под(?![а-яёa-z0-9])",
        r"проект\w*\s+организац\w+\s+работ\s+по\s+сносу",
        r"работ\w*\s+по\s+сносу\s+или\s+демонтаж\w*",
        r"работ\w*\s+по\s+сносу\s+\(демонтажу\)",
        r"снос\w*\s+(?:и\s+)?демонтаж\w*",
    ],
    "oos": [
        r"(?<![а-яёa-z0-9])(?:оос|моос|пмоос)(?![а-яёa-z0-9])",
        r"мероприяти\w+\s+по\s+охран\w+\s+окружающ\w+\s+сред\w*",
        r"охран\w+\s+окружающ\w+\s+сред\w*",
    ],
    "pb": [
        r"(?<![а-яёa-z0-9])(?:мпб|ппм|пб)(?![а-яёa-z0-9])",
        r"мероприяти\w+\s+по\s+обеспечени\w+\s+пожарн\w+\s+безопасност\w*",
        r"обеспечени\w+\s+пожарн\w+\s+безопасност\w*",
        r"пожарн\w+\s+сигнализац\w*",
    ],
    "tbe": [
        r"(?<![а-яёa-z0-9])тбэ(?![а-яёa-z0-9])",
        r"требовани\w+\s+к\s+обеспечени\w+\s+безопасн\w+\s+эксплуатац\w*",
        r"безопасн\w+\s+эксплуатац\w+\s+объект\w*",
    ],
    "odi": [
        r"(?<![а-яёa-z0-9])(?:оди|моди)(?![а-яёa-z0-9])",
        r"обеспечени\w+\s+доступ\w+\s+инвалид\w*",
        r"доступност\w+\s+для\s+(?:инвалид\w+|маломобильн\w+)",
    ],
    "ee": [
        r"(?<![а-яёa-z0-9])ээ(?![а-яёa-z0-9])",
        r"энергетическ\w+\s+эффективност\w*",
        r"энергоэффективност\w*",
    ],
    "sm": [
        r"(?<![а-яёa-z0-9])(?:см|ссрсс)(?![а-яёa-z0-9\.])",
        r"раздел\s*№?\s*12(?:\.1)?(?![0-9])",
        r"смет\w+\s+на\s+строительств\w*",
        r"сводн\w+\s+сметн\w+\s+расчет",
        r"сметн\w+\s+документац\w*",
    ],
    "sm_p": [
        r"(?<![а-яёa-z0-9])см\.п(?![а-яёa-z0-9])",
        r"раздел\s*№?\s*12\.2(?![0-9])",
        r"конъюнктурн\w+\s+анализ",
    ],
    "sm_vor": [
        r"(?<![а-яёa-z0-9])(?:см\.вор|вор)(?![а-яёa-z0-9])",
        r"раздел\s*№?\s*12\.3(?![0-9])",
        r"ведомост\w+\s+объемов\s+работ",
    ],
    "gochs": [
        r"(?<![а-яёa-z0-9])(?:гочс|пм\s*гочс|итм\s*гочс)(?![а-яёa-z0-9])",
        r"(?<![а-яёa-z0-9])го\s*и\s*чс(?![а-яёa-z0-9])",
        r"гражданск\w+\s+оборон\w+",
        r"гост\s*р\s*22\.2\.13",
    ],
    "ots": [
        r"(?<![а-яёa-z0-9])отс(?![а-яёa-z0-9])",
        r"обследовани\w+\s+техническ\w+\s+состояни\w*",
        r"техническ\w+\s+обследовани\w+",
        r"гост\s*31937",
    ],
    # Линейные разделы
    "ppo": [
        r"(?<![а-яёa-z0-9])ппо(?![а-яёa-z0-9])",
        r"проект\w*\s+полос\w+\s+отвода",
    ],
    "tkr": [
        r"(?<![а-яёa-z0-9])ткр(?![а-яёa-z0-9])",
        r"технологическ\w+\s+и\s+конструктивн\w+\s+решени\w+\s+линейн\w+",
    ],
    "lin_infra": [
        r"(?<![а-яёa-z0-9])(?:ило|зси)(?![а-яёa-z0-9])",
        r"входящ\w+\s+в\s+инфраструктур\w+\s+линейн\w+",
    ],
    "rekult": [
        r"(?<![а-яёa-z0-9])прз(?![а-яёa-z0-9])",
        r"проект\w*\s+рекультивац\w+",
        r"рекультивац\w+\s+(?:нарушенн\w+\s+)?земел",
    ],
}

# Паттерны марок РД (ГОСТ Р 21.101) — как по буквенным маркам, так и по инженерным дисциплинам
RD_MARK_PATTERNS: Dict[str, List[str]] = {
    "rd_gp": [
        r"(?<![а-яёa-z0-9])гп(?![а-яёa-z0-9])",
        r"генеральн\w+\s+план\w*",
        r"благоустройств\w+",
    ],
    "rd_ar": [
        r"архитектурн\w+\s+решени\w*",
    ],
    "rd_as": [
        r"(?<![а-яёa-z0-9])ас(?![а-яёa-z0-9])",
        r"архитектурно[\-\s]строительн\w+\s+решени\w*",
        r"строительн\w+\s+част[ьию]\b",
    ],
    "rd_kzh": [
        r"(?<![а-яёa-z0-9])кж(?![а-яёa-z0-9])",
        r"конструкци\w+\s+железобетонн\w*",
        r"железобетонн\w+\s+конструкци\w*",
    ],
    "rd_km": [
        r"(?<![а-яёa-z0-9])(?<!\d\s)км(?![а-яёa-z0-9])",  # «5 км» и «5км» - это километры, а не марка КМ
        r"конструкци\w+\s+металлическ\w*",
        r"металлическ\w+\s+конструкци\w*",
    ],
    "rd_kd": [
        r"(?<![а-яёa-z0-9])кд(?![а-яёa-z0-9])",
        r"конструкци\w+\s+деревянн\w*",
        r"деревянн\w+\s+конструкци\w*",
    ],
    "rd_eom": [
        r"(?<![а-яёa-z0-9])(?:эом|эо|эм)(?![а-яёa-z0-9])",
        r"силов\w+\s+электрооборудовани\w*",
        r"электроосвещени\w*",
        r"электроснабжени[еяюем]\b",
    ],
    "rd_es": [
        r"(?<![а-яёa-z0-9])(?:эс|эн)(?![а-яёa-z0-9])",
        r"наружн\w+\s+сет\w+\s+электроснабжени\w*",
    ],
    "rd_vk": [
        r"(?<![а-яёa-z0-9])вк(?![а-яёa-z0-9])",
        r"внутренн\w+\s+(?:систем\w+\s+)?водоснабжени\w*\s+и\s+канализац\w*",
        r"водоснабжени[еяюем]\s+и\s+водоотведени\w*",
    ],
    "rd_nvk": [
        r"(?<![а-яёa-z0-9])нвк(?![а-яёa-z0-9])",
        r"наружн\w+\s+сет\w+\s+водоснабжени\w*",
        r"наружн\w+\s+сет\w+\s+водоотведени\w*",
        r"наружн\w+\s+сет\w+\s+канализац\w*",
        r"участк\w+\s+водопровод\w*",
        r"сет[иейям]\s+водопровод\w*",
        r"реконструируем\w+\s+водопровод\w*",
    ],
    "rd_ov": [
        r"(?<![а-яёa-z0-9])(?:овик|ов)(?![а-яёa-z0-9])",
        r"отоплени[еяюем]\s+и\s+вентиляци\w*",
        r"отоплени[еяю]\s*,?\s*вентиляци\w*",
    ],
    "rd_ts": [
        r"(?<![а-яёa-z0-9])тс(?![а-яёa-z0-9])",
        r"теплов\w+\s+сет\w*",
    ],
    "rd_ss": [
        r"(?<![а-яёa-z0-9])сс(?![а-яёa-z0-9])",
        r"канал\w*\s+связи",
        r"сет[иейям]\s+связи",
        r"видеонаблюдени[еяюем]\b",
        r"слаботочн\w+\s+(?:сет\w*|систем\w*)",
    ],
    "rd_ak": [
        r"(?<![а-яёa-z0-9])(?:ак|атх|авк|аов|кипиа|кип|асутп|асу\s*тп)(?![а-яёa-z0-9])",
        r"автоматизац\w+\s+и\s+диспетчеризац\w*",
        r"диспетчеризац\w+",
    ],
    "rd_gsn": [
        r"(?<![а-яёa-z0-9])(?:гсн|гсв)(?![а-яёa-z0-9])",
        r"газоснабжени[еяюем]\b",
    ],
    "rd_tx": [
        r"(?<![а-яёa-z0-9])тх(?![а-яёa-z0-9])",
        r"технологическ\w+\s+решени\w*",
        r"технологическ\w+\s+схем\w*",
        r"очистк\w+\s+вод\w*",
        r"станци\w+\s+водоочистк\w*",
        r"водоподготовк\w*",
    ],
    "rd_aps": [
        r"(?<![а-яёa-z0-9])(?:апс|соуэ|аупт)(?![а-яёa-z0-9])",
        r"пожарн\w+\s+сигнализац\w*",
    ],
    "rd_ad": [
        r"(?<![а-яёa-z0-9])ад(?![а-яёa-z0-9])",
        r"автомобильн\w+\s+дорог\w*",
    ],
    "rd_sm": [
        r"сметн\w+\s+документац\w*",
        r"сводн\w+\s+сметн\w+\s+расчет",
    ],
}

PD_TO_RD_DEFAULT: Dict[str, str] = {
    "pzu": "rd_gp",
    "ar": "rd_ar",
    "kr": "rd_kzh",
    "ios1": "rd_eom",
    "ios2": "rd_vk",
    "ios3": "rd_nvk",
    "ios4": "rd_ov",
    "ios5_1": "rd_ss",
    "ios5_2": "rd_ak",
    "ios6": "rd_gsn",
    "tx": "rd_tx",
    "sm": "rd_sm",
    "ppo": "rd_gp",
    "tkr": "rd_nvk",
    "lin_infra": "rd_as",
}

RD_TO_PD_CAPITAL: Dict[str, List[str]] = {
    "rd_gp": ["pzu"],
    "rd_ar": ["ar"],
    "rd_as": ["ar", "kr"],
    "rd_kzh": ["kr"],
    "rd_km": ["kr"],
    "rd_kd": ["kr"],
    "rd_eom": ["ios1"],
    "rd_es": ["ios1"],
    "rd_vk": ["ios2", "ios3"],
    "rd_nvk": ["ios2", "ios3"],
    "rd_ov": ["ios4"],
    "rd_ts": ["ios4"],
    "rd_ss": ["ios5_1"],
    "rd_ak": ["ios5_2"],
    "rd_gsn": ["ios6"],
    "rd_tx": ["tx"],
    "rd_aps": ["pb"],
    "rd_ad": ["pzu"],
    "rd_sm": ["sm"],
}

RD_TO_PD_LINEAR: Dict[str, List[str]] = {
    "rd_gp": ["ppo"],
    "rd_ar": ["lin_infra"],
    "rd_as": ["lin_infra"],
    "rd_kzh": ["tkr"],
    "rd_km": ["tkr"],
    "rd_kd": ["tkr"],
    "rd_eom": ["tkr"],
    "rd_es": ["tkr"],
    "rd_vk": ["tkr"],
    "rd_nvk": ["tkr"],
    "rd_ov": ["tkr"],
    "rd_ts": ["tkr"],
    "rd_ss": ["tkr"],
    "rd_ak": ["tkr"],
    "rd_gsn": ["tkr"],
    "rd_tx": ["tkr"],
    "rd_aps": ["pb"],
    "rd_ad": ["tkr"],
    "rd_sm": ["sm"],
}

# 1. Комплект СТРОГО для получения Разрешения на строительство (ч. 7 ст. 51 ГрК РФ) — остальные галочки сняты
PERMIT_BASE_CAPITAL: Set[str] = {
    "pz", "pzu", "ar", "kr", "ios1", "ios2", "ios3", "ios4", "ios5_1", "pos", "pb"
}
PERMIT_BASE_LINEAR: Set[str] = {
    "pz", "ppo", "tkr", "lin_infra", "pos", "pb"
}

# 2. Базовый обязательный комплект для прохождения Экспертизы ПД (ПП РФ № 87)
EXPERTISE_BASE_CAPITAL: Set[str] = {
    "pz", "pzu", "ar", "kr", "ios1", "ios2", "ios3", "ios4", "ios5_1", "pos", "oos", "pb", "tbe", "ee"
}
EXPERTISE_BASE_LINEAR: Set[str] = {
    "pz", "ppo", "tkr", "lin_infra", "pos", "oos", "pb", "tbe"
}


def map_rd_to_pd_ids(rd_ids: Set[str], facility_type: FacilityType) -> Set[str]:
    """Возвращает множество id разделов ПД, аналогичных переданным маркам РД."""
    mapping = RD_TO_PD_LINEAR if facility_type == FacilityType.LINEAR else RD_TO_PD_CAPITAL
    res: Set[str] = set()
    for rid in rd_ids:
        for pid in mapping.get(rid, []):
            res.add(pid)
    return res


def map_pd_to_rd_ids(pd_ids: Set[str], text_lower: str = "") -> Set[str]:
    """Возвращает множество id марок РД, аналогичных найденным разделам ПД (с учетом текста ТЗ)."""
    res: Set[str] = set()
    for pid in pd_ids:
        if pid in PD_TO_RD_DEFAULT:
            res.add(PD_TO_RD_DEFAULT[pid])
    if "kr" in pd_ids and re.search(r"строительн\w+\s+част[ьию]\b", text_lower):
        res.add("rd_as")
    if "ios2" in pd_ids and re.search(r"(?:наружн\w+\s+сет\w+\s+водоснабж|участк\w+\s+водопровод|реконструируем\w+\s+водопровод)", text_lower):
        res.add("rd_nvk")
    return res


def _detect_stages_and_explicit_sections(raw_text: str, facility_type: FacilityType) -> Tuple[bool, bool, str, Set[str], Set[str]]:
    """
    Анализирует текст ТЗ и определяет:
    - has_pd: требуется ли проектная документация
    - has_rd: требуется ли рабочая документация
    - auto_preset:
        * "tz" — если явно указан состав разделов / инженерных дисциплин в ТЗ (без экспертизы)
        * "expertise" — если указана экспертиза ПД (комплект для экспертизы + разделы из ТЗ)
        * "permit" — если в ТЗ вообще не указаны разделы и нет экспертизы (строго комплект для РнС)
    - explicit_pd: все разделы ПД, найденные в тексте ТЗ (включая аналоги марок РД)
    - explicit_rd: все марки РД, найденные в тексте ТЗ (включая аналоги разделов ПД)
    """
    text_lower = raw_text.lower()

    mentions_pd = bool(re.search(
        r"(?:проектн\w+\s+документац|проектно[\-\s]сметн\w+|проектн\w+/рабоч\w+|проектн\w+\s+и\s+рабоч\w+|(?<![а-яёa-z0-9])пд(?![а-яёa-z0-9])|стади[ияю]\s*[«\"']?п[»\"']?(?:\b|$)|раздел\w*\s+проектн|проектн\w+\s+решени\w*)",
        text_lower
    ))
    mentions_rd = bool(re.search(
        r"(?:рабоч\w+\s+документац|проектн\w+/рабоч\w+|проектн\w+\s+и\s+рабоч\w+|(?<![а-яёa-z0-9])рд(?![а-яёa-z0-9])|рабочи[ех]\s+чертеж|стади[ияю]\s*[«\"']?р[»\"']?(?:\b|$)|марк[аиуе]\s+[а-яё]{2,5}(?![а-яё]))",
        text_lower
    ))
    # Точное определение стадии проектирования из заголовков таблицы ТЗ
    stage_row_match = re.search(
        r"(?:^|\n)[\|\s0-9\.\-]*\bстади[ияюйн\w]*\s*(?:проектирования)?\b[\t\|:\-– ]*([^\n\r\|]{2,120})",
        text_lower
    )
    stage_header_text = stage_row_match.group(1).strip() if stage_row_match else ""

    explicit_both_stages = bool(re.search(
        r"(?:пд\s*[\+,и\/]\s*рд|п\s*[\+,и\/]\s*р|проектн\w+\s*(?:и|\/)\s*рабоч\w+|две\s+стадии|в\s+2\s+стадии)",
        stage_header_text or text_lower
    ))
    # В строке «Стадийность» названы обе стадии («Проектная документация и рабочая документация»,
    # «ПД, РД») и нет ограничителей — это ПД + РД, а не «только РД» / «только ПД».
    if (
        not explicit_both_stages
        and stage_header_text
        and re.search(r"(?:проектн\w+\s+документац|(?<![а-яёa-z0-9])пд(?![а-яёa-z0-9]))", stage_header_text)
        and re.search(r"(?:рабоч\w+\s+документац|(?<![а-яёa-z0-9])рд(?![а-яёa-z0-9]))", stage_header_text)
        and not re.search(r"(?:только|без\s|не\s+(?:разрабатыва|требу)|на\s+основании|ранее\s+разработан)", stage_header_text)
    ):
        explicit_both_stages = True

    explicit_only_rd = (not explicit_both_stages) and bool(re.search(
        r"(?:рабочая\s+документация|\bрд\b|стади[ияю]\s*[«\"']?р[»\"']?(?:\b|$)|только\s+рабоч|без\s+проектн\w+\s+документац|на\s+основании\s+(?:ранее\s+разработанной\s+)?проектной)",
        stage_header_text if stage_header_text else text_lower
    ))

    explicit_only_pd = (not explicit_both_stages) and bool(re.search(
        r"(?:проектная\s+документация|\bпд\b|стади[ияю]\s*[«\"']?п[»\"']?(?:\b|$)|только\s+проектн|без\s+рабоч\w+\s+документац|в\s+одну\s+стадию\s*[\-–:]?\s*пд|рабоч\w+\s+документац\w*\s+не\s+(?:разрабатыва|требу))",
        stage_header_text if stage_header_text else text_lower
    ))

    mentions_sm = bool(re.search(r"(?:сметн\w+\s+документац|\bсм\b|\bсср\b|локальн\w+\s+смет|сметы\b)", stage_header_text or text_lower))

    explicit_pd: Set[str] = set()
    explicit_rd: Set[str] = set()

    # ШАГ 1. Ищем все разделы ПД и инженерные дисциплины по всему тексту ТЗ
    for sec_id, patterns in PD_CODE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                explicit_pd.add(sec_id)
                break

    if "sm_p" in explicit_pd or "sm_vor" in explicit_pd:
        explicit_pd.add("sm")

    # ШАГ 2. Ищем все марки и дисциплины РД по всему тексту ТЗ
    for rd_id, patterns in RD_MARK_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                explicit_rd.add(rd_id)
                break

    # Признаки явно ограниченного в 1 раздел ТЗ
    single_pd_hint = bool(re.search(r"(?:один|одного|1)\s+раздел\w*\s+(?:проектн\w+|(?<![а-яёa-z0-9])пд(?![а-яёa-z0-9]))", text_lower))
    single_rd_hint = bool(re.search(r"(?:один|одного|1)\s+(?:раздел\w*|комплект\w*|марк\w*)\s+(?:рабоч\w+|(?<![а-яёa-z0-9])рд(?![а-яёa-z0-9]))", text_lower))
    explicit_list_hint = bool(re.search(
        r"(?:состав\s+проект\w*\s*[:\-]|состав\s+разрабатываем\w+\s+документац\w*\s*[:\-]|разработать\s+(?:следующ\w+\s+)?раздел\w*|в\s+составе\s+раздел\w*|в\s+объеме\s+раздел\w*|перечень\s+разрабатываем\w+\s+раздел\w*|только\s+раздел\w*|проектными\s+решениями[^\n]{0,60}предусмотрено)",
        text_lower
    ))

    if explicit_only_rd:
        has_pd = False
        has_rd = True
        explicit_pd = set()
    elif explicit_only_pd:
        has_pd = True
        has_rd = False
        explicit_rd = set()
    elif explicit_both_stages:
        has_pd = True
        has_rd = True
        if explicit_rd and not (single_pd_hint and explicit_pd):
            explicit_pd |= map_rd_to_pd_ids(explicit_rd, facility_type)
        if explicit_pd and not (single_rd_hint and explicit_rd):
            explicit_rd |= map_pd_to_rd_ids(explicit_pd, text_lower)
    else:
        # ПРАВИЛО ДВУСТОРОННЕЙ СВЯЗКИ ПД <-> РД:
        # 1) Если найдены марки/дисциплины РД -> автоматически добавляем аналогичные разделы в ПД
        if explicit_rd and not (single_pd_hint and explicit_pd):
            explicit_pd |= map_rd_to_pd_ids(explicit_rd, facility_type)

        # 2) Если найдены разделы/дисциплины ПД -> автоматически формируем аналогичные марки в РД
        if explicit_pd and not (single_rd_hint and explicit_rd):
            explicit_rd |= map_pd_to_rd_ids(explicit_pd, text_lower)

        has_pd = True
        # Включаем РД, если она упомянута явно ИЛИ если в ТЗ перечислены инженерные разделы/марки
        has_rd = bool(mentions_rd or explicit_rd)

    # Если сметы (СМ) выделены отдельно в графе стадийности/состава:
    if mentions_sm:
        if has_pd:
            explicit_pd.add("sm")
        if has_rd:
            explicit_rd.add("rd_sm")

    demands_full_pp87 = bool(re.search(
        r"(?:состав\s+разделов\s+принять\s+согласно\s+постановлени\w*[^\n]{0,50}№\s*87|в\s+полном\s+объеме[^\n]{0,40}№\s*87)",
        text_lower
    ))
    has_expertise_mention = bool(re.search(
        r"(?:государственн\w+\s+экспертиз|негосударственн\w+\s+экспертиз|экспертиз\w+\s+проектн\w+\s+документац|прохождени\w+\s+экспертиз|положительн\w+\s+заключени\w+\s+экспертиз|достоверност\w+\s+(?:определения\s+)?сметн\w+\s+стоимост|главгосэкспертиз|мосгосэкспертиз|гау\s+«?угэц)",
        text_lower
    ))

    # ВЫБОР НАИБОЛЕЕ ПОДХОДЯЩЕГО ВАРИАНТА ПО УМОЛЧАНИЮ:
    # 1) Если указана экспертиза ПД (и это не точечное ТЗ на 1-2 раздела) -> "expertise" (Для Экспертизы ПД + разделы из ТЗ)
    # 2) Иначе если в ТЗ найдены конкретные разделы/системы (и не требуется полный ПП 87) -> "tz" (Только разделы из ТЗ)
    # 3) Иначе (если в ТЗ вообще не указаны разделы и нет экспертизы) -> "permit" (Для Разрешения на строительство)
    total_explicit = len(explicit_pd) + len(explicit_rd)
    if single_pd_hint or single_rd_hint:
        auto_preset = "tz"
    elif has_expertise_mention and not (explicit_list_hint and len(explicit_pd) <= 4):
        auto_preset = "expertise"
    elif not demands_full_pp87 and total_explicit > 0:
        auto_preset = "tz"
    elif has_expertise_mention:
        auto_preset = "expertise"
    else:
        auto_preset = "permit"

    # Корректировка для строго одиночных указаний («1 раздел ПД и 1 раздел РД»)
    if single_pd_hint:
        if not explicit_pd:
            explicit_pd = {"kr" if facility_type != FacilityType.LINEAR else "tkr"}
        elif len(explicit_pd) > 1:
            non_pz = [x for x in explicit_pd if x != "pz"]
            explicit_pd = {non_pz[0] if non_pz else next(iter(explicit_pd))}

    if single_rd_hint:
        if not explicit_rd:
            first_pd = next(iter(explicit_pd)) if explicit_pd else "kr"
            explicit_rd = {PD_TO_RD_DEFAULT.get(first_pd, "rd_kzh")}
        elif len(explicit_rd) > 1:
            # Если в строке РД явно была названа марка — берем первую найденную до авторасширения
            explicit_rd = {next(iter(explicit_rd))}

    return has_pd, has_rd, auto_preset, explicit_pd, explicit_rd


def apply_tz_to_sections(
    raw_text: str,
    facility_type: FacilityType,
    preset_override: Optional[str] = None,
) -> Tuple[List[SectionItem], bool, bool, str, List[str], Dict[str, object]]:
    """
    Формирует состав разделов ПД и РД по одному из 3 режимов:
    1. "tz" (Только по ТЗ): включает разделы ПД и марки РД, найденные по тексту ТЗ (с двусторонней связкой ПД <-> РД).
    2. "permit" (Для Разрешения на строительство): включает СТРОГО разделы, необходимые для РнС, со всех остальных снимает галочки.
    3. "expertise" (Для Экспертизы ПД): включает обязательный комплект для экспертизы + добавляет все разделы и марки РД из ТЗ.
    """
    detected_features: List[str] = []
    text_lower = (raw_text or "").lower()

    has_pd, has_rd, auto_preset, explicit_pd, explicit_rd = _detect_stages_and_explicit_sections(raw_text or "", facility_type)
    chosen_preset = preset_override if preset_override in ("tz", "permit", "expertise") else auto_preset

    if facility_type == FacilityType.LINEAR:
        pd_sections = get_default_linear_sections()
    else:
        pd_sections = get_default_capital_sections()

    valid_pd_ids = {s.id for s in pd_sections}

    mapped_explicit_pd = set(explicit_pd)
    if facility_type == FacilityType.LINEAR:
        if mapped_explicit_pd & {"kr", "ios1", "ios2", "ios3", "ios4", "ios5_1", "ios5_2", "ios6", "tx"}:
            mapped_explicit_pd.add("tkr")
        if "pzu" in mapped_explicit_pd:
            mapped_explicit_pd.add("ppo")
        if "ar" in mapped_explicit_pd:
            mapped_explicit_pd.add("lin_infra")
    else:
        if "ppo" in mapped_explicit_pd:
            mapped_explicit_pd.add("pzu")
        if "tkr" in mapped_explicit_pd:
            mapped_explicit_pd.add("kr")
        if "lin_infra" in mapped_explicit_pd:
            mapped_explicit_pd.add("ar")

    matched_pd_in_catalog = mapped_explicit_pd & valid_pd_ids

    has_ots = bool(re.search(r"(?:обследование|гост\s*31937|техническ\w+\s+состояни\w+|\bотс\b)", text_lower))
    has_gochs = bool(re.search(r"(?:гочс|го\s*и\s*чс|гражданск\w+\s+оборон\w+|чрезвычайн\w+\s+ситуац|гост\s*р\s*22\.2\.13)", text_lower))
    has_pod = bool(re.search(r"(?:снос|демонтаж|ликвидаци\w+\s+сооружен)", text_lower))
    has_automation = bool(re.search(r"(?:автоматизац|диспетчеризац|кип|асу)", text_lower))
    has_tx = bool(re.search(r"(?:технологическ\w+\s+схем|технологическ\w+\s+решени|водоподготовк|очистк\w+\s+вод|водоочистк|уфо|фильтр|насосн\w+|технологическ\w+\s+регламент)", text_lower))
    has_sm = bool(re.search(r"(?:смет|фснб|проверк\w+\s+достоверност|гранд[\-\s]смет|бюджетн\w+\s+финансирован|государственн\w+\s+экспертиз)", text_lower))
    has_odi = bool(re.search(r"(?:доступ\w*\s+инвалид|маломобильн|\bоди\b|\bмоди\b|общественн\w+|административн\w+|школ|детск\w+|больниц|поликлиник|торгов\w+|жилой\s+дом)", text_lower))
    has_ee = bool(re.search(r"(?:энергетическ\w+\s+эффективност|энергоэффективност|\bээ\b)", text_lower))
    has_gas = bool(re.search(r"(?:систем\w+\s+газоснабжени|газопотреблени|газов\w+\s+котельн|\bиос\s*6\b)", text_lower))
    has_rekult = bool(re.search(r"(?:рекультивац\w+\s+нарушенн\w+\s+земел|рекультивац\w+\s+земел)", text_lower))

    trigger_map = {
        "ots": has_ots,
        "gochs": has_gochs,
        "pod": has_pod,
        "ios5_2": has_automation,
        "ios6": has_gas,
        "tx": has_tx,
        "sm": has_sm,
        "sm_p": has_sm,
        "sm_vor": has_sm,
        "odi": has_odi,
        "ee": has_ee,
        "rekult": has_rekult,
    }

    if chosen_preset == "tz":
        # ВАРИАНТ 1: ТОЛЬКО ПО ТЗ (включаем разделы ПД и марки РД, найденные в ТЗ)
        for s in pd_sections:
            if has_pd and s.id in matched_pd_in_catalog:
                s.enabled = True
                s.source = "tz"
            else:
                s.enabled = False
                s.source = "default"

        rd_sections = build_rd_sections(facility_type, pd_sections, text_lower)
        for r in rd_sections:
            if has_rd and r.id in explicit_rd:
                r.enabled = True
                r.source = "tz"
            else:
                r.enabled = False
                r.source = "default"

        enabled_pd_marks = [s.code_mark for s in pd_sections if s.enabled]
        enabled_rd_marks = [r.code_mark for r in rd_sections if r.enabled]
        summary_parts = []
        if enabled_pd_marks:
            summary_parts.append(f"ПД ({len(enabled_pd_marks)}): {', '.join(enabled_pd_marks)}")
        if enabled_rd_marks:
            summary_parts.append(f"РД ({len(enabled_rd_marks)}): {', '.join(enabled_rd_marks)}")
        if summary_parts:
            detected_features.append(f"Предложен вариант «Только по ТЗ» — {' | '.join(summary_parts)}")

    elif chosen_preset == "permit":
        # ВАРИАНТ 2: СТРОГО ДЛЯ РАЗРЕШЕНИЯ НА СТРОИТЕЛЬСТВО (ч. 7 ст. 51 ГрК РФ) — остальные галочки сняты!
        base_set = PERMIT_BASE_LINEAR if facility_type == FacilityType.LINEAR else PERMIT_BASE_CAPITAL
        for s in pd_sections:
            if s.id in base_set:
                s.enabled = True
                s.source = "tz" if s.id in matched_pd_in_catalog else "default"
            else:
                s.enabled = False
                s.source = "default"

        rd_sections = build_rd_sections(facility_type, pd_sections, text_lower)
        for r in rd_sections:
            r.enabled = False
            r.source = "default"
        has_rd = False

        detected_features.append("Предложен вариант «Для Разрешения на строительство» (только обязательные разделы по ч. 7 ст. 51 ГрК РФ, остальные отключены)")

    else:
        # ВАРИАНТ 3: ДЛЯ ЭКСПЕРТИЗЫ ПД (ПП РФ № 87) + РАЗДЕЛЫ И МАРКИ, УКАЗАННЫЕ В ТЗ
        chosen_preset = "expertise"
        base_set = EXPERTISE_BASE_LINEAR if facility_type == FacilityType.LINEAR else EXPERTISE_BASE_CAPITAL

        for s in pd_sections:
            if s.id in matched_pd_in_catalog:
                s.enabled = True
                s.source = "tz"
            elif s.id in base_set:
                s.enabled = True
                s.source = "default"
            elif trigger_map.get(s.id, False):
                s.enabled = True
                s.source = "trigger"
            else:
                s.enabled = False
                s.source = "default"

        rd_sections = build_rd_sections(facility_type, pd_sections, text_lower)
        if not has_rd:
            for r in rd_sections:
                r.enabled = False
        elif explicit_rd:
            for r in rd_sections:
                r.enabled = r.id in explicit_rd
                if r.enabled:
                    r.source = "tz"

        detected_features.append("Предложен вариант «Для Экспертизы ПД (ПП РФ № 87)» + дополнительные разделы из ТЗ")
        if has_ots or "ots" in matched_pd_in_catalog:
            detected_features.append("Включен раздел ОТС (техническое обследование)")
        if has_gochs or "gochs" in matched_pd_in_catalog:
            detected_features.append("Включен раздел ГОЧС (ГОСТ Р 22.2.13)")
        if has_pod or "pod" in matched_pd_in_catalog:
            detected_features.append("Включен раздел ПОД (снос / демонтаж)")
        if has_automation or "ios5_2" in matched_pd_in_catalog:
            detected_features.append("Включен подраздел ИОС5.2 (автоматизация и диспетчеризация)")
        if has_tx or "tx" in matched_pd_in_catalog:
            detected_features.append("Включен Раздел 6 ТХ (технологические решения)")
        if has_sm or "sm" in matched_pd_in_catalog:
            detected_features.append("Включен Раздел 12 СМ (сметная документация)")

    if "цус" in text_lower or "цифровое управление строительством" in text_lower:
        detected_features.append("Особое требование: электронный документооборот через ИАС «ЦУС» с УКЭП")

    # Признаки для графика
    has_surveys = bool(re.search(r"(?:инженерн\w+\s+изыскани|геодезическ\w+|геологическ\w+|экологическ\w+|\bигди\b|\bиги\b|\bиэи\b)", text_lower))
    has_internal_exp = bool(re.search(r"внутренн\w+\s+экспертиз", text_lower))
    has_state_exp = bool(re.search(r"(?:государственн\w+\s+экспертиз|негосударственн\w+\s+экспертиз|экспертиз\w+\s+проектн\w+\s+документац|достоверност\w+\s+(?:определения\s+)?сметн\w+\s+стоимост)", text_lower))
    has_permit = bool(re.search(r"разрешени\w+\s+на\s+строительств", text_lower))
    has_techplan = bool(re.search(r"техническ\w+\s+план", text_lower))
    ots_enabled = any(s.id == "ots" and s.enabled for s in pd_sections)

    schedule_flags = {
        "ots": ots_enabled,
        "surveys": has_surveys,
        "survey_types": "ИГДИ, ИГИ, ИЭИ",
        "internal_expertise": True,  # Включаем этапы внутренней экспертизы РВК в график по умолчанию
        "expertise": True,           # Включаем этапы Главгосэкспертизы и смет в график по умолчанию
        "permit": False,             # Разрешение на строительство убрано по требованию ГИПа
        "techplan": has_techplan,
    }

    all_sections = pd_sections + rd_sections
    return all_sections, has_pd, has_rd, chosen_preset, detected_features, schedule_flags


def parse_tz_content(raw_text: str, engine: str = "local") -> Tuple[ProjectData, List[str]]:
    """
    Анализирует текст ТЗ, извлекает параметры объекта,
    определяет тип объекта, стадии и наиболее подходящий вариант состава разделов ПД/РД.
    Параметр engine:
      - 'local': мгновенный нормативный расчет по ключевым маркерам и словарям (<0.05 сек).
      - 'ai': анализ через нейросеть (OpenRouter LLM) с подробными пояснениями.
    """
    object_name = "Строительство объекта"
    table_fields = parse_tz_table_fields(raw_text)
    table_object = clean_extracted_entity(table_fields.get("object", ""))
    match_obj = re.search(
        r"(?:по объекту|наименование объекта|объект проектирования|объект строительства)[\s:«\"'\-]+([^\n\r|]+)",
        raw_text,
        re.IGNORECASE,
    )
    if len(table_object) > 3:
        object_name = table_object
    elif match_obj:
        val = match_obj.group(1).strip()
        val = re.sub(r"^[«\"']|[»\"'.]+$", "", val).strip()
        if len(val) > 3:
            object_name = val
    else:
        match_constr = re.search(
            r"((?:Строительство|Реконструкция|Капитальный ремонт|Техническое перевооружение|Проектирование)[ \t]+[^\n\r\|]{4,90})",
            raw_text,
            re.IGNORECASE,
        )
        if match_constr:
            object_name = match_constr.group(1).strip()

    customer = ""
    match_cust = re.search(
        r"(?:Заказчик(?:[\-\s]Застройщик)?)\s*(?:\|[^\n\r|]*\|)?\s*[:\-–|]\s*([^\n\r|]+)",
        raw_text,
        re.IGNORECASE,
    )
    if table_fields.get("customer"):
        customer = clean_extracted_entity(table_fields["customer"])
    elif match_cust:
        customer = clean_extracted_entity(match_cust.group(1))

    contractor = ""
    if table_fields.get("contractor"):
        cand_tab = clean_extracted_entity(table_fields["contractor"])
        if not re.search(r"^(?:не\s+требуется|нет|не\s+указан|\-+)$", cand_tab, re.IGNORECASE):
            contractor = cand_tab
    match_gen = re.search(
        r"(?:Генпроектировщик|Генеральный\s+проектировщик)\s*(?:\|[^\n\r|]*\|)?\s*[:\-–|]\s*([^\n\r|]+)",
        raw_text,
        re.IGNORECASE,
    )
    if not contractor and match_gen:
        cand = clean_extracted_entity(match_gen.group(1))
        if not re.search(r"^(?:не\s+требуется|нет|не\s+указан|\-+)$", cand, re.IGNORECASE):
            contractor = cand

    contract_number = ""
    contract_date = ""
    contract_re = r"(?:Договор[а-я\s]*|контракт[а-я\s]*)№\s*([0-9А-Яа-яA-Za-z\/\-]+)(?:\s+от\s+([0-9]{1,2}\.[0-9]{1,2}\.[0-9]{2,4}\s*г?\.?))?"
    match_contract = None
    if table_fields.get("basis"):
        match_contract = re.search(contract_re, table_fields["basis"], re.IGNORECASE)
    if not match_contract:
        match_contract = re.search(contract_re, raw_text, re.IGNORECASE)
    if match_contract:
        contract_number = match_contract.group(1).strip()
        if match_contract.group(2):
            contract_date = match_contract.group(2).strip()

    text_lower = raw_text.lower()
    linear_keywords = [
        "линейный объект", "полоса отвода", "полосы отвода", "протяженность трассы",
        "трасса водопровода", "коллектор", "кабельная линия",
        "наружные сети водоснабжения протяженностью", "вдоль трассы", "газопровод", "автомобильная дорога",
        "раздел 5 «проект организации строительства»", "раздел 5 \"проект организации строительства\"",
    ]
    capital_keywords = [
        "сооружение водоподготовки", "станция", "станции водоочистки", "здание", "блок-бокс",
        "площадка", "резервуар", "цех", "вос", "кос", "сооружение", "спозу", "корпус", "жилой дом",
    ]

    has_linear_markers = any(k in text_lower for k in linear_keywords)
    has_capital_markers = any(k in text_lower for k in capital_keywords)

    detected_features: List[str] = []

    llm_result = None
    if engine == "ai":
        llm_result, llm_error = query_llm_tz_analysis(raw_text)
        if not llm_result:
            # Пользователь специально нажал AI, поэтому не подменяем молча на внутренний расчет,
            # а сообщаем точную причину ошибки!
            raise HTTPException(
                status_code=502,
                detail=f"Ошибка нейросети: {llm_error or 'Нейросеть не вернула результат'}. Проверьте соединение или используйте кнопку 'Быстрый анализ (без AI)'."
            )
        detected_features.append("Успешно применены выводы нейросети (AI)")
        if llm_result.get("explanation"):
            detected_features.append(f"AI пояснение: {llm_result['explanation']}")

        if llm_result.get("object_name") and len(llm_result["object_name"].strip()) > 3:
            object_name = llm_result["object_name"].strip()
        if llm_result.get("customer"):
            customer = clean_extracted_entity(llm_result["customer"])
        if llm_result.get("contractor"):
            contractor = clean_extracted_entity(llm_result["contractor"])
        if llm_result.get("contract_number"):
            contract_number = llm_result["contract_number"].strip()
        if llm_result.get("contract_date"):
            contract_date = llm_result["contract_date"].strip()

        fac_str = str(llm_result.get("facility_type", "")).lower()
        if fac_str == "linear":
            facility_type = FacilityType.LINEAR
            detected_features.append("Линейный объект (Раздел III ПП РФ № 87)")
        else:
            facility_type = FacilityType.CAPITAL
            detected_features.append("Объект капитального строительства (Раздел II ПП РФ № 87)")

        has_pd = bool(llm_result.get("has_pd", True))
        has_rd = bool(llm_result.get("has_rd", False))
        chosen_preset = llm_result.get("composition_preset", "tz")
        if chosen_preset not in ("tz", "permit", "expertise"):
            chosen_preset = "tz" if (has_rd and not has_pd) else "permit"

        pd_sec_ids = set(llm_result.get("pd_sections", [])) if has_pd else set()
        rd_mark_ids = set(llm_result.get("rd_marks", [])) if has_rd else set()

        if facility_type == FacilityType.LINEAR:
            pd_sections = get_default_linear_sections()
        else:
            pd_sections = get_default_capital_sections()

        for s in pd_sections:
            if has_pd and s.id in pd_sec_ids:
                s.enabled = True
                s.source = "tz"
            else:
                s.enabled = False
                s.source = "default"

        rd_sections = build_rd_sections(facility_type, pd_sections, text_lower)
        for r in rd_sections:
            if has_rd and r.id in rd_mark_ids:
                r.enabled = True
                r.source = "tz"
            else:
                r.enabled = False
                r.source = "default"

        schedule_flags = {
            "ots": any(s.id == "ots" and s.enabled for s in pd_sections),
            "surveys": bool(llm_result.get("has_surveys", False)),
            "survey_types": "ИГДИ, ИГИ, ИЭИ",
            "internal_expertise": True,
            "expertise": True,
            "permit": False,
            "techplan": False,
        }
        sections = pd_sections + rd_sections
    else:
        # 2. Резервный режим (fallback): классический парсер по правилам и словарям
        if has_capital_markers and has_linear_markers:
            facility_type = FacilityType.CAPITAL
            detected_features.append("Комплексный объект: площадочные сооружения + прилегающие сети")
        elif has_linear_markers and not has_capital_markers:
            facility_type = FacilityType.LINEAR
            detected_features.append("Линейный объект (Раздел III ПП РФ № 87)")
        else:
            facility_type = FacilityType.CAPITAL
            detected_features.append("Объект капитального строительства (Раздел II ПП РФ № 87)")

        sections, has_pd, has_rd, chosen_preset, sec_features, schedule_flags = apply_tz_to_sections(raw_text, facility_type)
        detected_features.extend(sec_features)

    project_mode = ProjectMode.PRE_CONTRACT
    cipher = compute_cipher_from_contract(contract_number, contract_date) if contract_number else ""

    project_data = ProjectData(
        mode=project_mode,
        object_name=object_name,
        customer=customer,
        contractor=contractor,
        contract_number=contract_number,
        contract_date=contract_date,
        cipher=cipher,
        facility_type=facility_type,
        start_date=datetime.date.today().isoformat(),
        has_pd=has_pd,
        has_rd=has_rd,
        composition_preset=chosen_preset,
        schedule_flags=schedule_flags,
        schedule_detail="sections",
        tz_text=raw_text,
        sections=sections,
    )

    apply_volume_ciphers(project_data)
    project_data.schedule_phases = build_schedule(project_data)

    return project_data, detected_features


def clean_extracted_entity(raw: str) -> str:
    """Очищает название организации от лишних разделителей."""
    cleaned = raw.strip()
    parts = re.split(r"[\n\r\|]", cleaned)
    first_part = parts[0].strip()
    first_part = re.sub(r"^[:\s\-–]+|[:\s\-–]+$", "", first_part)
    return first_part
