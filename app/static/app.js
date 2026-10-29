// Состояние приложения
let currentProject = null;
let currentMode = "pre_contract"; // pre_contract или contract
let activeTab = "sections";

// DOM элементы
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const selectedFileName = document.getElementById("selectedFileName");
const tzText = document.getElementById("tzText");
const btnParseLocal = document.getElementById("btnParseLocal");
const btnParseAI = document.getElementById("btnParseAI");

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

const inputContractNumber = document.getElementById("inputContractNumber");
const inputContractDate = document.getElementById("inputContractDate");
const inputCipher = document.getElementById("inputCipher");
const inputStartDate = document.getElementById("inputStartDate");

function getTodayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

if (inputStartDate && !inputStartDate.value) {
  inputStartDate.value = getTodayIso();
}

const btnPresetTz = document.getElementById("btnPresetTz");
const btnPresetPermit = document.getElementById("btnPresetPermit");
const btnPresetExpertise = document.getElementById("btnPresetExpertise");

const chkStagePd = document.getElementById("chkStagePd");
const chkStageRd = document.getElementById("chkStageRd");
const btnAddCustomPd = document.getElementById("btnAddCustomPd");
const btnAddCustomRd = document.getElementById("btnAddCustomRd");
const btnSyncScheduleFromSections = document.getElementById("btnSyncScheduleFromSections");

const btnSchedDetailSections = document.getElementById("btnSchedDetailSections");
const btnSchedDetailStages = document.getElementById("btnSchedDetailStages");
const btnRebuildSchedule = document.getElementById("btnRebuildSchedule");
const btnAddPhase = document.getElementById("btnAddPhase");
const btnAddMilestone = document.getElementById("btnAddMilestone");
const scheduleMonthHeaderRow = document.getElementById("scheduleMonthHeaderRow");
const finishDateLabel = document.getElementById("finishDateLabel");

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

// Соответствие марок РД аналогичным разделам ПД (при включении марки РД автоматически включается раздел ПД)
const RD_TO_PD_MAP_CAPITAL = {
  rd_gp: ["pzu"],
  rd_ar: ["ar"],
  rd_as: ["ar", "kr"],
  rd_kzh: ["kr"],
  rd_km: ["kr"],
  rd_kd: ["kr"],
  rd_eom: ["ios1"],
  rd_es: ["ios1"],
  rd_vk: ["ios2", "ios3"],
  rd_nvk: ["ios2", "ios3"],
  rd_ov: ["ios4"],
  rd_ts: ["ios4"],
  rd_ss: ["ios5_1"],
  rd_ak: ["ios5_2"],
  rd_gsn: ["ios6"],
  rd_tx: ["tx"],
  rd_aps: ["pb"],
  rd_ad: ["pzu"],
  rd_sm: ["sm"],
};

const RD_TO_PD_MAP_LINEAR = {
  rd_gp: ["ppo"],
  rd_ar: ["lin_infra"],
  rd_as: ["lin_infra"],
  rd_kzh: ["tkr"],
  rd_km: ["tkr"],
  rd_kd: ["tkr"],
  rd_eom: ["tkr"],
  rd_es: ["tkr"],
  rd_vk: ["tkr"],
  rd_nvk: ["tkr"],
  rd_ov: ["tkr"],
  rd_ts: ["tkr"],
  rd_ss: ["tkr"],
  rd_ak: ["tkr"],
  rd_gsn: ["tkr"],
  rd_tx: ["tkr"],
  rd_aps: ["pb"],
  rd_ad: ["tkr"],
  rd_sm: ["sm"],
};

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

// Функция запуска анализа ТЗ с выбором движка ('local' или 'ai')
async function runParseTZ(engine) {
  const formData = new FormData();
  formData.append("text", tzText.value);
  formData.append("engine", engine);
  if (fileInput.files.length > 0) {
    formData.append("file", fileInput.files[0]);
  }

  if (!tzText.value.trim() && fileInput.files.length === 0) {
    alert("Пожалуйста, вставьте текст ТЗ или выберите файл (.docx, .pdf, .txt)");
    return;
  }

  btnParseLocal.disabled = true;
  btnParseAI.disabled = true;

  if (engine === "ai") {
    btnParseAI.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Запрос к нейросети (10-25 сек)...';
  } else {
    btnParseLocal.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Быстрый анализ...';
  }

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

    renderInsights(data.detected_features);
    populateForm(currentProject);
    renderSectionsTable();
    renderScheduleTable();

    workspaceCard.classList.remove("hidden");
    insightsCard.classList.remove("hidden");
    workspaceCard.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("Ошибка: " + err.message);
  } finally {
    btnParseLocal.disabled = false;
    btnParseAI.disabled = false;
    btnParseLocal.innerHTML = '<i class="fa-solid fa-bolt mr-2 text-amber-400"></i> Быстрый анализ (без AI)';
    btnParseAI.innerHTML = '<i class="fa-solid fa-brain mr-2 text-indigo-200"></i> Анализ через нейросеть (AI)';
  }
}

if (btnParseLocal) {
  btnParseLocal.addEventListener("click", () => runParseTZ("local"));
}
if (btnParseAI) {
  btnParseAI.addEventListener("click", () => runParseTZ("ai"));
}

function renderInsights(features) {
  detectedFeaturesList.innerHTML = "";
  if (!features || features.length === 0) {
    detectedFeaturesList.innerHTML = "<li>Стандартные требования к проектированию объекта</li>";
    return;
  }
  features.forEach((feat) => {
    const li = document.createElement("li");
    li.textContent = feat;
    detectedFeaturesList.appendChild(li);
  });
}

function updatePresetButtonsUI() {
  if (!currentProject) return;
  const preset = currentProject.composition_preset || "permit";
  const activeCls = "px-3 py-1.5 rounded-md font-semibold transition bg-blue-600 text-white shadow-xs";
  const inactiveCls = "px-3 py-1.5 rounded-md font-semibold transition bg-white text-slate-700 border border-slate-300 hover:border-blue-400";

  if (btnPresetTz) btnPresetTz.className = preset === "tz" ? activeCls : inactiveCls;
  if (btnPresetPermit) btnPresetPermit.className = preset === "permit" ? activeCls : inactiveCls;
  if (btnPresetExpertise) btnPresetExpertise.className = preset === "expertise" ? activeCls : inactiveCls;
}

async function applyPresetBackend(preset) {
  if (!currentProject) return;
  syncProjectFromInputs();
  try {
    const res = await fetch(`/api/apply-preset?preset=${preset}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentProject),
    });
    if (res.ok) {
      currentProject = await res.json();
      if (chkStagePd) chkStagePd.checked = currentProject.has_pd !== false;
      if (chkStageRd) chkStageRd.checked = !!currentProject.has_rd;
      updatePresetButtonsUI();
      renderSectionsTable();
      renderScheduleTable();
    }
  } catch (err) {
    console.error("Ошибка применения режима комплектности:", err);
  }
}

if (btnPresetTz) btnPresetTz.addEventListener("click", () => applyPresetBackend("tz"));
if (btnPresetPermit) btnPresetPermit.addEventListener("click", () => applyPresetBackend("permit"));
if (btnPresetExpertise) btnPresetExpertise.addEventListener("click", () => applyPresetBackend("expertise"));

function populateForm(proj) {
  inputObjectName.value = proj.object_name || "";
  selectFacilityType.value = proj.facility_type || "capital";
  inputCustomer.value = proj.customer || "";
  inputContractor.value = proj.contractor || "";

  inputContractNumber.value = proj.contract_number || "";
  inputContractDate.value = proj.contract_date || "";
  inputCipher.value = proj.cipher || "";
  inputStartDate.value = proj.start_date || getTodayIso();

  if (chkStagePd) chkStagePd.checked = proj.has_pd !== false;
  if (chkStageRd) chkStageRd.checked = !!proj.has_rd;

  updatePresetButtonsUI();
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

    if (!inputCipher.value && inputContractNumber.value) {
      updateCipher();
    }
  }

  recalculateCiphers();
}

inputContractNumber.addEventListener("input", updateCipher);
inputContractDate.addEventListener("input", updateCipher);
inputStartDate.addEventListener("change", () => {
  if (currentProject) {
    currentProject.start_date = inputStartDate.value;
    if (activeTab === "schedule") renderScheduleTable();
  }
});

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
  if (chkStagePd) chkStagePd.checked = currentProject.has_pd !== false;
  if (chkStageRd) chkStageRd.checked = !!currentProject.has_rd;
  updatePresetButtonsUI();
  renderSectionsTable();
  renderScheduleTable();
});

// Пересчет шифров и номеров томов
function recalculateCiphers() {
  if (!currentProject) return;
  const cipher = inputCipher.value.trim();

  let pdMainIdx = 0;
  let lastCategory = null;
  let subIdx = 0;
  let rdIdx = 0;

  currentProject.sections.forEach((sec) => {
    const stage = sec.stage || "П";
    if (stage === "П") {
      if (sec.category_header) {
        if (sec.category_header !== lastCategory) {
          pdMainIdx += 1;
          lastCategory = sec.category_header;
          subIdx = 1;
        } else {
          subIdx += 1;
        }
        sec.volume_num = `Том ${pdMainIdx}.${subIdx}`;
      } else {
        pdMainIdx += 1;
        lastCategory = null;
        sec.volume_num = `Том ${pdMainIdx}`;
      }
    } else {
      rdIdx += 1;
      sec.volume_num = `Книга ${rdIdx}`;
    }

    if (currentMode === "contract" && cipher) {
      sec.full_code = `${cipher}-${sec.code_mark}`;
    } else {
      sec.full_code = sec.code_mark;
    }
  });

  renderSectionsTable();
}

function syncProjectFromInputs() {
  if (!currentProject) return;
  currentProject.object_name = inputObjectName.value.trim();
  currentProject.customer = inputCustomer.value.trim();
  currentProject.contractor = inputContractor.value.trim();
  currentProject.contract_number = inputContractNumber.value.trim();
  currentProject.contract_date = inputContractDate.value.trim();
  currentProject.cipher = inputCipher.value.trim();
  currentProject.start_date = inputStartDate.value;
  if (chkStagePd) currentProject.has_pd = chkStagePd.checked;
  if (chkStageRd) currentProject.has_rd = chkStageRd.checked;
}

if (chkStagePd) {
  chkStagePd.addEventListener("change", async () => {
    if (!currentProject) return;
    currentProject.has_pd = chkStagePd.checked;
    if (!currentProject.has_pd) {
      currentProject.sections.forEach((s) => {
        if ((s.stage || "П") === "П") s.enabled = false;
      });
    } else {
      const anyPd = currentProject.sections.some((s) => (s.stage || "П") === "П" && s.enabled);
      if (!anyPd) {
        currentProject.sections.forEach((s) => {
          if ((s.stage || "П") === "П" && s.required_by_norm) s.enabled = true;
        });
      }
    }
    await syncSectionsWithBackend();
  });
}

if (chkStageRd) {
  chkStageRd.addEventListener("change", async () => {
    if (!currentProject) return;
    currentProject.has_rd = chkStageRd.checked;
    if (!currentProject.has_rd) {
      currentProject.sections.forEach((s) => {
        if (s.stage === "Р") s.enabled = false;
      });
    } else {
      const anyRd = currentProject.sections.some((s) => s.stage === "Р" && s.enabled);
      if (!anyRd) {
        const defaultMarks = new Set(["ГП", "АР", "КЖ", "ЭОМ", "ВК", "ОВ"]);
        currentProject.sections.forEach((s) => {
          if (s.stage === "Р" && defaultMarks.has(s.code_mark)) s.enabled = true;
        });
      }
    }
    await syncSectionsWithBackend();
  });
}

async function syncSectionsWithBackend() {
  if (!currentProject) return;
  syncProjectFromInputs();
  try {
    const res = await fetch("/api/recalculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentProject),
    });
    if (res.ok) {
      currentProject = await res.json();
    }
  } catch (e) {
    console.error(e);
  }
  renderSectionsTable();
}

// Добавление пользовательского раздела ПД или марки РД
if (btnAddCustomPd) {
  btnAddCustomPd.addEventListener("click", async () => {
    if (!currentProject) return;
    const code = prompt("Введите шифр/обозначение раздела ПД (например, ТХ или СТУ):", "СТУ");
    if (!code) return;
    const title = prompt("Введите наименование раздела ПД:", "Специальные технические условия");
    if (!title) return;
    currentProject.has_pd = true;
    if (chkStagePd) chkStagePd.checked = true;
    const newSec = {
      id: "custom_pd_" + Date.now(),
      stage: "П",
      volume_num: "Том",
      code_mark: code.trim(),
      full_code: code.trim(),
      title: title.trim(),
      enabled: true,
      required_by_norm: false,
      source: "user",
      note: "Добавлен пользователем",
      category_header: null,
    };
    const firstRdIdx = currentProject.sections.findIndex((s) => s.stage === "Р");
    if (firstRdIdx >= 0) {
      currentProject.sections.splice(firstRdIdx, 0, newSec);
    } else {
      currentProject.sections.push(newSec);
    }
    await syncSectionsWithBackend();
  });
}

if (btnAddCustomRd) {
  btnAddCustomRd.addEventListener("click", async () => {
    if (!currentProject) return;
    const code = prompt("Введите марку основного комплекта РД (например, АТП, КМД, СКУД):", "АТП");
    if (!code) return;
    const title = prompt("Введите наименование комплекта РД:", "Автоматизация теплового пункта");
    if (!title) return;
    currentProject.has_rd = true;
    if (chkStageRd) chkStageRd.checked = true;
    currentProject.sections.push({
      id: "custom_rd_" + Date.now(),
      stage: "Р",
      volume_num: "Книга",
      code_mark: code.trim(),
      full_code: code.trim(),
      title: title.trim(),
      enabled: true,
      required_by_norm: false,
      source: "user",
      note: "Марка РД (добавлена пользователем)",
      category_header: null,
    });
    await syncSectionsWithBackend();
  });
}

if (btnSyncScheduleFromSections) {
  btnSyncScheduleFromSections.addEventListener("click", async () => {
    await rebuildScheduleBackend();
    switchTab("schedule");
  });
}

// Отрисовка таблицы разделов (Вкладка 1)
function renderSectionsTable() {
  if (!currentProject) return;
  sectionsTableBody.innerHTML = "";

  const pdEnabled = currentProject.sections.filter((s) => (s.stage || "П") === "П" && s.enabled).length;
  const rdEnabled = currentProject.sections.filter((s) => s.stage === "Р" && s.enabled).length;
  sectionsCountBadge.textContent = `ПД: ${pdEnabled} | РД: ${rdEnabled}`;

  let lastStage = null;
  let lastCatHeader = null;

  currentProject.sections.forEach((sec, idx) => {
    const stage = sec.stage || "П";

    if (stage !== lastStage) {
      lastStage = stage;
      lastCatHeader = null;
      const stageTr = document.createElement("tr");
      if (stage === "П") {
        stageTr.className = "bg-blue-900 text-white font-bold text-xs";
        stageTr.innerHTML = `
          <td colspan="5" class="py-2.5 px-4">
            <i class="fa-solid fa-book-open mr-2"></i> СТАДИЯ «П» — ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ (по ПП РФ № 87) — выбрано: ${pdEnabled}
          </td>
        `;
      } else {
        stageTr.className = "bg-cyan-900 text-white font-bold text-xs";
        stageTr.innerHTML = `
          <td colspan="5" class="py-2.5 px-4">
            <i class="fa-solid fa-compass-drafting mr-2"></i> СТАДИЯ «Р» — РАБОЧАЯ ДОКУМЕНТАЦИЯ (по ГОСТ Р 21.101-2020) — выбрано: ${rdEnabled}
          </td>
        `;
      }
      sectionsTableBody.appendChild(stageTr);
    }

    if (sec.category_header && sec.category_header !== lastCatHeader) {
      lastCatHeader = sec.category_header;
      const catTr = document.createElement("tr");
      catTr.className = "bg-slate-100 font-bold text-xs text-slate-800";
      catTr.innerHTML = `
        <td colspan="5" class="py-2 px-4 border-t border-b border-slate-200">
          <i class="fa-solid fa-folder-tree text-blue-600 mr-2"></i> ${sec.category_header}
        </td>
      `;
      sectionsTableBody.appendChild(catTr);
    }

    const tr = document.createElement("tr");
    tr.className = `hover:bg-blue-50/40 transition ${!sec.enabled ? "opacity-45 bg-slate-50/70" : ""}`;

    let badgeHtml = "";
    if (sec.source === "tz") {
      badgeHtml = `<span class="ml-2 bg-emerald-100 text-emerald-800 text-[10px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap">из ТЗ</span>`;
    } else if (sec.source === "trigger") {
      badgeHtml = `<span class="ml-2 bg-amber-100 text-amber-800 text-[10px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap">по тексту ТЗ</span>`;
    } else if (sec.source === "user") {
      badgeHtml = `<span class="ml-2 bg-purple-100 text-purple-800 text-[10px] px-1.5 py-0.5 rounded font-bold whitespace-nowrap">вручную</span>`;
    }

    tr.innerHTML = `
      <td class="py-2 px-4 text-center">
        <input type="checkbox" class="section-chk w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500" data-idx="${idx}" ${sec.enabled ? "checked" : ""}>
      </td>
      <td class="py-2 px-4 text-center font-mono text-xs font-semibold text-slate-600 whitespace-nowrap">
        ${sec.volume_num}
      </td>
      <td class="py-2 px-4 text-center font-mono text-xs font-bold ${stage === "Р" ? "text-cyan-700" : "text-blue-700"}">
        <input type="text" class="w-28 text-center font-mono text-xs font-bold border-0 focus:ring-1 focus:ring-blue-400 rounded px-1 py-0.5 bg-transparent hover:bg-white" value="${sec.full_code || sec.code_mark}" data-field="code_mark" data-idx="${idx}">
      </td>
      <td class="py-2 px-4">
        <div class="flex items-center">
          <input type="text" class="w-full text-xs font-medium border-0 focus:ring-1 focus:ring-blue-400 rounded px-1.5 py-1 bg-transparent hover:bg-white" value="${sec.title}" data-field="title" data-idx="${idx}">
          ${badgeHtml}
        </div>
      </td>
      <td class="py-2 px-4">
        <input type="text" class="w-full text-xs text-slate-500 border-0 focus:ring-1 focus:ring-blue-400 rounded px-1.5 py-1 bg-transparent hover:bg-white" placeholder="Примечание..." value="${sec.note || ""}" data-field="note" data-idx="${idx}">
      </td>
    `;

    sectionsTableBody.appendChild(tr);
  });

  // Навешиваем слушатели чекбоксов и инпутов
  document.querySelectorAll(".section-chk").forEach((chk) => {
    chk.addEventListener("change", async (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const isEnabled = e.target.checked;
      const sec = currentProject.sections[idx];
      sec.enabled = isEnabled;

      if (isEnabled) {
        if ((sec.stage || "П") === "П") {
          currentProject.has_pd = true;
          if (chkStagePd) chkStagePd.checked = true;
        } else {
          currentProject.has_rd = true;
          if (chkStageRd) chkStageRd.checked = true;

          // При включении марки РД автоматически включаем аналогичный раздел в ПД
          const rdMap = currentProject.facility_type === "linear" ? RD_TO_PD_MAP_LINEAR : RD_TO_PD_MAP_CAPITAL;
          const mappedPdIds = rdMap[sec.id] || [];
          if (mappedPdIds.length > 0) {
            currentProject.has_pd = true;
            if (chkStagePd) chkStagePd.checked = true;
            currentProject.sections.forEach((pSec) => {
              if ((pSec.stage || "П") === "П" && mappedPdIds.includes(pSec.id)) {
                pSec.enabled = true;
              }
            });
          }
        }
      }
      await syncSectionsWithBackend();
    });
  });

  document.querySelectorAll("input[data-field]").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const field = e.target.dataset.field;
      currentProject.sections[idx][field] = e.target.value;
      if (field === "code_mark") recalculateCiphers();
    });
  });
}

btnSelectAll.addEventListener("click", async () => {
  if (!currentProject) return;
  const wantPd = chkStagePd ? chkStagePd.checked : true;
  const wantRd = chkStageRd ? chkStageRd.checked : false;
  currentProject.sections.forEach((s) => {
    const st = s.stage || "П";
    if (st === "П" && wantPd) s.enabled = true;
    if (st === "Р" && wantRd) s.enabled = true;
  });
  await syncSectionsWithBackend();
});

btnUnselectAll.addEventListener("click", async () => {
  if (!currentProject) return;
  currentProject.sections.forEach((s) => (s.enabled = false));
  await syncSectionsWithBackend();
});

// ==========================================
// МОДУЛЬ: КАЛЕНДАРНЫЙ ГРАФИК (НЕДЕЛИ + МЕСЯЦЫ + WBS)
// ==========================================

const SCHEDULE_GROUPS = {
  precontract: { label: "0. Организационно-договорной этап", barClass: "bg-slate-600 hover:bg-slate-700" },
  survey: { label: "1. Сбор ИД и изыскания", barClass: "bg-emerald-500 hover:bg-emerald-600" },
  tx_concept: { label: "2. Согласование технологии и Генплана", barClass: "bg-orange-500 hover:bg-orange-600" },
  pd: { label: "3. Проектная документация (стадия ПД)", barClass: "bg-blue-600 hover:bg-blue-700" },
  approval: { label: "4. Согласование с Заказчиком", barClass: "bg-amber-500 hover:bg-amber-600" },
  expertise: { label: "5. Экспертиза (ИИ + ПД + Сметы)", barClass: "bg-purple-600 hover:bg-purple-700" },
  rd: { label: "6. Рабочая документация (стадия РД)", barClass: "bg-teal-600 hover:bg-teal-700" },
  other: { label: "7. Разрешение на строительство и ввод", barClass: "bg-slate-500 hover:bg-slate-600" },
};

const RESP_PARTIES = ["Проектировщик", "Заказчик", "Экспертиза", "Подрядчик", "Заказчик / Проектировщик"];
const PHASE_STATUSES = ["В работе", "На согласовании", "Согласовано", "Замечания", "Завершено"];

const MONTH_NAMES_SHORT = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];

function resolveScheduleLocal() {
  if (!currentProject || !currentProject.schedule_phases) return;
  const phases = currentProject.schedule_phases;
  const byId = {};
  phases.forEach((p, i) => {
    if (!p.id) p.id = i + 1;
    byId[p.id] = p;
  });

  for (let pass = 0; pass < phases.length; pass++) {
    phases.forEach((p) => {
      if (p.enabled === false) return;
      if (p.depends_on && p.depends_on.length > 0) {
        let maxEnd = 0;
        p.depends_on.forEach((pid) => {
          const parent = byId[pid];
          if (parent && parent.enabled !== false) {
            const pDur = parent.milestone ? 0 : Math.max(1, parent.duration_weeks || 1);
            const pEnd = (parent.start_week || 1) + pDur;
            if (pEnd > maxEnd) maxEnd = pEnd;
          }
        });
        if (maxEnd > 0) {
          p.start_week = Math.max(1, maxEnd + (p.lag_weeks || 0));
        }
      }
      p.start_week = Math.max(1, parseInt(p.start_week, 10) || 1);
      p.duration_weeks = p.milestone ? 0 : Math.max(1, parseInt(p.duration_weeks, 10) || 1);
    });
  }
}

async function rebuildScheduleBackend(detailOverride = null) {
  if (!currentProject) return;
  syncProjectFromInputs();
  if (detailOverride) currentProject.schedule_detail = detailOverride;
  const q = currentProject.schedule_detail ? `?detail=${currentProject.schedule_detail}` : "";
  try {
    const res = await fetch(`/api/rebuild-schedule${q}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentProject),
    });
    if (res.ok) {
      currentProject = await res.json();
      renderScheduleTable();
    }
  } catch (err) {
    console.error("Ошибка перестроения графика:", err);
  }
}

// Чекбоксы фильтрации блоков графика (Этап 0, Изыскания, Концепция, Согласования, Экспертиза, РнС)
function setupScheduleBlockFilters() {
  const mapFilters = [
    { id: "chkFilterPrecontract", groups: ["precontract"] },
    { id: "chkFilterSurvey", groups: ["survey"] },
    { id: "chkFilterConcept", groups: ["tx_concept"] },
    { id: "chkFilterApproval", groups: ["approval"] },
    { id: "chkFilterExpertise", groups: ["expertise"] },
    { id: "chkFilterPermit", groups: ["other"] },
  ];

  mapFilters.forEach(({ id, groups }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("change", (e) => {
      if (!currentProject || !currentProject.schedule_phases) return;
      const checked = e.target.checked;
      currentProject.schedule_phases.forEach((p) => {
        if (groups.includes(p.group)) {
          p.enabled = checked;
        }
      });
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });
}
setupScheduleBlockFilters();

const chkToggleApprovalDates = document.getElementById("chkToggleApprovalDates");
if (chkToggleApprovalDates) {
  chkToggleApprovalDates.addEventListener("change", () => {
    renderScheduleTable();
  });
}

if (btnSchedDetailSections) {
  btnSchedDetailSections.addEventListener("click", () => rebuildScheduleBackend("sections"));
}
if (btnSchedDetailStages) {
  btnSchedDetailStages.addEventListener("click", () => rebuildScheduleBackend("stages"));
}
if (btnRebuildSchedule) {
  btnRebuildSchedule.addEventListener("click", () => rebuildScheduleBackend());
}

if (btnAddPhase) {
  btnAddPhase.addEventListener("click", () => {
    if (!currentProject) return;
    const phases = currentProject.schedule_phases || [];
    const maxId = phases.reduce((m, p) => Math.max(m, p.id || 0), 0);
    const lastPhase = phases[phases.length - 1];
    phases.push({
      id: maxId + 1,
      name: "Новый этап работ",
      group: lastPhase ? lastPhase.group : "pd",
      start_week: lastPhase ? lastPhase.start_week : 1,
      duration_weeks: 3,
      depends_on: lastPhase ? [lastPhase.id] : [],
      lag_weeks: 0,
      milestone: false,
      note: "",
    });
    resolveScheduleLocal();
    renderScheduleTable();
  });
}

if (btnAddMilestone) {
  btnAddMilestone.addEventListener("click", () => {
    if (!currentProject) return;
    const phases = currentProject.schedule_phases || [];
    const maxId = phases.reduce((m, p) => Math.max(m, p.id || 0), 0);
    const lastPhase = phases[phases.length - 1];
    phases.push({
      id: maxId + 1,
      name: "Контрольная точка (веха)",
      group: lastPhase ? lastPhase.group : "approval",
      start_week: lastPhase ? lastPhase.start_week : 1,
      duration_weeks: 0,
      depends_on: lastPhase ? [lastPhase.id] : [],
      lag_weeks: 0,
      milestone: true,
      note: "Контрольное событие",
    });
    resolveScheduleLocal();
    renderScheduleTable();
  });
}

function renderScheduleTable() {
  if (!currentProject || !currentProject.schedule_phases) return;

  resolveScheduleLocal();

  const detail = currentProject.schedule_detail || "sections";
  if (btnSchedDetailSections && btnSchedDetailStages) {
    if (detail === "sections") {
      btnSchedDetailSections.className = "px-3 py-1.5 rounded-md font-semibold transition bg-blue-600 text-white shadow-xs";
      btnSchedDetailStages.className = "px-3 py-1.5 rounded-md font-medium text-slate-600 hover:text-slate-900 transition";
    } else {
      btnSchedDetailStages.className = "px-3 py-1.5 rounded-md font-semibold transition bg-blue-600 text-white shadow-xs";
      btnSchedDetailSections.className = "px-3 py-1.5 rounded-md font-medium text-slate-600 hover:text-slate-900 transition";
    }
  }

  const phases = currentProject.schedule_phases;
  const maxWeekRaw = phases.reduce((max, p) => {
    if (p.enabled === false) return max;
    const endW = p.milestone ? p.start_week : p.start_week + Math.max(1, p.duration_weeks) - 1;
    return Math.max(max, endW);
  }, 8);

  const numMonths = Math.max(2, Math.ceil(maxWeekRaw / 4));
  const numWeeks = numMonths * 4;
  const approxMonths = (maxWeekRaw / 4.33).toFixed(1);
  totalDurationLabel.textContent = `${maxWeekRaw} нед. (~${approxMonths} мес.)`;

  let startDt = null;
  if (inputStartDate && inputStartDate.value) {
    const parsed = new Date(inputStartDate.value + "T00:00:00");
    if (!isNaN(parsed.getTime())) startDt = parsed;
  }
  if (finishDateLabel) {
    if (startDt) {
      const endDt = new Date(startDt.getTime() + maxWeekRaw * 7 * 86400000);
      finishDateLabel.textContent = endDt.toLocaleDateString("ru-RU");
    } else {
      finishDateLabel.textContent = "—";
    }
  }

  // 1. Двухуровневая шапка с понятными названиями колонок
  const chkToggleApprovalDates = document.getElementById("chkToggleApprovalDates");
  const showApprovalCols = chkToggleApprovalDates ? chkToggleApprovalDates.checked : true;

  if (scheduleMonthHeaderRow) {
    let mHtml = `
      <th rowspan="2" class="py-2 px-1 w-10 text-center border-b border-slate-700" title="Включить / исключить этап из графика">Вкл</th>
      <th rowspan="2" class="py-2 px-2 w-10 text-center border-l border-b border-slate-700">№</th>
      <th rowspan="2" class="py-2 px-3 min-w-[250px] border-l border-b border-slate-700">Наименование этапа / раздела</th>
      <th rowspan="2" class="py-2 px-2 w-28 text-center border-l border-b border-slate-700">Вид работ</th>
      <th rowspan="2" class="py-2 px-2 w-28 text-center border-l border-b border-slate-700">Ответственный</th>
      <th rowspan="2" class="py-2 px-2 w-24 text-center border-l border-b border-slate-700">Статус</th>
      <th rowspan="2" class="py-2 px-1.5 w-16 text-center border-l border-b border-slate-700" title="Номер недели начала этапа от старта проекта">Начало</th>
      <th rowspan="2" class="py-2 px-1.5 w-16 text-center border-l border-b border-slate-700" title="Продолжительность выполнения этапа в неделях">Длительн.</th>
      <th rowspan="2" class="py-2 px-1.5 w-16 text-center border-l border-b border-slate-700">Действия</th>
    `;

    if (showApprovalCols) {
      mHtml += `
        <th rowspan="2" class="py-2 px-1.5 w-24 text-center border-l border-b border-amber-600 bg-amber-900/60" title="Дата передачи документации Заказчику на рассмотрение">Передано<br>Заказчику</th>
        <th rowspan="2" class="py-2 px-1.5 w-24 text-center border-l border-b border-amber-600 bg-amber-900/60" title="Дата поступления замечаний от Заказчика (1-й круг)">Замечания 1</th>
        <th rowspan="2" class="py-2 px-1.5 w-24 text-center border-l border-b border-amber-600 bg-amber-900/60" title="Дата отправки ответов и снятия замечаний 1">Ответы 1</th>
        <th rowspan="2" class="py-2 px-1.5 w-24 text-center border-l border-b border-amber-600 bg-amber-900/60" title="Дата повторных замечаний от Заказчика (2-й круг)">Замечания 2</th>
        <th rowspan="2" class="py-2 px-1.5 w-24 text-center border-l border-b border-amber-600 bg-amber-900/60" title="Дата финального согласования / ответов 2">Ответы 2</th>
        <th rowspan="2" class="py-2 px-2 w-32 text-center border-l border-b border-amber-600 bg-amber-900/60" title="Статус / результат согласования с Заказчиком">Результат<br>согласования</th>
      `;
    }

    for (let m = 0; m < numMonths; m++) {
      let label = `Месяц ${m + 1}`;
      if (startDt) {
        const mDate = new Date(startDt.getTime() + m * 30.4375 * 86400000);
        label = `М${m + 1} (${MONTH_NAMES_SHORT[mDate.getMonth()]} ${String(mDate.getFullYear()).slice(-2)})`;
      }
      mHtml += `<th colspan="4" class="py-1.5 px-1 text-center text-[11px] font-bold bg-slate-800 border-l border-b border-slate-600">${label}</th>`;
    }
    mHtml += `<th rowspan="2" class="py-2 px-3 min-w-[150px] border-l border-b border-slate-700">Примечание</th>`;
    scheduleMonthHeaderRow.innerHTML = mHtml;
  }

  let wHtml = "";
  for (let w = 1; w <= numWeeks; w++) {
    wHtml += `<th class="py-1 px-0.5 text-center text-[10px] font-mono w-7 bg-slate-700 border-l border-slate-600">Н${w}</th>`;
  }
  scheduleHeaderRow.innerHTML = wHtml;

  // 2. Отрисовка строк графика с группировкой по видам работ
  scheduleTableBody.innerHTML = "";
  let lastGroup = null;
  const extraCols = showApprovalCols ? 6 : 0;
  const totalCols = 10 + extraCols + numWeeks;

  phases.forEach((phase, idx) => {
    const isPhaseEnabled = phase.enabled !== false;
    const grp = phase.group || "pd";
    if (grp !== lastGroup) {
      lastGroup = grp;
      const grpInfo = SCHEDULE_GROUPS[grp] || SCHEDULE_GROUPS.other;
      const grpTr = document.createElement("tr");
      grpTr.className = "bg-slate-100/90 font-bold text-[11px] text-slate-700 uppercase tracking-wider";
      grpTr.innerHTML = `<td colspan="${totalCols}" class="py-1.5 px-3 border-t border-b border-slate-200">${grpInfo.label}</td>`;
      scheduleTableBody.appendChild(grpTr);
    }

    const tr = document.createElement("tr");
    tr.className = `hover:bg-blue-50/30 transition border-b border-slate-100 ${!isPhaseEnabled ? "opacity-40 bg-slate-50" : ""} ${phase.milestone ? "bg-amber-50/40" : ""}`;

    const pStart = phase.start_week;
    const pEnd = phase.milestone ? phase.start_week : phase.start_week + Math.max(1, phase.duration_weeks) - 1;
    const grpInfo = SCHEDULE_GROUPS[grp] || SCHEDULE_GROUPS.other;

    let groupOptionsHtml = "";
    Object.entries(SCHEDULE_GROUPS).forEach(([gKey, gVal]) => {
      const shortLbl = gVal.label.replace(/^\d+\.\s*/, "");
      groupOptionsHtml += `<option value="${gKey}" ${gKey === grp ? "selected" : ""}>${shortLbl}</option>`;
    });

    let respOptionsHtml = "";
    RESP_PARTIES.forEach((rp) => {
      respOptionsHtml += `<option value="${rp}" ${(phase.resp_party || "Проектировщик") === rp ? "selected" : ""}>${rp}</option>`;
    });

    let statusOptionsHtml = "";
    PHASE_STATUSES.forEach((st) => {
      statusOptionsHtml += `<option value="${st}" ${(phase.status || "В работе") === st ? "selected" : ""}>${st}</option>`;
    });

    let weekCellsHtml = "";
    for (let w = 1; w <= numWeeks; w++) {
      const isMonthStart = (w - 1) % 4 === 0;
      const borderCls = isMonthStart ? "border-l border-slate-300" : "border-l border-slate-100";
      if (!isPhaseEnabled) {
        weekCellsHtml += `<td class="p-0.5 ${borderCls} bg-slate-50"></td>`;
      } else if (phase.milestone) {
        if (w === pStart) {
          weekCellsHtml += `
            <td class="p-0.5 text-center ${borderCls} cursor-pointer gantt-cell" data-idx="${idx}" data-week="${w}" title="Кликните для переноса вехи на Н${w}">
              <div class="h-5 flex items-center justify-center text-amber-600 text-sm font-black">◆</div>
            </td>
          `;
        } else {
          weekCellsHtml += `<td class="p-0.5 ${borderCls} cursor-pointer hover:bg-amber-100/50 gantt-cell" data-idx="${idx}" data-week="${w}" title="Кликните для переноса вехи на Н${w}"></td>`;
        }
      } else if (w >= pStart && w <= pEnd) {
        const isFirst = w === pStart;
        const isLast = w === pEnd;
        const roundCls = `${isFirst ? "rounded-l" : ""} ${isLast ? "rounded-r" : ""}`;
        weekCellsHtml += `
          <td class="p-0.5 text-center ${borderCls} cursor-pointer gantt-cell" data-idx="${idx}" data-week="${w}" title="Н${pStart}–Н${pEnd} (${phase.duration_weeks} нед.). Клик = старт, Shift+клик = длительность">
            <div class="h-5 ${roundCls} ${grpInfo.barClass} flex items-center justify-center text-white text-[9px] font-bold shadow-2xs">
              ${isFirst ? phase.duration_weeks + "н" : ""}
            </div>
          </td>
        `;
      } else {
        weekCellsHtml += `<td class="p-0.5 ${borderCls} cursor-pointer hover:bg-blue-100/40 gantt-cell" data-idx="${idx}" data-week="${w}" title="Кликните, чтобы поставить начало на Н${w} (Shift+клик — растянуть длительность до Н${w})"></td>`;
      }
    }

    tr.innerHTML = `
      <td class="py-1.5 px-1 text-center">
        <input type="checkbox" class="sched-chk-enable rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer" data-idx="${idx}" ${isPhaseEnabled ? "checked" : ""} title="Включить / исключить этап из графика">
      </td>
      <td class="py-1.5 px-1 text-center font-mono text-xs font-bold text-slate-600 border-l border-slate-100">${phase.id}</td>
      <td class="py-1.5 px-2 border-l border-slate-100">
        <div class="flex items-center gap-1">
          <button class="sched-milestone-btn text-xs px-1 rounded ${phase.milestone ? "text-amber-600 font-bold" : "text-slate-300 hover:text-amber-500"}" data-idx="${idx}" title="Переключить: Этап / Контрольная веха ◆">◆</button>
          <input type="text" class="sched-inp-name w-full text-xs ${phase.milestone ? "font-bold text-amber-900" : "font-medium text-slate-800"} border border-transparent hover:border-slate-200 focus:border-blue-400 focus:bg-white rounded px-1.5 py-0.5 bg-transparent" data-idx="${idx}" value="${phase.name}">
        </div>
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <select class="sched-inp-group w-full text-[11px] border border-slate-200 rounded px-1 py-0.5 bg-white" data-idx="${idx}">
          ${groupOptionsHtml}
        </select>
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <select class="sched-inp-resp w-full text-[11px] border border-slate-200 rounded px-1 py-0.5 bg-white text-slate-700" data-idx="${idx}">
          ${respOptionsHtml}
        </select>
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <select class="sched-inp-status w-full text-[11px] border border-slate-200 rounded px-1 py-0.5 bg-white font-medium ${phase.status === 'Согласовано' ? 'text-emerald-700' : phase.status === 'Замечания' ? 'text-rose-700' : 'text-slate-700'}" data-idx="${idx}">
          ${statusOptionsHtml}
        </select>
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <input type="number" step="1" min="1" max="200" class="sched-inp-start w-full text-center font-mono text-xs font-semibold border border-slate-200 rounded px-1 py-0.5 bg-white text-blue-700" data-idx="${idx}" value="${phase.start_week}" title="Неделя начала работ от старта проекта">
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <input type="number" step="1" min="0" max="100" class="sched-inp-dur w-full text-center font-mono text-xs font-semibold border border-slate-200 rounded px-1 py-0.5 ${phase.milestone ? "bg-slate-100 text-slate-400" : "bg-white"}" data-idx="${idx}" value="${phase.milestone ? 0 : phase.duration_weeks}" ${phase.milestone ? "disabled" : ""} title="Длительность этапа в неделях">
      </td>
      <td class="py-1.5 px-1 text-center border-l border-slate-100 whitespace-nowrap">
        <button class="sched-move-up text-slate-400 hover:text-blue-600 px-1" data-idx="${idx}" title="Переместить выше"><i class="fa-solid fa-arrow-up"></i></button>
        <button class="sched-move-down text-slate-400 hover:text-blue-600 px-1" data-idx="${idx}" title="Переместить ниже"><i class="fa-solid fa-arrow-down"></i></button>
        <button class="sched-delete text-slate-400 hover:text-rose-600 px-1" data-idx="${idx}" title="Удалить строку"><i class="fa-solid fa-xmark"></i></button>
      </td>
      ${showApprovalCols ? `
        <td class="py-1 px-1 border-l border-amber-200 bg-amber-50/30">
          <input type="text" class="sched-inp-appr-sent w-full text-center font-mono text-[11px] border border-transparent hover:border-amber-300 focus:border-amber-500 rounded px-1 py-0.5 bg-transparent" placeholder="ДД.ММ.ГГ" data-idx="${idx}" value="${phase.sent_to_client_date || ""}">
        </td>
        <td class="py-1 px-1 border-l border-amber-200 bg-amber-50/30">
          <input type="text" class="sched-inp-appr-rem1 w-full text-center font-mono text-[11px] border border-transparent hover:border-amber-300 focus:border-amber-500 rounded px-1 py-0.5 bg-transparent" placeholder="ДД.ММ.ГГ" data-idx="${idx}" value="${phase.client_remarks_1_date || ""}">
        </td>
        <td class="py-1 px-1 border-l border-amber-200 bg-amber-50/30">
          <input type="text" class="sched-inp-appr-ans1 w-full text-center font-mono text-[11px] border border-transparent hover:border-amber-300 focus:border-amber-500 rounded px-1 py-0.5 bg-transparent" placeholder="ДД.ММ.ГГ" data-idx="${idx}" value="${phase.designer_answers_1_date || ""}">
        </td>
        <td class="py-1 px-1 border-l border-amber-200 bg-amber-50/30">
          <input type="text" class="sched-inp-appr-rem2 w-full text-center font-mono text-[11px] border border-transparent hover:border-amber-300 focus:border-amber-500 rounded px-1 py-0.5 bg-transparent" placeholder="ДД.ММ.ГГ" data-idx="${idx}" value="${phase.client_remarks_2_date || ""}">
        </td>
        <td class="py-1 px-1 border-l border-amber-200 bg-amber-50/30">
          <input type="text" class="sched-inp-appr-ans2 w-full text-center font-mono text-[11px] border border-transparent hover:border-amber-300 focus:border-amber-500 rounded px-1 py-0.5 bg-transparent" placeholder="ДД.ММ.ГГ" data-idx="${idx}" value="${phase.designer_answers_2_date || ""}">
        </td>
        <td class="py-1 px-1 border-l border-amber-200 bg-amber-50/30">
          <input type="text" class="sched-inp-appr-res w-full text-[11px] border border-transparent hover:border-amber-300 focus:border-amber-500 rounded px-1 py-0.5 bg-transparent" placeholder="Результат..." data-idx="${idx}" value="${phase.approval_result || ""}">
        </td>
      ` : ""}
      ${weekCellsHtml}
      <td class="py-1.5 px-2 border-l border-slate-100">
        <input type="text" class="sched-inp-note w-full text-xs text-slate-500 border border-transparent hover:border-slate-200 focus:border-blue-400 focus:bg-white rounded px-1.5 py-0.5 bg-transparent" placeholder="Примечание..." data-idx="${idx}" value="${phase.note || ""}">
      </td>
    `;

    scheduleTableBody.appendChild(tr);
  });

  document.querySelectorAll(".sched-chk-enable").forEach((chk) => {
    chk.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].enabled = e.target.checked;
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-inp-resp").forEach((sel) => {
    sel.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].resp_party = e.target.value;
    });
  });

  document.querySelectorAll(".sched-inp-status").forEach((sel) => {
    sel.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].status = e.target.value;
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-inp-appr-sent").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].sent_to_client_date = e.target.value;
    });
  });
  document.querySelectorAll(".sched-inp-appr-rem1").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].client_remarks_1_date = e.target.value;
    });
  });
  document.querySelectorAll(".sched-inp-appr-ans1").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].designer_answers_1_date = e.target.value;
    });
  });
  document.querySelectorAll(".sched-inp-appr-rem2").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].client_remarks_2_date = e.target.value;
    });
  });
  document.querySelectorAll(".sched-inp-appr-ans2").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].designer_answers_2_date = e.target.value;
    });
  });
  document.querySelectorAll(".sched-inp-appr-res").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].approval_result = e.target.value;
    });
  });

  document.querySelectorAll(".sched-inp-name").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].name = e.target.value;
    });
  });

  document.querySelectorAll(".sched-inp-note").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].note = e.target.value;
    });
  });

  document.querySelectorAll(".sched-inp-group").forEach((sel) => {
    sel.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].group = e.target.value;
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-inp-deps").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const raw = e.target.value.trim();
      if (!raw || raw === "—" || raw.toLowerCase() === "нет") {
        phases[idx].depends_on = [];
      } else {
        const ids = raw
          .split(/[,;\s]+/)
          .map((x) => parseInt(x, 10))
          .filter((n) => !isNaN(n) && n > 0 && n !== phases[idx].id);
        phases[idx].depends_on = ids;
      }
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-inp-lag").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      phases[idx].lag_weeks = parseInt(e.target.value, 10) || 0;
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-inp-start").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const newStart = Math.max(1, parseInt(e.target.value, 10) || 1);
      phases[idx].depends_on = [];
      phases[idx].start_week = newStart;
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-inp-dur").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const val = Math.max(0, parseInt(e.target.value, 10) || 0);
      if (val === 0) {
        phases[idx].milestone = true;
        phases[idx].duration_weeks = 0;
      } else {
        phases[idx].milestone = false;
        phases[idx].duration_weeks = val;
      }
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-milestone-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.currentTarget.dataset.idx, 10);
      phases[idx].milestone = !phases[idx].milestone;
      phases[idx].duration_weeks = phases[idx].milestone ? 0 : Math.max(1, phases[idx].duration_weeks || 2);
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-move-up").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.currentTarget.dataset.idx, 10);
      if (idx <= 0) return;
      const tmp = phases[idx - 1];
      phases[idx - 1] = phases[idx];
      phases[idx] = tmp;
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-move-down").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.currentTarget.dataset.idx, 10);
      if (idx >= phases.length - 1) return;
      const tmp = phases[idx + 1];
      phases[idx + 1] = phases[idx];
      phases[idx] = tmp;
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".sched-delete").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.currentTarget.dataset.idx, 10);
      const removedId = phases[idx].id;
      phases.splice(idx, 1);
      phases.forEach((p) => {
        if (p.depends_on) {
          p.depends_on = p.depends_on.filter((d) => d !== removedId);
        }
      });
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });

  document.querySelectorAll(".gantt-cell").forEach((cell) => {
    cell.addEventListener("click", (e) => {
      const idx = parseInt(e.currentTarget.dataset.idx, 10);
      const clickedWeek = parseInt(e.currentTarget.dataset.week, 10);
      const p = phases[idx];
      if (!p) return;

      if (e.shiftKey && !p.milestone) {
        if (clickedWeek >= p.start_week) {
          p.duration_weeks = clickedWeek - p.start_week + 1;
        } else {
          const oldEnd = p.start_week + p.duration_weeks - 1;
          p.depends_on = [];
          p.start_week = clickedWeek;
          p.duration_weeks = Math.max(1, oldEnd - clickedWeek + 1);
        }
      } else {
        p.depends_on = [];
        p.start_week = clickedWeek;
      }
      resolveScheduleLocal();
      renderScheduleTable();
    });
  });
}

// Переключение вкладок
tabBtnSections.addEventListener("click", () => switchTab("sections"));
tabBtnSchedule.addEventListener("click", () => switchTab("schedule"));

function switchTab(tab) {
  activeTab = tab;

  [tabBtnSections, tabBtnSchedule].forEach((btn) => {
    if (btn) {
      btn.className = "py-3.5 px-4 font-medium text-sm text-slate-500 hover:text-slate-800 border-b-2 border-transparent flex items-center";
    }
  });

  tabContentSections.classList.add("hidden");
  tabContentSchedule.classList.add("hidden");

  if (tab === "sections") {
    tabBtnSections.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-blue-600 text-blue-600 flex items-center";
    tabContentSections.classList.remove("hidden");
  } else if (tab === "schedule") {
    tabBtnSchedule.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-blue-600 text-blue-600 flex items-center";
    tabContentSchedule.classList.remove("hidden");
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

    let fname = "Ведомость_состава_проекта.docx";
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
    btnDownloadDocx.innerHTML = '<i class="fa-solid fa-file-word mr-2 text-blue-200"></i> Скачать Ведомость состава проекта (.docx)';
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
    btnDownloadXlsx.innerHTML = '<i class="fa-solid fa-calendar-days mr-2 text-emerald-200"></i> Скачать Календарный график (.xlsx)';
  }
});
