import React from 'react';
import GlassPanel from '../common/GlassPanel';
import ScoreCard from './ScoreCard';
import GradeDisplay from './GradeDisplay';
import Histogram from './Histogram';
import WeightBar from './WeightBar';

export interface ScoreData {
  overall: number;
  grade: string;
  collision: number;
  visibility: number;
  path: number;
  reachability: number;
  orientation: number;
  weights: {
    collision: number;
    visibility: number;
    path: number;
    reachability: number;
    orientation: number;
  };
  histogramData?: {
    clearance: number[];
    pathDistances: number[];
  };
}

export interface DashboardProps {
  scores: ScoreData | null;
}

const TOOL_SCORES: Array<{
  key: keyof Pick<ScoreData, 'collision' | 'visibility' | 'path' | 'reachability' | 'orientation'>;
  label: string;
  weightKey: keyof ScoreData['weights'];
}> = [
  { key: 'collision', label: 'Collision', weightKey: 'collision' },
  { key: 'visibility', label: 'Visibility', weightKey: 'visibility' },
  { key: 'path', label: 'Path', weightKey: 'path' },
  { key: 'reachability', label: 'Reachability', weightKey: 'reachability' },
  { key: 'orientation', label: 'Orientation', weightKey: 'orientation' },
];

const EmptyState: React.FC = () => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: '12px',
    color: '#6b7b8d',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  }}>
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="rgba(0,229,255,0.25)" strokeWidth="1.5">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
    <div style={{ fontSize: '13px' }}>No scores yet</div>
    <div style={{ fontSize: '11px', opacity: 0.7 }}>Run the agent to generate layout scores</div>
  </div>
);

const Dashboard: React.FC<DashboardProps> = ({ scores }) => {
  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
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

  const dividerStyle: React.CSSProperties = {
    height: '1px',
    background: 'rgba(0,229,255,0.1)',
    margin: '14px 0',
  };

  const panelStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'auto',
  };

  return (
    <GlassPanel style={panelStyle}>
      <div style={headerStyle}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00E5FF" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        <span style={titleStyle}>Analysis Dashboard</span>
      </div>

      {!scores ? (
        <EmptyState />
      ) : (
        <>
          {/* Row 1: 5 score cards */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: '8px',
            flexWrap: 'wrap',
          }}>
            {TOOL_SCORES.map(tool => (
              <div key={tool.key} style={{ flex: '1 1 80px', display: 'flex', justifyContent: 'center' }}>
                <ScoreCard
                  name={tool.label}
                  score={scores[tool.key] as number}
                  weight={scores.weights[tool.weightKey] as number}
                />
              </div>
            ))}
          </div>

          <div style={dividerStyle} />

          {/* Row 2: Overall grade + WeightBar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '24px',
          }}>
            <GradeDisplay grade={scores.grade} score={scores.overall} />
            <div style={{ flex: 1 }}>
              <WeightBar scores={scores} />
            </div>
          </div>

          {/* Row 3: Histograms */}
          {scores.histogramData && (
            <>
              <div style={dividerStyle} />
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '16px',
              }}>
                <Histogram
                  data={scores.histogramData.clearance}
                  label="Clearance Distribution"
                  color="#00E5FF"
                />
                <Histogram
                  data={scores.histogramData.pathDistances}
                  label="Path Distance Distribution"
                  color="#00C853"
                />
              </div>
            </>
          )}
        </>
      )}
    </GlassPanel>
  );
};

export default React.memo(Dashboard);
