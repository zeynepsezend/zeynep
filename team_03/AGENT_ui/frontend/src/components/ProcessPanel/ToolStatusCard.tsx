import React from 'react';

export type NodeStatus = 'pending' | 'running' | 'completed' | 'error';

export interface ToolStatusCardProps {
  name: string;
  status: NodeStatus;
  duration?: number;
}

const CheckIcon: React.FC = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00C853" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const XIcon: React.FC = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#FF3B30" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

const statusConfig: Record<NodeStatus, {
  border: string;
  glow: string;
  dotColor: string;
  dotGlow: string;
  animation?: string;
}> = {
  pending: {
    border: 'rgba(107, 123, 141, 0.2)',
    glow: 'none',
    dotColor: '#6b7b8d',
    dotGlow: 'none',
  },
  running: {
    border: 'rgba(0, 229, 255, 0.5)',
    glow: '0 0 12px rgba(0, 229, 255, 0.15)',
    dotColor: '#00E5FF',
    dotGlow: '0 0 6px #00E5FF',
    animation: 'runningPulse 1.2s ease-in-out infinite',
  },
  completed: {
    border: 'rgba(0, 200, 83, 0.25)',
    glow: '0 0 8px rgba(0, 200, 83, 0.08)',
    dotColor: '#00C853',
    dotGlow: 'none',
  },
  error: {
    border: 'rgba(255, 59, 48, 0.4)',
    glow: '0 0 10px rgba(255, 59, 48, 0.1)',
    dotColor: '#FF3B30',
    dotGlow: 'none',
  },
};

const ToolStatusCard: React.FC<ToolStatusCardProps> = ({ name, status, duration }) => {
  const cfg = statusConfig[status];

  const cardStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '8px 12px',
    borderRadius: '8px',
    border: `1px solid ${cfg.border}`,
    background: 'rgba(255, 255, 255, 0.025)',
    boxShadow: cfg.glow,
    transition: 'border-color 0.3s, box-shadow 0.3s',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
    animation: cfg.animation,
  };

  const nameStyle: React.CSSProperties = {
    flex: 1,
    color: status === 'pending' ? '#6b7b8d' : '#e0e6ed',
    fontSize: '12px',
    fontWeight: status === 'running' ? 600 : 400,
    letterSpacing: '0.01em',
    fontFamily: '"SF Mono", "Fira Code", monospace',
    transition: 'color 0.3s',
  };

  const durationStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '10px',
    letterSpacing: '0.02em',
    flexShrink: 0,
  };

  const iconContainerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '18px',
    height: '18px',
    flexShrink: 0,
  };

  const renderStatusIcon = () => {
    switch (status) {
      case 'completed':
        return <CheckIcon />;
      case 'error':
        return <XIcon />;
      case 'running':
        return (
          <span style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: cfg.dotColor,
            boxShadow: cfg.dotGlow,
            animation: 'dotPulse 1s ease-in-out infinite',
          }} />
        );
      default:
        return (
          <span style={{
            display: 'inline-block',
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: cfg.dotColor,
          }} />
        );
    }
  };

  return (
    <>
      <style>{`
        @keyframes runningPulse {
          0%, 100% { border-color: rgba(0, 229, 255, 0.5); box-shadow: 0 0 12px rgba(0, 229, 255, 0.15); }
          50% { border-color: rgba(0, 229, 255, 0.25); box-shadow: 0 0 4px rgba(0, 229, 255, 0.05); }
        }
        @keyframes dotPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.8); }
        }
      `}</style>
      <div style={cardStyle}>
        <div style={iconContainerStyle}>
          {renderStatusIcon()}
        </div>
        <span style={nameStyle}>{name}</span>
        {duration !== undefined && status === 'completed' && (
          <span style={durationStyle}>{formatDuration(duration)}</span>
        )}
      </div>
    </>
  );
};

export default React.memo(ToolStatusCard);
