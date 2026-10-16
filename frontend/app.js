const state = { loaded: new Set() };
const riskClass = (risk) => risk.toLowerCase();
const percent = (value) => `${(value * 100).toFixed(1)}%`;
const number = (value) => Number.isInteger(value) ? value : value.toFixed(1);
const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));

function showError(message) {
  const banner = document.querySelector("#global-error");
  banner.textContent = message;
  banner.hidden = false;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

function renderDashboard(data) {
  const cards = [
    ["Normal", "normal", "✓", "Within estimated shift capacity"],
    ["Warning", "warning", "!", "Keep an eye on queue pressure"],
    ["Critical", "critical", "!", "Needs operational attention"],
  ];
  document.querySelector("#summary-cards").innerHTML = cards.map(([label, style, icon, hint]) => `
    <article class="metric-card ${style}">
      <div class="metric-top"><span>${label}</span><span class="metric-icon">${icon}</span></div>
      <strong class="metric-value">${data.counts[label]}</strong>
      <span class="metric-hint">${hint}</span>
    </article>`).join("");

  document.querySelector("#department-rows").innerHTML = data.departments.map((item) => `
    <tr>
      <td>${escapeHTML(item.department)}</td><td>${number(item.appointments)}</td>
      <td>${number(item.staff_available)}</td><td>${percent(item.utilization)}</td>
      <td><span class="risk-badge ${riskClass(item.risk)}">${escapeHTML(item.risk)}</span></td>
    </tr>`).join("");
  document.querySelector("#today-date").textContent = data.departments[0]?.date || new Date().toLocaleDateString();
}

function renderBottlenecks(data) {
  const container = document.querySelector("#bottleneck-list");
  if (!data.bottlenecks.length) {
    container.innerHTML = '<div class="panel loading-card">No departments are currently flagged.</div>';
    return;
  }
  container.innerHTML = data.bottlenecks.map((item) => {
    const evidence = item.evidence;
    const rows = [
      ["Appointments", number(evidence.appointments)],
      ["Staff available", number(evidence.staff_available)],
      ["Avg task time", `${number(evidence.avg_task_minutes)} min`],
      ["Emergency cases", number(evidence.emergency_cases)],
      ["Demand / capacity", `${evidence.demand_minutes} / ${evidence.capacity_minutes} min`],
      ["Utilization", percent(evidence.utilization)],
    ];
    return `<article class="bottleneck-card">
      <div class="bottleneck-top"><h3>${escapeHTML(item.department)}</h3><span class="risk-badge ${riskClass(item.risk)}">${escapeHTML(item.risk)}</span></div>
      <div class="bottleneck-grid">
        <div class="bottleneck-col"><p class="col-label">COMPUTED EVIDENCE</p><div class="evidence-table">${rows.map(([label, value]) => `<span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong>`).join("")}</div></div>
        <div class="bottleneck-col"><p class="col-label">EXPLANATION</p><p class="problem-text">${escapeHTML(item.explanation.problem)}</p><div class="risk-window">${escapeHTML(item.explanation.risk_window)}</div></div>
        <div class="bottleneck-col"><p class="col-label">SUGGESTED MANAGEMENT ACTIONS</p><ol class="actions-list">${item.explanation.actions.map((action, index) => `<li><span class="action-number">${index + 1}</span><span>${escapeHTML(action)}</span></li>`).join("")}</ol></div>
      </div>
    </article>`;
  }).join("");
}

function renderForecast(data) {
  const chart = document.querySelector("#forecast-chart");
  const max = Math.max(1.2, Math.ceil(Math.max(...data.departments.map((item) => item.utilization)) * 10) / 10);
  chart.innerHTML = data.departments.map((item) => {
    const width = Math.min(100, (item.utilization / max) * 100);
    return `<div class="forecast-row">
      <span class="forecast-name">${escapeHTML(item.department)}</span>
      <div class="bar-track" style="--capacity-position:${100 / max}%" aria-label="${escapeHTML(item.department)}, ${percent(item.utilization)} utilization"><div class="bar-fill ${riskClass(item.risk)}" style="width:${width}%"></div></div>
      <span class="bar-value">${percent(item.utilization)}</span>
    </div>`;
  }).join("");
}

async function loadView(name) {
  if (state.loaded.has(name)) return;
  const loaders = {
    dashboard: ["/api/dashboard", renderDashboard],
    bottlenecks: ["/api/bottlenecks", renderBottlenecks],
    forecast: ["/api/forecast", renderForecast],
  };
  if (!loaders[name]) return;
  try {
    const [path, render] = loaders[name];
    render(await api(path));
    state.loaded.add(name);
  } catch (error) {
    showError(`Could not load ${name}: ${error.message}`);
  }
}

document.querySelectorAll(".nav-tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.classList.toggle("active", tab === button);
      if (tab === button) tab.setAttribute("aria-current", "page");
      else tab.removeAttribute("aria-current");
    });
    document.querySelectorAll(".view").forEach((view) => {
      view.classList.toggle("active", view.id === `view-${button.dataset.view}`);
    });
    loadView(button.dataset.view);
  });
});

document.querySelectorAll(".examples button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector("#question-input").value = button.textContent;
    document.querySelector("#question-input").focus();
  });
});

document.querySelector("#ask-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.querySelector("#question-input");
  const button = event.currentTarget.querySelector("button[type=submit]");
  const answerBox = document.querySelector("#answer-box");
  button.disabled = true;
  button.textContent = "Thinking…";
  answerBox.hidden = false;
  answerBox.textContent = "Checking the operational data…";
  try {
    const result = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question: input.value }),
    });
    answerBox.innerHTML = `<span class="answer-mode">${result.mode === "local" ? "LOCAL AI" : "RULE-BASED ANSWER"}</span>${escapeHTML(result.answer)}`;
  } catch (error) {
    answerBox.textContent = `Could not answer the question: ${error.message}`;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Ask question <span aria-hidden="true">→</span>';
  }
});

api("/api/status").then((data) => {
  const banner = document.querySelector("#mode-banner");
  banner.classList.toggle("fallback", data.mode !== "local");
  banner.querySelector("span:last-child").textContent = data.mode === "local"
    ? `AI running locally (Ollama · ${data.model})`
    : "Fallback mode (rule-based)";
}).catch(() => {
  const banner = document.querySelector("#mode-banner");
  banner.classList.add("fallback");
  banner.querySelector("span:last-child").textContent = "Fallback mode (rule-based)";
});

loadView("dashboard");
