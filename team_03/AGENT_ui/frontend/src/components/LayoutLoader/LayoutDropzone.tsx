import React, { useState, useRef, useCallback } from 'react';

export interface LayoutDropzoneProps {
  onUpload: (file: File) => void;
}

const UploadIcon: React.FC<{ active: boolean }> = ({ active }) => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={active ? '#00E5FF' : '#6b7b8d'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ transition: 'stroke 0.2s' }}>
    <polyline points="16 16 12 12 8 16" />
    <line x1="12" y1="12" x2="12" y2="21" />
    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
  </svg>
);

const LayoutDropzone: React.FC<LayoutDropzoneProps> = ({ onUpload }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback((file: File) => {
    if (!file.name.endsWith('.json')) {
      return;
    }
    setUploadedFileName(file.name);
    onUpload(file);
  }, [onUpload]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }, [processFile]);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
    // Reset so same file can be re-uploaded
    e.target.value = '';
  }, [processFile]);

  const dropzoneStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '20px 16px',
    borderRadius: '8px',
    border: `1.5px dashed ${isDragOver ? '#00E5FF' : 'rgba(0, 229, 255, 0.25)'}`,
    background: isDragOver ? 'rgba(0, 229, 255, 0.06)' : 'rgba(0, 229, 255, 0.02)',
    cursor: 'pointer',
    transition: 'border-color 0.2s, background 0.2s, box-shadow 0.2s',
    boxShadow: isDragOver ? '0 0 16px rgba(0, 229, 255, 0.12), inset 0 0 12px rgba(0, 229, 255, 0.04)' : 'none',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
    userSelect: 'none',
  };

  const mainTextStyle: React.CSSProperties = {
    color: isDragOver ? '#00E5FF' : '#6b7b8d',
    fontSize: '12px',
    transition: 'color 0.2s',
    textAlign: 'center',
  };

  const hintStyle: React.CSSProperties = {
    color: '#6b7b8d',
    fontSize: '10px',
    opacity: 0.7,
    textAlign: 'center',
  };

  const fileNameStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    marginTop: '6px',
    padding: '4px 10px',
    borderRadius: '4px',
    background: 'rgba(0, 200, 83, 0.1)',
    border: '1px solid rgba(0, 200, 83, 0.25)',
    color: '#00C853',
    fontSize: '11px',
    fontFamily: '"SF Mono", "Fira Code", monospace',
  };

  return (
    <div>
      <div
        style={dropzoneStyle}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        aria-label="Upload JSON layout file"
        onKeyDown={e => e.key === 'Enter' && handleClick()}
      >
        <UploadIcon active={isDragOver} />
        <span style={mainTextStyle}>
          {isDragOver ? 'Drop to upload' : 'Or drag & drop a JSON layout file'}
        </span>
        <span style={hintStyle}>Accepts .json files only</span>
      </div>

      {uploadedFileName && (
        <div style={fileNameStyle}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#00C853" strokeWidth="3">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {uploadedFileName}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".json"
        style={{ display: 'none' }}
        onChange={handleFileInput}
      />
    </div>
  );
};

export default React.memo(LayoutDropzone);
