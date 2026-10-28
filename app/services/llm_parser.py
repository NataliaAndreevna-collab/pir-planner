import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Список поддерживаемых моделей (в порядке приоритета).
# Если одна модель временно перегружена (429/503), автоматически пробуется следующая.
DEFAULT_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-31b-it:free",
    "liquid/lfm-2.5-2.6b:free",
]

# Промпт для строгого извлечения структуры из ТЗ
SYSTEM_PROMPT = """Ты главный инженер проекта (ГИП) и эксперт по проектированию в РФ (Градостроительный кодекс РФ, Постановление Правительства РФ № 87, ГОСТ Р 21.101-2020).

Твоя задача — проанализировать текст Технического задания (ТЗ) на проектирование и вернуть ТОЛЬКО структурированный JSON с составом проекта и параметрами.

КРИТИЧЕСКИЕ ПРАВИЛА ОПРЕДЕЛЕНИЯ СТАДИЙ:
1. Стадия «Рабочая документация» (РД) vs «Проектная документация» (ПД):
   - Если в ТЗ явно указано: «Стадия проектирования: рабочая документация», «разработать рабочую документацию», «стадия: Р», «РД на основании ранее разработанной ПД» — тогда:
     * has_pd: false (ПД НЕ разрабатывается!)
     * has_rd: true (разрабатывается только РД)
     * pd_sections: [] (список ПД ОБЯЗАН быть пустым!)
   - Если в ТЗ указано: «Стадия проектирования: проектная документация», «только проектная документация», «стадия: П», «без рабочей документации» — тогда:
     * has_pd: true
     * has_rd: false
     * rd_marks: []
   - Если указаны обе стадии («проектная и рабочая документация», «в две стадии: ПД и РД», «стадия: П, Р») — тогда:
     * has_pd: true
     * has_rd: true
   - Если стадия в ТЗ прямо не названа, по умолчанию считается разработка проектной документации:
     * has_pd: true
     * has_rd: false

2. Режим комплектности (composition_preset):
   - "tz" — если в ТЗ перечислен конкретный (урезанный или индивидуальный) перечень разделов/марок.
   - "expertise" — если в ТЗ требуется государственная/негосударственная экспертиза проектной документации или проверка достоверности сметной стоимости.
   - "permit" — если состав разделов не конкретизирован и экспертиза не требуется (минимальный пакет для получения разрешения на строительство по ст. 51 ГрК РФ).

3. Каталог идентификаторов разделов ПД (pd_sections):
   "pz" (Пояснительная записка)
   "pzu" (Схема планировочной организации земельного участка / ППО для линейных)
   "ar" (Архитектурные решения)
   "kr" (Конструктивные и объемно-планировочные решения / ТКР)
   "ios1" (Электроснабжение)
   "ios2" (Водоснабжение)
   "ios3" (Водоотведение / канализация)
   "ios4" (Отопление, вентиляция, кондиционирование, тепловые сети)
   "ios5_1" (Сети связи, видеонаблюдение)
   "ios5_2" (Автоматизация, диспетчеризация, КИПиА, АСУ ТП)
   "ios6" (Газоснабжение)
   "tx" (Технологические решения / водоочистка / технологическая схема)
   "pos" (Проект организации строительства)
   "pod" (Проект организации работ по сносу/демонтажу)
   "oos" (Охрана окружающей среды)
   "pb" (Пожарная безопасность)
   "tbe" (Безопасная эксплуатация)
   "odi" (Доступность для маломобильных групп / инвалидов)
   "ee" (Энергоэффективность)
   "sm" (Сметная документация)
   "ots" (Обследование технического состояния несущих конструкций)

4. Каталог идентификаторов марок РД (rd_marks):
   "rd_gp" (ГП - Генеральный план)
   "rd_ar" (АР - Архитектурные решения)
   "rd_as" (АС - Архитектурно-строительные решения / Строительная часть)
   "rd_kzh" (КЖ - Конструкции железобетонные)
   "rd_km" (КМ - Конструкции металлические)
   "rd_eom" (ЭОМ - Силовое электрооборудование и освещение)
   "rd_es" (ЭС - Наружные сети электроснабжения)
   "rd_vk" (ВК - Внутреннее водоснабжение и канализация)
   "rd_nvk" (НВК - Наружные сети водоснабжения и канализации / водопровод)
   "rd_ov" (ОВ - Отопление и вентиляция)
   "rd_ts" (ТС - Тепловые сети)
   "rd_ss" (СС - Сети связи, видеонаблюдение)
   "rd_ak" (АК / АТХ - Автоматизация, КИПиА)
   "rd_gsn" (ГСН - Газоснабжение)
   "rd_tx" (ТХ - Технологические решения)
   "rd_sm" (СМ - Сметная документация / локальные сметы)

ФОРМАТ ВЫХОДНЫХ ДАННЫХ (строго JSON):
{
  "object_name": "Название объекта из ТЗ",
  "customer": "Заказчик (если указан)",
  "contractor": "Генпроектировщик (только если прямо назван в ТЗ, иначе пустая строка)",
  "contract_number": "Номер договора (если есть)",
  "contract_date": "Дата договора (если есть)",
  "facility_type": "capital" или "linear",
  "has_pd": true или false,
  "has_rd": true или false,
  "composition_preset": "tz" или "permit" или "expertise",
  "pd_sections": ["id разделов ПД из каталога выше"],
  "rd_marks": ["id марок РД из каталога выше"],
  "has_surveys": true или false,
  "has_expertise": true или false,
  "explanation": "Краткое обоснование решения (1-2 предложения)"
}

В ответе должен быть ТОЛЬКО чистый JSON без символов ```json и ```!
"""


def get_api_key() -> str:
    """Получает ключ API из переменных окружения или файла .env."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENROUTER_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"\'')
        except Exception:
            pass
    return ""


def clean_json_response(raw_text: str) -> str:
    """Очищает ответ модели от возможных markdown-оберток."""
    t = raw_text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    match = re.search(r"(\{.*\})", t, re.DOTALL)
    if match:
        return match.group(1).strip()
    return t


def query_llm_tz_analysis(tz_text: str, model_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Отправляет текст ТЗ в нейросеть через OpenRouter API.
    Возвращает распарсенный словарь или None при ошибке/отсутствии ключа.
    """
    api_key = get_api_key()
    if not api_key:
        return None

    # Ограничиваем объем входного текста для надежности и скорости (до 25 000 символов)
    cleaned_tz = tz_text.strip()
    if len(cleaned_tz) > 25000:
        cleaned_tz = cleaned_tz[:25000] + "\n\n[... Текст сокращен для анализа ...]"

    user_message = f"Текст Технического задания (ТЗ):\n\n{cleaned_tz}\n\nСформируй JSON строго по инструкции."

    models_to_try = [model_name] if model_name else DEFAULT_MODELS

    for m in models_to_try:
        if not m:
            continue
        try:
            req_data = {
                "model": m,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.1,
                "max_tokens": 1200,
            }

            req = urllib.request.Request(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://pir-planner.local",
                    "X-Title": "PIR Planner AI",
                },
                data=json.dumps(req_data).encode("utf-8"),
            )

            with urllib.request.urlopen(req, timeout=35) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                choices = resp_json.get("choices", [])
                if not choices:
                    continue
                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    continue

                cleaned_json = clean_json_response(content)
                parsed = json.loads(cleaned_json)
                if isinstance(parsed, dict) and ("has_pd" in parsed or "has_rd" in parsed):
                    return parsed
        except urllib.error.HTTPError as he:
            # Если превышен лимит (429) или сервис недоступен, пробуем следующую модель
            continue
        except Exception:
            continue

    return None
