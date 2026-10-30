"""
Тесты этапа А: локальный парсер ТЗ («только РД»), график и восстановленный модуль сметы.
Запуск: python -m pytest tests -q
"""
import io
import os
import re

import pytest

from app.models import CalculationMethod, CollectionQuoteItem, KPRequest, KPStage
from app.services.cost_estimator import init_cost_parameters, recalculate_cost_parameters
from app.services.estimate_excel_generator import generate_estimate_excel
from app.services.kp_generator import generate_kp_docx
from app.services.pp87_rules import build_schedule
from app.services.tz_parser import parse_tz_content, parse_tz_table_fields

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _tz_tec1() -> str:
    with open(os.path.join(FIXTURES, "tz_tec1_rd_only.txt"), encoding="utf-8") as f:
        return f.read()


def _selected(project, stage):
    return sorted({s.code_mark for s in project.sections if s.enabled and s.id.startswith(stage)})


# ---------------------------------------------------------------------------
# Парсер: реальное ТЗ ТЭЦ-1 (только РД)
# ---------------------------------------------------------------------------

def test_tec1_only_rd_stage():
    project, _ = parse_tz_content(_tz_tec1(), "local")
    assert project.has_rd is True
    assert project.has_pd is False
    assert _selected(project, "pd") == []
    assert _selected(project, "rd") == ["АС", "КМ"]


def test_tec1_requisites():
    project, _ = parse_tz_content(_tz_tec1(), "local")
    assert project.object_name == "ТЭЦ1 г. Тюмень"
    assert project.customer == "ООО «Альфа»"
    assert project.contractor == "ООО «Бета»"
    assert project.contract_number == "10БТ0726"
    assert project.contract_date.startswith("15.07.2026")
    assert "Задание" not in project.contract_date


def test_tec1_schedule_does_not_crash_for_rd_only():
    project, _ = parse_tz_content(_tz_tec1(), "local")
    phases = build_schedule(project)
    assert len(phases) > 0
    names = " ".join(p.name for p in phases)
    assert "Разработка проектной документации" not in names


def test_table_row_without_number_is_accepted():
    text = "Заказчик\tООО «А»\n2\tПодрядчик\tООО «Б»\n"
    fields = parse_tz_table_fields(text)
    assert fields["customer"] == "ООО «А»"
    assert fields["contractor"] == "ООО «Б»"


def test_no_table_gives_empty_fields():
    assert parse_tz_table_fields("просто текст без таблицы") == {}


def test_distance_km_is_not_mark_km():
    from app.services.tz_parser import RD_MARK_PATTERNS

    def hits(text):
        return any(re.search(p, text.lower()) for p in RD_MARK_PATTERNS["rd_km"][:1])

    assert not hits("расстояние до площадки 5 км")
    assert not hits("длина трассы 12км")
    assert hits("разработать раздел КМ")


# ---------------------------------------------------------------------------
# Регрессия: меняем в реальном ТЗ только строку «Стадийность»
# ---------------------------------------------------------------------------

_STAGE_ROW = "6\tСтадийность проектирования\tРабочая документация"


def _with_stage(value):
    text = _tz_tec1()
    assert _STAGE_ROW in text
    project, _ = parse_tz_content(text.replace(_STAGE_ROW, "6\tСтадийность проектирования\t" + value), "local")
    return project


@pytest.mark.parametrize(
    "value",
    [
        "Проектная и рабочая документация",
        "Проектная документация и рабочая документация",
        "Проектная документация, рабочая документация",
    ],
)
def test_regression_pd_and_rd(value):
    project = _with_stage(value)
    assert project.has_pd is True
    assert project.has_rd is True
    assert len(build_schedule(project)) > 0


def test_regression_only_pd():
    project = _with_stage("Проектная документация")
    assert project.has_pd is True
    assert project.has_rd is False
    assert len(build_schedule(project)) > 0


def test_rd_based_on_existing_pd_stays_rd_only():
    project = _with_stage("Рабочая документация на основании ранее разработанной проектной документации")
    assert project.has_rd is True
    assert project.has_pd is False


# ---------------------------------------------------------------------------
# Смета: никаких скрытых сумм и подстановок
# ---------------------------------------------------------------------------

@pytest.fixture()
def tec1_cost():
    project, _ = parse_tz_content(_tz_tec1(), "local")
    project.cost_parameters = init_cost_parameters(project)
    return project


def test_cost_has_no_hidden_default_sum(tec1_cost):
    cp = tec1_cost.cost_parameters
    assert cp.collection_items == []
    assert cp.target_total_cost_net == 0
    assert cp.total_cost_net_rub == 0
    assert cp.total_cost_gross_rub == 0
    assert any("X" in w or "позиц" in w for w in cp.warnings)


def test_default_vat_is_5_percent(tec1_cost):
    cp = tec1_cost.cost_parameters
    assert cp.include_vat is True
    assert cp.vat_rate == 5.0


def test_item_without_x_is_zero_with_warning(tec1_cost):
    cp = tec1_cost.cost_parameters
    cp.collection_items.append(
        CollectionQuoteItem(row_id="r1", collection_id="mnz_848pr", item_id="848pr_t3_1_p2", x_value=0)
    )
    recalculate_cost_parameters(cp, has_pd=False, has_rd=True)
    item = cp.collection_items[0]
    assert item.current_cost_rub == 0
    assert "X" in item.warning
    assert cp.total_cost_net_rub == 0
    assert cp.warnings


def test_unknown_collection_is_not_substituted(tec1_cost):
    cp = tec1_cost.cost_parameters
    cp.collection_items.append(
        CollectionQuoteItem(row_id="r1", collection_id="no_such_collection", item_id="x", x_value=100)
    )
    recalculate_cost_parameters(cp, has_pd=False, has_rd=True)
    item = cp.collection_items[0]
    assert item.current_cost_rub == 0
    assert item.collection_id == "no_such_collection"
    assert "не найден" in item.warning


def test_unknown_item_is_not_substituted(tec1_cost):
    cp = tec1_cost.cost_parameters
    cp.collection_items.append(
        CollectionQuoteItem(row_id="r1", collection_id="mnz_848pr", item_id="no_such_item", x_value=100)
    )
    recalculate_cost_parameters(cp, has_pd=False, has_rd=True)
    item = cp.collection_items[0]
    assert item.current_cost_rub == 0
    assert item.item_id == "no_such_item"
    assert "не найдена" in item.warning


def _with_manual_item(project, vat_rate, include_vat=True):
    cp = project.cost_parameters
    cp.collection_items = [
        CollectionQuoteItem(
            row_id="r1", collection_id="mnz_848pr", item_id="848pr_t3_1_p2",
            x_value=1500.0, stage_mode="rd",
        )
    ]
    cp.vat_rate = vat_rate
    cp.include_vat = include_vat
    recalculate_cost_parameters(cp, has_pd=project.has_pd, has_rd=project.has_rd)
    return cp


def test_manual_x_gives_cost_and_no_warning(tec1_cost):
    cp = _with_manual_item(tec1_cost, 5.0)
    assert cp.collection_items[0].current_cost_rub > 0
    assert cp.collection_items[0].warning == ""
    assert cp.total_cost_net_rub == pytest.approx(cp.collections_total_net_rub)


@pytest.mark.parametrize("rate", [5.0, 22.0])
def test_vat_rates(tec1_cost, rate):
    cp = _with_manual_item(tec1_cost, rate)
    assert cp.vat_rub == pytest.approx(round(cp.total_cost_net_rub * rate / 100, 2))
    assert cp.total_cost_gross_rub == pytest.approx(cp.total_cost_net_rub + cp.vat_rub)


def test_vat_zero_means_no_vat(tec1_cost):
    cp = _with_manual_item(tec1_cost, 0.0, include_vat=False)
    assert cp.vat_rub == 0
    assert cp.total_cost_gross_rub == cp.total_cost_net_rub


def test_three_methods_are_independent(tec1_cost):
    cp = _with_manual_item(tec1_cost, 5.0)
    results = {}
    for method in (CalculationMethod.BY_COLLECTIONS, CalculationMethod.LABOR_707, CalculationMethod.LABOR_INTERNAL):
        cp.calculation_method = method
        recalculate_cost_parameters(cp, has_pd=False, has_rd=True)
        results[method] = cp.pir_only_cost_net_rub
    assert results[CalculationMethod.LABOR_707] > 0
    assert results[CalculationMethod.LABOR_INTERNAL] > 0
    assert cp.collections_total_net_rub > 0
    # расчёт по сборникам не подгоняется под трудозатраты
    assert results[CalculationMethod.BY_COLLECTIONS] == pytest.approx(cp.collections_total_net_rub)


def test_empty_collections_do_not_fall_back_to_target_sum(tec1_cost):
    cp = tec1_cost.cost_parameters
    cp.calculation_method = CalculationMethod.BY_COLLECTIONS
    cp.target_total_cost_net = 5_000_000.0  # даже если пользователь где-то задал цель
    recalculate_cost_parameters(cp, has_pd=False, has_rd=True)
    assert cp.pir_only_cost_net_rub == 0


def test_from_smr_without_smr_is_zero_with_warning(tec1_cost):
    cp = tec1_cost.cost_parameters
    cp.calculation_method = CalculationMethod.FROM_SMR
    cp.smr_cost_mln_rub = 0.0
    recalculate_cost_parameters(cp, has_pd=False, has_rd=True)
    assert cp.pir_only_cost_net_rub == 0
    assert any("СМР" in w for w in cp.warnings)


# ---------------------------------------------------------------------------
# Excel и КП
# ---------------------------------------------------------------------------

def test_estimate_excel_builds_with_warning(tec1_cost):
    stream = generate_estimate_excel(tec1_cost)
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(stream.getvalue()))
    text = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value)
    assert "ВНИМАНИЕ" in text


def test_estimate_excel_builds_with_items(tec1_cost):
    _with_manual_item(tec1_cost, 22.0)
    stream = generate_estimate_excel(tec1_cost)
    assert len(stream.getvalue()) > 5000


def test_kp_for_rd_only(tec1_cost):
    _with_manual_item(tec1_cost, 22.0)
    req = KPRequest(project=tec1_cost, stage=KPStage.RD)
    stream = generate_kp_docx(req)
    assert len(stream.getvalue()) > 5000
