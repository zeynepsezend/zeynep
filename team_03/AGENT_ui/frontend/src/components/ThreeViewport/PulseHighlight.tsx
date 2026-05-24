import { useRef } from 'react'
import { useThree, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface PulseHighlightProps {
  modifiedIds: Set<string>
}

/**
 * Traverses the scene each frame and applies a pulsing emissive glow
 * to any mesh whose userData.elementId is in the modifiedIds set.
 */
export default function PulseHighlight({ modifiedIds }: PulseHighlightProps) {
  const { scene } = useThree()
  const initialized = useRef(new Set<string>())

  useFrame(({ clock }) => {
    if (modifiedIds.size === 0) return

    const t = clock.getElapsedTime()
    // Pulse: sine wave between 0.3 and 1.0 intensity, period ~1.5s
    const pulse = 0.5 + 0.5 * Math.sin(t * 4.2)

    scene.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return
      const eid = obj.userData.elementId as string | undefined
      if (!eid) return

      const mat = obj.material as THREE.MeshStandardMaterial
      if (!mat || !('emissive' in mat)) return

      if (modifiedIds.has(eid)) {
        // Save original if not already saved
        if (!initialized.current.has(eid)) {
          obj.userData._origEmissive = mat.emissive.getHex()
          obj.userData._origEmissiveIntensityPulse = mat.emissiveIntensity
          initialized.current.add(eid)
        }
        // Apply pulse: white-cyan flash
        mat.emissive.setHex(0x00e5ff)
        mat.emissiveIntensity = 0.3 + pulse * 0.7
      } else if (initialized.current.has(eid)) {
        // Restore original
        if (obj.userData._origEmissive !== undefined) {
          mat.emissive.setHex(obj.userData._origEmissive)
          mat.emissiveIntensity = obj.userData._origEmissiveIntensityPulse
          delete obj.userData._origEmissive
          delete obj.userData._origEmissiveIntensityPulse
        }
        initialized.current.delete(eid)
      }
    })
  })

  return null
}
