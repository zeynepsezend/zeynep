import React, { useMemo, useCallback, useState, useRef, useEffect } from 'react'
import { Canvas, useThree, useFrame } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import * as THREE from 'three'
import FloorPlanRenderer from './FloorPlanRenderer'
import SelectionHighlight from './SelectionHighlight'
import PulseHighlight from './PulseHighlight'
import Labels3D from './Labels3D'
import ViewCube from './ViewCube'
import SelectionPanel from './SelectionPanel'
import { useTheme } from '../common/ThemeToggle'
import { LayoutJSON, LayerVisibility } from '../../types'
import type { NodeLinkData } from '../GraphPanel/graphDataMapper'

interface ThreeViewportProps {
  layout: LayoutJSON
  selectedId: string | null
  onSelect: (id: string | null) => void
  layers: LayerVisibility
  graphData?: NodeLinkData | null
  modifiedIds?: Set<string>
}

interface SceneProps extends ThreeViewportProps {
  isDark: boolean
  showLabels: boolean
}

// ── Camera angle tracker — reads camera orientation every frame ─────────
function CameraTracker({ onAnglesChange }: { onAnglesChange: (az: number, el: number) => void }) {
  const { camera } = useThree()
  const prevRef = useRef({ az: 0, el: 0 })

  useFrame(() => {
    const pos = camera.position
    const dist = Math.sqrt(pos.x * pos.x + pos.z * pos.z)
    const azimuth = Math.atan2(pos.x, pos.z)
    const elevation = Math.atan2(pos.y, dist)

    // Only update when changed meaningfully (avoid re-renders)
    if (
      Math.abs(azimuth - prevRef.current.az) > 0.01 ||
      Math.abs(elevation - prevRef.current.el) > 0.01
    ) {
      prevRef.current = { az: azimuth, el: elevation }
      onAnglesChange(azimuth, elevation)
    }
  })

  return null
}

// ── Camera view controller — receives view commands from ViewCube ───────
function CameraController({ viewCommand }: { viewCommand: string | null }) {
  const { camera, controls } = useThree()

  useEffect(() => {
    if (!viewCommand || !controls) return
    const ctrl = controls as any
    const dist = camera.position.length() || 40
    const viewName = viewCommand.split('__')[0]

    const views: Record<string, { pos: [number, number, number]; up?: [number, number, number] }> = {
      top: { pos: [0, dist, 0.001], up: [0, 0, -1] },
      bottom: { pos: [0, -dist, 0.001], up: [0, 0, 1] },
      front: { pos: [0, 0, dist] },
      back: { pos: [0, 0, -dist] },
      right: { pos: [dist, 0, 0] },
      left: { pos: [-dist, 0, 0] },
      'top-front': { pos: [0, dist * 0.7, dist * 0.7] },
      'top-right': { pos: [dist * 0.7, dist * 0.7, 0] },
      'front-right': { pos: [dist * 0.7, 0, dist * 0.7] },
      'top-front-right': { pos: [dist * 0.58, dist * 0.58, dist * 0.58] },
      'top-front-left': { pos: [-dist * 0.58, dist * 0.58, dist * 0.58] },
      'top-back-right': { pos: [dist * 0.58, dist * 0.58, -dist * 0.58] },
      'top-back-left': { pos: [-dist * 0.58, dist * 0.58, -dist * 0.58] },
    }

    const view = views[viewName]
    if (!view) return

    camera.position.set(...view.pos)
    if (view.up) camera.up.set(...view.up)
    else camera.up.set(0, 1, 0)
    camera.lookAt(0, 0, 0)
    ctrl.target.set(0, 0, 0)
    ctrl.update()
  }, [viewCommand, camera, controls])

  return null
}

// ── Ortho/Persp switch — modifies the camera in-place ──────────────────
function OrthoController({ isOrtho }: { isOrtho: boolean }) {
  const { camera, gl, set } = useThree()
  const prevIsOrtho = useRef(isOrtho)

  useEffect(() => {
    if (isOrtho === prevIsOrtho.current) return
    prevIsOrtho.current = isOrtho

    const pos = camera.position.clone()
    const target = new THREE.Vector3(0, 0, 0)
    const up = camera.up.clone()
    const canvas = gl.domElement
    const aspect = canvas.clientWidth / canvas.clientHeight

    if (isOrtho) {
      // Switch to orthographic
      const dist = pos.length()
      const frustumSize = dist * 0.8
      const ortho = new THREE.OrthographicCamera(
        -frustumSize * aspect, frustumSize * aspect,
        frustumSize, -frustumSize,
        0.1, 500
      )
      ortho.position.copy(pos)
      ortho.up.copy(up)
      ortho.lookAt(target)
      ortho.updateProjectionMatrix()
      set({ camera: ortho })
    } else {
      // Switch to perspective
      const persp = new THREE.PerspectiveCamera(50, aspect, 0.1, 500)
      persp.position.copy(pos)
      persp.up.copy(up)
      persp.lookAt(target)
      persp.updateProjectionMatrix()
      set({ camera: persp })
    }
  }, [isOrtho, camera, gl, set])

  return null
}

function SceneContent({ layout, selectedId, onSelect, layers, isDark, showLabels, modifiedIds }: SceneProps & { modifiedIds?: Set<string> }) {
  const bounds = useMemo(() => {
    const pts = layout.outline
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const [x, y] of pts) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x)
      minY = Math.min(minY, y); maxY = Math.max(maxY, y)
    }
    const w = maxX - minX
    const h = maxY - minY
    return { cx: (minX + maxX) / 2, cz: (minY + maxY) / 2, w, h, maxDim: Math.max(w, h) }
  }, [layout])

  const center = useMemo(() => ({ x: bounds.cx, z: bounds.cz }), [bounds])

  const bgColor = isDark ? '#06090f' : '#f0f2f5'

  return (
    <>
      {/* Background + fog */}
      <color attach="background" args={[bgColor]} />
      <fog attach="fog" args={[bgColor, 100, 250]} />

      {/* Lighting */}
      <ambientLight intensity={isDark ? 0.5 : 0.8} color={isDark ? '#8899bb' : '#c0c8d0'} />
      <directionalLight
        position={[bounds.w * 0.5, bounds.maxDim * 1.2, bounds.h * 0.3]}
        intensity={isDark ? 0.8 : 1.0}
        color={isDark ? '#c0d0e8' : '#ffffff'}
        castShadow={false}
      />
      <directionalLight
        position={[-bounds.w * 0.3, bounds.maxDim * 0.5, -bounds.h * 0.5]}
        intensity={isDark ? 0.25 : 0.4}
        color={isDark ? '#4488cc' : '#8899aa'}
      />

      {/* Glow point lights */}
      <pointLight
        position={[0, bounds.maxDim * 0.3, 0]}
        intensity={isDark ? 0.4 : 0.2}
        color={isDark ? '#00CED1' : '#88bbcc'}
        distance={bounds.maxDim * 2}
        decay={2}
      />
      <pointLight
        position={[bounds.w * 0.3, 1, bounds.h * 0.3]}
        intensity={isDark ? 0.2 : 0.1}
        color={isDark ? '#39FF14' : '#88cc88'}
        distance={bounds.maxDim * 1.5}
        decay={2}
      />

      {/* Floor grid */}
      <Grid
        args={[200, 200]}
        cellSize={1}
        cellThickness={0.5}
        cellColor={isDark ? '#0d1a28' : '#c0c8d2'}
        sectionSize={5}
        sectionThickness={1}
        sectionColor={isDark ? '#132438' : '#a0aab4'}
        fadeDistance={100}
        fadeStrength={1.5}
        infiniteGrid
        position={[0, 0, 0]}
      />

      {/* Floor plan */}
      <FloorPlanRenderer
        layout={layout}
        layers={layers}
        selectedId={selectedId}
        onSelect={onSelect}
        isDark={isDark}
      />

      {/* 3D Labels */}
      {showLabels && (
        <Labels3D layout={layout} isDark={isDark} center={center} />
      )}

      {/* Selection highlight manager */}
      <SelectionHighlight selectedId={selectedId} />

      {/* Pulse highlight for modified/new elements */}
      <PulseHighlight modifiedIds={modifiedIds || new Set()} />

      {/* Controls */}
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.12}
        minDistance={5}
        maxDistance={150}
        maxPolarAngle={Math.PI / 2.1}
        target={[0, 0, 0]}
      />
    </>
  )
}

export default function ThreeViewport({ layout, selectedId, onSelect, layers, graphData, modifiedIds }: ThreeViewportProps) {
  const { theme, colors } = useTheme()
  const isDark = theme === 'dark'
  const [showLabels, setShowLabels] = useState(false)
  const [isOrtho, setIsOrtho] = useState(false)
  const [viewCommand, setViewCommand] = useState<string | null>(null)
  const [cameraAngles, setCameraAngles] = useState({ azimuth: 0.75, elevation: 0.6 })
  const viewCounter = useRef(0)

  const cameraConfig = useMemo(() => {
    const pts = layout.outline
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const [x, y] of pts) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x)
      minY = Math.min(minY, y); maxY = Math.max(maxY, y)
    }
    const maxDim = Math.max(maxX - minX, maxY - minY)
    const dist = maxDim * 1.0
    return {
      position: [dist * 0.6, dist * 0.7, dist * 0.6] as [number, number, number],
      fov: 50,
    }
  }, [layout])

  const handleMissedClick = useCallback(() => {
    onSelect(null)
  }, [onSelect])

  const handleViewChange = useCallback((view: string) => {
    viewCounter.current++
    setViewCommand(view + '__' + viewCounter.current)
  }, [])

  const handleToggleOrtho = useCallback(() => {
    setIsOrtho(prev => !prev)
  }, [])

  const handleClosePanel = useCallback(() => {
    onSelect(null)
  }, [onSelect])

  const handleCameraAngles = useCallback((az: number, el: number) => {
    setCameraAngles({ azimuth: az, elevation: el })
  }, [])

  const bgColor = isDark ? '#06090f' : '#f0f2f5'

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        camera={{ position: cameraConfig.position, fov: cameraConfig.fov, near: 0.1, far: 500 }}
        style={{ width: '100%', height: '100%', background: bgColor, transition: 'background 0.3s ease' }}
        gl={{ antialias: true, alpha: false }}
        onPointerMissed={handleMissedClick}
      >
        <CameraTracker onAnglesChange={handleCameraAngles} />
        <CameraController viewCommand={viewCommand} />
        <OrthoController isOrtho={isOrtho} />
        <SceneContent
          layout={layout}
          selectedId={selectedId}
          onSelect={onSelect}
          layers={layers}
          isDark={isDark}
          showLabels={showLabels}
          modifiedIds={modifiedIds}
        />
      </Canvas>

      {/* Labels toggle button */}
      <button
        onClick={() => setShowLabels(v => !v)}
        title={showLabels ? 'Hide labels' : 'Show labels'}
        style={{
          position: 'absolute',
          top: 12,
          right: 120,
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: colors.panelBg,
          backdropFilter: 'blur(16px)',
          border: `1px solid ${showLabels ? colors.accent + '44' : colors.border}`,
          borderRadius: 8,
          padding: '5px 10px',
          color: showLabels ? colors.accent : colors.muted,
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          cursor: 'pointer',
          fontFamily: colors.font,
          transition: 'color 0.2s, border-color 0.2s',
        }}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 7V5a2 2 0 012-2h2" /><path d="M17 3h2a2 2 0 012 2v2" />
          <path d="M21 17v2a2 2 0 01-2 2h-2" /><path d="M7 21H5a2 2 0 01-2-2v-2" />
          <line x1="7" y1="12" x2="17" y2="12" /><line x1="7" y1="8" x2="13" y2="8" />
          <line x1="7" y1="16" x2="15" y2="16" />
        </svg>
        {showLabels ? 'Labels ON' : 'Labels'}
      </button>

      {/* Center/fit button */}
      <button
        onClick={() => handleViewChange('top-front-right')}
        title="Center geometry"
        style={{
          position: 'absolute',
          top: 12,
          right: 200,
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: colors.panelBg,
          backdropFilter: 'blur(16px)',
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: '5px 10px',
          color: colors.muted,
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          cursor: 'pointer',
          fontFamily: colors.font,
          transition: 'color 0.2s, border-color 0.2s',
        }}
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="3" />
          <line x1="12" y1="2" x2="12" y2="6" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="2" y1="12" x2="6" y2="12" />
          <line x1="18" y1="12" x2="22" y2="12" />
        </svg>
        Center
      </button>

      {/* ViewCube + Ortho toggle */}
      <ViewCube
        onViewChange={handleViewChange}
        isOrtho={isOrtho}
        onToggleOrtho={handleToggleOrtho}
        cameraAngles={cameraAngles}
      />

      {/* Selection detail panel */}
      <SelectionPanel
        selectedId={selectedId}
        layout={layout}
        graphData={graphData || null}
        onClose={handleClosePanel}
      />
    </div>
  )
}
