// Модуль «Коммерческое предложение»: форма параметров КП и скачивание .docx.
// Использует глобальные currentProject, syncProjectFromInputs, syncCostInputsToModel из app.js.
(function () {
  const btnOpen = document.getElementById("btnOpenKp");
  const modal = document.getElementById("kpModal");
  if (!btnOpen || !modal) return;

  const $ = (id) => document.getElementById(id);
  const lines = (id) => $(id).value.split("\n").map((s) => s.trim()).filter(Boolean);

  fetch("/api/kp-info")
    .then((r) => r.json())
    .then((info) => {
      $("kpModeInfo").textContent = info.corporate_letterhead
        ? "Режим: корпоративный бланк компании подключен."
        : "Режим: нейтральный образец (без данных компании). Реквизиты, подписант и исполнитель заполняются ниже.";
    })
    .catch(() => {});

  function toggleBlocks() {
    $("kpWorksBlock").classList.toggle("hidden", $("kpPriceFormat").value !== "works");
    $("kpAdvanceBlock").classList.toggle("hidden", $("kpPayment").value !== "advance");
    $("kpStagesBlock").classList.toggle("hidden", $("kpPayment").value !== "stages");
  }
  $("kpPriceFormat").addEventListener("change", toggleBlocks);
  $("kpPayment").addEventListener("change", toggleBlocks);
  toggleBlocks();

  btnOpen.addEventListener("click", () => {
    if (!currentProject) {
      alert("Сначала загрузите ТЗ или сформируйте состав проекта.");
      return;
    }
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

  $("kpGenerate").addEventListener("click", async () => {
    syncProjectFromInputs();
    syncCostInputsToModel();
    const exclusions = Array.from(document.querySelectorAll(".kpExcl:checked")).map((c) => c.value);
    lines("kpExclExtra").forEach((x) => exclusions.push(x));
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
      payment_scheme: $("kpPayment").value,
      advance_percent: parseFloat($("kpAdvance").value) || 0,
      payment_stages: [],
      validity_days: parseInt($("kpValidity").value, 10) || 15,
      phrase_counter_offers: $("kpPhraseCounter").checked,
      phrase_help_tz: $("kpPhraseTz").checked,
      signer_title: $("kpSignerTitle").value.trim() || "Директор",
      signer_name: $("kpSignerName").value.trim(),
      company_name: $("kpCompany").value.trim(),
      executor: $("kpExecutor").value.trim(),
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
      if (!res.ok) throw new Error("Не удалось сформировать КП");
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