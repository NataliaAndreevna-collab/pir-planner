from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ProjectMode(str, Enum):
    PRE_CONTRACT = "pre_contract"  # Предварительная оценка / КП (без шифра, марки по ГОСТ, месяцы 1..N)
    CONTRACT = "contract"          # Выход на договор (с шифром {номер}ТПС-{ГГ}, календарные даты)


class FacilityType(str, Enum):
    CAPITAL = "capital"  # Раздел II ПП 87: Капитальные объекты (здания, сооружения, площадки)
    LINEAR = "linear"    # Раздел III ПП 87: Линейные объекты (сети, водоводы, трубопроводы, дороги)
    COMPLEX = "complex"  # Комплексный объект (сочетание площадочной части и внеплощадочных сетей)


class SectionItem(BaseModel):
    id: str
    volume_num: str                  # Номер тома: "1", "5.1", "12.3", "13.1"
    code_mark: str                   # Базовая марка: "ПЗ", "АР", "ИОС1", "СМ.П"
    full_code: str = ""              # Полный шифр тома: "12ТПС-26-АР" или "АР" в режиме КП
    title: str                       # Наименование тома/раздела
    note: str = ""                   # Примечание
    category_header: Optional[str] = None  # Заголовок группирующего раздела (например, "Раздел 5. Сведения об...")
    enabled: bool = True             # Включен ли том в проект
    required_by_norm: bool = False   # Является ли строго обязательным по ПП 87


class SchedulePhase(BaseModel):
    id: int
    name: str
    start_month: int = 1             # С какого месяца (1..N)
    duration_months: int = 1         # Длительность в месяцах
    note: str = ""
    category: str = "ПИР"            # ПИР или СМР


class ProjectData(BaseModel):
    mode: ProjectMode = ProjectMode.PRE_CONTRACT
    object_name: str = "Строительство объекта"
    customer: str = ""
    contractor: str = ""
    subcontractor: str = ""
    contract_number: str = ""
    contract_date: str = ""
    cipher: str = ""                 # Базовый шифр, например 12ТПС-26
    facility_type: FacilityType = FacilityType.CAPITAL
    start_date: str = ""             # Например "2026-10-01"
    total_months: int = 8
    sections: List[SectionItem] = Field(default_factory=list)
    schedule_phases: List[SchedulePhase] = Field(default_factory=list)


class ParseTZRequest(BaseModel):
    text: str = ""
    file_name: Optional[str] = None


class ParseTZResponse(BaseModel):
    project_data: ProjectData
    detected_features: List[str] = Field(default_factory=list)
