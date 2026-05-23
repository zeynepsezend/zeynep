import React from 'react';
import { ScoreData } from './Dashboard';

export interface WeightBarProps {
  scores: ScoreData;
}

const getScoreColor = (score: number): string => {
  if (score > 75) return '#00E5FF';
  if (score >= 40) return '#FF9500';
  return '#FF3B30';
};

interface Tool {
  key: keyof Pick<ScoreData, 'collision' | 'visibility' | 'path' | 'reachability' | 'orientation'>;
  label: string;
  weightKey: keyof ScoreData['weights'];
}

const TOOLS: Tool[] = [
  { key: 'collision', label: 'Collision', weightKey: 'collision' },
  { key: 'visibility', label: 'Visibility', weightKey: 'visibility' },
  { key: 'path', label: 'Path', weightKey: 'path' },
  { key: 'reachability', label: 'Reach', weightKey: 'reachability' },
  { key: 'orientation', label: 'Orient', weightKey: 'orientation' },
];

const WeightBar: React.FC<WeightBarProps> = ({ scores }) => {
  const contributions = TOOLS.map(tool => ({
    ...tool,
    score: scores[tool.key] as number,
    weight: scores.weights[tool.weightKey] as number,
    contribution: (scores[tool.key] as number) * (scores.weights[tool.weightKey] as number),
  }));

  const totalContribution = contributions.reduce((sum, t) => sum + t.contribution, 0);

  const containerStyle: React.CSSProperties = {
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const titleStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '11px',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    marginBottom: '10px',
  };

  const barContainerStyle: React.CSSProperties = {
    display: 'flex',
    height: '20px',
    borderRadius: '6px',
    overflow: 'hidden',
    gap: '1px',
  };

  const labelsStyle: React.CSSProperties = {
    display: 'flex',
    marginTop: '6px',
    gap: '1px',
  };

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>Score Contributions</div>
      <div style={barContainerStyle}>
        {contributions.map(tool => {
          const pct = totalContribution > 0 ? (tool.contribution / totalContribution) * 100 : 20;
          const color = getScoreColor(tool.score);
          return (
            <div
              key={tool.key}
              title={`${tool.label}: ${Math.round(tool.contribution)} pts (${Math.round(tool.weight * 100)}% weight)`}
              style={{
                width: `${pct}%`,
                background: color,
                opacity: 0.7,
                transition: 'width 0.5s ease',
                position: 'relative',
              }}
            />
          );
        })}
      </div>
      <div style={labelsStyle}>
        {contributions.map(tool => {
          const pct = totalContribution > 0 ? (tool.contribution / totalContribution) * 100 : 20;
          const color = getScoreColor(tool.score);
          return (
            <div
              key={tool.key}
              style={{
                width: `${pct}%`,
                overflow: 'hidden',
              }}
            >
              <div style={{
                color,
                fontSize: '9px',
                letterSpacing: '0.03em',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {tool.label}
              </div>
              <div style={{ color: '#6b7b8d', fontSize: '9px' }}>
                {Math.round(tool.contribution)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default React.memo(WeightBar);
