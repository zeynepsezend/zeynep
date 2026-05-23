import React, { useCallback } from 'react';
import GlassPanel from '../common/GlassPanel';
import LayoutDropzone from './LayoutDropzone';

export interface LayoutInfo {
  name: string;
  path: string;
  category: string;
}

export interface LayoutLoaderProps {
  layouts: LayoutInfo[];
  selectedLayout: string | null;
  onSelect: (name: string) => void;
  onUpload: (file: File) => void;
}

const ChevronIcon: React.FC = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#6b7b8d" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const LayoutLoader: React.FC<LayoutLoaderProps> = ({
  layouts,
  selectedLayout,
  onSelect,
  onUpload,
}) => {
  const handleSelectChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const val = e.target.value;
      if (val) onSelect(val);
    },
    [onSelect]
  );

  const grouped = layouts.reduce<Record<string, LayoutInfo[]>>((acc, layout) => {
    const cat = layout.category || 'Other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(layout);
    return acc;
  }, {});

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '14px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const titleStyle: React.CSSProperties = {
    color: '#e0e6ed',
    fontSize: '13px',
    fontWeight: 600,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
  };

  const labelStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '11px',
    letterSpacing: '0.04em',
    marginBottom: '6px',
    display: 'block',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const selectWrapperStyle: React.CSSProperties = {
    position: 'relative',
    marginBottom: '14px',
  };

  const selectStyle: React.CSSProperties = {
    width: '100%',
    appearance: 'none',
    WebkitAppearance: 'none',
    background: 'rgba(255, 255, 255, 0.04)',
    border: '1px solid rgba(0, 229, 255, 0.2)',
    borderRadius: '8px',
    padding: '9px 36px 9px 12px',
    color: selectedLayout ? '#e0e6ed' : '#6b7b8d',
    fontSize: '13px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
    cursor: 'pointer',
    outline: 'none',
    transition: 'border-color 0.15s',
  };

  const chevronStyle: React.CSSProperties = {
    position: 'absolute',
    right: '10px',
    top: '50%',
    transform: 'translateY(-50%)',
    pointerEvents: 'none',
  };

  const dividerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    margin: '12px 0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
  };

  const dividerLineStyle: React.CSSProperties = {
    flex: 1,
    height: '1px',
    background: 'rgba(0, 229, 255, 0.1)',
  };

  const dividerTextStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '10px',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    flexShrink: 0,
  };

  return (
    <GlassPanel>
      <div style={headerStyle}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00E5FF" strokeWidth="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
        <span style={titleStyle}>Layout Loader</span>
      </div>

      {layouts.length > 0 ? (
        <div>
          <label style={labelStyle}>Select a layout</label>
          <div style={selectWrapperStyle}>
            <select
              style={selectStyle}
              value={selectedLayout ?? ''}
              onChange={handleSelectChange}
            >
              <option value="" disabled style={{ background: '#0a0e17', color: '#6b7b8d' }}>
                Choose a layout...
              </option>
              {Object.entries(grouped).map(([category, items]) => (
                <optgroup key={category} label={category} style={{ background: '#0d1120', color: '#6b7b8d' }}>
                  {items.map(layout => (
                    <option
                      key={layout.name}
                      value={layout.name}
                      style={{ background: '#0d1120', color: '#e0e6ed' }}
                    >
                      {layout.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <span style={chevronStyle}>
              <ChevronIcon />
            </span>
          </div>

          {selectedLayout && (
            <div style={{
              padding: '6px 10px',
              borderRadius: '6px',
              background: 'rgba(0, 229, 255, 0.06)',
              border: '1px solid rgba(0, 229, 255, 0.15)',
              color: '#00E5FF',
              fontSize: '11px',
              fontFamily: '"SF Mono", "Fira Code", monospace',
              marginBottom: '14px',
            }}>
              {layouts.find(l => l.name === selectedLayout)?.path ?? selectedLayout}
            </div>
          )}
        </div>
      ) : (
        <div style={{
          color: '#6b7b8d',
          fontSize: '12px',
          marginBottom: '14px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
        }}>
          No layouts found on server.
        </div>
      )}

      <div style={dividerStyle}>
        <div style={dividerLineStyle} />
        <span style={dividerTextStyle}>or upload</span>
        <div style={dividerLineStyle} />
      </div>

      <LayoutDropzone onUpload={onUpload} />
    </GlassPanel>
  );
};

export default React.memo(LayoutLoader);
