"""Тесты маскирования данных перед отправкой ТЗ в нейросеть. Все данные вымышленные."""
import os

import pytest

from app.services import tz_parser
from app.services.masking import mask_for_ai
from app.services.tz_parser import parse_tz_content

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

SAMPLE = """Заказчик\tООО «Ромашка»
Объект\tСтроительство школы на 500 мест в г. Тюмень
Адрес: 625000, г. Тюмень, ул. Республики, д. 12, офис 304
ИНН 7203123456, КПП 720301001, ОГРН 1027200000000
Р/с 40702810900000000001 в ПАО «Банк», БИК 047102651, к/с 30101810100000000001
Контакты: +7 (3452) 12-34-56, 8-912-345-67-89, info@romashka.example, тел. (3452) 55-66-77
Ответственный: Иванов И.И., И.И. Иванов, Петров Пётр Петрович.
Проезд пожарной техники предусмотреть со стороны улицы; ширина проездов 4,2 м.
Генеральный директор
ООО «Ромашка»
_____________ А.А. Сидоров
М.П.
"""


def _mask(text=SAMPLE, **kw):
    kw.setdefault("customer", "ООО «Ромашка»")
    return mask_for_ai(text, **kw)


@pytest.mark.parametrize(
    "secret",
    [
        "Ромашка", "7203123456", "720301001", "1027200000000", "40702810900000000001", "047102651",
        "30101810100000000001", "12-34-56", "345-67-89", "info@romashka.example", "55-66-77",
        "Иванов", "Петров", "Сидоров", "Республики", "625000",
    ],
)
def test_secrets_are_removed(secret):
    assert secret not in _mask().text


def test_city_and_task_content_are_kept():
    text = _mask(object_name="Строительство школы на 500 мест в г. Тюмень").text
    assert "Проезд пожарной техники" in text  # слово «проезд» не считается адресом
    assert "ширина проездов 4,2 м" in text
    text2 = _mask().text
    assert "г. Тюмень" in text2  # город остаётся


def test_known_values_use_placeholders():
    res = mask_for_ai(
        "Договор № 77-А/26 от 01.02.2026 г. Подрядчик ООО «Берёзка». Объект: Котельная «Северная».",
        contractor="ООО «Берёзка»", contract_number="77-А/26", contract_date="01.02.2026", object_name="Котельная «Северная»",
    )
    for placeholder in ("[ПОДРЯДЧИК]", "[НОМЕР ДОГОВОРА]", "[ДАТА ДОГОВОРА]", "[ОБЪЕКТ]"):
        assert placeholder in res.text
    assert "Берёзка" not in res.text and "77-А/26" not in res.text and "Северная" not in res.text


def test_object_abbreviation_variants_masked():
    res = mask_for_ai("На территории ТЭЦ-1 и ТЭЦ 1 расположены...", object_name="ТЭЦ1 г. Тюмень")
    assert "ТЭЦ-1" not in res.text and "ТЭЦ 1" not in res.text


def test_replacements_report_and_summary():
    res = _mask()
    kinds = res.summary()
    assert kinds.get("фио", 0) >= 3
    assert kinds.get("email") == 1
    assert kinds.get("телефон", 0) >= 3
    assert all({"kind", "original", "placeholder"} <= set(r) for r in res.replacements)


def test_empty_and_plain_text_do_not_break():
    assert mask_for_ai("").text == ""
    plain = "Разработать раздел АС и КМ для площадки хранения масла."
    assert mask_for_ai(plain).text == plain


def test_technical_text_is_not_damaged():
    tech = "СП 542.1325800.2024. ГОСТ Р 21.101-2020. Стена из габионов высотой 3,0м. ГРП №1,2; ППГ, ДКС №1, 2."
    assert mask_for_ai(tech).text == tech


# ---------------------------------------------------------------------------
# Что реально уходит в нейросеть
# ---------------------------------------------------------------------------

def test_ai_path_sends_only_masked_text_and_ignores_identity_from_ai(monkeypatch):
    with open(os.path.join(FIXTURES, "tz_tec1_rd_only.txt"), encoding="utf-8") as f:
        raw = f.read()
    sent = {}

    def fake_llm(text, model_name=None):
        sent["text"] = text
        return {
            "has_pd": False, "has_rd": True, "composition_preset": "tz", "pd_sections": [], "rd_marks": ["rd_as", "rd_km"],
            "facility_type": "capital", "has_surveys": False, "has_expertise": False,
            # даже если нейросеть вернёт реквизиты, мы их не используем
            "object_name": "ВЫДУМАННЫЙ ОБЪЕКТ", "customer": "ООО «Выдумка»", "contractor": "ООО «Фантазия»",
            "contract_number": "000", "contract_date": "01.01.2000", "explanation": "тест",
        }, None

    monkeypatch.setattr(tz_parser, "query_llm_tz_analysis", fake_llm)
    project, _ = parse_tz_content(raw, engine="ai")

    for secret in ("Альфа", "Бета", "10БТ0726", "15.07.2026", "Иванов", "Петрова", "ТЭЦ1"):
        assert secret not in sent["text"], secret
    assert "[ЗАКАЗЧИК]" in sent["text"] and "[ОБЪЕКТ]" in sent["text"]
    assert project.customer == "ООО «Альфа»"
    assert project.contractor == "ООО «Бета»"
    assert project.object_name == "ТЭЦ1 г. Тюмень"
    assert project.contract_number == "10БТ0726"
    assert project.has_rd is True and project.has_pd is False


def test_prompt_does_not_ask_for_identity_fields():
    from app.services.llm_parser import SYSTEM_PROMPT

    for field in ('"customer"', '"contractor"', '"contract_number"', '"object_name"'):
        assert field not in SYSTEM_PROMPT


@pytest.mark.parametrize("answer,expected", [(False, False), (True, True), (None, True)])
def test_ai_expertise_flags_follow_ai_answer(monkeypatch, answer, expected):
    from app.services.pp87_rules import build_schedule

    with open(os.path.join(FIXTURES, "tz_tec1_rd_only.txt"), encoding="utf-8") as f:
        raw = f.read()
    result = {"has_pd": False, "has_rd": True, "composition_preset": "tz", "pd_sections": [], "rd_marks": ["rd_as", "rd_km"],
              "facility_type": "capital", "has_surveys": False}
    if answer is not None:
        result["has_expertise"] = answer
    monkeypatch.setattr(tz_parser, "query_llm_tz_analysis", lambda text, model_name=None: (dict(result), None))
    project, _ = parse_tz_content(raw, engine="ai")
    assert project.schedule_flags["expertise"] is expected
    assert project.schedule_flags["internal_expertise"] is expected
    assert len(build_schedule(project)) > 0  # график строится при любом значении флагов
