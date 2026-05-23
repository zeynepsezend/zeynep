import React, { useMemo, useCallback } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import FloorPlanRenderer from './FloorPlanRenderer'
import SelectionHighlight from './SelectionHighlight'
import { LayoutJSON, LayerVisibility } from '../../types'

interface ThreeViewportProps {
  layout: LayoutJSON
  selectedId: string | null
  onSelect: (id: string | null) => void
  layers: LayerVisibility
}

function SceneContent({ layout, selectedId, onSelect, layers }: ThreeViewportProps) {
  // Compute bounding box center and size for camera positioning
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

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.35} color="#8899bb" />
      <directionalLight
        position={[bounds.w * 0.5, bounds.maxDim * 1.2, bounds.h * 0.3]}
        intensity={0.8}
        color="#c0d0e8"
        castShadow={false}
      />
      <directionalLight
        position={[-bounds.w * 0.3, bounds.maxDim * 0.5, -bounds.h * 0.5]}
        intensity={0.25}
        color="#4488cc"
      />

      {/* Subtle floor grid */}
      <Grid
        args={[200, 200]}
        cellSize={1}
        cellThickness={0.5}
        cellColor="#1a2332"
        sectionSize={5}
        sectionThickness={1}
        sectionColor="#1f2d40"
        fadeDistance={80}
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
      />

      {/* Selection highlight manager */}
      <SelectionHighlight selectedId={selectedId} />

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

export default function ThreeViewport({ layout, selectedId, onSelect, layers }: ThreeViewportProps) {
  // Compute camera position: isometric angle looking down at layout center
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

  return (
    <Canvas
      camera={{ position: cameraConfig.position, fov: cameraConfig.fov, near: 0.1, far: 500 }}
      style={{ width: '100%', height: '100%', background: '#0a0e17' }}
      gl={{ antialias: true, alpha: false }}
      onPointerMissed={handleMissedClick}
    >
      <color attach="background" args={['#0a0e17']} />
      <fog attach="fog" args={['#0a0e17', 80, 200]} />
      <SceneContent
        layout={layout}
        selectedId={selectedId}
        onSelect={onSelect}
        layers={layers}
      />
    </Canvas>
  )
}
