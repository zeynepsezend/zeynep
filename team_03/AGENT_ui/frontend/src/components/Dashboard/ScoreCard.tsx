import React from 'react';

export interface ScoreCardProps {
  name: string;
  score: number;
  weight: number;
  maxScore?: number;
}

const getScoreColor = (score: number): string => {
  if (score > 75) return '#00E5FF';
  if (score >= 40) return '#FF9500';
  return '#FF3B30';
};

const ScoreCard: React.FC<ScoreCardProps> = ({ name, score, weight, maxScore = 100 }) => {
  const size = 110;
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedScore = Math.max(0, Math.min(maxScore, score));
  const progress = clampedScore / maxScore;
  const dashOffset = circumference * (1 - progress);
  const color = getScoreColor(score);

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const svgContainerStyle: React.CSSProperties = {
    position: 'relative',
    width: size,
    height: size,
  };

  const centerTextStyle: React.CSSProperties = {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    textAlign: 'center',
    lineHeight: 1,
  };

  const scoreNumStyle: React.CSSProperties = {
    fontSize: '22px',
    fontWeight: 700,
    color,
    letterSpacing: '-0.02em',
    display: 'block',
  };

  const nameStyle: React.CSSProperties = {
    color: '#e0e6ed',
    fontSize: '11px',
    fontWeight: 500,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    textAlign: 'center',
  };

  const weightStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '10px',
    textAlign: 'center',
    letterSpacing: '0.02em',
  };

  return (
    <div style={containerStyle}>
      <div style={svgContainerStyle}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {/* Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={strokeWidth}
          />
          {/* Progress arc — starts from top (rotate -90deg) */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.4s ease' }}
            filter={`drop-shadow(0 0 4px ${color}40)`}
          />
        </svg>
        <div style={centerTextStyle}>
          <span style={scoreNumStyle}>{Math.round(score)}</span>
        </div>
      </div>
      <div style={nameStyle}>{name}</div>
      <div style={weightStyle}>{Math.round(weight * 100)}% weight</div>
    </div>
  );
};

export default React.memo(ScoreCard);
