import {
  NODE_COLORS,
  EDGE_COLORS,
  NODE_SHAPES,
  NODE_SIZES,
  EDGE_DASHES,
  STRUCTURAL_EDGES,
  THEME,
} from './graphConfig';

// ── Types ───────────────────────────────────────────────────────────────────

export interface RawNode {
  id: string;
  ntype: string;
  name?: string;
  area?: number;
  center?: [number, number];
  clearance_ok?: boolean;
  min_clearance_m?: number;
  required_clearance_m?: number;
  move_direction?: [number, number];
  move_distance_m?: number;
  reachable?: boolean;
  facing_ok?: boolean;
  angle_diff?: number;
  width?: number;
  wall_type?: string;
  window_type?: string;
  length?: number;
  bbox_w?: number;
  bbox_d?: number;
  system?: string;
  [key: string]: unknown;
}

export interface RawLink {
  source: string;
  target: string;
  key?: number;
  etype: string;
  via_door?: string;
  distance_m?: number;
  door_width?: number;
  visible?: boolean;
  reachable?: boolean;
  [key: string]: unknown;
}

export interface NodeLinkData {
  directed: boolean;
  multigraph: boolean;
  graph: Record<string, unknown>;
  nodes: RawNode[];
  links: RawLink[];
}

export interface VisNode {
  id: string;
  label: string;
  x: number;
  y: number;
  color: {
    background: string;
    border: string;
    highlight: { background: string; border: string };
    hover: { background: string; border: string };
  };
  shape: string;
  size: number;
  title: string;
  font: { color: string; size: number };
  borderWidth: number;
  ntype: string;
  _meta: Record<string, unknown>;
}

export interface VisEdge {
  id: string;
  from: string;
  to: string;
  color: { color: string; highlight: string; hover: string; opacity: number };
  dashes: boolean | number[];
  width: number;
  smooth: { type: string; roundness: number };
  title: string;
  etype: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function computeScale(nodes: RawNode[]): { minX: number; minY: number; scale: number } {
  const xs: number[] = [];
  const ys: number[] = [];

  for (const n of nodes) {
    if (n.center && n.center[0] != null && n.center[1] != null) {
      xs.push(n.center[0]);
      ys.push(n.center[1]);
    }
  }

  if (xs.length === 0) return { minX: 0, minY: 0, scale: 10 };

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;

  // Scale to roughly 1200x800 vis.js canvas pixels
  const scale = Math.min(1200 / xRange, 800 / yRange);
  return { minX, minY, scale };
}

function buildNodeColor(ntype: string): VisNode['color'] {
  const fill = (NODE_COLORS as Record<string, string>)[ntype] || '#555';
  return {
    background: fill,
    border: `${fill}88`,
    highlight: { background: fill, border: THEME.accent },
    hover: { background: fill, border: `${fill}cc` },
  };
}

function buildEdgeColor(etype: string): VisEdge['color'] {
  const base = (EDGE_COLORS as Record<string, string>)[etype] || '#555';
  return {
    color: base,
    highlight: THEME.accent,
    hover: base,
    opacity: 0.55,
  };
}

function buildNodeTooltip(node: RawNode): string {
  const rows: string[] = [];
  const color = (NODE_COLORS as Record<string, string>)[node.ntype] || '#555';

  rows.push(`<div style="padding:10px 12px;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',system-ui,sans-serif;font-size:11px;line-height:1.55;color:${THEME.text}">`);
  rows.push(`<div style="font-weight:600;font-size:12px;margin-bottom:4px">${node.name || node.id}</div>`);
  rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">type</span><span style="color:${color};font-size:10.5px;font-weight:500">${node.ntype}</span></div>`);
  rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">id</span><span style="color:${THEME.muted};font-size:10px">${node.id}</span></div>`);

  if (node.ntype === 'room' && node.area != null) {
    rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">area</span><span style="font-size:10.5px">${node.area} m\u00b2</span></div>`);
  }
  if (node.ntype === 'door' && node.width != null) {
    rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">width</span><span style="font-size:10.5px">${node.width}m</span></div>`);
  }
  if (node.ntype === 'furniture' && node.center) {
    rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">pos</span><span style="font-size:10.5px">(${node.center[0].toFixed(1)}, ${node.center[1].toFixed(1)})</span></div>`);
  }
  if (node.clearance_ok !== undefined) {
    const ok = node.clearance_ok;
    rows.push(`<div style="height:1px;background:${THEME.panelBorder};margin:5px 0"></div>`);
    rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">clearance</span><span style="color:${ok ? THEME.ok : THEME.fail};font-weight:500;font-size:10.5px">${ok ? 'OK' : 'FAIL'}</span></div>`);
  }

  rows.push('</div>');
  return rows.join('');
}

function buildEdgeTooltip(link: RawLink, nodesById: Map<string, RawNode>): string {
  const rows: string[] = [];
  const srcNode = nodesById.get(link.source);
  const tgtNode = nodesById.get(link.target);

  rows.push(`<div style="padding:10px 12px;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',system-ui,sans-serif;font-size:11px;line-height:1.55;color:${THEME.text}">`);
  rows.push(`<div style="font-weight:600;font-size:12px;margin-bottom:4px">${link.etype}</div>`);
  rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">from</span><span style="font-size:10.5px">${srcNode?.name || link.source}</span></div>`);
  rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">to</span><span style="font-size:10.5px">${tgtNode?.name || link.target}</span></div>`);

  if (link.distance_m != null) {
    rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">distance</span><span style="font-size:10.5px">${link.distance_m}m</span></div>`);
  }
  if (link.visible !== undefined) {
    rows.push(`<div style="display:flex;gap:6px;margin-bottom:2px"><span style="color:${THEME.muted};min-width:52px;font-size:9.5px">visible</span><span style="font-size:10.5px">${link.visible ? 'Yes' : 'No'}</span></div>`);
  }

  rows.push('</div>');
  return rows.join('');
}

function extractMeta(node: RawNode): Record<string, unknown> {
  const SKIP = new Set(['center', 'geometry', 'ntype', 'name']);
  const meta: Record<string, unknown> = { id: node.id };
  for (const [k, v] of Object.entries(node)) {
    if (SKIP.has(k)) continue;
    if (v === null || v === undefined) continue;
    if (typeof v === 'object' && !Array.isArray(v)) continue;
    meta[k] = v;
  }
  return meta;
}

// ── Main mapper ─────────────────────────────────────────────────────────────

export function mapGraphData(graphData: NodeLinkData): { nodes: VisNode[]; edges: VisEdge[] } {
  const { minX, minY, scale } = computeScale(graphData.nodes);

  const nodesById = new Map<string, RawNode>();
  graphData.nodes.forEach(n => nodesById.set(n.id, n));

  let fallbackIdx = 0;

  const nodes: VisNode[] = graphData.nodes.map((node) => {
    let x: number;
    let y: number;

    if (node.center && node.center[0] != null && node.center[1] != null) {
      x = (node.center[0] - minX) * scale;
      y = -(node.center[1] - minY) * scale; // flip Y for architectural coords
    } else {
      const col = fallbackIdx % 8;
      const row = Math.floor(fallbackIdx / 8);
      x = -200 + col * 90;
      y = 300 + row * 70;
      fallbackIdx++;
    }

    const label = node.name
      ? node.name.length > 16
        ? node.name.slice(0, 14) + '\u2026'
        : node.name
      : node.id;

    return {
      id: node.id,
      label,
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
      color: buildNodeColor(node.ntype),
      shape: NODE_SHAPES[node.ntype] || 'dot',
      size: NODE_SIZES[node.ntype] || 10,
      title: buildNodeTooltip(node),
      font: { color: '#e0e6ed', size: 11 },
      borderWidth: 2,
      ntype: node.ntype,
      _meta: extractMeta(node),
    };
  });

  const edges: VisEdge[] = graphData.links.map((link, idx) => {
    const etype = link.etype || 'unknown';
    const id = `${link.source}__${link.target}__${etype}__${link.key ?? idx}`;
    const isStructural = STRUCTURAL_EDGES.has(etype);

    return {
      id,
      from: link.source,
      to: link.target,
      color: buildEdgeColor(etype),
      dashes: EDGE_DASHES[etype] ?? false,
      width: isStructural ? 1.5 : 1.0,
      smooth: { type: 'continuous', roundness: 0.3 },
      title: buildEdgeTooltip(link, nodesById),
      etype,
    };
  });

  return { nodes, edges };
}
