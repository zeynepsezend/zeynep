import React, { useState, useEffect, useCallback, useRef } from 'react';
import ThreeViewport from './components/ThreeViewport/ThreeViewport';
import LayerToggle from './components/LayerToggle';
import GraphPanel from './components/GraphPanel/GraphPanel';
import ChatPanel from './components/ChatPanel/ChatPanel';
import Dashboard from './components/Dashboard/Dashboard';
import ProcessPanel from './components/ProcessPanel/ProcessPanel';
import LayoutLoader from './components/LayoutLoader/LayoutLoader';
import ReasoningLog from './components/ReasoningLog/ReasoningLog';
import ThemeToggle, { useTheme } from './components/common/ThemeToggle';
import ResizeHandle from './components/common/ResizeHandle';
import { useWebSocket } from './hooks/useWebSocket';
import { useSelectionSync } from './hooks/useSelectionSync';
import { useLayoutState } from './hooks/useLayoutState';
import { useAgentState } from './hooks/useAgentState';
import type { LayerVisibility, LayerName } from './types';

// ─── Constants ────────────────────────────────────────────────────────────────

const COLLAPSED_WIDTH = 24;
const LEFT_DEFAULT_WIDTH = 280;
const RIGHT_DEFAULT_WIDTH = 360;
const LEFT_MIN = 180;
const LEFT_MAX = 520;
const RIGHT_MIN = 240;
const RIGHT_MAX = 600;

const GRAPH_DEFAULT_HEIGHT_PCT = 40;      // percentage of centre column (also used for dashboard)
const LOG_DEFAULT_HEIGHT_PCT   = 30;      // percentage of right sidebar
const LOADER_DEFAULT_HEIGHT    = 120;     // px — left sidebar top section

const defaultVisibility: LayerVisibility = {
  outline: true,
  rooms: true,
  doors: true,
  windows: true,
  furniture: true,
  mep: true,
  structure: true,
};

// ─── Chevron icons ────────────────────────────────────────────────────────────

const ChevronLeft: React.FC<{ size?: number }> = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

const ChevronRight: React.FC<{ size?: number }> = ({ size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

// ─── Collapse button ──────────────────────────────────────────────────────────

interface CollapseButtonProps {
  collapsed: boolean;
  side: 'left' | 'right';
  onClick: () => void;
}

const CollapseButton: React.FC<CollapseButtonProps> = ({ collapsed, side, onClick }) => {
  const { colors } = useTheme();
  const [hovered, setHovered] = useState(false);

  // For left sidebar: when open show left arrow (collapse left), when closed show right arrow (expand right)
  // For right sidebar: when open show right arrow (collapse right), when closed show left arrow (expand left)
  const showRight = (side === 'left' && collapsed) || (side === 'right' && !collapsed);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={collapsed ? 'Expand panel' : 'Collapse panel'}
      aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 20,
        height: 20,
        borderRadius: 4,
        border: `1px solid ${hovered ? colors.accent : colors.border}`,
        background: hovered ? colors.accentDim : 'transparent',
        color: hovered ? colors.accent : colors.muted,
        cursor: 'pointer',
        flexShrink: 0,
        outline: 'none',
        transition: 'background 0.15s, border-color 0.15s, color 0.15s',
        padding: 0,
      }}
    >
      {showRight ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
    </button>
  );
};

// ─── Vertical label for collapsed sidebars ────────────────────────────────────

const VerticalLabel: React.FC<{ text: string }> = ({ text }) => {
  const { colors } = useTheme();
  return (
    <div style={{
      writingMode: 'vertical-rl',
      textOrientation: 'mixed',
      transform: 'rotate(180deg)',
      fontSize: 9,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: colors.muted,
      userSelect: 'none',
      whiteSpace: 'nowrap',
    }}>
      {text}
    </div>
  );
};

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  // ── Theme & core hooks ────────────────────────────────────────────────────
  const { colors } = useTheme();
  const ws = useWebSocket();
  const { selectedId, select } = useSelectionSync(ws);
  const layoutState = useLayoutState();
  const agentState = useAgentState({ onScoresReady: layoutState.setScores });
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(defaultVisibility);
  const [logVisible, setLogVisible] = useState(false);

  // ── Sidebar widths ────────────────────────────────────────────────────────
  const [leftWidth, setLeftWidth]   = useState(LEFT_DEFAULT_WIDTH);
  const [rightWidth, setRightWidth] = useState(RIGHT_DEFAULT_WIDTH);
  const [leftCollapsed, setLeftCollapsed]   = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  // ── Left sidebar sub-panel heights ───────────────────────────────────────
  // LayoutLoader height in px (fixed), ProcessPanel takes the rest
  const [loaderHeight, setLoaderHeight] = useState(LOADER_DEFAULT_HEIGHT);

  // ── Centre sub-panel heights ──────────────────────────────────────────────
  // GraphPanel height as percentage of centre column height
  const [graphHeightPct, setGraphHeightPct] = useState(GRAPH_DEFAULT_HEIGHT_PCT);

  // ── Right sidebar sub-panel heights ──────────────────────────────────────
  // Log height as percentage; Chat takes the rest; Dashboard height mirrors graphHeightPct
  const [logHeightPct, setLogHeightPct] = useState(LOG_DEFAULT_HEIGHT_PCT);

  // ── Panel refs (used by ResizeHandle for size baseline) ───────────────────
  const leftRef    = useRef<HTMLDivElement>(null);
  const rightRef   = useRef<HTMLDivElement>(null);
  const centreRef  = useRef<HTMLDivElement>(null);
  const loaderRef  = useRef<HTMLDivElement>(null);
  const logRef     = useRef<HTMLDivElement>(null);

  // ── WebSocket dispatcher ──────────────────────────────────────────────────
  useEffect(() => {
    if (!ws.lastMessage) return;
    const msg = ws.lastMessage;
    switch (msg.type) {
      case 'agent_event':    agentState.handleAgentEvent(msg);    break;
      case 'agent_response': agentState.handleAgentResponse(msg); break;
      case 'state_update':   layoutState.updateFromWS(msg);       break;
      case 'selection_sync': select(msg.elementId, msg.source);   break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.lastMessage]);

  // ── Auto-load layout ──────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      await layoutState.fetchLayouts();
      if (!layoutState.layout) await layoutState.loadLayout('industrial_005');
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleToggleLayer = useCallback((layer: LayerName) => {
    setLayerVisibility(prev => ({ ...prev, [layer]: !prev[layer] }));
  }, []);

  const handleChatSend = useCallback((content: string) => {
    agentState.addUserMessage(content);
    // Always run demo simulation for now — the real backend pipeline
    // is not yet wired up, so WS messages won't produce agent events.
    // When the backend is connected, WS events will drive the UI instead.
    agentState.runDemoSimulation(content);
  }, [agentState]);

  const handleChatReset  = useCallback(() => { agentState.resetChat(); }, [agentState]);
  const handleChatCancel = useCallback(() => { agentState.cancelLast(); }, [agentState]);

  const handleLayoutSelect  = useCallback(async (name: string) => { await layoutState.loadLayout(name); }, [layoutState]);
  const handleLayoutUpload  = useCallback(async (file: File)   => { await layoutState.uploadLayout(file); }, [layoutState]);
  const handleViewportSelect = useCallback((id: string | null) => { select(id, 'viewport'); }, [select]);
  const handleGraphSelect    = useCallback((id: string | null) => { select(id, 'graph');    }, [select]);

  // ── Resize callbacks (clamped) ────────────────────────────────────────────
  const handleLeftResize = useCallback((px: number) => {
    setLeftWidth(Math.min(LEFT_MAX, Math.max(LEFT_MIN, px)));
  }, []);

  const handleRightResize = useCallback((px: number) => {
    // The right handle is on the left edge of the right panel;
    // drag right = smaller panel, so invert delta via the handle itself
    setRightWidth(Math.min(RIGHT_MAX, Math.max(RIGHT_MIN, px)));
  }, []);

  const handleLoaderResize = useCallback((px: number) => {
    setLoaderHeight(Math.min(400, Math.max(60, px)));
  }, []);

  const handleGraphResize = useCallback((px: number) => {
    if (!centreRef.current) return;
    const totalH = centreRef.current.getBoundingClientRect().height;
    if (totalH === 0) return;
    // px here is the height of the *graph* panel (bottom section)
    // ResizeHandle gives us leading panel size; here the leading panel is the viewport (top).
    // We use (totalH - px) for the graph percentage.
    const graphPx = Math.max(120, Math.min(totalH - 100, totalH - px));
    setGraphHeightPct(Math.round((graphPx / totalH) * 100));
  }, []);

  const handleLogResize = useCallback((px: number) => {
    if (!rightRef.current) return;
    const totalH = rightRef.current.getBoundingClientRect().height;
    if (totalH === 0) return;
    setLogHeightPct(Math.round((Math.max(80, Math.min(totalH * 0.6, px)) / totalH) * 100));
  }, []);

  // ── Derived widths ────────────────────────────────────────────────────────
  const effectiveLeftWidth  = leftCollapsed  ? COLLAPSED_WIDTH : leftWidth;
  const effectiveRightWidth = rightCollapsed ? COLLAPSED_WIDTH : rightWidth;

  // ── Shared styles ─────────────────────────────────────────────────────────
  const connectionDot: React.CSSProperties = {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background:  ws.isConnected ? '#39FF14' : '#FF4444',
    boxShadow:   ws.isConnected ? '0 0 8px #39FF14, 0 0 2px #39FF14' : '0 0 8px #FF4444, 0 0 2px #FF4444',
    flexShrink: 0,
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      background: colors.bg,
      color: colors.text,
      fontFamily: colors.font,
      overflow: 'hidden',
      transition: 'background 0.3s ease, color 0.3s ease',
    }}>

      {/* ══════════════════════════════════════════════════════════════════════
          LEFT SIDEBAR
      ══════════════════════════════════════════════════════════════════════ */}
      <div
        ref={leftRef}
        style={{
          width: effectiveLeftWidth,
          minWidth: effectiveLeftWidth,
          display: 'flex',
          flexDirection: 'column',
          borderRight: `1px solid ${colors.border}`,
          overflow: 'hidden',
          transition: leftCollapsed ? 'width 0.2s ease, min-width 0.2s ease' : 'none',
          flexShrink: 0,
        }}
      >
        {leftCollapsed ? (
          /* ── Collapsed strip ── */
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 8,
            gap: 10,
            height: '100%',
          }}>
            <CollapseButton collapsed side="left" onClick={() => setLeftCollapsed(false)} />
            <VerticalLabel text="Pipeline" />
          </div>
        ) : (
          /* ── Expanded content ── */
          <>
            {/* Top bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              borderBottom: `1px solid ${colors.border}`,
              flexShrink: 0,
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 10,
                color: colors.muted,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}>
                <span style={connectionDot} />
                {ws.isConnected ? 'Connected' : 'Disconnected'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ThemeToggle />
                <CollapseButton collapsed={false} side="left" onClick={() => setLeftCollapsed(true)} />
              </div>
            </div>

            {/* Layout Loader (resizable height) */}
            <div
              ref={loaderRef}
              style={{ height: loaderHeight, minHeight: 60, flexShrink: 0, overflow: 'hidden' }}
            >
              <LayoutLoader
                layouts={layoutState.availableLayouts}
                selectedLayout={layoutState.selectedLayoutName}
                onSelect={handleLayoutSelect}
                onUpload={handleLayoutUpload}
              />
            </div>

            {/* Horizontal resize handle between loader and pipeline */}
            <ResizeHandle
              orientation="horizontal"
              panelRef={loaderRef}
              onResize={handleLoaderResize}
            />

            {/* Process Panel */}
            <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
              <ProcessPanel nodeStatuses={agentState.nodeStatuses} />
            </div>
          </>
        )}
      </div>

      {/* Vertical resize handle — right edge of left sidebar */}
      {!leftCollapsed && (
        <ResizeHandle
          orientation="vertical"
          panelRef={leftRef}
          onResize={handleLeftResize}
        />
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          CENTRE COLUMN: Viewport (top) + Graph Panel (bottom)
      ══════════════════════════════════════════════════════════════════════ */}
      <div
        ref={centreRef}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}
      >
        {/* 3D Viewport */}
        <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
          {layoutState.layout ? (
            <ThreeViewport
              layout={layoutState.layout}
              selectedId={selectedId}
              onSelect={handleViewportSelect}
              layers={layerVisibility}
              graphData={layoutState.graphData}
            />
          ) : (
            <div style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: colors.bg,
              color: colors.muted,
              fontSize: 13,
              flexDirection: 'column',
              gap: 12,
              transition: 'background 0.3s ease',
            }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none"
                stroke={colors.accentDim} strokeWidth="1.5">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
              <span>Select or upload a layout to begin</span>
            </div>
          )}
          {layoutState.layout && (
            <LayerToggle layers={layerVisibility} onToggle={handleToggleLayer} />
          )}
        </div>

        {/* Horizontal resize handle between viewport and graph */}
        <ResizeHandle
          orientation="horizontal"
          panelRef={centreRef}
          onResize={handleGraphResize}
        />

        {/* Graph Panel */}
        <div style={{
          height: `${graphHeightPct}%`,
          minHeight: 120,
          borderTop: `1px solid ${colors.border}`,
        }}>
          <GraphPanel
            graphData={layoutState.graphData}
            selectedId={selectedId}
            onSelect={handleGraphSelect}
          />
        </div>
      </div>

      {/* Vertical resize handle — left edge of right sidebar */}
      {!rightCollapsed && (
        <ResizeHandle
          orientation="vertical"
          panelRef={rightRef}
          onResize={handleRightResize}
        />
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          RIGHT SIDEBAR: Chat + Log + Dashboard
      ══════════════════════════════════════════════════════════════════════ */}
      <div
        ref={rightRef}
        style={{
          width: effectiveRightWidth,
          minWidth: effectiveRightWidth,
          display: 'flex',
          flexDirection: 'column',
          borderLeft: `1px solid ${colors.border}`,
          overflow: 'hidden',
          transition: rightCollapsed ? 'width 0.2s ease, min-width 0.2s ease' : 'none',
          flexShrink: 0,
        }}
      >
        {rightCollapsed ? (
          /* ── Collapsed strip ── */
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingTop: 8,
            gap: 10,
            height: '100%',
          }}>
            <CollapseButton collapsed side="right" onClick={() => setRightCollapsed(false)} />
            <VerticalLabel text="Chat" />
          </div>
        ) : (
          /* ── Expanded content ── */
          <>
            {/* Chat Panel header row with collapse button */}
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {/* Collapse button row */}
              <div style={{
                display: 'flex',
                justifyContent: 'flex-start',
                padding: '6px 10px',
                borderBottom: `1px solid ${colors.border}`,
                flexShrink: 0,
              }}>
                <CollapseButton collapsed={false} side="right" onClick={() => setRightCollapsed(true)} />
              </div>
              <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                <ChatPanel
                  messages={agentState.messages}
                  onSend={handleChatSend}
                  isAgentRunning={agentState.isAgentRunning}
                  onReset={handleChatReset}
                  onCancel={handleChatCancel}
                />
              </div>
            </div>

            {/* Horizontal resize handle between Chat and Log */}
            <ResizeHandle
              orientation="horizontal"
              panelRef={logRef}
              onResize={handleLogResize}
            />

            {/* Reasoning Log */}
            <div
              ref={logRef}
              style={{
                height: logVisible ? `${logHeightPct}%` : 'auto',
                minHeight: logVisible ? 80 : 0,
                borderTop: `1px solid ${colors.border}`,
                overflow: 'hidden',
              }}
            >
              <ReasoningLog
                entries={agentState.logEntries}
                visible={logVisible}
                onToggle={() => setLogVisible(v => !v)}
                isRunning={agentState.isAgentRunning}
              />
            </div>

            {/* Dashboard — height mirrors graph panel (graphHeightPct) */}
            <div
              style={{
                height: `${graphHeightPct}%`,
                minHeight: 100,
                overflow: 'auto',
                borderTop: `1px solid ${colors.border}`,
              }}
            >
              <Dashboard scores={layoutState.scores} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
