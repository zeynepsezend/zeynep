// ── Industrial-futuristic color palette ─────────────────────────────────────

export const NODE_COLORS = {
  room: '#1A4A6B',      // deep ocean blue
  door: '#FF8C42',      // warm orange
  wall: '#2D3A45',      // dark steel
  window: '#00E5FF',    // cyan neon
  furniture: '#00CED1', // turquoise
  mep: '#39FF14',       // electric green
} as const;

export const EDGE_COLORS = {
  contained_in: '#2D3A45',    // structural, muted
  door_connects: '#FF8C42',   // orange (door color)
  adjacent: '#1A4A6B',        // room connectivity
  near: '#00CED1',            // proximity (turquoise)
  near_wall: '#2D3A45',       // structural
  near_window: '#00E5FF',     // cyan
  sightline: '#39FF14',       // green for visible, red for blocked
  blocks: '#FF4444',          // red for obstructions
  path: '#00CED1',            // turquoise for paths
} as const;

export const NODE_SHAPES: Record<string, string> = {
  room: 'dot',
  door: 'diamond',
  wall: 'dot',
  window: 'dot',
  furniture: 'square',
  mep: 'dot',
};

export const NODE_SIZES: Record<string, number> = {
  room: 25,
  door: 10,
  wall: 8,
  window: 8,
  furniture: 15,
  mep: 12,
};

export const EDGE_DASHES: Record<string, boolean | number[]> = {
  contained_in: true,
  door_connects: false,
  adjacent: false,
  near: false,
  near_wall: true,
  near_window: true,
  sightline: [6, 4, 2, 4],
  blocks: false,
  path: false,
};

export const STRUCTURAL_EDGES = new Set([
  'contained_in', 'door_connects', 'adjacent', 'near_wall', 'near_window',
]);

export const NODE_DESCRIPTIONS: Record<string, string> = {
  room: 'A space enclosed by walls and accessible through doors.',
  door: 'An opening element connecting two spaces.',
  wall: 'A structural boundary element that encloses and separates spaces.',
  window: 'An opening in a wall providing natural light and ventilation.',
  furniture: 'A placed object occupying floor area with clearance requirements.',
  mep: 'Mechanical, Electrical, or Plumbing element.',
};

export const EDGE_DESCRIPTIONS: Record<string, string> = {
  contained_in: 'element belongs to room',
  door_connects: 'door links to room',
  adjacent: 'rooms share a door',
  near: 'furniture < 3m apart',
  near_wall: 'furniture < 3m from wall',
  near_window: 'furniture < 3m from window',
  blocks: 'object blocks access to another',
  sightline: 'direct line of sight',
  path: 'navigable route with distance',
};

// ── Vis.js network options ──────────────────────────────────────────────────

const FONT_FACE = '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif';

export const NETWORK_OPTIONS = {
  physics: { enabled: false },
  interaction: {
    hover: true,
    tooltipDelay: 150,
    dragNodes: true,
    dragView: true,
    zoomView: true,
    multiselect: false,
  },
  nodes: {
    shape: 'dot',
    font: {
      color: '#e0e6ed',
      size: 11,
      face: FONT_FACE,
      align: 'center' as const,
    },
    borderWidth: 2,
    shadow: {
      enabled: true,
      size: 8,
      x: 0,
      y: 2,
      color: 'rgba(0,0,0,0.25)',
    },
  },
  edges: {
    smooth: { type: 'continuous' as const, roundness: 0.3 },
    font: {
      color: '#6b7b8d',
      size: 9,
      face: FONT_FACE,
    },
  },
} as const;

// ── Theme constants ─────────────────────────────────────────────────────────

export const THEME = {
  panelBg: 'rgba(10, 14, 23, 0.85)',
  panelBorder: 'rgba(0, 229, 255, 0.15)',
  text: '#e0e6ed',
  muted: '#6b7b8d',
  accent: '#00E5FF',
  ok: '#39FF14',
  fail: '#FF4444',
  warn: '#FF8C42',
  canvasBg: '#0a0e17',
} as const;
