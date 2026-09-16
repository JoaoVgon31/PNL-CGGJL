"use strict";

const DATA_BASE = "data";

const NODE_STYLE = {
  Patient: { color: "#2a78d6", colorDark: "#3987e5", shape: "ellipse" },
  Symptom: { color: "#eb6834", colorDark: "#d95926", shape: "ellipse" },
  Exam: { color: "#1baf7a", colorDark: "#199e70", shape: "ellipse" },
  Finding: { color: "#eda100", colorDark: "#c98500", shape: "ellipse" },
  Diagnosis: { color: "#e87ba4", colorDark: "#d55181", shape: "ellipse" },
  Treatment: { color: "#008300", colorDark: "#008300", shape: "ellipse" },
  Medication: { color: "#4a3aa7", colorDark: "#9085e9", shape: "ellipse" },
  Outcome: { color: "#e34948", colorDark: "#e66767", shape: "ellipse" },
  History: { color: "#eb6834", colorDark: "#d95926", shape: "rectangle" },
  ExamResult: { color: "#1baf7a", colorDark: "#199e70", shape: "rectangle" },
  AnatomicalSite: { color: "#eda100", colorDark: "#c98500", shape: "rectangle" },
  Concept: { color: "#6b6b6b", colorDark: "#a3a3a3", shape: "diamond" },
};

const STRATEGY_LABELS = {
  combinado: "Combinado",
  tokenizacao: "Tokenização",
  stopwords: "Stopwords",
  dicionarios: "Dicionários",
  sintagmas: "Sintagmas",
  normalizacao: "Normalização",
};

const STRATEGY_ORDER = [
  "combinado",
  "tokenizacao",
  "stopwords",
  "dicionarios",
  "sintagmas",
  "normalizacao",
];

const state = {
  manifest: null,
  currentCase: null,
  currentCasePayload: null,
  currentStrategy: null,
  cy: null,
  hiddenTypes: new Set(),
};

function prefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function nodeColor(type) {
  const style = NODE_STYLE[type];
  if (!style) return "#999999";
  return prefersDark() ? style.colorDark : style.color;
}

function nodeShape(type) {
  const style = NODE_STYLE[type];
  return style ? style.shape : "ellipse";
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`falha ao carregar ${path}: ${response.status}`);
  }
  return response.json();
}

async function init() {
  state.manifest = await fetchJson(`${DATA_BASE}/manifest.json`);
  populateCaseOptions();
  document.getElementById("case-select").addEventListener("change", onCaseChange);
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (state.currentStrategy) {
        selectStrategy(state.currentStrategy);
      }
    });
  if (state.manifest.cases.length > 0) {
    const firstCaseId = state.manifest.cases[0].case_id;
    document.getElementById("case-select").value = firstCaseId;
    await loadCase(firstCaseId);
  }
}

function populateCaseOptions() {
  const datalist = document.getElementById("case-options");
  datalist.innerHTML = "";
  for (const entry of state.manifest.cases) {
    const option = document.createElement("option");
    option.value = entry.case_id;
    datalist.appendChild(option);
  }
}

async function onCaseChange(event) {
  const caseId = event.target.value.trim();
  const known = state.manifest.cases.some((entry) => entry.case_id === caseId);
  if (!known) return;
  await loadCase(caseId);
}

async function loadCase(caseId) {
  closeDrawer();
  state.currentCase = caseId;
  state.currentCasePayload = await fetchJson(`${DATA_BASE}/${caseId}.json`);
  renderTabs();
  const firstAvailable = STRATEGY_ORDER.find((key) => state.currentCasePayload.graphs[key]);
  if (firstAvailable) {
    selectStrategy(firstAvailable);
  } else {
    showEmptyState(true, "Nenhum grafo disponível para este caso.");
  }
}

function renderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  for (const key of STRATEGY_ORDER) {
    const available = Boolean(state.currentCasePayload.graphs[key]);
    const button = document.createElement("button");
    button.textContent = STRATEGY_LABELS[key];
    button.className = "tab";
    button.disabled = !available;
    button.setAttribute("role", "tab");
    button.dataset.strategy = key;
    button.setAttribute("aria-selected", "false");
    if (available) {
      button.addEventListener("click", () => selectStrategy(key));
    }
    nav.appendChild(button);
  }
}

function selectStrategy(key) {
  state.currentStrategy = key;
  for (const button of document.querySelectorAll(".tab")) {
    button.setAttribute("aria-selected", String(button.dataset.strategy === key));
  }
  showEmptyState(false, "");
  renderGraph(state.currentCasePayload.graphs[key]);
}

function showEmptyState(show, message) {
  const emptyState = document.getElementById("empty-state");
  emptyState.hidden = !show;
  emptyState.textContent = message;
  document.getElementById("cy").hidden = show;
}

function renderGraph(graph) {
  if (state.cy) {
    state.cy.destroy();
    state.cy = null;
  }
  state.hiddenTypes = new Set();

  const elements = [
    ...graph.nodes.map((node) => ({
      data: { id: node.node_id, label: node.label, type: node.type, attributes: node.attributes },
    })),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.edge_id,
        source: edge.source_id,
        target: edge.target_id,
        relation: edge.relation,
        attributes: edge.attributes,
      },
    })),
  ];

  state.cy = cytoscape({
    container: document.getElementById("cy"),
    elements,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (el) => nodeColor(el.data("type")),
          shape: (el) => nodeShape(el.data("type")),
          label: "data(label)",
          "font-size": 9,
          "text-wrap": "wrap",
          "text-max-width": "80px",
          width: 28,
          height: 28,
          color: "#1a1a1a",
          "text-valign": "bottom",
          "text-margin-y": 4,
        },
      },
      {
        selector: "edge",
        style: {
          width: 1.5,
          "line-color": "#999999",
          "target-arrow-color": "#999999",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(relation)",
          "font-size": 7,
          color: "#666666",
        },
      },
      {
        selector: ".hidden-type",
        style: { display: "none" },
      },
    ],
    layout: { name: "cose", animate: false },
  });

  state.cy.on("tap", "node", (event) => showNodeDetails(event.target.data()));
  state.cy.on("tap", "edge", (event) => showEdgeDetails(event.target.data()));

  renderLegend(graph.nodes);
}

function renderLegend(nodes) {
  const legend = document.getElementById("legend");
  legend.innerHTML = "";
  const types = Array.from(new Set(nodes.map((node) => node.type))).sort();
  for (const type of types) {
    const item = document.createElement("button");
    item.className = "legend-item";
    item.dataset.type = type;
    item.setAttribute("aria-pressed", "true");
    const swatch = document.createElement("span");
    swatch.className = `swatch shape-${nodeShape(type)}`;
    swatch.style.backgroundColor = nodeColor(type);
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(type));
    item.addEventListener("click", () => toggleType(type, item));
    legend.appendChild(item);
  }
}

function toggleType(type, legendItem) {
  if (state.hiddenTypes.has(type)) {
    state.hiddenTypes.delete(type);
    legendItem.setAttribute("aria-pressed", "true");
  } else {
    state.hiddenTypes.add(type);
    legendItem.setAttribute("aria-pressed", "false");
  }
  state.cy.nodes().forEach((node) => {
    node.toggleClass("hidden-type", state.hiddenTypes.has(node.data("type")));
  });
}

function openDrawer(html) {
  const drawer = document.getElementById("drawer");
  document.getElementById("drawer-body").innerHTML = html;
  drawer.hidden = false;
  const mark = document.getElementById("evidence-mark");
  if (mark) {
    mark.scrollIntoView({ block: "center" });
  }
}

function closeDrawer() {
  document.getElementById("drawer").hidden = true;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function showNodeDetails(data) {
  const rows = Object.entries(data.attributes || {})
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");
  openDrawer(`
    <h2>${escapeHtml(data.type)}</h2>
    <p class="drawer-label">${escapeHtml(data.label)}</p>
    <table class="attr-table"><tbody>${rows}</tbody></table>
  `);
}

function showEdgeDetails(data) {
  const attrs = data.attributes || {};
  const rows = Object.entries(attrs)
    .filter(([key]) => !["evidence_text", "char_start", "char_end"].includes(key))
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");

  openDrawer(`
    <h2>${escapeHtml(data.relation)}</h2>
    <table class="attr-table"><tbody>${rows}</tbody></table>
    <h3>Evidência</h3>
    ${buildEvidenceHtml(attrs)}
  `);
}

function buildEvidenceHtml(attrs) {
  const caseText = state.currentCasePayload.case_text;
  const start = Number.parseInt(attrs.char_start, 10);
  const end = Number.parseInt(attrs.char_end, 10);
  const hasSpan =
    caseText && Number.isFinite(start) && Number.isFinite(end) && end > start && end <= caseText.length;

  if (!hasSpan) {
    return `<p class="evidence-snippet">"${escapeHtml(attrs.evidence_text || "")}"</p>`;
  }

  const before = escapeHtml(caseText.slice(0, start));
  const span = escapeHtml(caseText.slice(start, end));
  const after = escapeHtml(caseText.slice(end));
  return `<p class="case-text">${before}<mark id="evidence-mark">${span}</mark>${after}</p>`;
}

init().catch((error) => {
  console.error(error);
  showEmptyState(true, `Erro ao carregar dados: ${error.message}`);
});
