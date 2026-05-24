import React from 'react'
import { useTheme } from './common/ThemeToggle'
import { LayerVisibility, LayerName } from '../types'

interface LayerToggleProps {
  layers: LayerVisibility
  onToggle: (layer: LayerName) => void
}

const LAYER_CONFIG: { key: LayerName; label: string; color: string }[] = [
  { key: 'outline',   label: 'Outline',   color: '#00E5FF' },
  { key: 'rooms',     label: 'Rooms',     color: '#142a3e' },
  { key: 'structure', label: 'Walls',     color: '#2a4060' },
  { key: 'doors',     label: 'Doors',     color: '#FF8C42' },
  { key: 'windows',   label: 'Windows',   color: '#00E5FF' },
  { key: 'furniture', label: 'Furniture', color: '#00CED1' },
  { key: 'mep',       label: 'MEP',       color: '#39FF14' },
]

export default function LayerToggle({ layers, onToggle }: LayerToggleProps) {
  const { colors, theme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <div style={{
      position: 'absolute',
      top: 16,
      left: 16,
      background: isDark ? 'rgba(10, 14, 23, 0.75)' : 'rgba(255, 255, 255, 0.85)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      border: `1px solid ${colors.border}`,
      borderRadius: 10,
      padding: '14px 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      fontSize: 12,
      color: colors.muted,
      userSelect: 'none',
      zIndex: 10,
      minWidth: 140,
      transition: 'background 0.3s ease, border-color 0.3s ease',
    }}>
      <div style={{
        fontSize: 10,
        letterSpacing: 2,
        textTransform: 'uppercase',
        color: colors.muted,
        marginBottom: 4,
        borderBottom: `1px solid ${colors.border}`,
        paddingBottom: 6,
      }}>
        Layers
      </div>
      {LAYER_CONFIG.map(({ key, label, color }) => (
        <label
          key={key}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            cursor: 'pointer',
            padding: '3px 0',
            opacity: layers[key] ? 1 : 0.4,
            transition: 'opacity 0.2s',
          }}
        >
          <input
            type="checkbox"
            checked={layers[key]}
            onChange={() => onToggle(key)}
            style={{ display: 'none' }}
          />
          <span style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: layers[key] ? color : (isDark ? '#333' : '#bbb'),
            border: `1px solid ${color}44`,
            transition: 'background 0.2s',
            flexShrink: 0,
            boxShadow: layers[key] ? `0 0 6px ${color}66` : 'none',
          }} />
          <span style={{
            color: layers[key] ? colors.text : colors.muted,
            transition: 'color 0.2s',
          }}>
            {label}
          </span>
        </label>
      ))}
    </div>
  )
}
