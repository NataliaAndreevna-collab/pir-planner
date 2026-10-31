"""
Маскирование данных в тексте ТЗ перед отправкой во внешнюю нейросеть (OpenRouter).

ВАЖНО: это набор шаблонов (регулярных выражений) и подстановка известных значений, а НЕ гарантия
конфиденциальности. Нестандартно записанные данные фильтр может пропустить. Поэтому в ИИ уходит только
замаскированный текст, а реквизиты (заказчик, подрядчик, договор, название объекта) заполняет локальный парсер.

Что заменяется:
  * известные значения, найденные локальным парсером: заказчик, подрядчик, номер и дата договора, название объекта;
  * ИНН, КПП, ОГРН, БИК, расчётные/корреспондентские счета, email, телефоны;
  * блоки подписей («Генеральный директор … М.П.»);
  * ФИО (в формах «И.О. Фамилия», «Фамилия И.О.», «Фамилия Имя Отчество»);
  * точный почтовый адрес (индекс, улица, дом, офис). Город и регион остаются.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class MaskResult:
    text: str
    replacements: List[Dict[str, object]] = field(default_factory=list)  # [{kind, original, placeholder}]

    def summary(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.replacements:
            out[str(r["kind"])] = out.get(str(r["kind"]), 0) + 1
        return out


_ORG_FORMS = r"(?:ООО|АО|ПАО|ОАО|ЗАО|АНО|НКО|МУП|ГУП|МБУ|ГБУ|ФГУП|ИП)"
_FIO_INITIALS_FIRST = re.compile(r"(?<![А-ЯЁа-яё])[А-ЯЁ]\.\s?[А-ЯЁ]\.\s?[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?")
_FIO_SURNAME_FIRST = re.compile(r"(?<![А-ЯЁа-яё])[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.")
_FIO_FULL = re.compile(
    r"(?<![А-ЯЁа-яё])[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:ович|евич|ьич|ична|овна|евна|инична)(?![а-яё])"
)

_SIGNATURE_BLOCK = re.compile(
    r"(?:Генеральный\s+директор|Директор|Руководитель|Заместитель\s+[^\n]{0,60}|Главный\s+инженер|Начальник\s+[^\n]{0,40}|Исполнительный\s+директор)"
    r"[^\n]*\n(?:[^\n]*\n){0,5}?[^\n]*?(?:_{3,}|М\.\s?П\.)[^\n]*(?:\s*М\.\s?П\.)?",
)

_STREET = (
    r"(?:ул\.|улица|пр-кт|пр-т|просп\.|проспект|пер\.|переулок|ш\.|шоссе|б-р|бульвар|наб\.|набережная|мкр\.?|микрорайон)"
)
_ADDRESS = re.compile(
    rf"(?<![А-ЯЁа-яё]){_STREET}\s*[^\n,;]{{2,60}}(?:,\s*(?:д\.|дом|корп\.|корпус|стр\.|строение|оф\.|офис|кв\.|пом\.|помещение|литера?|лит\.)\s*[\w/\-]+)*",
    re.IGNORECASE,
)
_POSTAL_INDEX = re.compile(r"(?<!\d)\d{6}(?!\d)(?=\s*,)")

_EMAIL = re.compile(r"[\w.\-+]+@[\w\-]+(?:\.[\w\-]+)+")
_PHONE = re.compile(
    r"(?<![\d\w])(?:\+7|8)[\s\-]*\(?\d{3}\)?[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"
    r"|(?<![\d\w])\(\d{3,5}\)[\s\-]*\d[\d\s\-]{4,10}\d(?!\d)"
)
_BANK_LABELED = re.compile(
    r"(?P<label>ИНН|КПП|ОГРНИП|ОГРН|БИК|ОКПО|ОКТМО|р/с|р\.\s?с\.|к/с|к\.\s?с\.|расч[её]тный\s+счёт|корр\.?\s*счёт)"
    r"[\s:№\-/]*(?P<num>\d[\d\s]{7,24}\d)",
    re.IGNORECASE,
)
_ACCOUNT_20 = re.compile(r"(?<!\d)\d{20}(?!\d)")


def _add(res: MaskResult, kind: str, original: str, placeholder: str) -> None:
    res.replacements.append({"kind": kind, "original": original.strip(), "placeholder": placeholder})


def _replace_known(text: str, value: Optional[str], placeholder: str, kind: str, res: MaskResult) -> str:
    """Заменяет все вхождения известного значения (без учёта регистра и разных пробелов)."""
    v = (value or "").strip().strip(" .,;")
    if len(v) < 3:
        return text
    pattern = re.escape(v)
    pattern = pattern.replace(r"\ ", r"\s+")
    new_text, n = re.subn(pattern, placeholder, text, flags=re.IGNORECASE)
    if n:
        _add(res, kind, v, placeholder)
    # Для организаций заменяем и «ядро» названия в кавычках: ООО «Альфа» -> Альфа
    core = re.search(r"[«\"]([^»\"]{3,60})[»\"]", v)
    if core and kind in ("заказчик", "подрядчик"):
        core_txt = core.group(1).strip()
        new_text, n2 = re.subn(
            r"(?<![А-ЯЁа-яёA-Za-z0-9])" + re.escape(core_txt).replace(r"\ ", r"\s+") + r"(?![А-ЯЁа-яёA-Za-z0-9])",
            placeholder,
            new_text,
            flags=re.IGNORECASE,
        )
        if n2:
            _add(res, kind, core_txt, placeholder)
    return new_text


def _sub_with_report(pattern: "re.Pattern[str]", placeholder: str, kind: str, text: str, res: MaskResult) -> str:
    def _repl(m: "re.Match[str]") -> str:
        _add(res, kind, m.group(0), placeholder)
        return placeholder

    return pattern.sub(_repl, text)


def mask_for_ai(
    raw_text: str,
    customer: str = "",
    contractor: str = "",
    contract_number: str = "",
    contract_date: str = "",
    object_name: str = "",
) -> MaskResult:
    """Возвращает текст ТЗ с заменёнными чувствительными данными и список замен."""
    res = MaskResult(text=raw_text or "")
    text = res.text

    # 1. Подписи — первыми, пока рядом ещё стоят названия организаций и ФИО
    text = _sub_with_report(_SIGNATURE_BLOCK, "[БЛОК ПОДПИСИ]", "подпись", text, res)

    # 2. Значения, найденные локальным парсером
    text = _replace_known(text, customer, "[ЗАКАЗЧИК]", "заказчик", res)
    text = _replace_known(text, contractor, "[ПОДРЯДЧИК]", "подрядчик", res)
    text = _replace_known(text, contract_number, "[НОМЕР ДОГОВОРА]", "договор", res)
    text = _replace_known(text, contract_date, "[ДАТА ДОГОВОРА]", "договор", res)
    text = _replace_known(text, object_name, "[ОБЪЕКТ]", "объект", res)
    # Короткие обозначения объекта в иных написаниях: «ТЭЦ1» -> «ТЭЦ-1», «ТЭЦ 1»
    for tok in re.findall(r"[А-ЯЁA-Zа-яёa-z]{2,}\d+", object_name or ""):
        letters, digits = re.match(r"([А-ЯЁA-Zа-яёa-z]+)(\d+)", tok).groups()
        variant = re.compile(re.escape(letters) + r"[-\s]?" + re.escape(digits) + r"(?!\d)", re.IGNORECASE)
        text = _sub_with_report(variant, "[ОБЪЕКТ]", "объект", text, res)

    # 3. Организации по форме собственности, не найденные парсером («ООО «Ромашка»»)
    org_pattern = re.compile(rf"{_ORG_FORMS}\s*[«\"][^»\"\n]{{2,80}}[»\"]")
    text = _sub_with_report(org_pattern, "[ОРГАНИЗАЦИЯ]", "организация", text, res)

    # 4. Реквизиты
    def _bank_repl(m: "re.Match[str]") -> str:
        _add(res, "реквизиты", m.group(0), f"{m.group('label')} [СКРЫТО]")
        return f"{m.group('label')} [СКРЫТО]"

    text = _BANK_LABELED.sub(_bank_repl, text)
    text = _sub_with_report(_ACCOUNT_20, "[СЧЁТ]", "реквизиты", text, res)
    text = _sub_with_report(_EMAIL, "[EMAIL]", "email", text, res)
    text = _sub_with_report(_PHONE, "[ТЕЛЕФОН]", "телефон", text, res)

    # 5. Адреса (город и регион остаются)
    text = _sub_with_report(_ADDRESS, "[АДРЕС]", "адрес", text, res)
    text = _sub_with_report(_POSTAL_INDEX, "[ИНДЕКС]", "адрес", text, res)

    # 6. ФИО
    text = _sub_with_report(_FIO_FULL, "[ФИО]", "фио", text, res)
    text = _sub_with_report(_FIO_INITIALS_FIRST, "[ФИО]", "фио", text, res)
    text = _sub_with_report(_FIO_SURNAME_FIRST, "[ФИО]", "фио", text, res)

    res.text = text
    return res
