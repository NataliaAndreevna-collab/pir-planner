import datetime
import os
import urllib.parse
from typing import Any, Dict, Optional
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models import FacilityType, KPRequest, ParseTZRequest, ParseTZResponse, ProjectData, ProjectMode
from app.services.cost_estimator import init_cost_parameters, recalculate_cost_parameters, sync_cost_with_sections
from app.services.docx_generator import generate_docx_sostav
from app.services.estimate_excel_generator import generate_estimate_excel
from app.services.kp_generator import generate_kp_docx, get_letterhead_path
from app.services.excel_generator import generate_excel_schedule
from app.services.normative_catalog import (
    check_indices_staleness,
    ensure_catalog_file,
    parse_uploaded_collection_file,
    save_catalog,
)
from app.services.pp87_rules import (
    apply_volume_ciphers,
    build_rd_sections,
    build_schedule,
    get_default_capital_sections,
    get_default_linear_sections,
    resolve_schedule,
)
from app.services.tz_parser import apply_tz_to_sections, extract_text_from_docx, extract_text_from_pdf, parse_tz_content
from app.services.masking import mask_for_ai

app = FastAPI(
    title="ПИР Генератор: Состав проекта и График работ",
    description="Автоматизированное формирование состава разделов по ПП РФ № 87, ГОСТ Р 21.101 и календарного графика на основе ТЗ",
    version="1.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.get("/")
def read_root():
    """Отдает главную страницу веб-интерфейса."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def _read_raw_tz(text: str, file: Optional[UploadFile]) -> str:
    """Собирает текст ТЗ из поля формы и/или загруженного файла (.docx, .pdf, .txt)."""
    raw_text = text

    if file and file.filename:
        content = await file.read()
        filename_lower = file.filename.lower()
        if filename_lower.endswith(".docx"):
            extracted = extract_text_from_docx(content)
            raw_text = (raw_text + "\n" + extracted).strip()
        elif filename_lower.endswith(".pdf"):
            extracted = extract_text_from_pdf(content)
            raw_text = (raw_text + "\n" + extracted).strip()
        elif filename_lower.endswith(".txt"):
            raw_text = (raw_text + "\n" + content.decode("utf-8", errors="ignore")).strip()

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Не передан текст или файл ТЗ для анализа")

    return raw_text


@app.post("/api/preview-ai-payload")
async def preview_ai_payload_endpoint(
    text: str = Form(default=""),
    file: UploadFile = File(default=None),
):
    """
    Служебный эндпоинт проверки: показывает, какой текст уйдёт в нейросеть после маскирования,
    и список замен. Ничего никуда не отправляет. Открыть можно на странице /docs.
    """
    raw_text = await _read_raw_tz(text, file)
    project_data, _ = parse_tz_content(raw_text, engine="local")
    masked = mask_for_ai(
        raw_text,
        customer=project_data.customer,
        contractor=project_data.contractor,
        contract_number=project_data.contract_number,
        contract_date=project_data.contract_date,
        object_name=project_data.object_name,
    )
    return {
        "masked_text": masked.text,
        "replacements_count": len(masked.replacements),
        "summary": masked.summary(),
        "replacements": masked.replacements,
        "warning": "Фильтр работает по шаблонам и не даёт гарантии: проверьте текст глазами.",
    }


@app.post("/api/parse-tz", response_model=ParseTZResponse)
async def parse_tz_endpoint(
    text: str = Form(default=""),
    file: UploadFile = File(default=None),
    engine: str = Form(default="local"),
):
    """
    Парсит ТЗ из загруженного файла (.docx, .pdf, .txt) или переданного текста.
    Параметр engine: 'local' (мгновенный по нормативам) или 'ai' (нейросеть).
    Возвращает предварительно заполненные параметры проекта и состав разделов.
    """
    raw_text = await _read_raw_tz(text, file)

    project_data, detected_features = parse_tz_content(raw_text, engine=engine)
    return ParseTZResponse(project_data=project_data, detected_features=detected_features)


@app.post("/api/recalculate", response_model=ProjectData)
def recalculate_project(data: ProjectData):
    """
    Пересчитывает шифры, разрешает зависимости в графике и синхронизирует смету с составом разделов.
    """
    apply_volume_ciphers(data)
    resolve_schedule(data.schedule_phases)
    sync_cost_with_sections(data)
    return data


@app.post("/api/rebuild-schedule", response_model=ProjectData)
def rebuild_schedule_endpoint(data: ProjectData, detail: Optional[str] = None):
    """
    Перестраивает календарный график по текущему выбранному составу разделов ПД и РД.
    """
    if detail in ("sections", "stages"):
        data.schedule_detail = detail
    apply_volume_ciphers(data)
    data.schedule_phases = build_schedule(data, detail=data.schedule_detail)
    return data


@app.post("/api/resolve-schedule", response_model=ProjectData)
def resolve_schedule_endpoint(data: ProjectData):
    """
    Пересчитывает даты старта этапов графика на основе зависимостей (depends_on) и сдвигов (lag_weeks).
    """
    resolve_schedule(data.schedule_phases)
    return data


@app.post("/api/apply-preset", response_model=ProjectData)
def apply_preset_endpoint(data: ProjectData, preset: str):
    """
    Переключает режим формирования состава разделов:
    - tz: Только указанные в ТЗ разделы (и аналоги ПД для марок РД)
    - permit: Минимум для получения Разрешения на строительство (ст. 51 ГрК РФ) + триггеры из ТЗ
    - expertise: Минимум для прохождения Экспертизы ПД (ПП РФ № 87) + триггеры из ТЗ
    """
    if preset not in ("tz", "permit", "expertise"):
        preset = "permit"
    sections, has_pd, has_rd, chosen_preset, _, flags = apply_tz_to_sections(
        data.tz_text or "", data.facility_type, preset_override=preset
    )
    data.sections = sections
    data.has_pd = has_pd
    data.has_rd = has_rd
    data.composition_preset = chosen_preset
    data.schedule_flags = flags
    apply_volume_ciphers(data)
    data.schedule_phases = build_schedule(data, detail=data.schedule_detail)
    sync_cost_with_sections(data)
    return data


@app.post("/api/switch-facility-type", response_model=ProjectData)
def switch_facility_type(data: ProjectData, facility_type: FacilityType):
    """
    Переключает структуру разделов между Площадочным (Капитальным) и Линейным.
    """
    data.facility_type = facility_type
    if data.tz_text and data.tz_text.strip():
        sections, has_pd, has_rd, chosen_preset, _, flags = apply_tz_to_sections(
            data.tz_text, facility_type, preset_override=data.composition_preset
        )
        data.sections = sections
        data.has_pd = has_pd
        data.has_rd = has_rd
        data.composition_preset = chosen_preset
        data.schedule_flags = flags
    else:
        sections, has_pd, has_rd, chosen_preset, _, flags = apply_tz_to_sections(
            "", facility_type, preset_override=data.composition_preset or "permit"
        )
        data.sections = sections
        data.has_pd = has_pd
        data.has_rd = has_rd
        data.composition_preset = chosen_preset
        data.schedule_flags = flags

    apply_volume_ciphers(data)
    data.schedule_phases = build_schedule(data, detail=data.schedule_detail)
    sync_cost_with_sections(data)
    return data


@app.post("/api/calculate-cost", response_model=ProjectData)
def calculate_cost_endpoint(data: ProjectData):
    """
    Пересчитывает стоимостные показатели, трудоемкость и сметное распределение
    по разделам на основе параметров сметного модуля.
    """
    apply_volume_ciphers(data)
    if data.cost_parameters:
        sync_cost_with_sections(data)
    else:
        data.cost_parameters = init_cost_parameters(data)
    return data


@app.post("/api/generate-cost-excel")
def generate_cost_excel_endpoint(data: ProjectData):
    """
    Генерирует официальный сметный расчет стоимости ПИР и калькуляцию трудозатрат (.xlsx).
    """
    apply_volume_ciphers(data)
    if data.cost_parameters:
        recalculate_cost_parameters(data.cost_parameters, has_pd=data.has_pd, has_rd=data.has_rd)
    else:
        data.cost_parameters = init_cost_parameters(data)

    stream = generate_estimate_excel(data)

    filename = "Смета_ПИР.xlsx"
    if data.mode == ProjectMode.CONTRACT and data.cipher:
        filename = f"{data.cipher}_Смета_ПИР.xlsx"
    elif data.object_name:
        clean_name = "".join(c for c in data.object_name[:30] if c.isalnum() or c in (" ", "_", "-")).strip()
        if clean_name:
            filename = f"Смета_{clean_name}.xlsx"

    quoted_filename = urllib.parse.quote(filename)
    return Response(
        content=stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}"
        }
    )


@app.post("/api/generate-docx")
def generate_docx_endpoint(data: ProjectData):
    """
    Генерирует документ Word (.docx) «Состав проектной документации».
    """
    apply_volume_ciphers(data)
    stream = generate_docx_sostav(data)

    filename = "Состав_проекта.docx"
    if data.mode == ProjectMode.CONTRACT and data.cipher:
        filename = f"{data.cipher}_Состав_проекта.docx"
    elif data.object_name:
        clean_name = "".join(c for c in data.object_name[:30] if c.isalnum() or c in (" ", "_", "-")).strip()
        if clean_name:
            filename = f"Состав_{clean_name}.docx"

    quoted_filename = urllib.parse.quote(filename)
    return Response(
        content=stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}"
        }
    )


@app.post("/api/generate-xlsx")
def generate_xlsx_endpoint(data: ProjectData):
    """
    Генерирует таблицу Excel (.xlsx) «Календарный график выполнения работ».
    """
    apply_volume_ciphers(data)
    resolve_schedule(data.schedule_phases)
    stream = generate_excel_schedule(data)

    filename = "Календарный_график.xlsx"
    if data.mode == ProjectMode.CONTRACT and data.cipher:
        filename = f"{data.cipher}_График_работ.xlsx"
    elif data.object_name:
        clean_name = "".join(c for c in data.object_name[:30] if c.isalnum() or c in (" ", "_", "-")).strip()
        if clean_name:
            filename = f"График_{clean_name}.xlsx"

    quoted_filename = urllib.parse.quote(filename)
    return Response(
        content=stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}"
        }
    )


# Подключение статических файлов (JS, CSS, картинки)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/kp-info")
def kp_info():
    """Режим формирования КП: корпоративный бланк подключен или используется нейтральный образец."""
    return {"corporate_letterhead": get_letterhead_path() is not None}


@app.get("/api/normative-catalog")
def get_normative_catalog_endpoint():
    """
    Возвращает базу нормативов: 15 сборников МНЗ/СБЦП, квартальные индексы Минстроя РФ
    с проверкой актуальности (3 месяца) и ссылкой на КонсультантПлюс, справочник специалистов
    по Тюменской области и таблицу нормативов от СМР по Методике № 707/пр.
    """
    catalog = ensure_catalog_file()
    indices = catalog.get("indices", {})
    staleness = check_indices_staleness(indices.get("updated_at", "2026-07-23"))
    return {
        "catalog": catalog,
        "staleness": staleness,
    }


@app.post("/api/update-indices")
def update_indices_endpoint(payload: Dict[str, Any] = Body(...)):
    """
    Сохраняет обновленные пользователем квартальные индексы Минстроя РФ
    и фиксирует дату актуализации (сегодня).
    """
    catalog = ensure_catalog_file()
    indices = catalog.setdefault("indices", {})
    if "period_label" in payload:
        indices["period_label"] = str(payload["period_label"]).strip()
    if "letter_ref" in payload:
        indices["letter_ref"] = str(payload["letter_ref"]).strip()
    if "smr_to_2001_index" in payload:
        indices["smr_to_2001_index"] = float(payload["smr_to_2001_index"])
    if isinstance(payload.get("pir"), dict):
        for k, v in payload["pir"].items():
            indices.setdefault("pir", {})[str(k)] = float(v)
    if isinstance(payload.get("survey"), dict):
        for k, v in payload["survey"].items():
            indices.setdefault("survey", {})[str(k)] = float(v)

    indices["updated_at"] = datetime.date.today().isoformat()
    save_catalog(catalog)
    staleness = check_indices_staleness(indices["updated_at"])
    return {"catalog": catalog, "staleness": staleness}


@app.post("/api/update-specialists")
def update_specialists_endpoint(payload: Dict[str, Any] = Body(...)):
    """
    Сохраняет изменения в справочнике специалистов и среднемесячную ЗП по региону (для Методики № 707/пр).
    """
    catalog = ensure_catalog_file()
    if "regional_salary_707_rub" in payload:
        catalog["regional_salary_707_rub"] = float(payload["regional_salary_707_rub"])
    if "working_days_per_month" in payload:
        catalog["working_days_per_month"] = float(payload["working_days_per_month"])
    if isinstance(payload.get("specialists_directory"), list):
        catalog["specialists_directory"] = payload["specialists_directory"]
    save_catalog(catalog)
    return {"catalog": catalog}


@app.post("/api/upload-collection")
async def upload_collection_endpoint(file: UploadFile = File(...)):
    """
    Принимает файл сборника (.docx или .pdf), автоматически извлекает базовый уровень цен
    и табличные параметры расценок и пополняет базу data/normative_catalog.json.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Файл сборника не выбран")
    content = await file.read()
    try:
        added_col = parse_uploaded_collection_file(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка разбора файла сборника: {e}")

    catalog = ensure_catalog_file()
    return {
        "added_collection": added_col,
        "catalog": catalog,
    }


@app.post("/api/generate-kp")
def generate_kp_endpoint(req: KPRequest):
    """
    Генерирует коммерческое предложение (.docx). Без приватного бланка - нейтральный образец.
    """
    data = req.project
    apply_volume_ciphers(data)
    if data.cost_parameters:
        recalculate_cost_parameters(data.cost_parameters, has_pd=data.has_pd, has_rd=data.has_rd)
    else:
        data.cost_parameters = init_cost_parameters(data)

    stream = generate_kp_docx(req)

    filename = "Коммерческое_предложение.docx"
    clean_name = "".join(c for c in data.object_name[:30] if c.isalnum() or c in (" ", "_", "-")).strip()
    if clean_name:
        filename = f"КП_{clean_name}.docx"
    quoted_filename = urllib.parse.quote(filename)
    return Response(
        content=stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}"}
    )
