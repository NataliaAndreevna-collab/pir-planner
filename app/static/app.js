// Состояние приложения
let currentProject = null;
let currentMode = "pre_contract"; // pre_contract или contract
let activeTab = "sections";

// DOM элементы
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const selectedFileName = document.getElementById("selectedFileName");
const tzText = document.getElementById("tzText");
const btnParse = document.getElementById("btnParse");

const insightsCard = document.getElementById("insightsCard");
const detectedFeaturesList = document.getElementById("detectedFeaturesList");
const workspaceCard = document.getElementById("workspaceCard");

const modePreContract = document.getElementById("modePreContract");
const modeContract = document.getElementById("modeContract");
const contractFieldsPanel = document.getElementById("contractFieldsPanel");

const inputObjectName = document.getElementById("inputObjectName");
const selectFacilityType = document.getElementById("selectFacilityType");
const inputCustomer = document.getElementById("inputCustomer");
const inputContractor = document.getElementById("inputContractor");
const inputSubcontractor = document.getElementById("inputSubcontractor");

const inputContractNumber = document.getElementById("inputContractNumber");
const inputContractDate = document.getElementById("inputContractDate");
const inputCipher = document.getElementById("inputCipher");
const inputStartDate = document.getElementById("inputStartDate");

const tabBtnSections = document.getElementById("tabBtnSections");
const tabBtnSchedule = document.getElementById("tabBtnSchedule");
const tabContentSections = document.getElementById("tabContentSections");
const tabContentSchedule = document.getElementById("tabContentSchedule");
const sectionsCountBadge = document.getElementById("sectionsCountBadge");

const sectionsTableBody = document.getElementById("sectionsTableBody");
const scheduleHeaderRow = document.getElementById("scheduleHeaderRow");
const scheduleTableBody = document.getElementById("scheduleTableBody");
const totalDurationLabel = document.getElementById("totalDurationLabel");

const btnSelectAll = document.getElementById("btnSelectAll");
const btnUnselectAll = document.getElementById("btnUnselectAll");
const btnDownloadDocx = document.getElementById("btnDownloadDocx");
const btnDownloadXlsx = document.getElementById("btnDownloadXlsx");

// Инициализация Drag & Drop
dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("border-blue-500", "bg-blue-50/50");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("border-blue-500", "bg-blue-50/50");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("border-blue-500", "bg-blue-50/50");
  if (e.dataTransfer.files.length > 0) {
    fileInput.files = e.dataTransfer.files;
    showSelectedFile(fileInput.files[0].name);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    showSelectedFile(fileInput.files[0].name);
  }
});

function showSelectedFile(name) {
  selectedFileName.textContent = `Выбран файл: ${name}`;
  selectedFileName.classList.remove("hidden");
}

// Кнопка парсинга
btnParse.addEventListener("click", async () => {
  const formData = new FormData();
  formData.append("text", tzText.value);
  if (fileInput.files.length > 0) {
    formData.append("file", fileInput.files[0]);
  }

  if (!tzText.value.trim() && fileInput.files.length === 0) {
    alert("Пожалуйста, вставьте текст ТЗ или выберите файл (.docx, .pdf, .txt)");
    return;
  }

  btnParse.disabled = true;
  btnParse.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Анализ ТЗ...';

  try {
    const res = await fetch("/api/parse-tz", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Ошибка при анализе ТЗ");
    }

    const data = await res.json();
    currentProject = data.project_data;

    // Выводим результаты анализа
    renderInsights(data.detected_features);

    // Заполняем форму и таблицы
    populateForm(currentProject);
    renderSectionsTable();
    renderScheduleTable();

    workspaceCard.classList.remove("hidden");
    insightsCard.classList.remove("hidden");
    workspaceCard.scrollIntoView({ behavior: "smooth" });

  } catch (err) {
    alert("Ошибка: " + err.message);
  } finally {
    btnParse.disabled = false;
    btnParse.innerHTML = '<i class="fa-solid fa-bolt mr-2"></i> Запустить экспресс-анализ ТЗ';
  }
});

// Отображение списка найденных триггеров
function renderInsights(features) {
  detectedFeaturesList.innerHTML = "";
  if (!features || features.length === 0) {
    detectedFeaturesList.innerHTML = "<li>Стандартные требования к проектированию капитального объекта</li>";
    return;
  }
  features.forEach((feat) => {
    const li = document.createElement("li");
    li.textContent = feat;
    detectedFeaturesList.appendChild(li);
  });
}

// Заполнение формы данными
function populateForm(proj) {
  inputObjectName.value = proj.object_name || "";
  selectFacilityType.value = proj.facility_type || "capital";
  inputCustomer.value = proj.customer || "";
  inputContractor.value = proj.contractor || "";
  inputSubcontractor.value = proj.subcontractor || "";

  inputContractNumber.value = proj.contract_number || "";
  inputContractDate.value = proj.contract_date || "";
  inputCipher.value = proj.cipher || "";
  inputStartDate.value = proj.start_date || "2026-10-01";

  setMode(proj.mode || "pre_contract");
}

// Переключение режимов: Предварительное КП vs Договор
modePreContract.addEventListener("click", () => setMode("pre_contract"));
modeContract.addEventListener("click", () => setMode("contract"));

function setMode(mode) {
  currentMode = mode;
  if (!currentProject) return;
  currentProject.mode = mode;

  if (mode === "pre_contract") {
    modePreContract.className = "px-3.5 py-1.5 rounded-md text-xs font-semibold transition bg-white text-blue-700 shadow-sm flex items-center";
    modeContract.className = "px-3.5 py-1.5 rounded-md text-xs font-semibold transition text-slate-600 hover:text-slate-900 flex items-center";
    contractFieldsPanel.classList.add("hidden");
  } else {
    modeContract.className = "px-3.5 py-1.5 rounded-md text-xs font-semibold transition bg-white text-blue-700 shadow-sm flex items-center";
    modePreContract.className = "px-3.5 py-1.5 rounded-md text-xs font-semibold transition text-slate-600 hover:text-slate-900 flex items-center";
    contractFieldsPanel.classList.remove("hidden");

    // Если шифр еще не сформирован, генерируем базовый
    if (!inputCipher.value && inputContractNumber.value) {
      updateCipher();
    }
  }

  recalculateCiphers();
}

// Автообновление шифра из номера договора
inputContractNumber.addEventListener("input", updateCipher);
inputContractDate.addEventListener("input", updateCipher);

function updateCipher() {
  const num = inputContractNumber.value.trim();
  const dateVal = inputContractDate.value.trim();
  let prefix = "01";
  const mNum = num.match(/^(\d+)/);
  if (mNum) prefix = mNum[1];

  let yearSuffix = "26";
  const mYear = dateVal.match(/20(\d{2})/);
  if (mYear) {
    yearSuffix = mYear[1];
  } else {
    const mNumYear = num.match(/(\d{2})$/);
    if (mNumYear) yearSuffix = mNumYear[1];
  }

  inputCipher.value = `${prefix}ТПС-${yearSuffix}`;
  if (currentProject) {
    currentProject.contract_number = num;
    currentProject.contract_date = dateVal;
    currentProject.cipher = inputCipher.value;
    recalculateCiphers();
  }
}

inputCipher.addEventListener("input", () => {
  if (currentProject) {
    currentProject.cipher = inputCipher.value;
    recalculateCiphers();
  }
});

// Переключение типа объекта (Капитальный vs Линейный)
selectFacilityType.addEventListener("change", async () => {
  if (!currentProject) return;
  const newType = selectFacilityType.value;
  syncProjectFromInputs();

  const res = await fetch(`/api/switch-facility-type?facility_type=${newType}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentProject),
  });
  currentProject = await res.json();
  renderSectionsTable();
  renderScheduleTable();
});

// Пересчет шифров
function recalculateCiphers() {
  if (!currentProject) return;
  const cipher = inputCipher.value.trim();

  currentProject.sections.forEach((sec) => {
    if (currentMode === "contract" && cipher) {
      sec.full_code = `${cipher}-${sec.code_mark}`;
    } else {
      sec.full_code = sec.code_mark;
    }
  });

  renderSectionsTable();
}

// Синхронизация данных из инпутов в объект
function syncProjectFromInputs() {
  if (!currentProject) return;
  currentProject.object_name = inputObjectName.value.trim();
  currentProject.customer = inputCustomer.value.trim();
  currentProject.contractor = inputContractor.value.trim();
  currentProject.subcontractor = inputSubcontractor.value.trim();
  currentProject.contract_number = inputContractNumber.value.trim();
  currentProject.contract_date = inputContractDate.value.trim();
  currentProject.cipher = inputCipher.value.trim();
  currentProject.start_date = inputStartDate.value;
}

// Отрисовка таблицы разделов (Вкладка 1)
function renderSectionsTable() {
  if (!currentProject) return;
  sectionsTableBody.innerHTML = "";

  let enabledCount = 0;
  let lastCatHeader = null;

  currentProject.sections.forEach((sec, idx) => {
    if (sec.enabled) enabledCount++;

    // Группирующий заголовок (Раздел 5, Раздел 12, Раздел 13)
    if (sec.category_header && sec.category_header !== lastCatHeader) {
      lastCatHeader = sec.category_header;
      const catTr = document.createElement("tr");
      catTr.className = "bg-slate-50 font-bold text-xs text-slate-800";
      catTr.innerHTML = `
        <td colspan="5" class="py-2.5 px-4 border-t border-b border-slate-200">
          <i class="fa-solid fa-folder-tree text-blue-600 mr-2"></i> ${sec.category_header}
        </td>
      `;
      sectionsTableBody.appendChild(catTr);
    }

    const tr = document.createElement("tr");
    tr.className = `hover:bg-blue-50/40 transition ${!sec.enabled ? "opacity-40 bg-slate-50" : ""}`;

    tr.innerHTML = `
      <td class="py-2.5 px-4 text-center">
        <input type="checkbox" class="section-chk w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500" data-idx="${idx}" ${sec.enabled ? "checked" : ""}>
      </td>
      <td class="py-2.5 px-4 text-center font-mono text-xs font-semibold text-slate-600">
        ${sec.volume_num}
      </td>
      <td class="py-2.5 px-4 text-center font-mono text-xs font-bold text-blue-700">
        ${sec.full_code || sec.code_mark}
      </td>
      <td class="py-2.5 px-4">
        <input type="text" class="w-full text-xs font-medium border-0 focus:ring-1 focus:ring-blue-400 rounded px-1.5 py-1 bg-transparent hover:bg-white" value="${sec.title}" data-field="title" data-idx="${idx}">
      </td>
      <td class="py-2.5 px-4">
        <input type="text" class="w-full text-xs text-slate-500 border-0 focus:ring-1 focus:ring-blue-400 rounded px-1.5 py-1 bg-transparent hover:bg-white" placeholder="Примечание..." value="${sec.note || ""}" data-field="note" data-idx="${idx}">
      </td>
    `;

    sectionsTableBody.appendChild(tr);
  });

  sectionsCountBadge.textContent = `${enabledCount} томов`;

  // Навешиваем слушатели чекбоксов и инпутов
  document.querySelectorAll(".section-chk").forEach((chk) => {
    chk.addEventListener("change", (e) => {
      const idx = e.target.dataset.idx;
      currentProject.sections[idx].enabled = e.target.checked;
      renderSectionsTable();
    });
  });

  document.querySelectorAll("input[data-field]").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = e.target.dataset.idx;
      const field = e.target.dataset.field;
      currentProject.sections[idx][field] = e.target.value;
    });
  });
}

// Кнопки "Выбрать все" / "Снять все"
btnSelectAll.addEventListener("click", () => {
  if (!currentProject) return;
  currentProject.sections.forEach((s) => (s.enabled = true));
  renderSectionsTable();
});

btnUnselectAll.addEventListener("click", () => {
  if (!currentProject) return;
  currentProject.sections.forEach((s) => (s.enabled = false));
  renderSectionsTable();
});

// Отрисовка таблицы Календарного графика (Вкладка 2)
function renderScheduleTable() {
  if (!currentProject || !currentProject.schedule_phases) return;

  const maxMonth = currentProject.schedule_phases.reduce(
    (max, p) => Math.max(max, p.start_month + p.duration_months - 1),
    8
  );
  const numMonths = Math.max(maxMonth, 8);
  totalDurationLabel.textContent = `${numMonths} месяцев`;

  // Очистка и отрисовка шапки графика
  scheduleHeaderRow.innerHTML = `
    <th class="py-3 px-3 w-10 text-center">№</th>
    <th class="py-3 px-4 w-72">Этап работ</th>
  `;

  for (let m = 1; m <= numMonths; m++) {
    const th = document.createElement("th");
    th.className = "py-3 px-2 text-center text-xs font-semibold w-16 bg-slate-700 border-l border-slate-600";
    th.textContent = `${m} мес`;
    scheduleHeaderRow.appendChild(th);
  }

  const thNote = document.createElement("th");
  thNote.className = "py-3 px-4 w-60 border-l border-slate-600";
  thNote.textContent = "Примечание";
  scheduleHeaderRow.appendChild(thNote);

  // Отрисовка строк этапов
  scheduleTableBody.innerHTML = "";

  currentProject.schedule_phases.forEach((phase, idx) => {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-50 transition border-b border-slate-100";

    const pStart = phase.start_month;
    const pEnd = phase.start_month + phase.duration_months - 1;

    let monthCellsHtml = "";
    for (let m = 1; m <= numMonths; m++) {
      if (m >= pStart && m <= pEnd) {
        monthCellsHtml += `
          <td class="p-1 text-center border-l border-slate-200">
            <div class="h-6 rounded gantt-bar flex items-center justify-center text-white text-[10px] font-bold shadow-xs">
              ${m === pStart ? phase.duration_months + "м" : "●"}
            </div>
          </td>
        `;
      } else {
        monthCellsHtml += `<td class="p-1 border-l border-slate-100"></td>`;
      }
    }

    tr.innerHTML = `
      <td class="py-2.5 px-3 text-center text-xs text-slate-500 font-mono">${idx + 1}</td>
      <td class="py-2.5 px-4 font-medium text-xs text-slate-800">
        ${phase.name}
        <div class="flex items-center space-x-2 mt-1 text-[11px] text-slate-400">
          <span>Старт: <b>${phase.start_month} мес</b></span>
          <span>Длительность: <b>${phase.duration_months} мес</b></span>
        </div>
      </td>
      ${monthCellsHtml}
      <td class="py-2.5 px-4 text-xs text-slate-500 border-l border-slate-100">${phase.note || ""}</td>
    `;

    scheduleTableBody.appendChild(tr);
  });
}

// Переключение вкладок
tabBtnSections.addEventListener("click", () => switchTab("sections"));
tabBtnSchedule.addEventListener("click", () => switchTab("schedule"));

function switchTab(tab) {
  activeTab = tab;
  if (tab === "sections") {
    tabBtnSections.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-blue-600 text-blue-600 flex items-center";
    tabBtnSchedule.className = "py-3.5 px-4 font-medium text-sm text-slate-500 hover:text-slate-800 border-b-2 border-transparent flex items-center";
    tabContentSections.classList.remove("hidden");
    tabContentSchedule.classList.add("hidden");
  } else {
    tabBtnSchedule.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-blue-600 text-blue-600 flex items-center";
    tabBtnSections.className = "py-3.5 px-4 font-medium text-sm text-slate-500 hover:text-slate-800 border-b-2 border-transparent flex items-center";
    tabContentSchedule.classList.remove("hidden");
    tabContentSections.classList.add("hidden");
    renderScheduleTable();
  }
}

// Скачивание Word (.docx)
btnDownloadDocx.addEventListener("click", async () => {
  if (!currentProject) return;
  syncProjectFromInputs();

  btnDownloadDocx.disabled = true;
  btnDownloadDocx.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Создание Word...';

  try {
    const res = await fetch("/api/generate-docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentProject),
    });

    if (!res.ok) throw new Error("Не удалось сгенерировать Word-документ");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    
    // Получаем имя файла из заголовка или по умолчанию
    let fname = "Состав_проекта.docx";
    if (currentMode === "contract" && currentProject.cipher) {
      fname = `${currentProject.cipher}_Состав_проекта.docx`;
    }
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert("Ошибка: " + err.message);
  } finally {
    btnDownloadDocx.disabled = false;
    btnDownloadDocx.innerHTML = '<i class="fa-solid fa-file-word mr-2 text-blue-200"></i> Скачать Состав проекта (.docx)';
  }
});

// Скачивание Excel (.xlsx)
btnDownloadXlsx.addEventListener("click", async () => {
  if (!currentProject) return;
  syncProjectFromInputs();

  btnDownloadXlsx.disabled = true;
  btnDownloadXlsx.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Создание Excel...';

  try {
    const res = await fetch("/api/generate-xlsx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentProject),
    });

    if (!res.ok) throw new Error("Не удалось сгенерировать Excel-таблицу");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    
    let fname = "Календарный_график.xlsx";
    if (currentMode === "contract" && currentProject.cipher) {
      fname = `${currentProject.cipher}_График_работ.xlsx`;
    }
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert("Ошибка: " + err.message);
  } finally {
    btnDownloadXlsx.disabled = false;
    btnDownloadXlsx.innerHTML = '<i class="fa-solid fa-file-excel mr-2 text-emerald-200"></i> Скачать График работ (.xlsx)';
  }
});
