import React, { useState, useEffect, useCallback } from 'react';
import ThreeViewport from './components/ThreeViewport/ThreeViewport';
import LayerToggle from './components/LayerToggle';
import GraphPanel from './components/GraphPanel/GraphPanel';
import ChatPanel from './components/ChatPanel/ChatPanel';
import Dashboard from './components/Dashboard/Dashboard';
import ProcessPanel from './components/ProcessPanel/ProcessPanel';
import LayoutLoader from './components/LayoutLoader/LayoutLoader';
import { useWebSocket } from './hooks/useWebSocket';
import { useSelectionSync } from './hooks/useSelectionSync';
import { useLayoutState } from './hooks/useLayoutState';
import { useAgentState } from './hooks/useAgentState';
import type { LayerVisibility, LayerName } from './types';

const defaultVisibility: LayerVisibility = {
  outline: true,
  rooms: true,
  doors: true,
  windows: true,
  furniture: true,
  mep: true,
  structure: true,
};

export default function App() {
  // Hooks
  const ws = useWebSocket();
  const { selectedId, select } = useSelectionSync(ws);
  const layoutState = useLayoutState();
  const agentState = useAgentState();
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>(defaultVisibility);

  // WebSocket message dispatcher
  useEffect(() => {
    if (!ws.lastMessage) return;
    const msg = ws.lastMessage;
    switch (msg.type) {
      case 'agent_event':
        agentState.handleAgentEvent(msg);
        break;
      case 'agent_response':
        agentState.handleAgentResponse(msg);
        break;
      case 'state_update':
        layoutState.updateFromWS(msg);
        break;
      case 'selection_sync':
        select(msg.elementId, msg.source);
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.lastMessage]);

  // Load available layouts on mount
  useEffect(() => {
    layoutState.fetchLayouts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Layer toggle handler
  const handleToggleLayer = useCallback((layer: LayerName) => {
    setLayerVisibility(prev => ({ ...prev, [layer]: !prev[layer] }));
  }, []);

  // Chat send handler
  const handleChatSend = useCallback((content: string) => {
    agentState.addUserMessage(content);
    ws.send({ type: 'chat_message', content });
  }, [agentState, ws]);

  // Layout selection handler
  const handleLayoutSelect = useCallback(async (name: string) => {
    await layoutState.loadLayout(name);
  }, [layoutState]);

  // Layout upload handler
  const handleLayoutUpload = useCallback(async (file: File) => {
    await layoutState.uploadLayout(file);
  }, [layoutState]);

  // Viewport select handler
  const handleViewportSelect = useCallback((id: string | null) => {
    select(id, 'viewport');
  }, [select]);

  // Graph select handler
  const handleGraphSelect = useCallback((id: string | null) => {
    select(id, 'graph');
  }, [select]);

  // Connection status indicator
  const connectionDot: React.CSSProperties = {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: ws.isConnected ? '#00C853' : '#FF3B30',
    boxShadow: ws.isConnected ? '0 0 6px #00C853' : '0 0 6px #FF3B30',
    flexShrink: 0,
  };

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      width: '100vw',
      background: '#0a0e17',
      color: '#e0e6ed',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
      overflow: 'hidden',
    }}>
      {/* LEFT SIDEBAR: Layout Loader + Process Panel */}
      <div style={{
        width: 280,
        minWidth: 280,
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid rgba(0,229,255,0.1)',
        overflow: 'hidden',
      }}>
        {/* Connection status bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '8px 16px',
          borderBottom: '1px solid rgba(0,229,255,0.1)',
          fontSize: 10,
          color: '#6b7b8d',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          flexShrink: 0,
        }}>
          <span style={connectionDot} />
          {ws.isConnected ? 'Connected' : 'Disconnected'}
        </div>

        {/* Layout Loader */}
        <div style={{ flexShrink: 0 }}>
          <LayoutLoader
            layouts={layoutState.availableLayouts}
            selectedLayout={layoutState.selectedLayoutName}
            onSelect={handleLayoutSelect}
            onUpload={handleLayoutUpload}
          />
        </div>

        {/* Process Panel */}
        <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
          <ProcessPanel nodeStatuses={agentState.nodeStatuses} />
        </div>
      </div>

      {/* CENTER: Three.js Viewport (top) + Graph Panel (bottom) */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* 3D Viewport */}
        <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
          {layoutState.layout ? (
            <ThreeViewport
              layout={layoutState.layout}
              selectedId={selectedId}
              onSelect={handleViewportSelect}
              layers={layerVisibility}
            />
          ) : (
            <div style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#0a0e17',
              color: '#6b7b8d',
              fontSize: 14,
              flexDirection: 'column',
              gap: 12,
            }}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgba(0,229,255,0.2)" strokeWidth="1.5">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
              <span>Select or upload a layout to begin</span>
            </div>
          )}
          {/* Layer toggle overlay (only when layout loaded) */}
          {layoutState.layout && (
            <LayerToggle layers={layerVisibility} onToggle={handleToggleLayer} />
          )}
          {/* Selection info bar */}
          {selectedId && (
            <div style={{
              position: 'absolute',
              bottom: 16,
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(10,14,23,0.85)',
              border: '1px solid rgba(0,229,255,0.2)',
              borderRadius: 8,
              padding: '8px 20px',
              color: '#c0d8ef',
              fontFamily: '"SF Mono", "Fira Code", monospace',
              fontSize: 12,
              backdropFilter: 'blur(12px)',
              pointerEvents: 'none',
              zIndex: 10,
            }}>
              Selected: <span style={{ color: '#00E5FF' }}>{selectedId}</span>
            </div>
          )}
        </div>

        {/* Graph Panel */}
        <div style={{
          height: '40%',
          minHeight: 200,
          borderTop: '1px solid rgba(0,229,255,0.1)',
        }}>
          <GraphPanel
            graphData={layoutState.graphData}
            selectedId={selectedId}
            onSelect={handleGraphSelect}
          />
        </div>
      </div>

      {/* RIGHT SIDEBAR: Chat + Dashboard */}
      <div style={{
        width: 360,
        minWidth: 360,
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid rgba(0,229,255,0.1)',
        overflow: 'hidden',
      }}>
        {/* Chat Panel */}
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          <ChatPanel
            messages={agentState.messages}
            onSend={handleChatSend}
            isAgentRunning={agentState.isAgentRunning}
          />
        </div>

        {/* Dashboard */}
        <div style={{
          height: '50%',
          minHeight: 200,
          overflow: 'auto',
          borderTop: '1px solid rgba(0,229,255,0.1)',
        }}>
          <Dashboard scores={layoutState.scores} />
        </div>
      </div>
    </div>
  );
}
