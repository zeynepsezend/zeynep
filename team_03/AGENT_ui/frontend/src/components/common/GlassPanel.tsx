import React from 'react';

export interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

const GlassPanel: React.FC<GlassPanelProps> = ({ children, className, style }) => {
  const baseStyle: React.CSSProperties = {
    background: 'rgba(10, 14, 23, 0.85)',
    backdropFilter: 'blur(24px) saturate(180%)',
    WebkitBackdropFilter: 'blur(24px) saturate(180%)',
    border: '1px solid rgba(0, 229, 255, 0.15)',
    borderRadius: '12px',
    padding: '16px',
    boxSizing: 'border-box',
    ...style,
  };

  return (
    <div className={className} style={baseStyle}>
      {children}
    </div>
  );
};

export default React.memo(GlassPanel);
