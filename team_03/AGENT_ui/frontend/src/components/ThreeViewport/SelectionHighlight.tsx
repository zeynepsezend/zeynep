import React, { useEffect, useRef } from 'react'
import { useThree, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface SelectionHighlightProps {
  selectedId: string | null
}

export default function SelectionHighlight({ selectedId }: SelectionHighlightProps) {
  const { scene, camera } = useThree()
  const targetPos = useRef<THREE.Vector3 | null>(null)
  const prevId = useRef<string | null>(null)

  useEffect(() => {
    // Reset previous selection
    if (prevId.current) {
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh && obj.userData.elementId === prevId.current) {
          if (obj.userData._origEmissiveIntensity !== undefined) {
            const mat = obj.material as THREE.MeshStandardMaterial
            mat.emissiveIntensity = obj.userData._origEmissiveIntensity
            delete obj.userData._origEmissiveIntensity
          }
        }
      })
    }

    if (!selectedId) {
      prevId.current = null
      targetPos.current = null
      return
    }

    // Find the selected mesh
    scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh && obj.userData.elementId === selectedId) {
        const mat = obj.material as THREE.MeshStandardMaterial
        // Save original
        obj.userData._origEmissiveIntensity = mat.emissiveIntensity
        // Apply highlight
        mat.emissiveIntensity = Math.max(mat.emissiveIntensity, 0.6)
        mat.emissive = new THREE.Color('#ffffff')

        // Compute center of selected mesh for camera focus
        obj.geometry.computeBoundingBox()
        const box = obj.geometry.boundingBox!
        const center = new THREE.Vector3()
        box.getCenter(center)
        obj.localToWorld(center)
        targetPos.current = center
      }
    })

    prevId.current = selectedId
  }, [selectedId, scene])

  // Smooth camera look-at transition
  useFrame(() => {
    if (targetPos.current && camera instanceof THREE.PerspectiveCamera) {
      // We don't force camera position, just let OrbitControls handle it
      // The highlight effect is enough feedback
    }
  })

  return null
}
