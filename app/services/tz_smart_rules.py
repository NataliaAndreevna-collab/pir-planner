import re
from typing import Dict, List, Optional, Set, Tuple
from app.models import FacilityType, ProjectData, SectionItem

def extract_section_block(text: str, section_names: List[str]) -> str:
    """Извлекает конкретный раздел ТЗ по его заголовкам."""
    pattern = r"(?:^|\n)[\|\s]*(?:" + "|".join(section_names) + r")[\s\|:\-\.]{1,10}([^\n\r\|]{3,1500})"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def is_negated(phrase: str, text_context: str) -> bool:
    """Проверяет, не отрицается ли фраза в ближайшем контексте."""
    negations = [
        r"не\s+(?:требуется|подлежит|проводится|разрабатывается)",
        r"без\s+",
        r"отсутству\w+",
        r"исключ\w+",
        r"не\s+входит",
    ]
    for neg in negations:
        if re.search(neg + r"[^\.\n]{0,50}" + phrase, text_context, re.IGNORECASE):
            return True
        if re.search(phrase + r"[^\.\n]{0,50}" + neg, text_context, re.IGNORECASE):
            return True
    return False
