import os
import urllib.parse
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models import FacilityType, ParseTZRequest, ParseTZResponse, ProjectData, ProjectMode
from app.services.docx_generator import generate_docx_sostav
from app.services.excel_generator import generate_excel_schedule
from app.services.pp87_rules import apply_volume_ciphers, get_default_capital_sections, get_default_linear_sections, get_default_schedule
from app.services.tz_parser import extract_text_from_docx, extract_text_from_pdf, parse_tz_content

app = FastAPI(
    title="ПИР Генератор: Состав проекта и График работ",
    description="Автоматизированное формирование состава разделов по ПП РФ № 87 и календарного графика на основе ТЗ",
    version="1.0.0"
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


@app.post("/api/parse-tz", response_model=ParseTZResponse)
async def parse_tz_endpoint(
    text: str = Form(default=""),
    file: UploadFile = File(default=None)
):
    """
    Парсит ТЗ из загруженного файла (.docx, .pdf, .txt) или переданного текста.
    Возвращает предварительно заполненные параметры проекта и состав разделов.
    """
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

    project_data, detected_features = parse_tz_content(raw_text)
    return ParseTZResponse(project_data=project_data, detected_features=detected_features)


@app.post("/api/recalculate", response_model=ProjectData)
def recalculate_project(data: ProjectData):
    """
    Пересчитывает шифры и при необходимости переключает набор разделов
    (Капитальный / Линейный) при изменении параметров пользователем в UI.
    """
    apply_volume_ciphers(data)
    return data


@app.post("/api/switch-facility-type", response_model=ProjectData)
def switch_facility_type(data: ProjectData, facility_type: FacilityType):
    """
    Переключает структуру разделов между Площадочным (Капитальным) и Линейным.
    """
    data.facility_type = facility_type
    if facility_type == FacilityType.LINEAR:
        data.sections = get_default_linear_sections()
    else:
        data.sections = get_default_capital_sections()
    
    data.schedule_phases = get_default_schedule(facility_type=facility_type)
    apply_volume_ciphers(data)
    return data


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
