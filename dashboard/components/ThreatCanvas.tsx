'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { getVerdictColor, getVerdictGlow } from '../lib/colors';
import { GraphLink, GraphNode } from '../types/events';

interface ThreatCanvasProps {
  nodes: GraphNode[];
  links: GraphLink[];
  onSelectNode?: (node: GraphNode) => void;
}

export default function ThreatCanvas({ nodes, links, onSelectNode }: ThreatCanvasProps) {
  const [ForceGraph3D, setForceGraph3D] = useState<any>(null);
  const graphRef = useRef<any>(null);

  useEffect(() => {
    // Dynamic import for react-force-graph-3d (WebGL client-side only)
    import('react-force-graph-3d').then((mod) => {
      setForceGraph3D(() => mod.default);
    });
  }, []);

  // Custom node Three.js object generator
  const createNodeObject = (node: GraphNode) => {
    const group = new THREE.Group();

    if (node.node_type === 'agent') {
      // Agent Node: Glowing Icosahedron with inner core
      const outerGeo = new THREE.IcosahedronGeometry(7, 1);
      const outerMat = new THREE.MeshPhongMaterial({
        color: '#8b5cf6',
        emissive: '#6d28d9',
        emissiveIntensity: 0.5,
        wireframe: true,
        transparent: true,
        opacity: 0.8,
      });
      const outerMesh = new THREE.Mesh(outerGeo, outerMat);

      const innerGeo = new THREE.SphereGeometry(3.5, 16, 16);
      const innerMat = new THREE.MeshBasicMaterial({ color: '#c084fc' });
      const innerMesh = new THREE.Mesh(innerGeo, innerMat);

      group.add(outerMesh);
      group.add(innerMesh);
    } else if (node.node_type === 'action') {
      // Action Node: Translucent sphere scaled by risk score
      const color = getVerdictColor(node.verdict);
      const riskScore = node.risk_score || 0;
      const radius = Math.max(4, Math.min(11, 4.5 + riskScore * 0.07));

      const sphereGeo = new THREE.SphereGeometry(radius, 20, 20);
      const sphereMat = new THREE.MeshPhongMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.4,
        transparent: true,
        opacity: 0.75,
        shininess: 80,
      });
      const sphereMesh = new THREE.Mesh(sphereGeo, sphereMat);
      group.add(sphereMesh);

      // Blocked Shield Wireframe Frame
      if (node.verdict === 'blocked') {
        const shieldGeo = new THREE.IcosahedronGeometry(radius + 3.5, 1);
        const shieldMat = new THREE.MeshBasicMaterial({
          color: '#ef4444',
          wireframe: true,
          transparent: true,
          opacity: 0.9,
        });
        const shieldMesh = new THREE.Mesh(shieldGeo, shieldMat);
        group.add(shieldMesh);
      } else if (node.verdict === 'quarantined') {
        const ringGeo = new THREE.RingGeometry(radius + 2, radius + 3, 24);
        const ringMat = new THREE.MeshBasicMaterial({
          color: '#f59e0b',
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.8,
        });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        group.add(ringMesh);
      }
    } else {
      // Resource Node: Cyan Box
      const boxGeo = new THREE.BoxGeometry(6, 6, 6);
      const boxMat = new THREE.MeshPhongMaterial({
        color: '#06b6d4',
        emissive: '#0891b2',
        emissiveIntensity: 0.4,
        transparent: true,
        opacity: 0.85,
      });
      const boxMesh = new THREE.Mesh(boxGeo, boxMat);
      group.add(boxMesh);
    }

    // Polyfill intersectsFrustum for cross-package Three.js compatibility
    group.traverse((obj: any) => {
      if (obj && typeof obj.intersectsFrustum !== 'function') {
        obj.intersectsFrustum = () => true;
      }
    });

    return group;
  };

  if (!ForceGraph3D) {
    return (
      <div className="w-full h-full min-h-[500px] flex items-center justify-center bg-background text-slate-400">
        <div className="flex flex-col items-center space-y-3">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs font-mono uppercase tracking-wider">Initializing WebGL Engine...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full min-h-[500px] overflow-hidden rounded-xl border border-surface-border bg-background">
      <ForceGraph3D
        ref={graphRef}
        graphData={{ nodes, links }}
        nodeThreeObject={createNodeObject}
        nodeLabel={(node: GraphNode) => `
          <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid rgba(255, 255, 255, 0.15); padding: 6px 10px; border-radius: 6px; font-family: monospace; font-size: 12px; color: #fff;">
            <div><strong>${node.label}</strong></div>
            <div style="color: ${getVerdictColor(node.verdict)}; text-transform: uppercase; font-size: 10px; font-weight: bold;">
              Verdict: ${node.verdict} | Risk: ${node.risk_score}
            </div>
          </div>
        `}
        onNodeClick={(node: GraphNode) => onSelectNode?.(node)}
        linkDirectionalParticles={(link: GraphLink) => (link.verdict === 'blocked' ? 5 : 2)}
        linkDirectionalParticleWidth={2.5}
        linkDirectionalParticleSpeed={0.008}
        linkDirectionalParticleColor={(link: GraphLink) => getVerdictColor(link.verdict)}
        linkColor={(link: GraphLink) => getVerdictColor(link.verdict)}
        linkOpacity={0.4}
        linkWidth={1.5}
        cooldownTicks={100}
        cooldownTime={3000}
        backgroundColor="#090d16"
        showNavInfo={false}
      />
      <div className="absolute top-3 left-3 pointer-events-none flex items-center space-x-3 bg-surface/80 backdrop-blur border border-surface-border px-3 py-1.5 rounded-lg text-xs font-mono text-slate-300">
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
          <span>Agent</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
          <span>Allowed</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
          <span>Quarantined</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
          <span>Blocked</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-500"></span>
          <span>Resource</span>
        </div>
      </div>
    </div>
  );
}
