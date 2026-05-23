import React, { useMemo } from 'react'
import * as THREE from 'three'
import { LayoutJSON, LayerVisibility } from '../../types'

// ── Height lookup ──────────────────────────────────────────────────────
const KEYWORD_HEIGHTS: Record<string, number> = {
  shelf: 1.6, rack: 1.6, shelving: 1.6,
  table: 0.85, desk: 0.85, counter: 0.85, workbench: 0.85, bench: 0.85,
  machine: 1.0, cnc: 1.2, conveyor: 0.7, press: 1.3,
  assembly: 0.9, packaging: 0.9, labeling: 0.85,
  toilet: 0.45, sink: 0.85, urinal: 0.6,
  hvac: 0.6, panel: 1.8, riser: 2.0, duct: 0.4,
  bin: 1.2,
}

function resolveHeight(name: string, attrs: Record<string, unknown>, fallback: number): number {
  if (typeof attrs.height === 'number') return attrs.height
  const lower = name.toLowerCase()
  for (const [kw, h] of Object.entries(KEYWORD_HEIGHTS)) {
    if (lower.includes(kw)) return h
  }
  return fallback
}

// ── Geometry helpers ───────────────────────────────────────────────────
/** Build a THREE.Shape from a polygon (closed polyline, [x,y] coords). */
function shapeFromPolygon(coords: [number, number][]): THREE.Shape {
  const shape = new THREE.Shape()
  // Use x -> x, y -> z mapping is handled by rotation; shape is built in XY
  shape.moveTo(coords[0][0], coords[0][1])
  for (let i = 1; i < coords.length; i++) {
    shape.lineTo(coords[i][0], coords[i][1])
  }
  shape.closePath()
  return shape
}

/** Compute the perpendicular offset points for a wall segment with thickness. */
function wallRectFromLine(
  p1: [number, number], p2: [number, number], thickness: number
): [number, number][] {
  const dx = p2[0] - p1[0]
  const dy = p2[1] - p1[1]
  const len = Math.sqrt(dx * dx + dy * dy)
  if (len === 0) return [p1, p2, p2, p1]
  const nx = (-dy / len) * thickness / 2
  const ny = (dx / len) * thickness / 2
  return [
    [p1[0] + nx, p1[1] + ny],
    [p2[0] + nx, p2[1] + ny],
    [p2[0] - nx, p2[1] - ny],
    [p1[0] - nx, p1[1] - ny],
  ]
}

// ── Sub-components ─────────────────────────────────────────────────────

interface FloorPlanRendererProps {
  layout: LayoutJSON
  layers: LayerVisibility
  selectedId: string | null
  onSelect: (id: string | null) => void
}

export default function FloorPlanRenderer({ layout, layers, selectedId, onSelect }: FloorPlanRendererProps) {
  // Compute center offset so layout is centered at origin
  const center = useMemo(() => {
    const outline = layout.outline
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const [x, y] of outline) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x)
      minY = Math.min(minY, y); maxY = Math.max(maxY, y)
    }
    return { x: (minX + maxX) / 2, z: (minY + maxY) / 2 }
  }, [layout])

  return (
    <group position={[-center.x, 0, -center.z]}>
      {/* Outline */}
      {layers.outline && <OutlineLayer outline={layout.outline} selectedId={selectedId} />}

      {/* Rooms */}
      {layers.rooms && <RoomsLayer rooms={layout.rooms} selectedId={selectedId} onSelect={onSelect} />}

      {/* Structure (walls) */}
      {layers.structure && <StructureLayer items={layout.structure} selectedId={selectedId} onSelect={onSelect} />}

      {/* Doors */}
      {layers.doors && <DoorsLayer items={layout.doors} selectedId={selectedId} onSelect={onSelect} />}

      {/* Windows */}
      {layers.windows && <WindowsLayer items={layout.windows} selectedId={selectedId} onSelect={onSelect} />}

      {/* Furniture */}
      {layers.furniture && <FurnitureLayer items={layout.furniture} selectedId={selectedId} onSelect={onSelect} />}

      {/* MEP */}
      {layers.mep && <MEPLayer items={layout.mep} selectedId={selectedId} onSelect={onSelect} />}
    </group>
  )
}

// ── Outline ────────────────────────────────────────────────────────────
function OutlineLayer({ outline, selectedId }: { outline: [number, number][]; selectedId: string | null }) {
  const points = useMemo(() => {
    return outline.map(([x, y]) => new THREE.Vector3(x, 0.02, y))
  }, [outline])

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry().setFromPoints(points)
    return g
  }, [points])

  return (
    <lineLoop geometry={geo}>
      <lineBasicMaterial color="#00E5FF" linewidth={2} />
    </lineLoop>
  )
}

// ── Rooms ──────────────────────────────────────────────────────────────
function RoomsLayer({ rooms, selectedId, onSelect }: {
  rooms: LayoutJSON['rooms']; selectedId: string | null; onSelect: (id: string | null) => void
}) {
  return (
    <group>
      {rooms.map(room => (
        <RoomMesh key={room.id} room={room} isSelected={selectedId === room.id} onSelect={onSelect} />
      ))}
    </group>
  )
}

function RoomMesh({ room, isSelected, onSelect }: {
  room: LayoutJSON['rooms'][0]; isSelected: boolean; onSelect: (id: string | null) => void
}) {
  const geo = useMemo(() => {
    const shape = shapeFromPolygon(room.geometry)
    const g = new THREE.ShapeGeometry(shape)
    // Rotate from XY plane to XZ plane (floor)
    g.rotateX(-Math.PI / 2)
    g.translate(0, 0.01, 0)
    return g
  }, [room.geometry])

  return (
    <mesh
      geometry={geo}
      userData={{ elementId: room.id, type: 'room', name: room.name }}
      onClick={(e) => { e.stopPropagation(); onSelect(room.id) }}
    >
      <meshStandardMaterial
        color={isSelected ? '#1a3050' : '#0d1b2a'}
        transparent
        opacity={0.85}
        side={THREE.DoubleSide}
        emissive={isSelected ? '#00E5FF' : '#000000'}
        emissiveIntensity={isSelected ? 0.15 : 0}
      />
    </mesh>
  )
}

// ── Structure (walls) ──────────────────────────────────────────────────
function StructureLayer({ items, selectedId, onSelect }: {
  items: LayoutJSON['structure']; selectedId: string | null; onSelect: (id: string | null) => void
}) {
  return (
    <group>
      {items.map(wall => (
        <WallMesh key={wall.id} wall={wall} isSelected={selectedId === wall.id} onSelect={onSelect} />
      ))}
    </group>
  )
}

function WallMesh({ wall, isSelected, onSelect }: {
  wall: LayoutJSON['structure'][0]; isSelected: boolean; onSelect: (id: string | null) => void
}) {
  const WALL_HEIGHT = 3.0
  const WALL_THICKNESS = 0.2

  const geo = useMemo(() => {
    const [p1, p2] = wall.geometry
    const rect = wallRectFromLine(p1, p2, WALL_THICKNESS)
    const shape = shapeFromPolygon(rect)
    const extrudeSettings = { depth: WALL_HEIGHT, bevelEnabled: false }
    const g = new THREE.ExtrudeGeometry(shape, extrudeSettings)
    // Rotate so extrusion goes up (Y axis)
    g.rotateX(-Math.PI / 2)
    return g
  }, [wall.geometry])

  return (
    <mesh
      geometry={geo}
      userData={{ elementId: wall.id, type: 'structure', name: wall.name }}
      onClick={(e) => { e.stopPropagation(); onSelect(wall.id) }}
    >
      <meshStandardMaterial
        color={isSelected ? '#2a4060' : '#1b2838'}
        transparent
        opacity={0.9}
        emissive={isSelected ? '#00E5FF' : '#000000'}
        emissiveIntensity={isSelected ? 0.3 : 0}
      />
    </mesh>
  )
}

// ── Doors ──────────────────────────────────────────────────────────────
function DoorsLayer({ items, selectedId, onSelect }: {
  items: LayoutJSON['doors']; selectedId: string | null; onSelect: (id: string | null) => void
}) {
  return (
    <group>
      {items.map(door => (
        <DoorMesh key={door.id} door={door} isSelected={selectedId === door.id} onSelect={onSelect} />
      ))}
    </group>
  )
}

function DoorMesh({ door, isSelected, onSelect }: {
  door: LayoutJSON['doors'][0]; isSelected: boolean; onSelect: (id: string | null) => void
}) {
  const DOOR_HEIGHT = 2.2

  const { position, size, rotation } = useMemo(() => {
    const [p1, p2] = door.geometry
    const cx = (p1[0] + p2[0]) / 2
    const cy = (p1[1] + p2[1]) / 2
    const dx = p2[0] - p1[0]
    const dy = p2[1] - p1[1]
    const length = Math.sqrt(dx * dx + dy * dy)
    const angle = Math.atan2(dy, dx)
    return {
      position: [cx, DOOR_HEIGHT / 2, cy] as [number, number, number],
      size: [length, DOOR_HEIGHT, 0.08] as [number, number, number],
      rotation: [0, -angle, 0] as [number, number, number],
    }
  }, [door.geometry])

  return (
    <mesh
      position={position}
      rotation={rotation}
      userData={{ elementId: door.id, type: 'door', name: door.name }}
      onClick={(e) => { e.stopPropagation(); onSelect(door.id) }}
    >
      <boxGeometry args={size} />
      <meshStandardMaterial
        color={isSelected ? '#FFB070' : '#FF8C42'}
        transparent
        opacity={0.6}
        emissive="#FF8C42"
        emissiveIntensity={isSelected ? 0.8 : 0.4}
      />
    </mesh>
  )
}

// ── Windows ────────────────────────────────────────────────────────────
function WindowsLayer({ items, selectedId, onSelect }: {
  items: LayoutJSON['windows']; selectedId: string | null; onSelect: (id: string | null) => void
}) {
  return (
    <group>
      {items.map(win => (
        <WindowMesh key={win.id} win={win} isSelected={selectedId === win.id} onSelect={onSelect} />
      ))}
    </group>
  )
}

function WindowMesh({ win, isSelected, onSelect }: {
  win: LayoutJSON['windows'][0]; isSelected: boolean; onSelect: (id: string | null) => void
}) {
  const WIN_BOTTOM = 1.0
  const WIN_HEIGHT = 1.0

  const { position, size, rotation } = useMemo(() => {
    const [p1, p2] = win.geometry
    const cx = (p1[0] + p2[0]) / 2
    const cy = (p1[1] + p2[1]) / 2
    const dx = p2[0] - p1[0]
    const dy = p2[1] - p1[1]
    const length = Math.sqrt(dx * dx + dy * dy)
    const angle = Math.atan2(dy, dx)
    return {
      position: [cx, WIN_BOTTOM + WIN_HEIGHT / 2, cy] as [number, number, number],
      size: [length, WIN_HEIGHT, 0.06] as [number, number, number],
      rotation: [0, -angle, 0] as [number, number, number],
    }
  }, [win.geometry])

  return (
    <mesh
      position={position}
      rotation={rotation}
      userData={{ elementId: win.id, type: 'window', name: win.name }}
      onClick={(e) => { e.stopPropagation(); onSelect(win.id) }}
    >
      <boxGeometry args={size} />
      <meshStandardMaterial
        color={isSelected ? '#80F0FF' : '#00E5FF'}
        transparent
        opacity={0.5}
        emissive="#00E5FF"
        emissiveIntensity={isSelected ? 1.0 : 0.6}
      />
    </mesh>
  )
}

// ── Furniture ──────────────────────────────────────────────────────────
function FurnitureLayer({ items, selectedId, onSelect }: {
  items: LayoutJSON['furniture']; selectedId: string | null; onSelect: (id: string | null) => void
}) {
  return (
    <group>
      {items.map(item => (
        <FurnitureMesh key={item.id} item={item} isSelected={selectedId === item.id} onSelect={onSelect} />
      ))}
    </group>
  )
}

function FurnitureMesh({ item, isSelected, onSelect }: {
  item: LayoutJSON['furniture'][0]; isSelected: boolean; onSelect: (id: string | null) => void
}) {
  const height = resolveHeight(item.name, item.attributes as Record<string, unknown>, 0.9)

  const geo = useMemo(() => {
    const shape = shapeFromPolygon(item.geometry)
    const extrudeSettings = { depth: height, bevelEnabled: false }
    const g = new THREE.ExtrudeGeometry(shape, extrudeSettings)
    g.rotateX(-Math.PI / 2)
    return g
  }, [item.geometry, height])

  return (
    <mesh
      geometry={geo}
      userData={{ elementId: item.id, type: 'furniture', name: item.name }}
      onClick={(e) => { e.stopPropagation(); onSelect(item.id) }}
    >
      <meshStandardMaterial
        color={isSelected ? '#40F0E8' : '#00CED1'}
        emissive="#00CED1"
        emissiveIntensity={isSelected ? 0.5 : 0.15}
        transparent
        opacity={0.85}
      />
    </mesh>
  )
}

// ── MEP ────────────────────────────────────────────────────────────────
function MEPLayer({ items, selectedId, onSelect }: {
  items: LayoutJSON['mep']; selectedId: string | null; onSelect: (id: string | null) => void
}) {
  return (
    <group>
      {items.map(item => (
        <MEPMesh key={item.id} item={item} isSelected={selectedId === item.id} onSelect={onSelect} />
      ))}
    </group>
  )
}

function MEPMesh({ item, isSelected, onSelect }: {
  item: LayoutJSON['mep'][0]; isSelected: boolean; onSelect: (id: string | null) => void
}) {
  const height = resolveHeight(item.name, item.attributes as Record<string, unknown>, 0.5)

  const geo = useMemo(() => {
    const shape = shapeFromPolygon(item.geometry)
    const extrudeSettings = { depth: height, bevelEnabled: false }
    const g = new THREE.ExtrudeGeometry(shape, extrudeSettings)
    g.rotateX(-Math.PI / 2)
    return g
  }, [item.geometry, height])

  return (
    <mesh
      geometry={geo}
      userData={{ elementId: item.id, type: 'mep', name: item.name }}
      onClick={(e) => { e.stopPropagation(); onSelect(item.id) }}
    >
      <meshStandardMaterial
        color={isSelected ? '#70FF50' : '#39FF14'}
        emissive="#39FF14"
        emissiveIntensity={isSelected ? 0.6 : 0.25}
        transparent
        opacity={0.85}
      />
    </mesh>
  )
}
