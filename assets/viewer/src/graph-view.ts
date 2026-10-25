import ForceGraph3D, {
  type ForceGraph3DInstance,
  type NodeObject,
  type LinkObject,
} from "3d-force-graph";
import SpriteText from "three-spritetext";
import {
  BoxGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  OctahedronGeometry,
  SphereGeometry,
  PerspectiveCamera,
  Vector3,
} from "three";
import { data, entities, related, type Entity, type Relation } from "./model";
const layout = await (await fetch("./layout.json")).json() as { positions: Record<string, {x:number;y:number;z:number}> };

type Selection = { kind: "node" | "edge"; id: string } | null;
interface VisualNode extends NodeObject {
  id: string;
  entity: Entity;
  x: number;
  y: number;
  z: number;
}
interface VisualLink extends LinkObject<VisualNode> {
  id: string;
  edge: Relation;
}
const endpoint = (value: VisualLink["source"]) =>
  typeof value === "object" ? value.id : String(value);
const wrap = (value: string) =>
  value.replace(/(.{1,24})(\s+|$)/g, "$1\n").trim();

export class GraphView {
  private graph?: ForceGraph3DInstance<VisualNode, VisualLink>;
  private nodes: VisualNode[];
  private links: VisualLink[];
  private visibleNodes = new Set(data.nodes.map((node) => node.id));
  private visibleLinks = new Set(data.edges.map((edge) => edge.id));
  private contextNodes = new Set<string>();
  private contextLinks = new Set<string>();
  private selection: Selection = null;
  private showLabels = false;
  private meshes = new Map<string, { mesh: Mesh; text: SpriteText }>();
  private labels = new Map<string, SpriteText>();
  private colors: Record<string, string> = {};
  constructor(
    private element: HTMLElement,
    choose: (kind: "node" | "edge", id: string) => void,
  ) {
    this.nodes = data.nodes.map((entity) => {
      const point =
        layout.positions[entity.id as keyof typeof layout.positions];
      if (!point) throw new Error(`Coordenada editorial ausente: ${entity.id}`);
      return {
        id: entity.id,
        entity,
        ...point,
        fx: point.x,
        fy: point.y,
        fz: point.z,
      };
    });
    this.links = data.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      edge,
    }));
    this.readColors();
    try {
      this.graph = new ForceGraph3D(element, {
        controlType: "orbit",
        rendererConfig: {
          antialias: true,
          alpha: false,
          preserveDrawingBuffer: true,
        },
      }) as unknown as ForceGraph3DInstance<VisualNode, VisualLink>;
    } catch {
      element.replaceChildren();
      const message = document.createElement("p");
      message.className = "graph-unavailable";
      message.textContent =
        "A visualização 3D exige WebGL. Use o catálogo de vértices e arestas para explorar todo o conteúdo neste navegador.";
      element.append(message);
      return;
    }
    const graph = this.graph;
    graph
      .cameraPosition({ x: 500, y: 250, z: 700 }, { x: 0, y: 0, z: 0 }, 0)
      .width(element.clientWidth)
      .height(element.clientHeight)
      .backgroundColor(this.colors.paper)
      .showNavInfo(false)
      .graphData({ nodes: this.nodes, links: this.links })
      .enableNodeDrag(false)
      .cooldownTicks(0)
      .warmupTicks(0)
      .nodeThreeObject((node) => this.makeNode(node))
      .nodeLabel((node) => this.tooltip(node.entity.label))
      .linkLabel((link) =>
        this.tooltip(
          `${entities.get(endpoint(link.source))!.label} → ${link.edge.label} → ${entities.get(endpoint(link.target))!.label}`,
        ),
      )
      .linkOpacity(0.7)
      .linkWidth((link) => (this.contextLinks.has(link.id) ? 1.2 : 0.35))
      .linkColor((link) => this.linkColor(link))
      .linkDirectionalArrowLength((link) =>
        this.contextLinks.has(link.id) ? 3 : 1.7,
      )
      .linkDirectionalArrowRelPos(0.78)
      .linkDirectionalArrowColor((link) => this.linkColor(link))
      .linkThreeObjectExtend(true)
      .linkThreeObject((link) => this.makeLinkLabel(link))
      .linkPositionUpdate((object, { start, end }) => {
        object.position.copy(
          new Vector3()
            .addVectors(start as Vector3, end as Vector3)
            .multiplyScalar(0.5),
        );
        return true;
      })
      .onNodeClick((node) => choose("node", node.id))
      .onLinkClick((link) => choose("edge", link.id))
      .onNodeHover((node) => {
        element.style.cursor = node ? "pointer" : "grab";
      })
      .onLinkHover((link) => {
        if (link) element.style.cursor = "pointer";
      })
      .linkHoverPrecision(4);
    this.update(data.nodes, data.edges, null);
    requestAnimationFrame(() => {
      this.resize();
      this.reframe();
      element.dataset.ready = "true";
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) graph.pauseAnimation();
      else graph.resumeAnimation();
    });
  }
  private tooltip(value: string): HTMLElement {
    const span = document.createElement("span");
    span.textContent = value;
    return span;
  }
  private readColors(): void {
    const css = getComputedStyle(document.documentElement);
    this.colors = Object.fromEntries(
      [
        "paper",
        "graph-text",
        "graph-edge",
        "graph-adjacent",
        "graph-selected",
        ...new Set(data.nodes.map((node) => `node-${node.type}`)),
      ].map((name) => [name, css.getPropertyValue(`--${name}`).trim()]),
    );
  }
  private makeNode(node: VisualNode): Group {
    const shape = node.entity.type;
    const geometry = ["method", "place"].includes(shape)
      ? new OctahedronGeometry(3.8)
      : [
              "result",
              "software",
              "problem",
              "format",
              "dataset",
              "application",
            ].includes(shape)
          ? new BoxGeometry(5.8, 5.8, 5.8)
          : new SphereGeometry(3.1, 16, 12);
    const mesh = new Mesh(
      geometry,
      new MeshBasicMaterial({
        color: this.colors[`node-${shape}`],
        transparent: true,
      }),
    );
    const text = new SpriteText(
      wrap(node.entity.label),
      4.2,
      this.colors["graph-text"],
    );
    // Transparent sprite rectangles must not intercept pointer hits on graph objects.
    text.raycast = () => {};
    text.fontFace = "DM Sans";
    text.fontSize = 64;
    text.padding = [1, 2];
    text.backgroundColor = this.colors.paper;
    text.borderRadius = 2;
    text.position.y = -7;
    text.material.depthWrite = false;
    const active = !this.selection || this.contextNodes.has(node.id);
    (mesh.material as MeshBasicMaterial).opacity = active ? 1 : 0.16;
    if (this.selection?.id === node.id) {
      mesh.scale.setScalar(1.6);
      text.color = this.colors["graph-selected"];
      text.textHeight = 6;
    }
    text.visible = active;
    const group = new Group();
    group.add(mesh, text);
    this.meshes.set(node.id, { mesh, text });
    return group;
  }
  private makeLinkLabel(link: VisualLink): SpriteText {
    const text = new SpriteText(
      wrap(link.edge.label),
      3.2,
      this.colors["graph-adjacent"],
    );
    // Transparent sprite rectangles must not intercept pointer hits on graph objects.
    text.raycast = () => {};
    text.fontFace = "DM Sans";
    text.fontSize = 56;
    text.backgroundColor = this.colors.paper;
    text.padding = 1;
    text.material.depthWrite = false;
    text.visible =
      this.visibleLinks.has(link.id) &&
      (this.showLabels || this.contextLinks.has(link.id));
    this.labels.set(link.id, text);
    return text;
  }
  private linkColor(link: VisualLink): string {
    if (this.selection?.id === link.id) return this.colors["graph-selected"];
    if (this.contextLinks.has(link.id)) return this.colors["graph-adjacent"];
    return this.selection
      ? document.documentElement.dataset.theme === "dark"
        ? "#293b30"
        : "#dce3dd"
      : this.colors["graph-edge"];
  }
  update(nodes: Entity[], links: Relation[], selection: Selection): void {
    this.visibleNodes = new Set(nodes.map((node) => node.id));
    this.visibleLinks = new Set(links.map((link) => link.id));
    this.selection = selection;
    this.contextNodes.clear();
    this.contextLinks.clear();
    if (selection?.kind === "node") {
      this.contextNodes.add(selection.id);
      for (const edge of related(selection.id)) {
        this.contextNodes.add(edge.source);
        this.contextNodes.add(edge.target);
        this.contextLinks.add(edge.id);
      }
    } else if (selection) {
      const edge = data.edges.find((edge) => edge.id === selection.id)!;
      this.contextNodes.add(edge.source);
      this.contextNodes.add(edge.target);
      this.contextLinks.add(edge.id);
    }
    this.paint();
  }
  private paint(): void {
    if (!this.graph) return;
    for (const node of this.nodes) {
      const view = this.meshes.get(node.id);
      if (!view) continue;
      const chosen = this.selection?.id === node.id,
        active = !this.selection || this.contextNodes.has(node.id);
      const material = view.mesh.material as MeshBasicMaterial;
      material.color.set(this.colors[`node-${node.entity.type}`]);
      material.opacity = active ? 1 : 0.16;
      view.mesh.scale.setScalar(chosen ? 1.6 : 1);
      view.text.color = chosen
        ? this.colors["graph-selected"]
        : this.colors["graph-text"];
      view.text.backgroundColor = this.colors.paper;
      view.text.visible = active;
      view.text.textHeight = chosen ? 6 : 4.2;
    }
    for (const link of this.links) {
      const label = this.labels.get(link.id);
      if (!label) continue;
      label.visible =
        this.visibleLinks.has(link.id) &&
        (this.showLabels || this.contextLinks.has(link.id));
      label.color = this.colors["graph-adjacent"];
      label.backgroundColor = this.colors.paper;
    }
    this.graph
      .nodeVisibility((node) => this.visibleNodes.has(node.id))
      .linkVisibility((link) => this.visibleLinks.has(link.id))
      .linkColor((link) => this.linkColor(link))
      .linkWidth((link) => (this.contextLinks.has(link.id) ? 1.2 : 0.35))
      .linkDirectionalArrowColor((link) => this.linkColor(link));
    // The library may build custom objects on the next render tick.
    requestAnimationFrame(() => {
      for (const [id, label] of this.labels)
        label.visible =
          this.visibleLinks.has(id) &&
          (this.showLabels || this.contextLinks.has(id));
    });
  }
  appearance(): void {
    this.readColors();
    this.graph?.backgroundColor(this.colors.paper);
    this.paint();
  }
  labelsVisible(value: boolean): void {
    this.showLabels = value;
    this.paint();
  }
  resize(): void {
    if (!this.graph) return;
    const width = this.element.clientWidth,
      height = this.element.clientHeight;
    if (width <= 0 || height <= 0) return;
    this.graph.width(width).height(height);
    // Apply the viewport synchronously before framing. The library debounces
    // prop updates, which otherwise leaves the camera using the previous aspect.
    this.graph.renderer().setSize(width, height);
    const camera = this.graph.camera() as PerspectiveCamera;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  fit(): void {
    if (this.visibleNodes.size)
      this.graph?.zoomToFit(0, 45, (node) => this.visibleNodes.has(node.id));
  }
  restore(): void {
    this.graph?.cameraPosition(
      { x: 500, y: 250, z: 700 },
      { x: 0, y: 0, z: 0 },
      0,
    );
    this.fit();
  }
  zoom(factor: number): void {
    if (!this.graph) return;
    const controls = this.graph.controls() as { target: Vector3 };
    const camera = this.graph.camera().position.clone();
    const next = camera
      .sub(controls.target)
      .multiplyScalar(1 / factor)
      .add(controls.target);
    this.graph.cameraPosition(next, controls.target, 150);
  }
  reframe(): void {
    if (this.selection) this.focus(0);
    else this.fit();
  }
  focus(duration = 350): void {
    if (!this.graph || !this.selection) return;
    const selected = this.selection;
    let target: Vector3;
    let radius: number;
    if (selected.kind === "node") {
      const node = this.nodes.find((node) => node.id === selected.id)!;
      if (!this.visibleNodes.has(node.id)) {
        this.fit();
        return;
      }
      target = new Vector3(node.x, node.y, node.z);
      const distances = this.nodes
        .filter(
          (neighbor) =>
            neighbor.id !== node.id &&
            this.contextNodes.has(neighbor.id) &&
            this.visibleNodes.has(neighbor.id),
        )
        .map((neighbor) =>
          target.distanceTo(new Vector3(neighbor.x, neighbor.y, neighbor.z)),
        )
        .sort((a, b) => a - b);
      // Keep the selected vertex at the exact center; fit the nearest context
      // instead of letting a distant neighbor pull the camera away from it.
      radius = Math.max(25, distances[Math.min(7, distances.length - 1)] || 25);
    } else {
      const edge = this.links.find((edge) => edge.id === selected.id)!;
      const source = this.nodes.find(
        (node) => node.id === endpoint(edge.source),
      )!;
      const destination = this.nodes.find(
        (node) => node.id === endpoint(edge.target),
      )!;
      target = new Vector3(source.x, source.y, source.z)
        .add(new Vector3(destination.x, destination.y, destination.z))
        .multiplyScalar(0.5);
      radius = Math.max(
        25,
        new Vector3(source.x, source.y, source.z).distanceTo(
          new Vector3(destination.x, destination.y, destination.z),
        ) /
          2 +
          12,
      );
    }
    const camera = this.graph.camera() as PerspectiveCamera;
    const controls = this.graph.controls() as { target: Vector3 };
    const verticalHalfFov = (camera.fov * Math.PI) / 360;
    const halfFov = Math.min(
      verticalHalfFov,
      Math.atan(Math.tan(verticalHalfFov) * camera.aspect),
    );
    const distance = Math.max(
      85,
      Math.min(
        selected.kind === "node" ? 420 : 900,
        (radius * 1.2) / Math.sin(halfFov),
      ),
    );
    const direction = camera.position.clone().sub(controls.target);
    if (direction.lengthSq() < 0.001) direction.set(1, 0.5, 1.4);
    const position = direction.normalize().multiplyScalar(distance).add(target);
    const milliseconds = matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 0
      : duration;
    this.graph.cameraPosition(position, target, milliseconds);
  }
}
