import { useRef, useLayoutEffect } from 'react';
import { useGLTF, Float } from '@react-three/drei';
import * as THREE from 'three';

export default function JetModel() {
  const { scene } = useGLTF('/jet.glb');
  const group = useRef<THREE.Group>(null);

  // Materiaux ultra-reflechissants pour le look cinématique
  useLayoutEffect(() => {
    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        if (mesh.material instanceof THREE.MeshStandardMaterial) {
          mesh.material.metalness = 0.85;
          mesh.material.roughness = 0.15;
          mesh.material.envMapIntensity = 1.8;
          mesh.material.needsUpdate = true;
        }
      }
    });
  }, [scene]);

  return (
    <Float 
      speed={1.5} 
      rotationIntensity={0.05} 
      floatIntensity={0.3} 
      floatingRange={[-0.05, 0.05]}
    >
      <group 
        ref={group}
        position={[1.5, 0.0, 0.8]}
        rotation={[0, 0, 0]}
      >
        <primitive 
          object={scene} 
          scale={0.24}
          // Nez vers bas-gauche, dessus des ailes visible avec lumière, breakout effect
          rotation={[0.4, 1.95, 0.15]}
        />
      </group>
    </Float>
  );
}

useGLTF.preload('/jet.glb');
