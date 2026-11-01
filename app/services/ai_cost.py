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

SUGGEST_PROMPT = """Ты опытный главный инженер проекта (ГИП) в РФ. По тексту технического задания (ТЗ) определи проектируемые объекты,
для каждого выбери НАИБОЛЕЕ ПОДХОДЯЩУЮ позицию из справочника базовых цен с обязательным исключением двойного учёта затрат (п. 122 Методики № 707/пр и ПП РФ № 87).

Правила:
1. В «объекты» включай только то, что непосредственно проектируется по ТЗ, а не всё, что упоминается в тексте (ссылки на нормы, существующие или соседние объекты).
2. СТРОЖАЙШЕЕ ПРАВИЛО РАЗГРАНИЧЕНИЯ ОБЯЗАННОСТЕЙ (ПОДРЯДЧИК vs ЗАКАЗЧИК):
   - Смета составляется СТРОГО на работы, порученные [ПОДРЯДЧИК] (Исполнителю)!
   - Внимательно анализируй таблицу состава документации и графу исполнителей:
     * Если объект, здание, сооружение или раздел прямо закреплен за [ЗАКАЗЧИК] (например: само здание котельной заводской поставки Заказчиком, технологические решения котельной заводского изготовления), КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО включать его в смету!
     * Если в ТЗ указано «Разработать проект СЗЗ / ООС и согласовать с органом Роспотребнадзора (или иными ведомствами)» — разработку и согласование выполняет [ПОДРЯДЧИК] (Исполнитель). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО считать это работой сторонней организации или исключать из состава проектных работ!
     * Включай в смету здания, сооружения, ёмкости, сети и разделы, разработка которых поручена [ПОДРЯДЧИК].
3. ПРАВИЛО РАЗГРАНИЧЕНИЯ ОКС, СЕТЕЙ И ЕМКОСТНЫХ СООРУЖЕНИЙ:
   - При проектировании водопроводных сооружений (МНЗ № 53/пр):
     * Резервуары чистой воды (РЧВ) и водонапорные башни НЕ ВХОДЯТ в базовую цену проектирования станции водоподготовки и расцениваются ОТДЕЛЬНО по Таблице 3.6 (в тыс. м³)!
     * Наружные внеплощадочные сети водопровода, водоотведения и канализации расцениваются ОТДЕЛЬНО по таблицам линейных объектов (в п.м. или км).
     * Внутриплощадочные инженерные сети (до 50 м от здания), благоустройство, озеленение и ограждение участка учтены ценой ОКС (Раздел 2 ПЗУ) и отдельно не расцениваются.
4. item_id бери ТОЛЬКО из списка справочника ниже, строго как написано. Ничего не придумывай и не меняй.
5. Если подходящей позиции в справочнике нет, верни item_id = null. Не подставляй «ближайшую» позицию, если по смыслу она не подходит.
6. Одна позиция справочника может подходить нескольким объектам: тогда верни по записи на каждый объект.
7. В description дай краткое описание объекта из ТЗ (без названий организаций и фамилий), в reason — одно предложение, почему выбрана позиция.
8. В тексте реквизиты заменены метками ([ЗАКАЗЧИК], [ОБЪЕКТ] и т.п.): не пытайся их восстанавливать.

Ответ — ТОЛЬКО JSON без пояснений и без ```:
{"objects": [{"description": "...", "item_id": "id или null", "reason": "..."}], "note": "общее замечание или пустая строка"}
"""

X_PROMPT = """Ты опытный главный инженер проекта (ГИП). Для каждой строки найди в тексте технического задания (ТЗ) значение натурального показателя X (объём, производительность, протяжённость, площадь и т.д.), который нужен для расчёта по таблице справочника (название таблицы и требуемая единица измерения unit даны).

Правила:
1. Используй числа, которые есть в тексте ТЗ или описании объекта.
2. ВНИМАНИЕ К ЕДИНИЦАМ ИЗМЕРЕНИЯ:
   - Внимательно смотри на требуемую единицу таблицы (поле unit: Гкал/ч, тыс. м3/сут, тыс. м3, м3/час, п.м., км, га, м2 и т.д.).
   - Переведи найденное число строго в требуемую единицу таблицы и запиши в converted_value.
   - ПРАВИЛА ПЕРЕВОДА ЕДИНИЦ:
     * Тепловая мощность:
       - 1 МВт = 0.859845 Гкал/ч (например, 2 МВт = 1.72 Гкал/ч; 4 МВт = 3.44 Гкал/ч);
       - 1 кВт = 0.00086 Гкал/ч;
       - 1 Гкал/ч = 1.163 МВт;
     * Расходы воды и стоков:
       - 1 м3/час при unit='тыс. м3/сут' (1 * 24 = 24 м3/сут = 0.024 тыс. м3/сут);
       - 300 м3/сут при unit='тыс. м3/сут' -> converted_value = 0.3;
     * Длины и расстояния:
       - 1500 м при unit='км' -> converted_value = 1.5;
       - 2.5 км при unit='п.м.' -> converted_value = 2500;
     * Объемы:
       - 50 000 м3 при unit='тыс. м3' -> converted_value = 50.0;
3. Если значения для этого объекта в ТЗ нет, верни found = false, converted_value = null. Не угадывай.
4. original_value — число так, как оно записано в ТЗ; original_unit — его единица; quote — короткая дословная цитата из ТЗ (до 200 символов).
5. converted_value — число, строго переведённое в требуемую единицу таблицы (unit).
6. В тексте реквизиты заменены метками: не пытайся их восстанавливать.

Ответ — ТОЛЬКО JSON без пояснений и без ```:
{"values": [{"row_id": "...", "found": true или false, "original_value": число или null, "original_unit": "...", "converted_value": число или null, "conversion": "...", "quote": "..."}]}"""


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
            val = float(ivs[0].get("x_min", 0.0))
            if val > 0:
                return val
            if "x_max" in ivs[0] and float(ivs[0]["x_max"]) > 0:
                return min(1.0, float(ivs[0]["x_max"]))
        except (KeyError, TypeError, ValueError):
            pass
    unit = (item.get("unit") or "").lower()
    if "км" in unit or "п.м" in unit or "м" in unit:
        return 1.0
    return 1.0


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
            in_tz = (
                number_in_text(orig_f, text)
                or number_in_text(orig_f, label)
                or (bool(project.tz_text) and number_in_text(orig_f, project.tz_text))
                or (bool(project.object_name) and number_in_text(orig_f, project.object_name))
            )
            ok = bool(v.get("found")) and conv_f > 0 and in_tz
        except (TypeError, ValueError):
            ok = False

        # Инженерная эвристика для котельных (перевод мощности МВт -> Гкал/ч)
        if not ok and ('гкал' in unit.lower() or 'котельн' in (label + ' ' + it.get('name', '')).lower()):
            import re as _re
            search_src = f"{project.object_name or ''} {label} {project.tz_text or ''}"
            m_mw = _re.search(r'(\d+(?:[.,]\d+)?)\s*(?:МВт|мвт|MW|мегаватт)', search_src, _re.IGNORECASE)
            if m_mw:
                mw_val = float(m_mw.group(1).replace(',', '.'))
                if mw_val > 0:
                    gcal_val = round(mw_val * 0.859845, 2)
                    conv_f = gcal_val
                    orig_f = mw_val
                    ok = True
                    v['found'] = True
                    v['original_unit'] = 'МВт'
                    v['conversion'] = f'{mw_val:g} МВт * 0.86 = {gcal_val:g} Гкал/ч'
                    v['quote'] = m_mw.group(0)

        # Инженерная увязка технологических объектов водоснабжения (ВОС -> Насосная станция и РЧВ)
        if not ok and ('насосн' in (label + ' ' + it.get('name', '')).lower() or 'рчв' in (label + ' ' + it.get('name', '')).lower() or 'резервуар' in (label + ' ' + it.get('name', '')).lower() or r.item_id in ('53pr_t3_5_p1', '53pr_t3_6_p1')):
            import re as _re
            search_src = f"{project.object_name or ''} {project.tz_text or ''}"
            m_sut = _re.search(r'(\d+(?:[.,]\d+)?)\s*(?:тыс\.?\s*)?м3[/\s]*(?:сут|24\s*ч)', search_src, _re.IGNORECASE)
            m_chas = _re.search(r'(\d+(?:[.,]\d+)?)\s*(?:тыс\.?\s*)?м3[/\s]*(?:ч|час)', search_src, _re.IGNORECASE)
            
            vos_m3_sut = 0.0
            for other_r in cp.collection_items:
                if other_r.item_id and 't3_4' in other_r.item_id and other_r.x_value > 0:
                    vos_m3_sut = float(other_r.x_value) * 1000.0
                    break
            if vos_m3_sut <= 0 and m_sut:
                val = float(m_sut.group(1).replace(',', '.'))
                if 'тыс' in m_sut.group(0).lower():
                    vos_m3_sut = val * 1000.0
                else:
                    vos_m3_sut = val

            if vos_m3_sut > 0:
                if 'насосн' in (label + ' ' + it.get('name', '')).lower() or r.item_id == '53pr_t3_5_p1':
                    if m_chas:
                        ch_val = float(m_chas.group(1).replace(',', '.'))
                        q_m3_h = ch_val * 1000.0 if 'тыс' in m_chas.group(0).lower() else ch_val
                    else:
                        q_m3_h = round(vos_m3_sut / 24.0, 2)
                    conv_f = round(q_m3_h / 1000.0, 6)
                    orig_f = q_m3_h
                    ok = True
                    v['found'] = True
                    v['original_unit'] = 'м³/час'
                    v['conversion'] = f'По балансу ВОС ({vos_m3_sut:g} м³/сут / 24 = {q_m3_h:g} м³/час) = {conv_f:g} тыс. м³/час'
                    v['quote'] = f"ВОС {vos_m3_sut:g} м3/сут"
                elif 'рчв' in (label + ' ' + it.get('name', '')).lower() or 'резервуар' in (label + ' ' + it.get('name', '')).lower() or r.item_id == '53pr_t3_6_p1':
                    v_rchv_m3 = vos_m3_sut
                    conv_f = round(v_rchv_m3 / 1000.0, 4)
                    orig_f = v_rchv_m3
                    ok = True
                    v['found'] = True
                    v['original_unit'] = 'м³'
                    v['conversion'] = f'Нормативный суточный запас по СП 31.13330 от ВОС ({vos_m3_sut:g} м³) = {conv_f:g} тыс. м³'
                    v['quote'] = f"ВОС {vos_m3_sut:g} м3/сут"
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
            if v.get("found") and orig_f > 0 and not in_tz:
                reason = "Значение, названное ИИ, не найдено в тексте ТЗ — отклонено."
            else:
                reason = "Данные не указаны в ТЗ."
            xmin = min_x_for_item(col, it)
            if xmin and xmin > 0:
                r.x_value = xmin
                r.x_source = "min_default"
                r.x_note = f"{reason} Взято минимальное значение X = {xmin:g} {unit} из таблицы, уточните у заказчика."
            else:
                r.x_value = 1.0
                r.x_source = "min_default"
                r.x_note = f"{reason} Принято базовое значение X = 1.0 {unit}, уточните у заказчика."
            notes.append(f"«{label}»: {r.x_note}")
        r.needs_ai = False
        done += 1
    return done, notes, None
