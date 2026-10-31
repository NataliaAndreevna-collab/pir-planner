"""
Этап Б: подбор позиций сборников и параметров X по тексту ТЗ с помощью нейросети.

Принципы:
  * в нейросеть уходит только замаскированный текст (app/services/masking.py);
  * ИИ ничего не считает и не придумывает: он указывает позицию справочника и число, которое ДОСЛОВНО есть в ТЗ;
    число проверяется по тексту ТЗ, выдуманное значение отбрасывается;
  * если в справочнике нет подходящей позиции или в ТЗ нет значения X, об этом явно сообщается
    (для X берётся минимальное значение таблицы с пометкой «уточните у заказчика»);
  * результат всегда проверяет и может исправить человек; ручные значения повторно не запрашиваются.
"""
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.models import CollectionQuoteItem, ProjectData
from app.services.llm_parser import query_llm_json
from app.services.masking import mask_for_ai

SUGGEST_PROMPT = """Ты опытный главный инженер проекта (ГИП) в РФ. По тексту технического задания (ТЗ) определи объекты и сооружения,
для которых разрабатывается документация, и для каждого выбери НАИБОЛЕЕ ПОДХОДЯЩУЮ позицию из справочника базовых цен.

Правила:
1. В «объекты» включай только то, что проектируется по ТЗ, а не всё, что упоминается в тексте (например, ссылки на нормы, соседние объекты).
2. item_id бери ТОЛЬКО из списка справочника ниже, строго как написано. Ничего не придумывай и не меняй.
3. Если подходящей позиции в справочнике нет, верни item_id = null. Не подставляй «ближайшую» позицию, если по смыслу она не подходит.
4. Одна позиция справочника может подходить нескольким объектам: тогда верни по записи на каждый объект.
5. В description дай краткое описание объекта из ТЗ (без названий организаций и фамилий), в reason — одно предложение, почему выбрана позиция.
6. В тексте реквизиты заменены метками ([ЗАКАЗЧИК], [ОБЪЕКТ] и т.п.): не пытайся их восстанавливать.

Ответ — ТОЛЬКО JSON без пояснений и без ```:
{"objects": [{"description": "...", "item_id": "id или null", "reason": "..."}], "note": "общее замечание или пустая строка"}
"""

X_PROMPT = """Ты опытный главный инженер проекта (ГИП). Для каждой строки найди в тексте технического задания (ТЗ) значение параметра, который
нужен для расчёта по таблице справочника (название таблицы и единица измерения даны).

Правила:
1. Используй ТОЛЬКО числа, которые есть в тексте ТЗ. Ничего не оценивай, не округляй и не вычисляй из общих соображений.
2. Если в ТЗ значение указано в другой единице, переведи в единицу таблицы и опиши перевод в поле conversion (например: «50 000 м3/сут = 50 тыс. м3/сут»).
3. Если значения для этого объекта в ТЗ нет, верни found = false. Это нормальный ответ, не угадывай.
4. original_value — число так, как оно записано в ТЗ; original_unit — его единица; quote — короткая дословная цитата из ТЗ (до 200 символов).
5. В тексте реквизиты заменены метками: не пытайся их восстанавливать.

Ответ — ТОЛЬКО JSON без пояснений и без ```:
{"values": [{"row_id": "...", "found": true или false, "original_value": число или null, "original_unit": "...", "converted_value": число или null, "conversion": "...", "quote": "..."}]}
"""


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def masked_tz_text(project: ProjectData) -> str:
    """Текст ТЗ проекта с замаскированными реквизитами (то, что можно отправлять в нейросеть)."""
    return mask_for_ai(
        project.tz_text or "",
        customer=project.customer,
        contractor=project.contractor,
        contract_number=project.contract_number,
        contract_date=project.contract_date,
        object_name=project.object_name,
    ).text


def catalog_index(catalog: Dict[str, Any]) -> Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]]:
    """item_id -> (сборник, позиция)."""
    out: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    for col in catalog.get("collections", []):
        for it in col.get("items", []):
            out[it["id"]] = (col, it)
    return out


def catalog_brief(catalog: Dict[str, Any]) -> str:
    """Компактный список позиций справочника для запроса: id | название | единица."""
    lines: List[str] = []
    for col in catalog.get("collections", []):
        lines.append(f"# Сборник {col.get('code', col['id'])}")
        for it in col.get("items", []):
            lines.append(f"{it['id']} | {it.get('name', '')} | {it.get('unit', '')}")
    return "\n".join(lines)


def _normalize_text_for_numbers(text: str) -> str:
    t = text.replace(" ", " ").replace(" ", " ")
    t = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", t)  # «50 000» -> «50000»
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)          # «3,0» -> «3.0»
    return t


def number_in_text(value: float, text: str) -> bool:
    """Проверяет, что число действительно встречается в тексте (защита от выдуманных значений)."""
    norm = _normalize_text_for_numbers(text)
    cands = {f"{value:g}", f"{value:.3f}".rstrip("0").rstrip("."), f"{value:.2f}".rstrip("0").rstrip(".")}
    if float(value).is_integer():
        cands.add(str(int(value)))
    for c in cands:
        if c and re.search(r"(?<![\d.])" + re.escape(c) + r"(?!\d)", norm):
            return True
    return False


def min_x_for_item(col: Dict[str, Any], item: Dict[str, Any]) -> Optional[float]:
    """Минимальное значение X нижнего интервала таблицы (для случая «в ТЗ не указано»)."""
    ivs = item.get("intervals") or item.get("report_intervals") or []
    if ivs:
        try:
            return float(ivs[0]["x_min"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _stage_mode(project: ProjectData) -> str:
    if project.has_pd and project.has_rd:
        return "pd_rd"
    return "rd" if project.has_rd else "pd"


# ---------------------------------------------------------------------------
# Запрос 1: объекты из ТЗ -> позиции справочника
# ---------------------------------------------------------------------------

def suggest_collection_items(
    project: ProjectData, catalog: Dict[str, Any]
) -> Tuple[List[CollectionQuoteItem], List[str], Optional[str]]:
    """
    Возвращает (новые строки без X, заметки для пользователя, ошибка).
    Строки создаются только для позиций, реально существующих в справочнике.
    """
    text = masked_tz_text(project)
    if not text.strip():
        return [], [], "В проекте нет текста ТЗ: загрузите ТЗ заново и повторите."
    idx = catalog_index(catalog)
    user_message = (
        f"Справочник позиций (id | название | единица):\n{catalog_brief(catalog)}\n\n"
        f"Текст ТЗ:\n{text[:20000]}\n\nВерни JSON строго по инструкции."
    )
    result, err = query_llm_json(SUGGEST_PROMPT, user_message, required_key="objects", max_tokens=3000)
    if not result:
        return [], [], err or "Нейросеть не вернула результат"

    existing = {(r.item_id, (r.source_description or "").strip().lower()) for r in (project.cost_parameters.collection_items if project.cost_parameters else [])}
    stamp = int(time.time())
    new_items: List[CollectionQuoteItem] = []
    notes: List[str] = []
    if result.get("note"):
        notes.append(f"Замечание ИИ: {str(result['note']).strip()}")

    for n, obj in enumerate(result.get("objects") or [], 1):
        if not isinstance(obj, dict):
            continue
        desc = str(obj.get("description") or "").strip()
        item_id = obj.get("item_id")
        if not item_id or item_id not in idx:
            if item_id and item_id not in idx:
                notes.append(f"ИИ указал несуществующую позицию «{item_id}» для «{desc}» — отклонено, выберите вручную.")
            else:
                notes.append(f"В справочнике нет подходящей позиции для: «{desc}». Добавьте позицию вручную, если она нужна.")
            continue
        if (item_id, desc.lower()) in existing:
            continue
        col, _it = idx[item_id]
        new_items.append(
            CollectionQuoteItem(
                row_id=f"ai_{stamp}_{n}",
                collection_id=col["id"],
                item_id=item_id,
                x_value=0.0,
                stage_mode=_stage_mode(project),
                completeness_pct=100.0,
                source_description=desc,
                ai_reason=str(obj.get("reason") or "").strip(),
                needs_ai=True,
            )
        )
        existing.add((item_id, desc.lower()))
    return new_items, notes, None


# ---------------------------------------------------------------------------
# Запрос 2: значение X для строк, где оно ещё не определено
# ---------------------------------------------------------------------------

def fill_x_values(project: ProjectData, catalog: Dict[str, Any]) -> Tuple[int, List[str], Optional[str]]:
    """
    Определяет X для строк с needs_ai (не трогает значения, введённые вручную).
    Возвращает (число обработанных строк, заметки, ошибка).
    """
    cp = project.cost_parameters
    if not cp:
        return 0, [], None
    idx = catalog_index(catalog)
    todo = [r for r in cp.collection_items if r.enabled and r.needs_ai and r.x_source != "manual"]
    if not todo:
        return 0, ["Нет строк, для которых требуется запрос: все значения уже подтверждены или введены вручную."], None

    text = masked_tz_text(project)
    if not text.strip():
        return 0, [], "В проекте нет текста ТЗ: загрузите ТЗ заново и повторите."

    rows_payload = []
    for r in todo:
        pair = idx.get(r.item_id)
        if not pair:
            continue
        _col, it = pair
        rows_payload.append(
            {
                "row_id": r.row_id,
                "object": r.source_description or r.custom_name or it.get("name", ""),
                "table": it.get("name", ""),
                "unit": it.get("unit", ""),
            }
        )
    import json as _json

    user_message = (
        f"Строки для поиска значений:\n{_json.dumps(rows_payload, ensure_ascii=False, indent=1)}\n\n"
        f"Текст ТЗ:\n{text[:20000]}\n\nВерни JSON строго по инструкции."
    )
    result, err = query_llm_json(X_PROMPT, user_message, required_key="values", max_tokens=3000)
    if not result:
        return 0, [], err or "Нейросеть не вернула результат"

    by_row = {str(v.get("row_id")): v for v in (result.get("values") or []) if isinstance(v, dict)}
    notes: List[str] = []
    done = 0
    for r in todo:
        pair = idx.get(r.item_id)
        if not pair:
            continue
        col, it = pair
        unit = it.get("unit", "")
        v = by_row.get(r.row_id) or {}
        label = r.source_description or it.get("name", "")
        conv = v.get("converted_value")
        orig = v.get("original_value")
        ok = False
        conv_f = orig_f = 0.0
        try:
            conv_f = float(conv) if conv is not None else 0.0
            orig_f = float(orig) if orig is not None else conv_f
            ok = bool(v.get("found")) and conv_f > 0 and number_in_text(orig_f, text)
        except (TypeError, ValueError):
            ok = False
        if ok:
            r.x_value = round(conv_f, 6)
            r.x_source = "ai"
            quote = str(v.get("quote") or "").strip()
            conversion = str(v.get("conversion") or "").strip()
            r.x_note = (
                f"Из ТЗ: {orig_f:g} {v.get('original_unit') or ''}".strip()
                + (f" → {conv_f:g} {unit} ({conversion})" if conversion else f" = {conv_f:g} {unit}")
                + (f". Цитата: «{quote}»" if quote else "")
            )
        else:
            if v.get("found") and orig_f > 0 and not number_in_text(orig_f, text):
                reason = "Значение, названное ИИ, не найдено в тексте ТЗ — отклонено."
            else:
                reason = "Данные не указаны в ТЗ."
            xmin = min_x_for_item(col, it)
            if xmin:
                r.x_value = xmin
                r.x_source = "min_default"
                r.x_note = f"{reason} Взято минимальное значение X = {xmin:g} {unit} из таблицы, уточните у заказчика."
            else:
                r.x_value = 0.0
                r.x_source = ""
                r.x_note = f"{reason} Для этой таблицы нет минимального значения — введите X вручную."
            notes.append(f"«{label}»: {r.x_note}")
        r.needs_ai = False
        done += 1
    return done, notes, None
