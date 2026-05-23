import React from 'react';

export interface GradeDisplayProps {
  grade: string;
  score: number;
}

const gradeColors: Record<string, string> = {
  A: '#00E5FF',
  B: '#00C853',
  C: '#FFD600',
  D: '#FF9500',
  F: '#FF3B30',
};

const GradeDisplay: React.FC<GradeDisplayProps> = ({ grade, score }) => {
  const normalizedGrade = grade?.toUpperCase() ?? 'F';
  const color = gradeColors[normalizedGrade] ?? '#6b7b8d';

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const circleBadgeStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100px',
    height: '100px',
    borderRadius: '50%',
    background: `radial-gradient(circle at 35% 35%, ${color}22, ${color}08)`,
    border: `2px solid ${color}`,
    boxShadow: `0 0 24px ${color}30, inset 0 0 16px ${color}10`,
    transition: 'all 0.4s ease',
  };

  const gradeLetterStyle: React.CSSProperties = {
    fontSize: '52px',
    fontWeight: 800,
    color,
    lineHeight: 1,
    letterSpacing: '-0.03em',
    textShadow: `0 0 20px ${color}60`,
  };

  const scoreStyle: React.CSSProperties = {
    color: '#e0e6ed',
    fontSize: '28px',
    fontWeight: 700,
    letterSpacing: '-0.02em',
    lineHeight: 1,
  };

  const scoreLabelStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '11px',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginTop: '-4px',
  };

  return (
    <div style={containerStyle}>
      <div style={circleBadgeStyle}>
        <span style={gradeLetterStyle}>{normalizedGrade}</span>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={scoreStyle}>{Math.round(score)}</div>
        <div style={scoreLabelStyle}>Overall Score</div>
      </div>
    </div>
  );
};

export default React.memo(GradeDisplay);
