// Модуль «Коммерческое предложение»: форма параметров КП и скачивание .docx на фирменном бланке компании.
// Использует глобальные currentProject, syncProjectFromInputs, syncCostInputsToModel из app.js.
(function () {
  const btnOpen = document.getElementById("btnOpenKp");
  const modal = document.getElementById("kpModal");
  if (!btnOpen || !modal) return;

  const $ = (id) => document.getElementById(id);
  const lines = (id) =>
    ($(id)?.value || "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

  const PAYMENT_PRESETS = {
    "100_advance": [
      "Предоплата в размере 100% стоимости работ производится в течение 5 рабочих дней с момента заключения договора (до начала выполнения работ)."
    ],
    "40_30_30": [
      "Предоплата - 40% стоимости работ по договору производится в течении 5-ти рабочих дней с момента заключения договора;",
      "Оплата в размере 30% стоимости работ производится в течении 5 рабочих дней с момента передачи полного комплекта проектной документации заказчику;",
      "Оплата в размере 30% стоимости работ производится в течении 5 рабочих дней с момента подписания акта выполненных работ."
    ],
    "50_50": [
      "Аванс в размере 50% стоимости работ производится в течение 5 рабочих дней с момента заключения договора.",
      "Оплата оставшихся 50% стоимости работ производится в течение 5 рабочих дней с момента подписания акта сдачи-приемки выполненных работ."
    ],
    "30_50_20": [
      "Предоплата — 30% стоимости работ производится в течение 5 рабочих дней с момента заключения договора.",
      "Оплата в размере 50% стоимости работ производится в течение 5 рабочих дней с момента передачи полного комплекта документации на согласование.",
      "Оплата в размере 20% стоимости работ производится в течение 5 рабочих дней с момента подписания акта сдачи-приемки выполненных работ."
    ],
    "100_post": [
      "Оплата в размере 100% стоимости работ производится в течение 10 рабочих дней с момента подписания акта сдачи-приемки выполненных работ (без авансирования)."
    ],
  };

  function updateOutSuffix() {
    const dtVal = $("kpDate")?.value;
    const d = dtVal ? new Date(dtVal + "T00:00:00") : new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = String(d.getFullYear()).slice(-2);
    if ($("kpOutSuffix")) {
      $("kpOutSuffix").textContent = `/${mm}${yy}`;
    }
  }

  if ($("kpDate") && !$("kpDate").value) {
    const now = new Date();
    $("kpDate").value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  }
  updateOutSuffix();
  if ($("kpDate")) $("kpDate").addEventListener("change", updateOutSuffix);

  fetch("/api/kp-info")
    .then((r) => r.json())
    .then((info) => {
      if ($("kpModeInfo")) {
        $("kpModeInfo").innerHTML = '<i class="fa-solid fa-circle-check mr-1.5"></i> Фирменный бланк компании подключен (data/private/kp_letterhead.docx)';
      }
    })
    .catch(() => {});

  function toggleBlocks() {
    if ($("kpWorksBlock")) {
      $("kpWorksBlock").classList.toggle("hidden", $("kpPriceFormat")?.value !== "works");
    }
  }
  if ($("kpPriceFormat")) $("kpPriceFormat").addEventListener("change", toggleBlocks);
  toggleBlocks();

  // Обработка пресетов условий оплаты
  if ($("kpPaymentPreset")) {
    $("kpPaymentPreset").addEventListener("change", () => {
      const val = $("kpPaymentPreset").value;
      if (val in PAYMENT_PRESETS && $("kpPaymentStagesText")) {
        $("kpPaymentStagesText").value = PAYMENT_PRESETS[val].join("\n");
      }
    });
  }
  if ($("kpPaymentStagesText")) {
    $("kpPaymentStagesText").addEventListener("input", () => {
      if ($("kpPaymentPreset")) {
        // Проверяем, совпадает ли текст с каким-то пресетом
        const cur = $("kpPaymentStagesText").value.trim();
        let matched = false;
        for (const [k, arr] of Object.entries(PAYMENT_PRESETS)) {
          if (arr.join("\n").trim() === cur) {
            $("kpPaymentPreset").value = k;
            matched = true;
            break;
          }
        }
        if (!matched) {
          $("kpPaymentPreset").value = "custom";
        }
      }
    });
  }

  function prefillModalFromProject() {
    if (!currentProject) return;
    const cp = currentProject.cost_parameters;

    // Автоподстановка стадии (ПД и РД / только ПД / только РД)
    if ($("kpStage")) {
      if (currentProject.has_pd && currentProject.has_rd) {
        $("kpStage").value = "pd_rd";
      } else if (currentProject.has_rd && !currentProject.has_pd) {
        $("kpStage").value = "rd";
      } else {
        $("kpStage").value = "pd";
      }
    }

    // Автоподстановка адресата, если указан Заказчик
    if ($("kpAddressee") && !$("kpAddressee").value.trim() && currentProject.customer) {
      $("kpAddressee").value = `Руководителю\n${currentProject.customer}`;
    }

    // Автоподстановка срока из календарного графика
    if ($("kpTermValue") && currentProject.schedule_phases && currentProject.schedule_phases.length) {
      const maxWeek = currentProject.schedule_phases.reduce((m, p) => {
        const endW = p.milestone ? p.start_week : p.start_week + Math.max(1, p.duration_weeks) - 1;
        return Math.max(m, endW);
      }, 8);
      if ($("kpTermUnit")?.value === "calendar_days") {
        $("kpTermValue").value = maxWeek * 7;
      }
    }

    // Автозаполнение таблицы по укрупнённым видам работ из текущего расчёта стоимости
    if ($("kpWorks") && cp) {
      const workLines = [];
      const pirStageTitle =
        currentProject.has_pd && currentProject.has_rd
          ? "Разработка проектной и рабочей документации (ПД и РД)"
          : currentProject.has_rd
          ? "Разработка рабочей документации (РД)"
          : "Разработка проектной документации (ПД)";
      const pirAmount = Math.round(cp.pir_only_cost_net_rub || cp.total_cost_net_rub || 0);
      workLines.push(`${pirStageTitle} | ${pirAmount}`);
      (cp.additional_works || []).forEach((aw) => {
        if (aw.enabled && aw.cost_net_rub > 0) {
          workLines.push(`${aw.name} | ${Math.round(aw.cost_net_rub)}`);
        }
      });
      $("kpWorks").value = workLines.join("\n");
    }

    // Автозаполнение блока «В коммерческое предложение входит»
    if ($("kpIncl") && !$("kpIncl").value.trim()) {
      const incl = ["Сбор и анализ исходных данных для проектирования"];
      if (currentProject.has_pd) incl.push("Разработка проектной документации в соответствии с ПП РФ № 87");
      if (currentProject.has_rd) incl.push("Разработка рабочей документации в соответствии с ГОСТ Р 21.101-2020");
      if (cp) {
        (cp.additional_works || []).forEach((aw) => {
          if (aw.enabled) incl.push(aw.name);
        });
      }
      $("kpIncl").value = incl.join("\n");
    }

    // Инициализация условий оплаты дефолтным пресетом, если пусто
    if ($("kpPaymentStagesText") && !$("kpPaymentStagesText").value.trim()) {
      const preset = $("kpPaymentPreset")?.value || "40_30_30";
      if (PAYMENT_PRESETS[preset]) {
        $("kpPaymentStagesText").value = PAYMENT_PRESETS[preset].join("\n");
      }
    }
  }

  btnOpen.addEventListener("click", () => {
    if (!currentProject) {
      alert("Сначала загрузите ТЗ или сформируйте состав проекта.");
      return;
    }
    syncProjectFromInputs();
    if (typeof syncCostInputsToModel === "function") syncCostInputsToModel();
    prefillModalFromProject();
    modal.classList.remove("hidden");
  });
  $("kpClose").addEventListener("click", () => modal.classList.add("hidden"));

  function parseWorks() {
    return lines("kpWorks").map((ln) => {
      const idx = ln.lastIndexOf("|");
      const name = (idx >= 0 ? ln.slice(0, idx) : ln).trim();
      const cost = idx >= 0 ? parseFloat(ln.slice(idx + 1).replace(/\s/g, "").replace(",", ".")) : 0;
      return { name, cost_rub: isNaN(cost) ? 0 : cost };
    });
  }

  function parsePaymentStages() {
    return lines("kpPaymentStagesText").map((ln) => {
      const m = ln.match(/(\d+(?:[.,]\d+)?)\s*%/);
      const percent = m ? parseFloat(m[1].replace(",", ".")) : 0;
      return {
        percent: percent,
        text: ln.trim(),
      };
    });
  }

  $("kpGenerate").addEventListener("click", async () => {
    syncProjectFromInputs();
    if (typeof syncCostInputsToModel === "function") syncCostInputsToModel();
    const exclusions = Array.from(document.querySelectorAll(".kpExcl:checked")).map((c) => c.value);
    lines("kpExclExtra").forEach((x) => exclusions.push(x));

    const paymentStages = parsePaymentStages();
    const firstPercent = paymentStages.length ? paymentStages[0].percent : 0;

    const payload = {
      project: currentProject,
      outgoing_number: $("kpOutNum").value.trim(),
      date: $("kpDate").value,
      addressee_lines: lines("kpAddressee"),
      salutation: $("kpSalutation").value.trim() || "Уважаемый Заказчик!",
      request_date: $("kpRequestDate").value.trim(),
      stage: $("kpStage").value,
      subject_text: $("kpSubject").value.trim(),
      inclusions: lines("kpIncl"),
      exclusions,
      price_format: $("kpPriceFormat").value,
      works: parseWorks(),
      term_value: parseInt($("kpTermValue").value, 10) || 0,
      term_unit: $("kpTermUnit").value,
      note_approval_excluded: $("kpApproval").checked,
      payment_scheme: "stages",
      advance_percent: firstPercent,
      payment_stages: paymentStages,
      validity_days: parseInt($("kpValidity").value, 10) || 15,
      phrase_counter_offers: $("kpPhraseCounter").checked,
      phrase_help_tz: $("kpPhraseTz").checked,
      signer_title: $("kpSignerTitle").value.trim() || "Директор",
      signer_name: $("kpSignerName").value.trim() || "Валова М.М.",
      company_name: $("kpCompany") ? $("kpCompany").value.trim() : "ООО «ТПС»",
      executor: $("kpExecutor").value.trim() || "Эберт Е.В. Тел. +7 932 326 93 83",
    };

    if (payload.price_format === "works" && !payload.works.length) {
      alert("Для таблицы по видам работ добавьте хотя бы одну строку.");
      return;
    }
    const btn = $("kpGenerate");
    const label = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Формирование...';
    try {
      const res = await fetch("/api/generate-kp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const errMsg = errJson?.detail || "Не удалось сформировать КП на фирменном бланке";
        throw new Error(errMsg);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const clean = (currentProject.object_name || "").replace(/[^a-zA-Zа-яА-Я0-9_-]/g, "_").substring(0, 30);
      a.download = clean ? `КП_${clean}.docx` : "Коммерческое_предложение.docx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Ошибка: " + err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = label;
    }
  });
})();
