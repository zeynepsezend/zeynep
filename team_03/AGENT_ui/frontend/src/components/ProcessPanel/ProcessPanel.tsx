import React from 'react';
import GlassPanel from '../common/GlassPanel';
import ToolStatusCard, { NodeStatus } from './ToolStatusCard';

export interface ProcessPanelProps {
  nodeStatuses: Record<string, NodeStatus>;
}

type PipelineEntry =
  | { type: 'single'; name: string }
  | { type: 'parallel'; names: string[] };

const PIPELINE: PipelineEntry[] = [
  { type: 'single', name: 'profile_agent' },
  { type: 'single', name: 'space_type_agent' },
  { type: 'single', name: 'reason' },
  { type: 'single', name: 'add_objects' },
  { type: 'parallel', names: ['collision', 'visibility', 'orientation'] },
  { type: 'parallel', names: ['path_analysis', 'reachability'] },
  { type: 'single', name: 'scoring' },
  { type: 'single', name: 'checkpoint' },
  { type: 'single', name: 'explain' },
];

const ConnectorLine: React.FC<{ width?: string }> = ({ width = '1px' }) => (
  <div style={{
    width,
    height: '16px',
    background: 'rgba(0, 229, 255, 0.15)',
    margin: '0 auto',
    flexShrink: 0,
  }} />
);

const FanConnector: React.FC<{ count: number }> = ({ count }) => {
  if (count <= 1) return <ConnectorLine />;
  return (
    <div style={{ position: 'relative', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg
        width="100%"
        height="20"
        viewBox={`0 0 ${count * 80} 20`}
        preserveAspectRatio="none"
        style={{ overflow: 'visible' }}
      >
        {Array.from({ length: count }, (_, i) => {
          const x = (i + 0.5) * (100 / count);
          return (
            <line
              key={i}
              x1="50%" y1="0"
              x2={`${x}%`} y2="20"
              stroke="rgba(0, 229, 255, 0.15)"
              strokeWidth="1"
            />
          );
        })}
      </svg>
    </div>
  );
};

const FanInConnector: React.FC<{ count: number }> = ({ count }) => {
  if (count <= 1) return <ConnectorLine />;
  return (
    <div style={{ position: 'relative', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg
        width="100%"
        height="20"
        viewBox={`0 0 ${count * 80} 20`}
        preserveAspectRatio="none"
        style={{ overflow: 'visible' }}
      >
        {Array.from({ length: count }, (_, i) => {
          const x = (i + 0.5) * (100 / count);
          return (
            <line
              key={i}
              x1={`${x}%`} y1="0"
              x2="50%" y2="20"
              stroke="rgba(0, 229, 255, 0.15)"
              strokeWidth="1"
            />
          );
        })}
      </svg>
    </div>
  );
};

const ProcessPanel: React.FC<ProcessPanelProps> = ({ nodeStatuses }) => {
  const getStatus = (name: string): NodeStatus =>
    nodeStatuses[name] ?? 'pending';

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '14px',
    flexShrink: 0,
  };

  const titleStyle: React.CSSProperties = {
    color: '#e0e6ed',
    fontSize: '13px',
    fontWeight: 600,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const parallelGroupStyle: React.CSSProperties = {
    display: 'flex',
    gap: '8px',
    alignItems: 'stretch',
  };

  const parallelGroupLabelStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '9px',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    textAlign: 'center',
    marginBottom: '4px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const panelStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflowY: 'auto',
    scrollbarWidth: 'thin',
    scrollbarColor: 'rgba(0,229,255,0.2) transparent',
  };

  return (
    <GlassPanel style={panelStyle}>
      <div style={headerStyle}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00E5FF" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
        </svg>
        <span style={titleStyle}>Pipeline</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {PIPELINE.map((entry, idx) => {
          const isLast = idx === PIPELINE.length - 1;
          const nextEntry = PIPELINE[idx + 1];

          if (entry.type === 'single') {
            return (
              <React.Fragment key={entry.name}>
                <ToolStatusCard
                  name={entry.name}
                  status={getStatus(entry.name)}
                />
                {!isLast && (
                  nextEntry?.type === 'parallel'
                    ? <FanConnector count={nextEntry.names.length} />
                    : <ConnectorLine />
                )}
              </React.Fragment>
            );
          } else {
            // parallel group
            return (
              <React.Fragment key={entry.names.join('|')}>
                <div style={parallelGroupLabelStyle}>parallel</div>
                <div style={parallelGroupStyle}>
                  {entry.names.map(name => (
                    <div key={name} style={{ flex: 1 }}>
                      <ToolStatusCard
                        name={name}
                        status={getStatus(name)}
                      />
                    </div>
                  ))}
                </div>
                {!isLast && <FanInConnector count={entry.names.length} />}
              </React.Fragment>
            );
          }
        })}
      </div>
    </GlassPanel>
  );
};

export default React.memo(ProcessPanel);
