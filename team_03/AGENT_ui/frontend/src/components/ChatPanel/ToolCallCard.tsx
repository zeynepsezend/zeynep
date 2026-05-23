import React, { useState } from 'react';

export interface ToolCallCardProps {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  args?: unknown;
  result?: unknown;
}

const statusColors: Record<string, string> = {
  pending: '#6b7b8d',
  running: '#FF9500',
  completed: '#00C853',
  error: '#FF3B30',
};

const StatusDot: React.FC<{ status: string }> = ({ status }) => {
  const color = statusColors[status] ?? '#6b7b8d';
  const isPulsing = status === 'running';

  return (
    <span
      style={{
        display: 'inline-block',
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        backgroundColor: color,
        flexShrink: 0,
        boxShadow: isPulsing ? `0 0 6px ${color}` : 'none',
        animation: isPulsing ? 'toolcardPulse 1.2s ease-in-out infinite' : 'none',
      }}
    />
  );
};

const ToolCallCard: React.FC<ToolCallCardProps> = ({ name, status, args, result }) => {
  const [expanded, setExpanded] = useState(false);

  const cardStyle: React.CSSProperties = {
    background: 'rgba(0, 229, 255, 0.04)',
    border: '1px solid rgba(0, 229, 255, 0.12)',
    borderRadius: '8px',
    padding: '8px 10px',
    marginTop: '6px',
    cursor: 'pointer',
    transition: 'background 0.15s',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  const nameStyle: React.CSSProperties = {
    color: '#00E5FF',
    fontSize: '12px',
    fontWeight: 500,
    letterSpacing: '0.02em',
    flex: 1,
    fontFamily: '"SF Mono", "Fira Code", monospace',
  };

  const statusTextStyle: React.CSSProperties = {
    color: statusColors[status] ?? '#6b7b8d',
    fontSize: '11px',
    textTransform: 'capitalize',
  };

  const chevronStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '10px',
    transition: 'transform 0.2s',
    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
    display: 'inline-block',
  };

  const codeStyle: React.CSSProperties = {
    marginTop: '10px',
    background: 'rgba(0, 0, 0, 0.3)',
    borderRadius: '6px',
    padding: '8px',
    fontSize: '11px',
    color: '#b0bec5',
    fontFamily: '"SF Mono", "Fira Code", monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    overflowX: 'auto',
    maxHeight: '200px',
    overflowY: 'auto',
  };

  const sectionLabelStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '10px',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginTop: '8px',
    marginBottom: '4px',
  };

  return (
    <>
      <style>{`
        @keyframes toolcardPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
      <div
        style={cardStyle}
        onClick={() => setExpanded(v => !v)}
        onMouseEnter={e => {
          (e.currentTarget as HTMLDivElement).style.background = 'rgba(0, 229, 255, 0.08)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLDivElement).style.background = 'rgba(0, 229, 255, 0.04)';
        }}
      >
        <div style={headerStyle}>
          <StatusDot status={status} />
          <span style={nameStyle}>{name}</span>
          <span style={statusTextStyle}>{status}</span>
          <span style={chevronStyle}>&#9660;</span>
        </div>

        {expanded && (
          <div>
            {args !== undefined && (
              <>
                <div style={sectionLabelStyle}>Arguments</div>
                <div style={codeStyle}>
                  {JSON.stringify(args, null, 2)}
                </div>
              </>
            )}
            {result !== undefined && (
              <>
                <div style={sectionLabelStyle}>Result</div>
                <div style={codeStyle}>
                  {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                </div>
              </>
            )}
            {args === undefined && result === undefined && (
              <div style={{ ...codeStyle, color: '#6b7b8d', fontStyle: 'italic' }}>
                No data available
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default React.memo(ToolCallCard);
