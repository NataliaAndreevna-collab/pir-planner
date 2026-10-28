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

// Кнопка парсинга ТЗ
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

    renderInsights(data.detected_features);
    populateForm(currentProject);
    renderSectionsTable();
    renderScheduleTable();
    if (typeof renderCostTab === "function") renderCostTab();

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
      if (typeof renderCostTab === "function") renderCostTab();
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
  if (typeof renderCostTab === "function") renderCostTab();
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
  if (typeof renderCostTab === "function") renderCostTab();
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
  if (typeof renderCostTab === "function") renderCostTab();
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
  survey: { label: "1. Обследование и изыскания", barClass: "bg-emerald-500 hover:bg-emerald-600" },
  pd: { label: "2. Проектная документация (ПД)", barClass: "bg-blue-600 hover:bg-blue-700" },
  approval: { label: "3. Согласования", barClass: "bg-amber-500 hover:bg-amber-600" },
  expertise: { label: "4. Экспертиза", barClass: "bg-purple-600 hover:bg-purple-700" },
  rd: { label: "5. Рабочая документация (РД)", barClass: "bg-cyan-600 hover:bg-cyan-700" },
  other: { label: "6. Прочие работы", barClass: "bg-slate-600 hover:bg-slate-700" },
};

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
      if (p.depends_on && p.depends_on.length > 0) {
        let maxEnd = 0;
        p.depends_on.forEach((pid) => {
          const parent = byId[pid];
          if (parent) {
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
  if (scheduleMonthHeaderRow) {
    let mHtml = `
      <th rowspan="2" class="py-2 px-2 w-12 text-center border-b border-slate-700" title="Порядковый номер этапа в графике">№<br>этапа</th>
      <th rowspan="2" class="py-2 px-3 min-w-[240px] border-b border-slate-700">Наименование этапа / раздела</th>
      <th rowspan="2" class="py-2 px-2 w-32 text-center border-l border-b border-slate-700">Вид работ</th>
      <th rowspan="2" class="py-2 px-2 w-24 text-center border-l border-b border-slate-700" title="Укажите номер этапа, после окончания которого начинается этот этап (можно несколько через запятую)">Старт после<br>этапа №</th>
      <th rowspan="2" class="py-2 px-1.5 w-16 text-center border-l border-b border-slate-700" title="Смещение относительно предыдущего этапа в неделях (+ задержка, - параллельный нахлест)">Сдвиг,<br>нед.</th>
      <th rowspan="2" class="py-2 px-1.5 w-16 text-center border-l border-b border-slate-700" title="Номер недели начала этапа от старта проекта">Начало,<br>нед.</th>
      <th rowspan="2" class="py-2 px-1.5 w-20 text-center border-l border-b border-slate-700" title="Продолжительность выполнения этапа в неделях">Длительн.,<br>нед.</th>
      <th rowspan="2" class="py-2 px-1.5 w-20 text-center border-l border-b border-slate-700">Действия</th>
    `;
    for (let m = 0; m < numMonths; m++) {
      let label = `Месяц ${m + 1}`;
      if (startDt) {
        const mDate = new Date(startDt.getTime() + m * 30.4375 * 86400000);
        label = `М${m + 1} (${MONTH_NAMES_SHORT[mDate.getMonth()]} ${String(mDate.getFullYear()).slice(-2)})`;
      }
      mHtml += `<th colspan="4" class="py-1.5 px-1 text-center text-[11px] font-bold bg-slate-800 border-l border-b border-slate-600">${label}</th>`;
    }
    mHtml += `<th rowspan="2" class="py-2 px-3 min-w-[160px] border-l border-b border-slate-700">Примечание</th>`;
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
  const totalCols = 9 + numWeeks;

  phases.forEach((phase, idx) => {
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
    tr.className = `hover:bg-blue-50/30 transition border-b border-slate-100 ${phase.milestone ? "bg-amber-50/40" : ""}`;

    const pStart = phase.start_week;
    const pEnd = phase.milestone ? phase.start_week : phase.start_week + Math.max(1, phase.duration_weeks) - 1;
    const grpInfo = SCHEDULE_GROUPS[grp] || SCHEDULE_GROUPS.other;

    let groupOptionsHtml = "";
    Object.entries(SCHEDULE_GROUPS).forEach(([gKey, gVal]) => {
      const shortLbl = gVal.label.replace(/^\d+\.\s*/, "");
      groupOptionsHtml += `<option value="${gKey}" ${gKey === grp ? "selected" : ""}>${shortLbl}</option>`;
    });

    let weekCellsHtml = "";
    for (let w = 1; w <= numWeeks; w++) {
      const isMonthStart = (w - 1) % 4 === 0;
      const borderCls = isMonthStart ? "border-l border-slate-300" : "border-l border-slate-100";
      if (phase.milestone) {
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

    const depsVal = (phase.depends_on || []).join(", ");
    const hasDeps = phase.depends_on && phase.depends_on.length > 0;

    tr.innerHTML = `
      <td class="py-1.5 px-2 text-center font-mono text-xs font-bold text-slate-600">${phase.id}</td>
      <td class="py-1.5 px-2">
        <div class="flex items-center gap-1">
          <button class="sched-milestone-btn text-xs px-1 rounded ${phase.milestone ? "text-amber-600 font-bold" : "text-slate-300 hover:text-amber-500"}" data-idx="${idx}" title="Переключить: Этап / Контрольная веха ◆">◆</button>
          <input type="text" class="sched-inp-name w-full text-xs ${phase.milestone ? "font-bold text-amber-900" : "font-medium text-slate-800"} border border-transparent hover:border-slate-200 focus:border-blue-400 focus:bg-white rounded px-1.5 py-0.5 bg-transparent" data-idx="${idx}" value="${phase.name}">
        </div>
      </td>
      <td class="py-1.5 px-1.5 border-l border-slate-100">
        <select class="sched-inp-group w-full text-[11px] border border-slate-200 rounded px-1 py-0.5 bg-white" data-idx="${idx}">
          ${groupOptionsHtml}
        </select>
      </td>
      <td class="py-1.5 px-1.5 border-l border-slate-100">
        <input type="text" class="sched-inp-deps w-full text-center font-mono text-xs border border-slate-200 rounded px-1 py-0.5 bg-white" placeholder="нет" data-idx="${idx}" value="${depsVal}" title="Укажите номер этапа, после которого стартует этот этап (например: 1 или 1, 2)">
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <input type="number" step="1" min="-20" max="52" class="sched-inp-lag w-full text-center font-mono text-xs border border-slate-200 rounded px-1 py-0.5 ${hasDeps ? "bg-white" : "bg-slate-100 text-slate-400"}" data-idx="${idx}" value="${phase.lag_weeks || 0}" ${hasDeps ? "" : "disabled"} title="Смещение в неделях относительно окончания предыдущего этапа (+ задержка, - нахлест)">
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <input type="number" step="1" min="1" max="200" class="sched-inp-start w-full text-center font-mono text-xs font-semibold border border-slate-200 rounded px-1 py-0.5 ${hasDeps ? "bg-slate-100 text-slate-500" : "bg-white text-blue-700"}" data-idx="${idx}" value="${phase.start_week}" title="Неделя начала работ от старта проекта">
      </td>
      <td class="py-1.5 px-1 border-l border-slate-100">
        <input type="number" step="1" min="0" max="100" class="sched-inp-dur w-full text-center font-mono text-xs font-semibold border border-slate-200 rounded px-1 py-0.5 ${phase.milestone ? "bg-slate-100 text-slate-400" : "bg-white"}" data-idx="${idx}" value="${phase.milestone ? 0 : phase.duration_weeks}" ${phase.milestone ? "disabled" : ""} title="Длительность этапа в неделях">
      </td>
      <td class="py-1.5 px-1 text-center border-l border-slate-100 whitespace-nowrap">
        <button class="sched-move-up text-slate-400 hover:text-blue-600 px-1" data-idx="${idx}" title="Переместить выше"><i class="fa-solid fa-arrow-up"></i></button>
        <button class="sched-move-down text-slate-400 hover:text-blue-600 px-1" data-idx="${idx}" title="Переместить ниже"><i class="fa-solid fa-arrow-down"></i></button>
        <button class="sched-delete text-slate-400 hover:text-rose-600 px-1" data-idx="${idx}" title="Удалить строку"><i class="fa-solid fa-xmark"></i></button>
      </td>
      ${weekCellsHtml}
      <td class="py-1.5 px-2 border-l border-slate-100">
        <input type="text" class="sched-inp-note w-full text-xs text-slate-500 border border-transparent hover:border-slate-200 focus:border-blue-400 focus:bg-white rounded px-1.5 py-0.5 bg-transparent" placeholder="Примечание..." data-idx="${idx}" value="${phase.note || ""}">
      </td>
    `;

    scheduleTableBody.appendChild(tr);
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
const tabBtnCost = document.getElementById("tabBtnCost");
const tabContentCost = document.getElementById("tabContentCost");
const costTotalBadge = document.getElementById("costTotalBadge");

tabBtnSections.addEventListener("click", () => switchTab("sections"));
tabBtnSchedule.addEventListener("click", () => switchTab("schedule"));
if (tabBtnCost) tabBtnCost.addEventListener("click", () => switchTab("cost"));

function switchTab(tab) {
  activeTab = tab;

  [tabBtnSections, tabBtnSchedule, tabBtnCost].forEach((btn) => {
    if (btn) {
      btn.className = "py-3.5 px-4 font-medium text-sm text-slate-500 hover:text-slate-800 border-b-2 border-transparent flex items-center";
    }
  });

  tabContentSections.classList.add("hidden");
  tabContentSchedule.classList.add("hidden");
  if (tabContentCost) tabContentCost.classList.add("hidden");

  if (tab === "sections") {
    tabBtnSections.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-blue-600 text-blue-600 flex items-center";
    tabContentSections.classList.remove("hidden");
  } else if (tab === "schedule") {
    tabBtnSchedule.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-blue-600 text-blue-600 flex items-center";
    tabContentSchedule.classList.remove("hidden");
    renderScheduleTable();
  } else if (tab === "cost" && tabContentCost) {
    tabBtnCost.className = "py-3.5 px-4 font-semibold text-sm border-b-2 border-emerald-600 text-emerald-700 flex items-center";
    tabContentCost.classList.remove("hidden");
    renderCostTab();
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

// ==========================================
// МОДУЛЬ 3: РАСЧЁТ СТОИМОСТИ ПИР И НОРМАТИВНАЯ БАЗА
// ==========================================

let normativeCatalog = null;
let indicesStaleness = null;

function formatRub(val) {
  const n = Number(val) || 0;
  return n.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + " ₽";
}

async function loadNormativeCatalog() {
  try {
    const res = await fetch("/api/normative-catalog");
    if (!res.ok) return;
    const data = await res.json();
    normativeCatalog = data.catalog;
    indicesStaleness = data.staleness;
    renderIndicesBanner();
  } catch (e) {
    console.error("Ошибка загрузки нормативной базы:", e);
  }
}

loadNormativeCatalog();

function renderIndicesBanner() {
  const banner = document.getElementById("indicesStalenessBanner");
  const statusTxt = document.getElementById("indicesStatusText");
  const subTxt = document.getElementById("indicesPeriodSubtext");
  if (!banner || !normativeCatalog) return;

  const idx = normativeCatalog.indices || {};
  const isStale = indicesStaleness ? indicesStaleness.is_stale : false;

  if (isStale) {
    banner.className = "rounded-xl border border-amber-300 bg-amber-50 p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs";
    statusTxt.textContent = indicesStaleness.warning_message;
  } else {
    banner.className = "rounded-xl border border-emerald-300 bg-emerald-50/70 p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs";
    statusTxt.textContent = indicesStaleness ? indicesStaleness.warning_message : "Индексы Минстроя РФ актуальны.";
  }

  const pir = idx.pir || {};
  const surv = idx.survey || {};
  subTxt.textContent = `${idx.period_label || ""} (${idx.letter_ref || ""}) — ПИР: [1995=${pir["1995"]}; 2001=${pir["2001"]}; 2021=${pir["2021"]}; 2022=${pir["2022"]}; 2023=${pir["2023"]}; 2024=${pir["2024"]}] | ИИ(2024)=${surv["2024"]}`;

  // Заполняем поля редактора индексов
  const setVal = (id, v) => {
    const el = document.getElementById(id);
    if (el && v !== undefined) el.value = v;
  };
  setVal("inpIdxPeriodLabel", idx.period_label || "");
  setVal("inpIdxLetterRef", idx.letter_ref || "");
  setVal("inpIdxPir1995", pir["1995"]);
  setVal("inpIdxPir2001", pir["2001"]);
  setVal("inpIdxPir2021", pir["2021"]);
  setVal("inpIdxPir2022", pir["2022"]);
  setVal("inpIdxPir2023", pir["2023"]);
  setVal("inpIdxPir2024", pir["2024"]);
  setVal("inpIdxSurvey2024", surv["2024"]);
  setVal("inpIdxSurvey2001", surv["2001"]);
  setVal("inpIdxSmr2001", idx.smr_to_2001_index || 11.45);
}

const btnToggleIndicesEditor = document.getElementById("btnToggleIndicesEditor");
const indicesEditorPanel = document.getElementById("indicesEditorPanel");
if (btnToggleIndicesEditor && indicesEditorPanel) {
  btnToggleIndicesEditor.addEventListener("click", () => {
    indicesEditorPanel.classList.toggle("hidden");
  });
}

const btnSaveIndices = document.getElementById("btnSaveIndices");
if (btnSaveIndices) {
  btnSaveIndices.addEventListener("click", async () => {
    const getNum = (id, def) => parseFloat(document.getElementById(id)?.value) || def;
    const payload = {
      period_label: document.getElementById("inpIdxPeriodLabel")?.value || "",
      letter_ref: document.getElementById("inpIdxLetterRef")?.value || "",
      smr_to_2001_index: getNum("inpIdxSmr2001", 11.45),
      pir: {
        "1995": getNum("inpIdxPir1995", 55.26),
        "2001": getNum("inpIdxPir2001", 7.22),
        "2021": getNum("inpIdxPir2021", 1.71),
        "2022": getNum("inpIdxPir2022", 1.56),
        "2023": getNum("inpIdxPir2023", 1.40),
        "2024": getNum("inpIdxPir2024", 1.29),
      },
      survey: {
        "2001": getNum("inpIdxSurvey2001", 7.19),
        "2024": getNum("inpIdxSurvey2024", 1.27),
      },
    };
    try {
      const res = await fetch("/api/update-indices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        normativeCatalog = data.catalog;
        indicesStaleness = data.staleness;
        renderIndicesBanner();
        indicesEditorPanel.classList.add("hidden");
        await recalculateCostBackend();
      }
    } catch (e) {
      alert("Ошибка сохранения индексов: " + e.message);
    }
  });
}

// Загрузка нового сборника (.docx или .pdf) целиком
const inputUploadCollectionFile = document.getElementById("inputUploadCollectionFile");
if (inputUploadCollectionFile) {
  inputUploadCollectionFile.addEventListener("change", async () => {
    if (!inputUploadCollectionFile.files || !inputUploadCollectionFile.files.length) return;
    const file = inputUploadCollectionFile.files[0];
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/api/upload-collection", { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Ошибка разбора файла сборника");
      }
      const data = await res.json();
      normativeCatalog = data.catalog;
      const added = data.added_collection;
      alert(`Сборник «${added.title}» (базовый уровень цен: 01.01.${added.base_year} г., распознано расценок: ${added.items.length}) успешно добавлен в базу!`);
      renderCostTab();
    } catch (e) {
      alert("Ошибка подгрузки сборника: " + e.message);
    } finally {
      inputUploadCollectionFile.value = "";
    }
  });
}

function syncCostInputsToModel() {
  if (!currentProject || !currentProject.cost_parameters) return;
  const cp = currentProject.cost_parameters;

  const vatSel = document.getElementById("selectVatMode");
  if (vatSel) {
    const v = parseFloat(vatSel.value);
    if (v === 0) {
      cp.include_vat = false;
      cp.vat_rate = 0;
    } else {
      cp.include_vat = true;
      cp.vat_rate = v;
    }
  }

  const smrInp = document.getElementById("inputSmrMln");
  if (smrInp) cp.smr_cost_mln_rub = parseFloat(smrInp.value) || 0;

  const chkRec = document.getElementById("chkCostReconstr");
  if (chkRec) cp.is_reconstruction = chkRec.checked;

  const chkBim = document.getElementById("chkCostBim");
  if (chkBim) cp.use_bim = chkBim.checked;

  const inpComp = document.getElementById("inpCostComplexity");
  if (inpComp) cp.complexity_factor = parseFloat(inpComp.value) || 1.0;

  const inpUrg = document.getElementById("inpCostUrgency");
  if (inpUrg) cp.urgency_factor = parseFloat(inpUrg.value) || 1.0;

  const inpRegSal = document.getElementById("inpRegionalSalary707");
  if (inpRegSal) cp.regional_monthly_salary_707 = parseFloat(inpRegSal.value) || 95000;

  const inpWd707 = document.getElementById("inpWorkDays707");
  if (inpWd707) cp.work_days_707 = parseFloat(inpWd707.value) || 20.6;

  const inpK3 = document.getElementById("inpK3SalaryShare707");
  if (inpK3) cp.k3_salary_share_707 = parseFloat(inpK3.value) || 0.4006;

  const inpProf707 = document.getElementById("inpProfitability707Pct");
  if (inpProf707) cp.profitability_707 = (parseFloat(inpProf707.value) || 10) / 100.0;

  const inpWdMkt = document.getElementById("inpWorkDaysMarket");
  if (inpWdMkt) cp.work_days_per_month = parseFloat(inpWdMkt.value) || 21.0;

  const inpOvh = document.getElementById("inpOverheadPct");
  if (inpOvh) cp.overhead_percent = parseFloat(inpOvh.value) || 60;

  const inpPrf = document.getElementById("inpProfitPct");
  if (inpPrf) cp.profit_percent = parseFloat(inpPrf.value) || 20;

  const chkSplit = document.getElementById("chkSplitPdRdCost");
  if (chkSplit) cp.split_pd_rd_in_cost = chkSplit.checked;
}

async function recalculateCostBackend() {
  if (!currentProject) return;
  syncProjectFromInputs();
  syncCostInputsToModel();
  try {
    const res = await fetch("/api/calculate-cost", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentProject),
    });
    if (res.ok) {
      currentProject = await res.json();
      renderCostTab();
    }
  } catch (e) {
    console.error("Ошибка расчёта стоимости:", e);
  }
}

function renderCostTab() {
  if (!currentProject || !currentProject.cost_parameters) return;
  const cp = currentProject.cost_parameters;

  if (costTotalBadge) {
    costTotalBadge.textContent = formatRub(cp.total_cost_gross_rub || cp.total_cost_net_rub);
  }

  const elNet = document.getElementById("costSummaryNetRub");
  const elPirSub = document.getElementById("costSummaryPirSub");
  const elVat = document.getElementById("costSummaryVatRub");
  const elGross = document.getElementById("costSummaryGrossRub");
  const elLaborSub = document.getElementById("costSummaryLaborSub");

  if (elNet) elNet.textContent = formatRub(cp.total_cost_net_rub);
  if (elPirSub) {
    elPirSub.textContent =
      cp.additional_works_total_net_rub > 0
        ? `ПИР: ${formatRub(cp.pir_only_cost_net_rub)} + Доп.: ${formatRub(cp.additional_works_total_net_rub)}`
        : "Основные проектные работы (без НДС)";
  }
  if (elVat) elVat.textContent = cp.include_vat ? formatRub(cp.vat_rub) : "Без НДС (0 ₽)";
  if (elGross) elGross.textContent = formatRub(cp.total_cost_gross_rub);
  if (elLaborSub) elLaborSub.textContent = `Расчётная трудоёмкость: ${cp.total_labor_days || 0} чел.-дней`;

  const vatSel = document.getElementById("selectVatMode");
  if (vatSel) vatSel.value = cp.include_vat ? String(cp.vat_rate || 5) : "0";

  const smrInp = document.getElementById("inputSmrMln");
  const smrValEl = document.getElementById("costSmrRefValue");
  const smrSubEl = document.getElementById("costSmrRefSub");
  if (smrInp) smrInp.value = cp.smr_cost_mln_rub > 0 ? cp.smr_cost_mln_rub : "";
  if (smrValEl) {
    smrValEl.textContent =
      cp.smr_reference_pir_cost_rub > 0
        ? `${formatRub(cp.smr_reference_pir_cost_rub)} (${cp.smr_normative_pct}%)`
        : "Введите СМР (млн ₽)";
  }
  if (smrSubEl) {
    smrSubEl.textContent = cp.smr_detected_from_tz
      ? "Извлечено из ТЗ • Табл. 1.5 Методики № 707/пр"
      : "Справочно по Табл. 1.5 Методики № 707/пр";
  }

  // Независимые итоги на 4 карточках сравнения
  const indCol = document.getElementById("indTotalCollections");
  if (indCol) indCol.textContent = formatRub(cp.collections_total_net_rub || 0);
  const ind707 = document.getElementById("indTotalLabor707");
  if (ind707) ind707.textContent = formatRub(cp.labor_707_total_net_rub || 0);
  const indMkt = document.getElementById("indTotalLaborMarket");
  if (indMkt) indMkt.textContent = formatRub(cp.labor_market_total_net_rub || 0);
  const indSmr = document.getElementById("indTotalSmr");
  if (indSmr) {
    indSmr.textContent = cp.smr_reference_pir_cost_rub > 0 ? formatRub(cp.smr_reference_pir_cost_rub) : "Введите СМР";
  }

  // Переключатели метода расчёта
  const activeMethod = cp.calculation_method || "by_collections";
  document.querySelectorAll(".cost-method-btn").forEach((btn) => {
    const m = btn.dataset.method;
    btn.className =
      m === activeMethod
        ? "cost-method-btn text-left p-3 rounded-xl border transition bg-blue-600 text-white border-blue-700 shadow-xs"
        : "cost-method-btn text-left p-3 rounded-xl border transition bg-white text-slate-800 border-slate-300 hover:border-blue-400";
  });

  const panelCol = document.getElementById("panelMethodCollections");
  const panelLab707 = document.getElementById("panelMethodLabor707");
  const panelLabMkt = document.getElementById("panelMethodLaborMarket");
  if (panelCol && panelLab707 && panelLabMkt) {
    panelCol.classList.toggle("hidden", activeMethod === "labor_707" || activeMethod === "labor_internal");
    panelLab707.classList.toggle("hidden", activeMethod !== "labor_707");
    panelLabMkt.classList.toggle("hidden", activeMethod !== "labor_internal");
  }

  // Коэффициенты
  const chkRec = document.getElementById("chkCostReconstr");
  if (chkRec) chkRec.checked = !!cp.is_reconstruction;
  const chkBim = document.getElementById("chkCostBim");
  if (chkBim) chkBim.checked = !!cp.use_bim;
  const inpComp = document.getElementById("inpCostComplexity");
  if (inpComp) inpComp.value = cp.complexity_factor ?? 1.0;
  const inpUrg = document.getElementById("inpCostUrgency");
  if (inpUrg) inpUrg.value = cp.urgency_factor ?? 1.0;

  // Параметры Метода 2А (Методика № 707/пр)
  const inpRegSal = document.getElementById("inpRegionalSalary707");
  if (inpRegSal) inpRegSal.value = cp.regional_monthly_salary_707 || 95000;
  const inpWd707 = document.getElementById("inpWorkDays707");
  if (inpWd707) inpWd707.value = cp.work_days_707 || 20.6;
  const inpK3 = document.getElementById("inpK3SalaryShare707");
  if (inpK3) inpK3.value = cp.k3_salary_share_707 || 0.4006;
  const inpProf707 = document.getElementById("inpProfitability707Pct");
  if (inpProf707) inpProf707.value = Math.round((cp.profitability_707 ?? 0.10) * 100);
  const lblVsr = document.getElementById("lblVsr707");
  if (lblVsr) lblVsr.textContent = formatRub(cp.v_sr_707_rub || 0) + "/дн.";
  const lblKkv = document.getElementById("lblKkvUch707");
  if (lblKkv) lblKkv.textContent = Number(cp.k_kv_uch_707 || 1).toFixed(4);
  const lblF707 = document.getElementById("lblFormula707");
  if (lblF707) lblF707.textContent = cp.labor_707_formula_text || "";

  // Параметры Метода 2Б (Рыночная таблица г. Тюмень)
  const inpWdMkt = document.getElementById("inpWorkDaysMarket");
  if (inpWdMkt) inpWdMkt.value = cp.work_days_per_month || 21;
  const inpOvh = document.getElementById("inpOverheadPct");
  if (inpOvh) inpOvh.value = cp.overhead_percent ?? 60;
  const inpPrf = document.getElementById("inpProfitPct");
  if (inpPrf) inpPrf.value = cp.profit_percent ?? 20;
  const lblFMkt = document.getElementById("lblFormulaMarket");
  if (lblFMkt) lblFMkt.textContent = cp.labor_market_formula_text || "";

  const chkSplit = document.getElementById("chkSplitPdRdCost");
  if (chkSplit) chkSplit.checked = !!cp.split_pd_rd_in_cost;

  renderCollectionItemsTable(cp);
  renderLabor707RowsTable(cp);
  renderSpecialistRowsTable(cp);
  renderAdditionalWorksBlock(cp);
  renderCostSectionsTable(cp);
}

function renderCollectionItemsTable(cp) {
  const tbody = document.getElementById("collectionItemsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const cols = (normativeCatalog && normativeCatalog.collections) || [];
  const items = cp.collection_items || [];

  items.forEach((q, idx) => {
    const tr = document.createElement("tr");
    tr.className = `hover:bg-blue-50/30 transition ${!q.enabled ? "opacity-50 bg-slate-50" : ""}`;

    const selectedCol = cols.find((c) => c.id === q.collection_id) || cols[0] || { items: [] };
    const colOptions = cols
      .map(
        (c) =>
          `<option value="${c.id}" ${c.id === selectedCol.id ? "selected" : ""}>№${c.num}. ${c.title} [цены ${c.base_year} г.]</option>`
      )
      .join("");

    const colItems = selectedCol.items || [];
    const itemOptions = colItems
      .map(
        (it) =>
          `<option value="${it.id}" ${it.id === q.item_id ? "selected" : ""}>${it.table_ref ? it.table_ref + " — " : ""}${it.name}</option>`
      )
      .join("");

    // Специальные поля для № 283/пр и № 270/пр
    let extraControlsHtml = "";
    if (selectedCol.calc_type === "survey_283") {
      extraControlsHtml = `
        <label class="inline-flex items-center mt-1.5 text-[11px] font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded cursor-pointer">
          <input type="checkbox" class="col-item-adv w-3.5 h-3.5 text-emerald-600 rounded mr-1.5" data-idx="${idx}" ${q.adverse_period ? "checked" : ""}>
          Неблагоприятный период года (Тюменская обл. +19%)
        </label>
      `;
    } else if (selectedCol.calc_type === "obmer_270") {
      const heights = [4, 6, 8, 10, 12, 15, 18, 21];
      const hOpts = heights
        .map((h) => `<option value="h_up_to_${h}" ${String(q.height_group).includes(String(h)) ? "selected" : ""}>Высота до ${h} м</option>`)
        .join("");
      extraControlsHtml = `
        <div class="grid grid-cols-2 gap-1.5 mt-1.5 text-[11px]">
          <select class="col-item-wt border border-slate-300 rounded px-1.5 py-0.5 bg-white" data-idx="${idx}">
            <option value="obmer_plus_obsled" ${q.work_type === "obmer_plus_obsled" ? "selected" : ""}>Многоэт.: Обмеры + Обследование</option>
            <option value="single_obmer_plus_obsled" ${q.work_type === "single_obmer_plus_obsled" ? "selected" : ""}>Одноэт.: Обмеры + Обследование</option>
            <option value="obmer" ${q.work_type === "obmer" ? "selected" : ""}>Только обмерные работы</option>
            <option value="obsled" ${q.work_type === "obsled" ? "selected" : ""}>Только обследование конструкций</option>
          </select>
          <select class="col-item-hg border border-slate-300 rounded px-1.5 py-0.5 bg-white" data-idx="${idx}">${hOpts}</select>
          <select class="col-item-bcat border border-slate-300 rounded px-1.5 py-0.5 bg-white" data-idx="${idx}">
            <option value="I" ${q.building_category === "I" ? "selected" : ""}>Кат. здания: I</option>
            <option value="II" ${q.building_category === "II" ? "selected" : ""}>Кат. здания: II</option>
            <option value="III" ${q.building_category === "III" ? "selected" : ""}>Кат. здания: III</option>
          </select>
          <select class="col-item-wcomp border border-slate-300 rounded px-1.5 py-0.5 bg-white" data-idx="${idx}">
            <option value="I" ${q.work_complexity === "I" ? "selected" : ""}>Сложн. работ: I</option>
            <option value="II" ${q.work_complexity === "II" ? "selected" : ""}>Сложн. работ: II</option>
            <option value="III" ${q.work_complexity === "III" ? "selected" : ""}>Сложн. работ: III</option>
          </select>
        </div>
      `;
    }

    tr.innerHTML = `
      <td class="py-2.5 px-3 text-center align-top">
        <input type="checkbox" class="col-item-chk w-4 h-4 text-blue-600 rounded border-slate-300 mt-1" data-idx="${idx}" ${q.enabled ? "checked" : ""}>
      </td>
      <td class="py-2.5 px-3 align-top">
        <select class="col-item-col w-full text-xs font-semibold border border-slate-300 rounded-md px-2 py-1 bg-white text-slate-800" data-idx="${idx}">
          ${colOptions}
        </select>
        <span class="block text-[10px] text-slate-500 mt-1">${selectedCol.code || ""}</span>
      </td>
      <td class="py-2.5 px-3 align-top">
        <select class="col-item-rate w-full text-xs border border-slate-300 rounded-md px-2 py-1 bg-white text-slate-800" data-idx="${idx}">
          ${itemOptions}
        </select>
        ${extraControlsHtml}
      </td>
      <td class="py-2.5 px-3 text-center align-top">
        <input type="number" step="any" min="0.01" class="col-item-x w-24 text-center font-mono font-bold text-xs border border-blue-300 rounded px-2 py-1 bg-white text-blue-900" data-idx="${idx}" value="${q.x_value}">
        <span class="block text-[10px] text-slate-500 mt-1">${q.unit || "ед."}</span>
      </td>
      <td class="py-2.5 px-3 text-center align-top space-y-1">
        <select class="col-item-stage w-full text-[11px] font-semibold border border-slate-300 rounded px-1.5 py-0.5 bg-white" data-idx="${idx}">
          <option value="pd_rd" ${q.stage_mode === "pd_rd" ? "selected" : ""}>П + Р (100%)</option>
          <option value="pd" ${q.stage_mode === "pd" ? "selected" : ""}>Только П</option>
          <option value="rd" ${q.stage_mode === "rd" ? "selected" : ""}>Только Р</option>
        </select>
        <div class="flex items-center justify-center gap-1 text-[10px]" title="Доля разрабатываемых разделов относительно полного комплекса по сборнику (К_разд), %">
          <span class="text-slate-600 font-semibold">Разделы, %:</span>
          <input type="number" step="1" min="1" max="100" class="col-item-comp w-14 text-center font-mono font-bold border border-blue-300 rounded px-1 py-0.5 bg-white text-blue-900" data-idx="${idx}" value="${q.completeness_pct ?? 100}">
        </div>
        <div class="flex items-center justify-center gap-1 text-[10px]">
          <span class="text-slate-500">К_попр:</span>
          <input type="number" step="0.05" min="0.1" max="5.0" class="col-item-k w-14 text-center font-mono border border-slate-300 rounded px-1 py-0.5 bg-white" data-idx="${idx}" value="${q.k_coeff || 1.0}">
        </div>
      </td>
      <td class="py-2.5 px-3 align-top font-mono text-[11px] text-slate-700">
        <div class="bg-slate-50 border border-slate-200 rounded p-1.5">${q.formula_text || "—"}</div>
        <span class="block text-[10px] text-slate-500 mt-1">База (01.01.${q.price_level_year}): <b>${formatRub(q.base_cost_rub)}</b></span>
      </td>
      <td class="py-2.5 px-3 text-right align-top font-mono font-bold text-sm text-emerald-700 whitespace-nowrap">
        ${formatRub(q.current_cost_rub)}
      </td>
      <td class="py-2.5 px-2 text-center align-top">
        <button type="button" class="col-item-del text-slate-400 hover:text-rose-600 p-1" data-idx="${idx}" title="Удалить позицию">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Обработчики событий в таблице сборников
  tbody.querySelectorAll(".col-item-chk").forEach((el) => {
    el.addEventListener("change", (e) => {
      items[parseInt(e.target.dataset.idx, 10)].enabled = e.target.checked;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-col").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const newColId = e.target.value;
      const foundCol = cols.find((c) => c.id === newColId);
      items[idx].collection_id = newColId;
      if (foundCol && foundCol.items && foundCol.items.length) {
        items[idx].item_id = foundCol.items[0].id;
      }
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-rate").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].item_id = e.target.value;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-x").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].x_value = parseFloat(e.target.value) || 1.0;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-stage").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].stage_mode = e.target.value;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-comp").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].completeness_pct = Math.min(100, Math.max(1, parseFloat(e.target.value) || 100));
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-k").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].k_coeff = parseFloat(e.target.value) || 1.0;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-adv").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].adverse_period = e.target.checked;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-wt").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].work_type = e.target.value;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-hg").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].height_group = e.target.value;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-bcat").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].building_category = e.target.value;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-wcomp").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      items[idx].work_complexity = e.target.value;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".col-item-del").forEach((el) => {
    el.addEventListener("click", (e) => {
      const idx = parseInt(e.currentTarget.dataset.idx, 10);
      items.splice(idx, 1);
      recalculateCostBackend();
    });
  });
}

const btnAddCollectionRow = document.getElementById("btnAddCollectionRow");
if (btnAddCollectionRow) {
  btnAddCollectionRow.addEventListener("click", () => {
    if (!currentProject || !currentProject.cost_parameters) return;
    const cols = (normativeCatalog && normativeCatalog.collections) || [];
    const firstCol = cols[0] || { id: "mnz_53pr", items: [{ id: "53pr_t1_p1" }] };
    currentProject.cost_parameters.collection_items.push({
      row_id: "col_row_" + Date.now(),
      collection_id: firstCol.id,
      item_id: firstCol.items[0]?.id || "",
      x_value: 1.0,
      stage_mode: currentProject.has_pd && currentProject.has_rd ? "pd_rd" : currentProject.has_rd ? "rd" : "pd",
      completeness_pct: 100.0,
      k_coeff: 1.0,
      enabled: true,
      adverse_period: true,
      height_group: "h_up_to_6",
      building_category: "II",
      work_complexity: "II",
      work_type: "obmer_plus_obsled",
      small_volume_auto: true,
    });
    recalculateCostBackend();
  });
}

// ---------------------------------------------------------------------------
// Таблица 2А (В1): Независимый нормативный расчёт по Методике № 707/пр (Табл. 1.3)
// ---------------------------------------------------------------------------
function renderLabor707RowsTable(cp) {
  const tbody = document.getElementById("labor707RowsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const rows = cp.labor_707_rows || [];
  const t13List = (normativeCatalog && normativeCatalog.method_707_table_1_3) || [];

  rows.forEach((r, idx) => {
    const tr = document.createElement("tr");
    tr.className = `hover:bg-indigo-50/40 transition ${!r.enabled ? "opacity-50 bg-slate-50" : ""}`;

    const roleOptions = t13List
      .map(
        (item) =>
          `<option value="${item.id}" ${item.id === r.role_id ? "selected" : ""}>${item.role} (И_i = ${Number(item.index_i).toFixed(2)})</option>`
      )
      .join("");

    tr.innerHTML = `
      <td class="py-2 px-3 text-center">
        <input type="checkbox" class="l707-row-chk w-4 h-4 text-indigo-600 rounded" data-idx="${idx}" ${r.enabled ? "checked" : ""}>
      </td>
      <td class="py-2 px-3">
        <select class="l707-row-role-sel w-full text-xs font-medium border border-slate-300 rounded px-2 py-1 bg-white text-slate-800" data-idx="${idx}">
          ${roleOptions}
          <option value="custom" ${!t13List.some((x) => x.id === r.role_id) ? "selected" : ""}>Своя должность...</option>
        </select>
      </td>
      <td class="py-2 px-3">
        <input type="text" class="l707-row-dep w-full text-xs text-slate-600 border border-slate-200 rounded px-2 py-1 bg-white" data-idx="${idx}" value="${r.department || ""}">
      </td>
      <td class="py-2 px-3 text-center">
        <input type="number" min="1" max="50" class="l707-row-cnt w-16 text-center font-mono text-xs border border-slate-300 rounded px-1 py-1 bg-white" data-idx="${idx}" value="${r.count}">
      </td>
      <td class="py-2 px-3 text-center">
        <input type="number" step="0.5" min="0.5" class="l707-row-days w-20 text-center font-mono text-xs border border-slate-300 rounded px-1 py-1 bg-white" data-idx="${idx}" value="${r.days}">
      </td>
      <td class="py-2 px-3 text-center font-mono font-bold text-slate-700">${r.total_days || 0}</td>
      <td class="py-2 px-3 text-center">
        <input type="number" step="0.01" min="0.2" max="4.0" class="l707-row-idx w-20 text-center font-mono font-bold text-xs border border-indigo-300 rounded px-1 py-1 bg-white text-indigo-900" data-idx="${idx}" value="${r.index_i}">
      </td>
      <td class="py-2 px-3 text-right font-mono font-semibold text-indigo-800">${Number(r.weighted_days || 0).toFixed(2)}</td>
      <td class="py-2 px-3 text-right font-mono font-bold text-emerald-700">${formatRub(r.cost_rub)}</td>
      <td class="py-2 px-2 text-center">
        <button type="button" class="l707-row-del text-slate-400 hover:text-rose-600" data-idx="${idx}"><i class="fa-solid fa-xmark"></i></button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".l707-row-chk").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].enabled = e.target.checked;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".l707-row-role-sel").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const roleId = e.target.value;
      const found = t13List.find((x) => x.id === roleId);
      rows[idx].role_id = roleId;
      if (found) {
        rows[idx].role_name = found.role;
        rows[idx].department = found.department || rows[idx].department;
        rows[idx].index_i = found.index_i;
      }
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".l707-row-dep").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].department = e.target.value;
    });
  });

  tbody.querySelectorAll(".l707-row-cnt").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].count = parseInt(e.target.value, 10) || 1;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".l707-row-days").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].days = parseFloat(e.target.value) || 1;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".l707-row-idx").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].index_i = parseFloat(e.target.value) || 1.0;
      recalculateCostBackend();
    });
  });

  tbody.querySelectorAll(".l707-row-del").forEach((el) => {
    el.addEventListener("click", (e) => {
      rows.splice(parseInt(e.currentTarget.dataset.idx, 10), 1);
      recalculateCostBackend();
    });
  });
}

const btnAddLabor707Row = document.getElementById("btnAddLabor707Row");
if (btnAddLabor707Row) {
  btnAddLabor707Row.addEventListener("click", () => {
    if (!currentProject || !currentProject.cost_parameters) return;
    currentProject.cost_parameters.labor_707_rows = currentProject.cost_parameters.labor_707_rows || [];
    currentProject.cost_parameters.labor_707_rows.push({
      row_id: "l707_" + Date.now(),
      role_id: "t13_7",
      role_name: "Ведущий специалист: инженер, архитектор, экономист, сметчик (Табл. 1.3 п. 7)",
      department: "Профильные отделы",
      count: 1,
      days: 10,
      index_i: 1.0,
      enabled: true,
    });
    recalculateCostBackend();
  });
}

// ---------------------------------------------------------------------------
// Таблица 2Б (В2): Независимый коммерческий расчёт по рыночной стоимости (г. Тюмень)
// ---------------------------------------------------------------------------
function renderSpecialistRowsTable(cp) {
  const tbody = document.getElementById("specialistRowsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const rows = cp.specialist_rows || [];
  const specDir = (normativeCatalog && normativeCatalog.specialists_directory) || [];

  rows.forEach((s, idx) => {
    const tr = document.createElement("tr");
    tr.className = `hover:bg-teal-50/40 transition ${!s.enabled ? "opacity-50 bg-slate-50" : ""}`;

    const roleOptions = specDir
      .map(
        (item) =>
          `<option value="${item.id}" ${item.id === s.role_id ? "selected" : ""}>${item.role} (${Number(item.monthly_salary_rub).toLocaleString("ru-RU")} ₽/мес)</option>`
      )
      .join("");

    tr.innerHTML = `
      <td class="py-2 px-3 text-center">
        <input type="checkbox" class="spec-row-chk w-4 h-4 text-teal-600 rounded" data-idx="${idx}" ${s.enabled ? "checked" : ""}>
      </td>
      <td class="py-2 px-3">
        <select class="spec-row-role-sel w-full text-xs font-medium border border-slate-300 rounded px-2 py-1 bg-white text-slate-800" data-idx="${idx}">
          ${roleOptions}
          <option value="custom" ${!specDir.some((x) => x.id === s.role_id) ? "selected" : ""}>${s.role_name || "Своя должность..."}</option>
        </select>
      </td>
      <td class="py-2 px-3">
        <input type="text" class="spec-row-dep w-full text-xs text-slate-600 border border-slate-200 rounded px-2 py-1 bg-white" data-idx="${idx}" value="${s.department}">
      </td>
      <td class="py-2 px-3 text-center">
        <input type="number" min="1" max="50" class="spec-row-cnt w-16 text-center font-mono text-xs border border-slate-300 rounded px-1 py-1 bg-white" data-idx="${idx}" value="${s.count}">
      </td>
      <td class="py-2 px-3 text-center">
        <input type="number" step="0.5" min="0.5" class="spec-row-days w-20 text-center font-mono text-xs border border-slate-300 rounded px-1 py-1 bg-white" data-idx="${idx}" value="${s.days}">
      </td>
      <td class="py-2 px-3 text-center font-mono font-bold text-slate-700">${s.total_days || 0}</td>
      <td class="py-2 px-3 text-right">
        <input type="number" step="1000" class="spec-row-sal w-28 text-right font-mono font-bold text-xs border border-teal-300 rounded px-2 py-1 bg-white text-teal-950" data-idx="${idx}" value="${s.monthly_salary_rub}">
      </td>
      <td class="py-2 px-3 text-right font-mono text-slate-600">${formatRub(s.daily_rate_rub)}</td>
      <td class="py-2 px-3 text-right font-mono font-bold text-emerald-700">${formatRub(s.total_wage_rub)}</td>
      <td class="py-2 px-2 text-center">
        <button type="button" class="spec-row-del text-slate-400 hover:text-rose-600" data-idx="${idx}"><i class="fa-solid fa-xmark"></i></button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".spec-row-chk").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].enabled = e.target.checked;
      recalculateCostBackend();
    });
  });
  tbody.querySelectorAll(".spec-row-role-sel").forEach((el) => {
    el.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.idx, 10);
      const roleId = e.target.value;
      const found = specDir.find((x) => x.id === roleId);
      rows[idx].role_id = roleId;
      if (found) {
        rows[idx].role_name = found.role;
        rows[idx].department = found.department || rows[idx].department;
        rows[idx].monthly_salary_rub = found.monthly_salary_rub;
      }
      recalculateCostBackend();
    });
  });
  tbody.querySelectorAll(".spec-row-dep").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].department = e.target.value;
    });
  });
  tbody.querySelectorAll(".spec-row-cnt").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].count = parseInt(e.target.value, 10) || 1;
      recalculateCostBackend();
    });
  });
  tbody.querySelectorAll(".spec-row-days").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].days = parseFloat(e.target.value) || 1;
      recalculateCostBackend();
    });
  });
  tbody.querySelectorAll(".spec-row-sal").forEach((el) => {
    el.addEventListener("change", (e) => {
      rows[parseInt(e.target.dataset.idx, 10)].monthly_salary_rub = parseFloat(e.target.value) || 80000;
      recalculateCostBackend();
    });
  });
  tbody.querySelectorAll(".spec-row-del").forEach((el) => {
    el.addEventListener("click", (e) => {
      rows.splice(parseInt(e.currentTarget.dataset.idx, 10), 1);
      recalculateCostBackend();
    });
  });
}

const btnAddSpecialistRow = document.getElementById("btnAddSpecialistRow");
if (btnAddSpecialistRow) {
  btnAddSpecialistRow.addEventListener("click", () => {
    if (!currentProject || !currentProject.cost_parameters) return;
    currentProject.cost_parameters.specialist_rows.push({
      row_id: "spec_" + Date.now(),
      role_id: "eng_1",
      role_name: "Инженер-проектировщик I категории",
      department: "Профильный отдел",
      count: 1,
      days: 10,
      monthly_salary_rub: 95000,
      qual_coeff_707: 1.0,
      enabled: true,
    });
    recalculateCostBackend();
  });
}

function renderAdditionalWorksBlock(cp) {
  const container = document.getElementById("additionalWorksContainer");
  if (!container) return;
  container.innerHTML = "";

  (cp.additional_works || []).forEach((aw, idx) => {
    const card = document.createElement("div");
    card.className = `rounded-lg border p-3 transition ${aw.enabled ? "bg-emerald-50/70 border-emerald-300" : "bg-white border-slate-200"}`;
    card.innerHTML = `
      <div class="flex items-start justify-between gap-2">
        <label class="inline-flex items-start cursor-pointer font-semibold text-slate-800">
          <input type="checkbox" class="add-work-chk w-4 h-4 text-emerald-600 rounded mt-0.5 mr-2" data-idx="${idx}" ${aw.enabled ? "checked" : ""}>
          <span>${aw.name}</span>
        </label>
      </div>
      <div class="mt-2 flex items-center justify-between gap-2">
        <span class="text-[11px] text-slate-500">Сумма без НДС, ₽:</span>
        <input type="number" step="5000" min="0" class="add-work-cost w-32 text-right font-mono font-bold text-xs border border-slate-300 rounded px-2 py-1 bg-white" data-idx="${idx}" value="${aw.cost_net_rub}">
      </div>
    `;
    container.appendChild(card);
  });

  container.querySelectorAll(".add-work-chk").forEach((el) => {
    el.addEventListener("change", (e) => {
      cp.additional_works[parseInt(e.target.dataset.idx, 10)].enabled = e.target.checked;
      recalculateCostBackend();
    });
  });
  container.querySelectorAll(".add-work-cost").forEach((el) => {
    el.addEventListener("change", (e) => {
      cp.additional_works[parseInt(e.target.dataset.idx, 10)].cost_net_rub = parseFloat(e.target.value) || 0;
      recalculateCostBackend();
    });
  });
}

function renderCostSectionsTable(cp) {
  const tbody = document.getElementById("costSectionsTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  (cp.sections_costs || []).forEach((sec, idx) => {
    if (!sec.enabled) return;
    const tr = document.createElement("tr");
    tr.className = "hover:bg-blue-50/30 transition";
    const stBadge =
      sec.stage === "Р"
        ? `<span class="bg-cyan-100 text-cyan-800 px-2 py-0.5 rounded font-bold text-[10px]">Р</span>`
        : sec.stage === "П"
        ? `<span class="bg-blue-100 text-blue-800 px-2 py-0.5 rounded font-bold text-[10px]">П</span>`
        : `<span class="bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded font-bold text-[10px]">П+Р</span>`;

    tr.innerHTML = `
      <td class="py-2 px-3 text-center">${stBadge}</td>
      <td class="py-2 px-3 text-center font-mono text-slate-600">${sec.volume_num || ""}</td>
      <td class="py-2 px-3 text-center font-mono font-bold text-blue-700">${sec.full_code || sec.code_mark}</td>
      <td class="py-2 px-3 font-medium text-slate-800">${sec.title}</td>
      <td class="py-2 px-3">
        <input type="text" class="cost-sec-dep w-full text-xs text-slate-600 border border-transparent hover:border-slate-300 rounded px-1.5 py-0.5 bg-transparent focus:bg-white" data-idx="${idx}" value="${sec.department || ""}">
      </td>
      <td class="py-2 px-3 text-right">
        <input type="number" step="0.5" min="0" max="100" class="cost-sec-share w-20 text-right font-mono font-semibold text-xs border border-slate-300 rounded px-1.5 py-0.5 bg-white" data-idx="${idx}" value="${sec.relative_share_percent}">
      </td>
      <td class="py-2 px-3 text-right font-mono text-slate-700">${sec.labor_days}</td>
      <td class="py-2 px-3 text-right font-mono font-bold text-slate-900">${formatRub(sec.cost_rub)}</td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".cost-sec-dep").forEach((el) => {
    el.addEventListener("change", (e) => {
      cp.sections_costs[parseInt(e.target.dataset.idx, 10)].department = e.target.value;
    });
  });

  tbody.querySelectorAll(".cost-sec-share").forEach((el) => {
    el.addEventListener("change", (e) => {
      cp.sections_costs[parseInt(e.target.dataset.idx, 10)].relative_share_percent = parseFloat(e.target.value) || 0;
      recalculateCostBackend();
    });
  });
}

// Слушатели верхних контролов вкладки 3
document.querySelectorAll(".cost-method-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (!currentProject || !currentProject.cost_parameters) return;
    currentProject.cost_parameters.calculation_method = btn.dataset.method;
    recalculateCostBackend();
  });
});

[
  "selectVatMode",
  "inputSmrMln",
  "chkCostReconstr",
  "chkCostBim",
  "inpCostComplexity",
  "inpCostUrgency",
  "inpRegionalSalary707",
  "inpWorkDays707",
  "inpK3SalaryShare707",
  "inpProfitability707Pct",
  "inpWorkDaysMarket",
  "inpOverheadPct",
  "inpProfitPct",
  "chkSplitPdRdCost",
].forEach((id) => {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener("change", () => recalculateCostBackend());
  }
});

const btnNormalizeShares = document.getElementById("btnNormalizeShares");
if (btnNormalizeShares) {
  btnNormalizeShares.addEventListener("click", () => recalculateCostBackend());
}

// Скачивание сметного расчёта ПИР (.xlsx)
const btnDownloadCostExcel = document.getElementById("btnDownloadCostExcel");
if (btnDownloadCostExcel) {
  btnDownloadCostExcel.addEventListener("click", async () => {
    if (!currentProject) return;
    syncProjectFromInputs();
    syncCostInputsToModel();

    const origHtml = btnDownloadCostExcel.innerHTML;
    btnDownloadCostExcel.disabled = true;
    btnDownloadCostExcel.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Формирование сметы...';
    try {
      const res = await fetch("/api/generate-cost-excel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentProject),
      });
      if (!res.ok) throw new Error("Не удалось сформировать Excel-смету");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      let fname = "Смета_ПИР.xlsx";
      if (currentMode === "contract" && currentProject.cipher) {
        fname = `${currentProject.cipher}_Смета_ПИР.xlsx`;
      }
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert("Ошибка: " + e.message);
    } finally {
      btnDownloadCostExcel.disabled = false;
      btnDownloadCostExcel.innerHTML = origHtml;
    }
  });
}
