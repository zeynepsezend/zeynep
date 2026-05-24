import React, { useCallback } from 'react'
import { useTheme } from '../common/ThemeToggle'

interface ViewCubeProps {
  onViewChange: (view: string) => void
  isOrtho: boolean
  onToggleOrtho: () => void
  /** Euler angles [azimuth, elevation] in radians from CameraTracker */
  cameraAngles?: { azimuth: number; elevation: number }
}

// ── 3D Cube projection with camera-relative rotation ──────────────────────

const CUBE_SIZE = 80
const S = 0.48

interface Vec3 { x: number; y: number; z: number }

function rotateY(v: Vec3, angle: number): Vec3 {
  const c = Math.cos(angle), s = Math.sin(angle)
  return { x: v.x * c + v.z * s, y: v.y, z: -v.x * s + v.z * c }
}

function rotateX(v: Vec3, angle: number): Vec3 {
  const c = Math.cos(angle), s = Math.sin(angle)
  return { x: v.x, y: v.y * c - v.z * s, z: v.y * s + v.z * c }
}

function projectPt(v: Vec3): [number, number] {
  // Simple orthographic projection after rotation
  const scale = CUBE_SIZE * 0.42
  return [v.x * scale, -v.y * scale]
}

interface FaceDef {
  name: string
  corners: Vec3[]
  label: string
  color: string
}

const FACES: FaceDef[] = [
  { name: 'top',    corners: [{x:-S,y:S,z:-S},{x:S,y:S,z:-S},{x:S,y:S,z:S},{x:-S,y:S,z:S}],     label: 'T', color: 'top' },
  { name: 'bottom', corners: [{x:-S,y:-S,z:S},{x:S,y:-S,z:S},{x:S,y:-S,z:-S},{x:-S,y:-S,z:-S}],  label: 'B', color: 'bottom' },
  { name: 'front',  corners: [{x:-S,y:S,z:S},{x:S,y:S,z:S},{x:S,y:-S,z:S},{x:-S,y:-S,z:S}],      label: 'F', color: 'front' },
  { name: 'back',   corners: [{x:S,y:S,z:-S},{x:-S,y:S,z:-S},{x:-S,y:-S,z:-S},{x:S,y:-S,z:-S}],  label: 'Bk', color: 'back' },
  { name: 'right',  corners: [{x:S,y:S,z:S},{x:S,y:S,z:-S},{x:S,y:-S,z:-S},{x:S,y:-S,z:S}],      label: 'R', color: 'right' },
  { name: 'left',   corners: [{x:-S,y:S,z:-S},{x:-S,y:S,z:S},{x:-S,y:-S,z:S},{x:-S,y:-S,z:-S}],  label: 'L', color: 'left' },
]

function faceNormal(corners: Vec3[]): Vec3 {
  const a = corners[0], b = corners[1], c = corners[2]
  const u = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z }
  const v = { x: c.x - a.x, y: c.y - a.y, z: c.z - a.z }
  return {
    x: u.y * v.z - u.z * v.y,
    y: u.z * v.x - u.x * v.z,
    z: u.x * v.y - u.y * v.x,
  }
}

export default function ViewCube({ onViewChange, isOrtho, onToggleOrtho, cameraAngles }: ViewCubeProps) {
  const { colors } = useTheme()

  const handleFaceClick = useCallback((face: string) => {
    onViewChange(face)
  }, [onViewChange])

  const azimuth = cameraAngles?.azimuth ?? 0.75
  const elevation = cameraAngles?.elevation ?? 0.6

  // Transform all face corners by camera angles
  const transformedFaces = FACES.map(face => {
    const rotated = face.corners.map(c => {
      let v = rotateY(c, -azimuth)
      v = rotateX(v, -elevation)
      return v
    })
    const projected = rotated.map(projectPt)
    const normal = faceNormal(rotated)
    // Face center Z for depth sorting
    const avgZ = rotated.reduce((s, v) => s + v.z, 0) / rotated.length
    // Face center in 2D for label
    const cx2d = projected.reduce((s, p) => s + p[0], 0) / projected.length
    const cy2d = projected.reduce((s, p) => s + p[1], 0) / projected.length

    return {
      ...face,
      projected,
      normal,
      avgZ,
      center2d: [cx2d, cy2d] as [number, number],
      visible: normal.z < 0, // facing camera (towards -z in screen space after projection)
    }
  })

  // Sort by depth (back to front)
  const sorted = [...transformedFaces].sort((a, b) => b.avgZ - a.avgZ)

  const cx = CUBE_SIZE / 2
  const cy = CUBE_SIZE / 2

  const faceColors: Record<string, { fill: string; fillHover: string }> = {
    top:    { fill: 'rgba(0,229,255,0.18)', fillHover: 'rgba(0,229,255,0.30)' },
    bottom: { fill: 'rgba(0,229,255,0.05)', fillHover: 'rgba(0,229,255,0.15)' },
    front:  { fill: 'rgba(0,229,255,0.10)', fillHover: 'rgba(0,229,255,0.22)' },
    back:   { fill: 'rgba(0,229,255,0.06)', fillHover: 'rgba(0,229,255,0.18)' },
    right:  { fill: 'rgba(0,229,255,0.08)', fillHover: 'rgba(0,229,255,0.20)' },
    left:   { fill: 'rgba(0,229,255,0.06)', fillHover: 'rgba(0,229,255,0.18)' },
  }

  return (
    <div style={{
      position: 'absolute',
      top: 12,
      right: 12,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 6,
      zIndex: 20,
      pointerEvents: 'auto',
    }}>
      {/* Rotating View Cube */}
      <div style={{
        background: colors.panelBg,
        backdropFilter: 'blur(24px)',
        border: `1px solid ${colors.border}`,
        borderRadius: 10,
        padding: 4,
        width: CUBE_SIZE + 8,
        height: CUBE_SIZE + 8,
      }}>
        <svg
          width={CUBE_SIZE}
          height={CUBE_SIZE}
          viewBox={`0 0 ${CUBE_SIZE} ${CUBE_SIZE}`}
          style={{ display: 'block' }}
        >
          {sorted.map(face => {
            if (!face.visible) return null
            const pts = face.projected.map(([px, py]) => `${cx + px},${cy + py}`).join(' ')
            const fc = faceColors[face.color] || faceColors.front
            return (
              <g key={face.name} style={{ cursor: 'pointer' }} onClick={() => handleFaceClick(face.name)}>
                <polygon
                  points={pts}
                  fill={fc.fill}
                  stroke={colors.accent + '55'}
                  strokeWidth="0.8"
                  strokeLinejoin="round"
                >
                  <title>{face.name}</title>
                </polygon>
                <text
                  x={cx + face.center2d[0]}
                  y={cy + face.center2d[1]}
                  fill={colors.accent}
                  fontSize="8"
                  fontWeight="700"
                  fontFamily="-apple-system, system-ui, sans-serif"
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{ pointerEvents: 'none', letterSpacing: '0.06em', opacity: 0.8 }}
                >
                  {face.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Ortho/Perspective toggle */}
      <button
        onClick={onToggleOrtho}
        title={isOrtho ? 'Switch to perspective' : 'Switch to orthographic'}
        style={{
          background: isOrtho ? colors.accent + '18' : colors.panelBg,
          backdropFilter: 'blur(16px)',
          border: `1px solid ${isOrtho ? colors.accent + '44' : colors.border}`,
          borderRadius: 6,
          padding: '4px 10px',
          color: isOrtho ? colors.accent : colors.muted,
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          cursor: 'pointer',
          fontFamily: colors.font,
          transition: 'all 0.2s',
        }}
      >
        {isOrtho ? 'ORTHO' : 'PERSP'}
      </button>

      {/* Quick view buttons */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        background: colors.panelBg,
        backdropFilter: 'blur(16px)',
        border: `1px solid ${colors.border}`,
        borderRadius: 6,
        padding: 3,
      }}>
        {['top', 'front', 'right', 'back', 'left'].map(view => (
          <button
            key={view}
            onClick={() => onViewChange(view)}
            style={{
              background: 'transparent',
              border: 'none',
              color: colors.muted,
              fontSize: 8,
              fontWeight: 600,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: 4,
              fontFamily: colors.font,
              transition: 'color 0.15s, background 0.15s',
            }}
            onMouseEnter={e => {
              (e.target as HTMLElement).style.color = colors.accent;
              (e.target as HTMLElement).style.background = colors.accent + '15';
            }}
            onMouseLeave={e => {
              (e.target as HTMLElement).style.color = colors.muted;
              (e.target as HTMLElement).style.background = 'transparent';
            }}
          >
            {view}
          </button>
        ))}
      </div>
    </div>
  )
}
