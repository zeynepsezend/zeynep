export interface ThemeColors {
  bg: string;
  panelBg: string;
  text: string;
  muted: string;
  accent: string;
  accentDim: string;
  ok: string;
  warning: string;
  error: string;
  success: string;
  font: string;
  border: string;
  cardBg: string;
  inputBg: string;
}

export const darkTheme: ThemeColors = {
  bg: '#06090f',
  panelBg: 'rgba(10, 14, 22, 0.88)',
  text: '#e0e6ed',
  muted: '#4a5a6e',
  accent: '#00E5FF',
  accentDim: 'rgba(0, 229, 255, 0.10)',
  ok: '#00E5FF',
  warning: '#FF8C42',
  error: '#FF4444',
  success: '#39FF14',
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif',
  border: 'rgba(0, 229, 255, 0.10)',
  cardBg: 'rgba(12, 18, 30, 0.85)',
  inputBg: 'rgba(0, 6, 14, 0.6)',
};

export const lightTheme: ThemeColors = {
  bg: '#f0f2f5',
  panelBg: 'rgba(255, 255, 255, 0.78)',
  text: '#1a1d24',
  muted: '#6b7280',
  accent: '#0077ed',
  accentDim: 'rgba(0, 119, 237, 0.08)',
  ok: '#0077ed',
  warning: '#e07020',
  error: '#d63230',
  success: '#248a3d',
  font: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif',
  border: 'rgba(0, 0, 0, 0.08)',
  cardBg: 'rgba(255, 255, 255, 0.88)',
  inputBg: 'rgba(240, 242, 245, 0.8)',
};

export const theme = darkTheme;
