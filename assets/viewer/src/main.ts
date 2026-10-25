import { initializeAppearance } from "./appearance";
import { GraphView } from "./graph-view";
import katex from "katex";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/newsreader/400.css";
import "katex/dist/katex.min.css";
import "./style.css";
import {
  data,
  viewerConfig,
  entities,
  relations,
  types,
  themes,
  filterGraph,
  paginate,
  related,
  sourceUrl,
  bibliographyUrl,
  citationKeys,
  validateGraph,
  type Entity,
  type Relation,
  type Filters,
} from "./model";

document.title = viewerConfig.title;
for (const [key, type] of Object.entries(types)) {
  if (/^[a-z0-9-]+$/i.test(key) && /^#[a-f0-9]{6}$/i.test(type.color)) document.documentElement.style.setProperty(`--node-${key}`, type.color);
}
const errors = validateGraph(data);
if (errors.length) throw new Error(errors.join("\n"));
const $ = <T extends HTMLElement = HTMLElement>(selector: string) =>
  document.querySelector<T>(selector)!;
const esc = (text: string) =>
  text.replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ]!,
  );
const icon = (name: string) => {
  const paths: Record<string, string> = {
    sidebar:
      '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m5-10 3 2-3 2"/>',
    expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2 6M20 4v7h-7"/>',
    graph:
      '<circle cx="6" cy="6" r="3"/><circle cx="18" cy="7" r="3"/><circle cx="12" cy="19" r="3"/><path d="m9 6 6 1M7 9l4 7m5-6-3 6"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
    book: '<path d="M12 5v15M3 4c3-1 6-1 9 1 3-2 6-2 9-1v15c-3-1-6-1-9 1-3-2-6-2-9-1Z"/>',
    fit: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/><circle cx="12" cy="12" r="3"/>',
    back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.graph}</svg>`;
};
let selection: { kind: "node" | "edge"; id: string } | null = null;
let graphView: GraphView;
let listMode: "nodes" | "edges" = "nodes";
let neighborhood = false;
let explorerOpen = false;
let graphExpanded = false;
let listPage = 0;
const filters: Filters = { query: "", type: "", theme: "" };
$("#app").innerHTML = `
<a class="skip-link" href="#details">Pular para a explicação</a>
<header class="topbar"><a class="brand" href="#"><span class="brand-icon">${icon("graph")}</span><span>Grafo de conhecimento<small>EXPLORADOR DE CONHECIMENTO</small></span></a><p class="book-context">${esc(viewerConfig.subtitle)}</p><div class="topbar-actions"><label class="appearance-control"><span class="sr-only">Aparência</span><select id="appearance" aria-label="Tema de aparência"><option value="system">Sistema</option><option value="light">Claro</option><option value="dark">Escuro</option></select></label><a class="book-link" aria-label="Abrir livro" href="${esc(/^https?:\/\//.test(data.bookUrl) ? data.bookUrl : "#")}" target="_blank" rel="noopener">${icon("book")}<span>Abrir livro</span>${icon("arrow")}</a></div></header>
<main class="workspace">
<h1 class="sr-only">Grafo de conhecimento</h1>
<aside class="explorer" aria-label="Catálogo do grafo">
<div class="explorer-bar"><button id="toggle-explorer" aria-label="Explorar o grafo" aria-expanded="false" aria-controls="explorer-content" title="Abrir explorador">${icon("sidebar")}<span>Explorar</span></button><div class="rail-counts" aria-label="${data.nodes.length} vértices e ${data.edges.length} arestas"><span><strong>${data.nodes.length}</strong>vértices</span><span><strong>${data.edges.length}</strong>arestas</span></div></div>
<div id="explorer-content" class="explorer-content" hidden>
<div class="eyebrow">CATÁLOGO DO GRAFO</div><h2>Explorar o grafo</h2><p class="intro">Encontre entidades e relações em todo o conteúdo registrado.</p>
<label class="search">${icon("search")}<span class="sr-only">Buscar entidade</span><input id="search" type="search" placeholder="Buscar no grafo…" autocomplete="off"></label>
<div class="filter-row"><label>Tipo<select id="type"><option value="">Todos os tipos</option>${Object.entries(
  types,
)
  .map(([id, type]) => `<option value="${esc(id)}">${esc(type.plural)}</option>`)
  .join(
    "",
  )}</select></label><label>Tema<select id="theme"><option value="">Todos os temas</option>${Object.entries(
  themes,
)
  .map(([id, label]) => `<option value="${esc(id)}">${esc(label)}</option>`)
  .join("")}</select></label></div>
<div class="list-heading"><div class="segmented" aria-label="Listagem"><button id="nodes-tab" aria-pressed="true">Vértices</button><button id="edges-tab" aria-pressed="false">Arestas</button></div><button id="clear" class="text-button">Limpar filtros</button></div>
<p id="result-count" class="result-count" role="status"></p><div id="entity-list" class="entity-list"></div><nav class="pagination" aria-label="Páginas do catálogo"><button id="previous-page" aria-label="Página anterior">${icon("back")}</button><span id="page-count" role="status"></span><button id="next-page" aria-label="Próxima página">${icon("arrow")}</button></nav>
<div class="explorer-footer">Um grafo de conhecimento com fontes.<br>Selecione uma entidade ou uma relação.</div></div>
</aside>
<section class="graph-area" aria-label="Grafo interativo do livro">
<div class="graph-top-controls" role="toolbar" aria-label="Ferramentas do grafo"><div class="layout-actions"><button id="relayout" class="toolbar-button">${icon("refresh")} Restaurar vista</button><button id="expand-graph" class="toolbar-button" aria-pressed="false">${icon("expand")}<span>Ampliar grafo</span></button><button id="focus-selection" class="toolbar-button" disabled>Focar seleção</button></div><label class="switch"><input id="neighbors" type="checkbox" disabled> Apenas vizinhos</label><label class="switch"><input id="labels" type="checkbox"> Rótulos das relações</label></div>
<div id="graph" role="img" aria-label="Grafo de entidades do livro. Use as listas de vértices e arestas para navegar pelo teclado."></div>
<div id="empty" class="empty" hidden><strong>Nenhuma entidade encontrada</strong><p>Tente outro termo ou limpe os filtros.</p><button id="empty-clear">Limpar filtros</button></div>
<div class="graph-bottom"><div class="graph-hint">${icon("info")} Arraste para girar · Role para aproximar · Selecione para descobrir</div><div class="zoom-controls"><button id="zoom-out" aria-label="Diminuir zoom">−</button><button id="fit" aria-label="Ajustar grafo à tela">${icon("fit")}</button><button id="zoom-in" aria-label="Aumentar zoom">+</button></div></div>
<div class="legend" aria-label="Tipos de entidade">${Object.entries(types)
  .map(
    ([key, type]) =>
      `<span><i style="--dot:${esc(type.color)}"></i>${esc(type.label)}</span>`,
  )
  .join("")}</div>
</section>
<aside id="details" class="details" tabindex="-1" aria-label="Explicação da seleção"></aside>
</main><div id="announcement" class="sr-only" role="status" aria-live="polite"></div>`;

function refreshGraphAppearance(): void {
  graphView?.appearance();
}
initializeAppearance(refreshGraphAppearance);

function sourceMarkup(keys: string[]): string {
  const citations = citationKeys(keys);
  const links = keys
    .filter((key) => data.sources[key].kind !== "bibliography")
    .map((key) => {
      const source = data.sources[key];
      return `<a class="source-link" href="${esc(sourceUrl(source))}" target="_blank" rel="noopener noreferrer">${icon("book")}<span>${source.chapter > 0 ? `Capítulo ${source.chapter}` : esc(source.title || "Fonte")}<strong>${esc(source.section)}</strong></span>${icon("arrow")}</a>`;
    })
    .join("");
  const references = citations.length
    ? `<p class="citations">Referências: ${citations
        .map((key) => {
          const reference = data.bibliography[key];
          return `<a class="bibliography-link" data-citation-key="${esc(key)}" title="${esc(reference.label)}" aria-label="${esc(reference.label)}" href="${esc(bibliographyUrl(reference))}" target="_blank" rel="noopener noreferrer">${esc(reference.label)}</a>`;
        })
        .join(" · ")}.</p>`
    : "";
  return `<section class="sources"><h3>Fontes</h3>${links}${references}<p class="source-note">Confira as evidências e os localizadores nas fontes indicadas.</p></section>`;
}
function wikipediaMarkup(node: Entity): string {
  const wiki = node.wikipedia;
  if (!wiki) return "";
  const language = wiki.language === "pt" ? "Português" : "Inglês";
  return `<section class="additional-reading"><h3>Leitura complementar</h3><a class="wikipedia-link" href="${esc(wiki.url)}" target="_blank" rel="noopener noreferrer" hreflang="${wiki.language}"><span class="wiki-mark" aria-hidden="true">W</span><span><small>Wikipédia · ${language}</small><strong lang="${wiki.language}">${esc(wiki.title)}</strong></span>${icon("arrow")}<span class="sr-only">(abre em nova aba)</span></a>${wiki.note ? `<p class="source-note">${esc(wiki.note)}</p>` : ""}</section>`;
}
function nodeButton(
  node: Entity,
  subtitle: string = types[node.type].label,
): string {
  return `<button class="entity-item ${selection?.id === node.id ? "active" : ""}" data-node="${esc(node.id)}" ${selection?.id === node.id ? 'aria-current="true"' : ""}><span class="entity-dot" style="--dot:${esc(types[node.type].color)}"></span><span><strong>${esc(node.label)}</strong><small>${esc(subtitle)}</small></span>${icon("arrow")}</button>`;
}
function renderPanel(): void {
  const panel = $("#details");
  if (!selection) {
    panel.innerHTML = `<div class="panel-top"><span class="eyebrow">SEU PONTO DE PARTIDA</span>${icon("graph")}</div><div class="welcome-mark" aria-hidden="true">${icon("graph")}</div><h2>${esc(viewerConfig.title)}</h2><p class="summary">Explore entidades, relações e fontes do conteúdo analisado. Abra o catálogo para buscar e filtrar.</p><div class="quick-start"><h3>Pontos de partida</h3>${data.nodes.slice(0, 5).map(node => nodeButton(node)).join("") || "<p>O grafo ainda não contém entidades.</p>"}</div><section class="model-note"><h3>Como ler o grafo</h3><p>As setas representam proposições apoiadas nas fontes. As posições agrupam entidades por tema editorial; a distância não mede similaridade, importância ou tempo.</p></section>`;
    return;
  }
  const item =
    selection.kind === "node"
      ? entities.get(selection.id)!
      : relations.get(selection.id)!;
  const top = `<div class="panel-top"><button class="text-button" id="back">${icon("back")} Voltar</button><button class="icon-button" id="close-details" aria-label="Fechar explicação">${icon("close")}</button></div>`;
  if (selection.kind === "node") {
    const node = item as Entity;
    const edges = related(node.id);
    panel.innerHTML = `${top}<div class="type-tag" style="--dot:${esc(types[node.type].color)}"><i></i>${esc(types[node.type].label)}</div><h2>${esc(node.label)}</h2><p class="summary">${esc(node.summary)}</p>${node.math ? `<div class="equation">${katex.renderToString(node.math, { displayMode: true, throwOnError: true, trust: false })}</div>` : ""}<p class="detail-text">${esc(node.detail)}</p><div class="panel-divider"></div><section><div class="section-heading"><h3>Relações</h3><span>${edges.length}</span></div><div class="related-list">${edges
      .map((edge) => {
        const other = entities.get(
          edge.source === node.id ? edge.target : edge.source,
        )!;
        return `<div class="relation-card"><button class="relation-label" data-edge="${esc(edge.id)}" aria-label="Explicar relação: ${esc(entities.get(edge.source)!.label)} ${esc(edge.label)} ${esc(entities.get(edge.target)!.label)}">${edge.source === node.id ? "→" : "←"} ${esc(edge.label)}</button>${nodeButton(other)}</div>`;
      })
      .join(
        "",
      )}</div></section>${sourceMarkup(node.sources)}${wikipediaMarkup(node)}`;
  } else {
    const edge = item as Relation;
    const from = entities.get(edge.source)!;
    const to = entities.get(edge.target)!;
    panel.innerHTML = `${top}<div class="type-tag relation-tag">RELAÇÃO · ARCO</div><h2 class="relation-title">${esc(from.label)}<span>${esc(edge.label)}</span>${esc(to.label)}</h2><p class="summary">${esc(edge.summary)}</p><section class="endpoints"><h3>Extremidades do arco</h3>${nodeButton(from, "Origem · " + types[from.type].label)}${nodeButton(to, "Destino · " + types[to.type].label)}</section><p class="source-note">A seta indica como ler a relação, da origem para o destino.</p>${sourceMarkup(edge.sources)}`;
  }
  $("#back")?.addEventListener("click", () => {
    if (history.state?.graphSelection) history.back();
    else clearSelection();
  });
  $("#close-details")?.addEventListener("click", clearSelection);
}
function updateList(): void {
  const visible = filterGraph(filters);
  $("#result-count").textContent =
    `${visible.nodes.length} de ${data.nodes.length} vértices · ${visible.edges.length} de ${data.edges.length} arestas`;
  const page = paginate<Entity | Relation>(
    listMode === "nodes" ? visible.nodes : visible.edges,
    listPage,
  );
  listPage = page.page;
  $("#entity-list").innerHTML = page.items
    .map((item) =>
      listMode === "nodes"
        ? nodeButton(item as Entity)
        : edgeButton(item as Relation),
    )
    .join("");
  if (!page.total)
    $("#entity-list").innerHTML =
      '<p class="no-results">Nenhum resultado. Tente outro termo ou limpe os filtros.</p>';
  $("#page-count").textContent = `${page.start}–${page.end} de ${page.total}`;
  $<HTMLButtonElement>("#previous-page").disabled = page.page === 0;
  $<HTMLButtonElement>("#next-page").disabled = page.page === page.pages - 1;
  $("#empty").hidden = visible.nodes.length > 0;
}
function edgeButton(edge: Relation): string {
  return `<button class="edge-item ${selection?.id === edge.id ? "active" : ""}" data-edge="${esc(edge.id)}"><span>${esc(entities.get(edge.source)!.label)}</span><strong>→ ${esc(edge.label)}</strong><span>${esc(entities.get(edge.target)!.label)}</span></button>`;
}
function setExplorer(open: boolean): void {
  explorerOpen = open;
  $(".workspace").classList.toggle("explorer-open", open);
  $("#explorer-content").hidden = !open;
  const button = $("#toggle-explorer");
  button.setAttribute("aria-expanded", String(open));
  $("#toggle-explorer span").textContent = open ? "Recolher" : "Explorar";
  button.setAttribute(
    "aria-label",
    open ? "Recolher explorador" : "Explorar o grafo",
  );
  button.setAttribute(
    "title",
    open ? "Recolher explorador" : "Explorar o grafo",
  );
  if (open) $("#search").focus({ preventScroll: true });
  else button.focus({ preventScroll: true });
  graphView.resize();
  graphView.reframe();
}
function setGraphExpanded(expanded: boolean): void {
  graphExpanded = expanded;
  $(".workspace").classList.toggle("graph-expanded", expanded);
  $("#details").hidden = expanded;
  $("#expand-graph").setAttribute("aria-pressed", String(expanded));
  $("#expand-graph span").textContent = expanded
    ? "Mostrar explicação"
    : "Ampliar grafo";
  graphView.resize();
  graphView.reframe();
}
function updateGraph(): void {
  const visible = filterGraph(filters);
  graphView.update(visible.nodes, visible.edges, selection);
  $<HTMLButtonElement>("#focus-selection").disabled = !selection;
  updateList();
}
function resetFilters(): void {
  listPage = 0;
  filters.query = "";
  filters.type = "";
  filters.theme = "";
  filters.neighborhood = undefined;
  neighborhood = false;
  $<HTMLInputElement>("#search").value = "";
  $<HTMLSelectElement>("#type").value = "";
  $<HTMLSelectElement>("#theme").value = "";
  $<HTMLInputElement>("#neighbors").checked = false;
}
function choose(
  kind: "node" | "edge",
  id: string,
  push = true,
  focus = false,
): void {
  if (!(kind === "node" ? entities.has(id) : relations.has(id))) return;
  selection = { kind, id };
  if (graphExpanded) setGraphExpanded(false);
  const visible = filterGraph(filters);
  if (
    !(kind === "node" ? visible.nodes : visible.edges).some(
      (item) => item.id === id,
    )
  )
    resetFilters();
  filters.neighborhood = neighborhood && kind === "node" ? id : undefined;
  $<HTMLInputElement>("#neighbors").disabled = kind !== "node";
  if (kind === "edge") {
    neighborhood = false;
    $<HTMLInputElement>("#neighbors").checked = false;
  }
  if (push && location.hash !== `#${kind}=${encodeURIComponent(id)}`)
    history.pushState({ graphSelection: true }, "", `#${kind}=${encodeURIComponent(id)}`);
  renderPanel();
  const items =
    listMode === "nodes"
      ? filterGraph(filters).nodes
      : filterGraph(filters).edges;
  const selectedIndex = items.findIndex((item) => item.id === id);
  if (selectedIndex >= 0) listPage = Math.floor(selectedIndex / 30);
  updateGraph();
  graphView.focus();
  $("#announcement").textContent =
    kind === "node"
      ? `Vértice selecionado: ${entities.get(id)!.label}`
      : `Relação selecionada: ${relations.get(id)!.label}`;
  if (focus) {
    $("#details").focus({ preventScroll: true });
  }
  if (matchMedia("(max-width: 760px)").matches)
    $("#details").scrollIntoView({ behavior: "instant", block: "start" });
}
function clearSelection(): void {
  selection = null;
  neighborhood = false;
  filters.neighborhood = undefined;
  $<HTMLInputElement>("#neighbors").disabled = true;
  $<HTMLInputElement>("#neighbors").checked = false;
  history.pushState(
    { graphSelection: true },
    "",
    `${location.pathname}${location.search}`,
  );
  renderPanel();
  updateGraph();
}
function syncLocation(): void {
  const match = /^#(node|edge)=(.+)$/.exec(location.hash);
  if (match) { try { match[2] = decodeURIComponent(match[2]); } catch { return; } }
  if (
    match &&
    (match[1] === "node" ? entities.has(match[2]) : relations.has(match[2]))
  )
    choose(match[1] as "node" | "edge", match[2], false);
  else {
    selection = null;
    neighborhood = false;
    filters.neighborhood = undefined;
    $<HTMLInputElement>("#neighbors").checked = false;
    $<HTMLInputElement>("#neighbors").disabled = true;
    renderPanel();
    updateGraph();
  }
}

async function start(): Promise<void> {
  await document.fonts.ready;
  graphView = new GraphView($("#graph"), (kind, id) => choose(kind, id));
  let resizeFrame = 0;
  const observer = new ResizeObserver(() => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      graphView.resize();
      graphView.reframe();
    });
  });
  observer.observe($("#graph"));
  $("#app").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>(
      "[data-node], [data-edge]",
    );
    if (button?.dataset.node) choose("node", button.dataset.node, true, true);
    if (button?.dataset.edge) choose("edge", button.dataset.edge, true, true);
  });
  $("#search").addEventListener("input", (event) => {
    listPage = 0;
    filters.query = (event.target as HTMLInputElement).value;
    updateGraph();
  });
  for (const key of ["type", "theme"] as const)
    $(`#${key}`).addEventListener("change", (event) => {
      listPage = 0;
      filters[key] = (event.target as HTMLSelectElement).value;
      updateGraph();
      graphView.fit();
    });
  for (const id of ["clear", "empty-clear"])
    $(`#${id}`).addEventListener("click", () => {
      resetFilters();
      updateGraph();
      graphView.fit();
    });
  $("#neighbors").addEventListener("change", (event) => {
    neighborhood = (event.target as HTMLInputElement).checked;
    filters.neighborhood =
      neighborhood && selection?.kind === "node" ? selection.id : undefined;
    updateGraph();
    graphView.fit();
  });
  $("#labels").addEventListener("change", (event) =>
    graphView.labelsVisible((event.target as HTMLInputElement).checked),
  );
  $("#fit").addEventListener("click", () => graphView.fit());
  $("#focus-selection").addEventListener("click", () => graphView.focus());
  for (const [id, factor] of [
    ["zoom-in", 1.3],
    ["zoom-out", 1 / 1.3],
  ] as const)
    $("#" + id).addEventListener("click", () => graphView.zoom(factor));
  for (const [id, mode] of [
    ["nodes-tab", "nodes"],
    ["edges-tab", "edges"],
  ] as const)
    $(`#${id}`).addEventListener("click", () => {
      listMode = mode;
      listPage = 0;
      $("#nodes-tab").setAttribute("aria-pressed", String(mode === "nodes"));
      $("#edges-tab").setAttribute("aria-pressed", String(mode === "edges"));
      updateList();
    });
  $(".brand").addEventListener("click", (event) => {
    event.preventDefault();
    resetFilters();
    clearSelection();
    graphView.fit();
  });
  $("#toggle-explorer").addEventListener("click", () =>
    setExplorer(!explorerOpen),
  );
  $("#expand-graph").addEventListener("click", () =>
    setGraphExpanded(!graphExpanded),
  );
  $("#relayout").addEventListener("click", () => graphView.restore());
  for (const [id, direction] of [
    ["previous-page", -1],
    ["next-page", 1],
  ] as const)
    $("#" + id).addEventListener("click", () => {
      listPage += direction;
      updateList();
      $("#entity-list").scrollTop = 0;
    });
  window.addEventListener("popstate", syncLocation);
  window.addEventListener("hashchange", syncLocation);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (explorerOpen) setExplorer(false);
      else if (graphExpanded) setGraphExpanded(false);
      else clearSelection();
    }
  });
  syncLocation();
  // The instance stays private; navigation is exposed through semantic HTML controls.
}
renderPanel();
start().catch((error) => {
  $("#details").innerHTML =
    "<h2>Não foi possível abrir o grafo</h2><p>Recarregue a página para tentar novamente.</p>";
  console.error(error);
});
