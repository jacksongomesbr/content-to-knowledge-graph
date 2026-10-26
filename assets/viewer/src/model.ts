async function loadJson(path: string) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Falha ao carregar ${path}: ${response.status}`);
  return response.json();
}
const graph = await loadJson("./graph.json");
export const viewerConfig = await loadJson("./viewer-config.json") as { title: string; subtitle: string; layoutDescription?: string; types?: Record<string, {label: string; plural: string; color: string; shape: string}>; themes?: Record<string,string> };

export const types: Record<string, { label: string; plural: string; color: string; shape: string }> = {
  concept: { label: "Conceito", plural: "Conceitos", color: "#21675c", shape: "ellipse" },
  person: { label: "Pessoa", plural: "Pessoas", color: "#9a552d", shape: "ellipse" },
  place: { label: "Lugar", plural: "Lugares", color: "#467da4", shape: "diamond" },
  method: { label: "Método", plural: "Métodos", color: "#7f6b30", shape: "hexagon" },
  software: { label: "Software", plural: "Softwares", color: "#615b9d", shape: "round-rectangle" },
  format: { label: "Formato", plural: "Formatos", color: "#6c633b", shape: "round-rectangle" },
  application: { label: "Aplicação", plural: "Aplicações", color: "#45688d", shape: "round-rectangle" },
} as const;
export type EntityType = string;
export const themes: Record<string,string> = {};
Object.assign(types, viewerConfig.types || {});
Object.assign(themes, viewerConfig.themes || {});
for (const node of graph.nodes) {
  if (!Object.hasOwn(types, node.type)) types[node.type] = { label: node.type, plural: node.type, color: "#21675c", shape: "ellipse" };
  if (!Object.hasOwn(themes, node.theme)) themes[node.theme] = node.theme;
}
// Only catalogs represented by this graph belong in filters and legends.
for (const key of Object.keys(types)) if (!graph.nodes.some((n:Entity)=>n.type===key)) delete types[key];
for (const key of Object.keys(themes)) if (!graph.nodes.some((n:Entity)=>n.theme===key)) delete themes[key];
function safeUrl(path: string, base: string): string {
  const url = new URL(path, base);
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Protocolo de fonte não permitido");
  return url.href;
}
export interface Source {
  kind?: "book" | "bibliography";
  title?: string;
  chapter: number;
  path: string;
  sourceFile: string;
  section: string;
  anchor: string;
  citations: string[];
}
export interface WikipediaReference {
  title: string;
  url: string;
  language: "pt" | "en";
  verifiedAt: string;
  note?: string;
}
export function validWikipediaReference(
  reference: WikipediaReference,
): boolean {
  try {
    const url = new URL(reference.url);
    return (
      ["pt", "en"].includes(reference.language) &&
      url.protocol === "https:" &&
      url.hostname === `${reference.language}.wikipedia.org` &&
      !url.port &&
      !url.username &&
      !url.password &&
      url.pathname.startsWith("/wiki/") &&
      reference.title.trim().length > 0 &&
      /^\d{4}-\d{2}-\d{2}$/.test(reference.verifiedAt) &&
      !Number.isNaN(Date.parse(reference.verifiedAt))
    );
  } catch {
    return false;
  }
}
export interface Entity {
  id: string;
  label: string;
  type: EntityType;
  theme: keyof typeof themes;
  summary: string;
  detail: string;
  math?: string;
  wikipedia?: WikipediaReference;
  sources: string[];
  aliases?: string[];
}
export interface Relation {
  id: string;
  source: string;
  target: string;
  label: string;
  summary: string;
  sources: string[];
}
export interface BibliographicReference {
  label: string;
  path: string;
  anchor: string;
}
export interface GraphData {
  bibliography: Record<string, BibliographicReference>;
  schemaVersion: number;
  bookUrl: string;
  sources: Record<string, Source>;
  nodes: Entity[];
  edges: Relation[];
}
export const data = graph as GraphData;
export const entities = new Map(data.nodes.map((node) => [node.id, node]));
export const relations = new Map(data.edges.map((edge) => [edge.id, edge]));
export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}
export function sourceUrl(source: Source): string {
  return `${safeUrl(source.path, source.path.startsWith("evidence/") ? location.href : data.bookUrl)}#${encodeURIComponent(source.anchor)}`;
}
export function bibliographyUrl(reference: BibliographicReference): string {
  return `${safeUrl(reference.path, reference.path.startsWith("evidence/") ? location.href : data.bookUrl)}#${encodeURIComponent(reference.anchor)}`;
}
export function citationKeys(sourceKeys: string[]): string[] {
  return [...new Set(sourceKeys.flatMap((key) => data.sources[key].citations))];
}
export function related(id: string): Relation[] {
  return data.edges.filter((edge) => edge.source === id || edge.target === id);
}
export interface Filters {
  query: string;
  type: string;
  theme: string;
  neighborhood?: string;
}
export function filterGraph(filters: Filters): {
  nodes: Entity[];
  edges: Relation[];
} {
  const query = normalize(filters.query.trim());
  const neighborhood = filters.neighborhood
    ? new Set([
        filters.neighborhood,
        ...related(filters.neighborhood).flatMap((edge) => [
          edge.source,
          edge.target,
        ]),
      ])
    : null;
  const nodes = data.nodes.filter(
    (node) =>
      (!filters.type || node.type === filters.type) &&
      (!filters.theme || node.theme === filters.theme) &&
      (!neighborhood || neighborhood.has(node.id)) &&
      (!query ||
        normalize(
          `${node.label} ${(node.aliases || []).join(" ")} ${node.summary} ${node.detail} ${types[node.type].label}`,
        ).includes(query)),
  );
  const ids = new Set(nodes.map((node) => node.id));
  return {
    nodes,
    edges: data.edges.filter(
      (edge) => ids.has(edge.source) && ids.has(edge.target),
    ),
  };
}
export function validateGraph(graph: GraphData): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();
  for (const item of [...graph.nodes, ...graph.edges]) {
    if (ids.has(item.id)) errors.push(`Identificador repetido: ${item.id}`);
    ids.add(item.id);
    if (!item.sources.length) errors.push(`Fonte ausente: ${item.id}`);
    for (const key of item.sources)
      if (!graph.sources[key]) errors.push(`Fonte desconhecida: ${key}`);
  }
  for (const source of Object.values(graph.sources)) {
    for (const key of source.citations) {
      if (!graph.bibliography[key]?.label)
        errors.push(`Referência bibliográfica ausente: ${key}`);
    }
  }
  const nodeIds = new Set(graph.nodes.map((node) => node.id));
  for (const node of graph.nodes) {
    if (node.wikipedia && !validWikipediaReference(node.wikipedia))
      errors.push(`Referência Wikipédia inválida: ${node.id}`);
    if (!(node.type in types)) errors.push(`Tipo desconhecido: ${node.type}`);
    if (!(node.theme in themes))
      errors.push(`Tema desconhecido: ${node.theme}`);
    if (!node.summary || !node.detail)
      errors.push(`Explicação ausente: ${node.id}`);
  }
  for (const edge of graph.edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target))
      errors.push(`Extremidade inexistente: ${edge.id}`);
    if (!edge.label || !edge.summary)
      errors.push(`Relação sem explicação: ${edge.id}`);
  }
  return errors;
}

export function paginate<T>(items: T[], page: number, size = 30) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.max(0, Math.min(page, pages - 1));
  return {
    items: items.slice(current * size, (current + 1) * size),
    page: current,
    pages,
    total: items.length,
    start: items.length ? current * size + 1 : 0,
    end: Math.min((current + 1) * size, items.length),
  };
}
