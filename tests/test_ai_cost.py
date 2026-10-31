"""Тесты этапа Б: подбор позиций и значений X через нейросеть (нейросеть подменена заглушкой)."""
import os

import pytest

from app.models import CollectionQuoteItem
from app.services import ai_cost
from app.services.cost_estimator import init_cost_parameters, recalculate_cost_parameters
from app.services.normative_catalog import ensure_catalog_file
from app.services.tz_parser import parse_tz_content

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

TZ = """1\tЗаказчик\tООО «Альфа»
2\tПодрядчик\tООО «Бета»
3\tОбъект\tКотельная «Северная»
4\tСтадийность проектирования\tРабочая документация
5\tСостав\tРаздел АС, раздел КМ
Площадь здания модульной котельной 1 250 м2. Протяжённость сетей 3,5 км. Производительность 50 000 м3/сутки.
"""


@pytest.fixture()
def project():
    p, _ = parse_tz_content(TZ, "local")
    p.tz_text = TZ
    p.cost_parameters = init_cost_parameters(p)
    return p


@pytest.fixture()
def catalog():
    return ensure_catalog_file()


def _item_with_unit(catalog, unit_substr):
    for col in catalog["collections"]:
        for it in col["items"]:
            if unit_substr in it.get("unit", "") and it.get("intervals"):
                return col, it
    raise AssertionError(unit_substr)


# --- запрос 1 ---------------------------------------------------------------

def test_suggest_creates_rows_only_for_real_catalog_items(monkeypatch, project, catalog):
    col, it = _item_with_unit(catalog, "м2")
    sent = {}

    def fake(system, user, required_key, **kw):
        sent["user"] = user
        return {
            "objects": [
                {"description": "Здание модульной котельной", "item_id": it["id"], "reason": "по площади"},
                {"description": "Защитные габионные стены", "item_id": None, "reason": "нет в справочнике"},
                {"description": "Выдуманный объект", "item_id": "no_such_id", "reason": "?"},
            ],
            "note": "",
        }, None

    monkeypatch.setattr(ai_cost, "query_llm_json", fake)
    items, notes, err = ai_cost.suggest_collection_items(project, catalog)
    assert err is None
    assert len(items) == 1
    row = items[0]
    assert row.item_id == it["id"] and row.collection_id == col["id"]
    assert row.x_value == 0 and row.needs_ai is True
    assert row.source_description == "Здание модульной котельной"
    text = " ".join(notes)
    assert "Защитные габионные стены" in text  # нет подходящей позиции: явное сообщение
    assert "no_such_id" in text                 # несуществующий id отклонён
    # в нейросеть ушёл замаскированный текст
    assert "Альфа" not in sent["user"] and "Бета" not in sent["user"] and "Северная" not in sent["user"]


def test_suggest_skips_duplicates(monkeypatch, project, catalog):
    _col, it = _item_with_unit(catalog, "м2")
    fake = lambda *a, **k: ({"objects": [{"description": "Котельная", "item_id": it["id"], "reason": "x"}], "note": ""}, None)
    monkeypatch.setattr(ai_cost, "query_llm_json", fake)
    items, _, _ = ai_cost.suggest_collection_items(project, catalog)
    project.cost_parameters.collection_items.extend(items)
    items2, _, _ = ai_cost.suggest_collection_items(project, catalog)
    assert items2 == []


def test_suggest_reports_llm_error(monkeypatch, project, catalog):
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda *a, **k: (None, "нет ключа"))
    items, notes, err = ai_cost.suggest_collection_items(project, catalog)
    assert items == [] and err == "нет ключа"


# --- запрос 2 ---------------------------------------------------------------

def _row(project, catalog, unit_substr="м2", **kw):
    col, it = _item_with_unit(catalog, unit_substr)
    row = CollectionQuoteItem(
        row_id=kw.pop("row_id", "r1"), collection_id=col["id"], item_id=it["id"],
        source_description="Здание модульной котельной", needs_ai=True, **kw,
    )
    project.cost_parameters.collection_items.append(row)
    return row, it


def test_fill_x_found_with_conversion(monkeypatch, project, catalog):
    row, it = _row(project, catalog)
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda *a, **k: ({"values": [{
        "row_id": "r1", "found": True, "original_value": 1250, "original_unit": "м2",
        "converted_value": 1250, "conversion": "единицы совпадают", "quote": "Площадь здания модульной котельной 1 250 м2",
    }]}, None))
    done, notes, err = ai_cost.fill_x_values(project, catalog)
    assert err is None and done == 1
    assert row.x_value == 1250 and row.x_source == "ai" and row.needs_ai is False
    assert "Цитата" in row.x_note


def test_fill_x_unit_conversion(monkeypatch, project, catalog):
    row, it = _row(project, catalog, unit_substr="тыс. м3/сут")
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda *a, **k: ({"values": [{
        "row_id": "r1", "found": True, "original_value": 50000, "original_unit": "м3/сутки",
        "converted_value": 50, "conversion": "50 000 м3/сут = 50 тыс. м3/сут", "quote": "Производительность 50 000 м3/сутки",
    }]}, None))
    ai_cost.fill_x_values(project, catalog)
    assert row.x_value == 50 and row.x_source == "ai"
    assert "50 000" in row.x_note


def test_fill_x_hallucinated_number_is_rejected(monkeypatch, project, catalog):
    row, it = _row(project, catalog)
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda *a, **k: ({"values": [{
        "row_id": "r1", "found": True, "original_value": 7777, "original_unit": "м2", "converted_value": 7777,
        "conversion": "", "quote": "выдумка",
    }]}, None))
    ai_cost.fill_x_values(project, catalog)
    xmin = ai_cost.min_x_for_item(*_pair(catalog, it["id"]))
    assert row.x_source == "min_default" and row.x_value == xmin
    assert "не найдено в тексте" in row.x_note


def _pair(catalog, item_id):
    return ai_cost.catalog_index(catalog)[item_id]


def test_fill_x_not_found_uses_min_with_warning(monkeypatch, project, catalog):
    row, it = _row(project, catalog)
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda *a, **k: ({"values": [{"row_id": "r1", "found": False}]}, None))
    done, notes, err = ai_cost.fill_x_values(project, catalog)
    xmin = ai_cost.min_x_for_item(*_pair(catalog, it["id"]))
    assert row.x_value == xmin and row.x_source == "min_default" and row.needs_ai is False
    assert "не указаны в ТЗ" in row.x_note and "уточните у заказчика" in row.x_note
    recalculate_cost_parameters(project.cost_parameters, has_pd=project.has_pd, has_rd=project.has_rd)
    assert any("минимальное значение" in w and "уточните у заказчика" in w for w in project.cost_parameters.warnings)
    assert row.current_cost_rub > 0


def test_manual_and_confirmed_rows_are_not_requested(monkeypatch, project, catalog):
    manual, _ = _row(project, catalog, row_id="m", x_value=500.0, x_source="manual")
    manual.needs_ai = False
    confirmed, _ = _row(project, catalog, row_id="c", x_value=900.0, x_source="ai")
    confirmed.needs_ai = False
    calls = []
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda *a, **k: calls.append(1) or ({"values": []}, None))
    done, notes, err = ai_cost.fill_x_values(project, catalog)
    assert done == 0 and calls == []  # запрос вообще не отправлялся
    assert manual.x_value == 500.0 and confirmed.x_value == 900.0


def test_changed_row_requested_again_but_manual_x_survives(monkeypatch, project, catalog):
    row, _ = _row(project, catalog, row_id="a", x_value=10.0, x_source="manual")
    row.needs_ai = False
    other, _ = _row(project, catalog, row_id="b")
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda s, u, **k: ({"values": [{"row_id": "b", "found": False}]}, None))
    done, _, _ = ai_cost.fill_x_values(project, catalog)
    assert done == 1 and row.x_value == 10.0 and other.x_source == "min_default"


def test_sent_text_is_masked_for_x_query(monkeypatch, project, catalog):
    _row(project, catalog)
    seen = {}
    monkeypatch.setattr(ai_cost, "query_llm_json", lambda s, u, **k: seen.update(u=u) or ({"values": []}, None))
    ai_cost.fill_x_values(project, catalog)
    assert "Альфа" not in seen["u"] and "Бета" not in seen["u"]


def test_number_in_text_formats():
    t = "Производительность 50 000 м3/сутки, площадь 1 250,5 м2, высота 3,0м"
    assert ai_cost.number_in_text(50000, t)
    assert ai_cost.number_in_text(1250.5, t)
    assert ai_cost.number_in_text(3, t)
    assert not ai_cost.number_in_text(5000, t)
    assert not ai_cost.number_in_text(25, "125 и 2500")


def test_unset_x_without_ai_is_still_zero_with_warning(project):
    row = CollectionQuoteItem(row_id="z", collection_id="mnz_848pr", item_id="848pr_t3_1_p2", needs_ai=True)
    project.cost_parameters.collection_items.append(row)
    recalculate_cost_parameters(project.cost_parameters, has_pd=project.has_pd, has_rd=project.has_rd)
    assert row.current_cost_rub == 0
    assert any("ещё не определено" in w for w in project.cost_parameters.warnings)
