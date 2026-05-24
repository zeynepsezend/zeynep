import React from 'react';
import { useTheme } from './ThemeToggle';

export interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  glow?: boolean;
}

const GlassPanel: React.FC<GlassPanelProps> = ({ children, className, style, glow = false }) => {
  const { colors, theme } = useTheme();
  const isDark = theme === 'dark';

  const baseStyle: React.CSSProperties = {
    background: colors.panelBg,
    backdropFilter: 'blur(40px) saturate(180%)',
    WebkitBackdropFilter: 'blur(40px) saturate(180%)',
    border: `1px solid ${colors.border}`,
    borderRadius: '10px',
    padding: '16px',
    boxSizing: 'border-box',
    transition: 'background 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease',
    boxShadow: glow && isDark
      ? `0 0 20px rgba(0, 229, 255, 0.06), inset 0 1px 0 rgba(255,255,255,0.03)`
      : isDark
        ? 'inset 0 1px 0 rgba(255,255,255,0.03)'
        : '0 1px 3px rgba(0,0,0,0.04)',
    ...style,
  };

  return (
    <div className={className} style={baseStyle}>
      {children}
    </div>
  );
};

export default React.memo(GlassPanel);
