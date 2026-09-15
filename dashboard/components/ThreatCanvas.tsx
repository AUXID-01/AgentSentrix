'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { getVerdictColor, getVerdictGlow } from '../lib/colors';
import { GraphLink, GraphNode } from '../types/events';

// Global prototype polyfill for Three.js Object3D & Matrix4 cross-package compatibility
if (typeof THREE !== 'undefined') {
  if (THREE.Object3D && !(THREE.Object3D.prototype as any).intersectsFrustum) {
    (THREE.Object3D.prototype as any).intersectsFrustum = function () {
      return true;
    };
  }
  if (THREE.Matrix4 && !(THREE.Matrix4.prototype as any).determinantAffine) {
    (THREE.Matrix4.prototype as any).determinantAffine = function () {
      return typeof (this as any).determinant === 'function' ? (this as any).determinant() : 1.0;
    };
  }
}

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

  useEffect(() => {
    if (graphRef.current) {
      // Configure d3 force physics for tight, well-structured 3D graph cluster
      const fg = graphRef.current;
      fg.d3Force('charge')?.strength(-140);
      fg.d3Force('link')?.distance(65);
    }
  }, [ForceGraph3D]);

  useEffect(() => {
    if (graphRef.current && nodes.length > 0) {
      // Smoothly auto-fit camera view to frame all nodes in scene
      const timer = setTimeout(() => {
        graphRef.current?.zoomToFit(400, 45);
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [nodes.length]);

  // Setup scene lights when graph renders
  const handleEngineInit = () => {
    if (graphRef.current) {
      const scene = graphRef.current.scene();
      if (scene) {
        // Add ambient & directional lights for rich 3D material shading
        const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
        const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.5);
        dirLight1.position.set(100, 100, 100);
        const dirLight2 = new THREE.DirectionalLight(0x8b5cf6, 1.0);
        dirLight2.position.set(-100, -100, -100);
        scene.add(ambientLight);
        scene.add(dirLight1);
        scene.add(dirLight2);
      }
    }
  };

  const handleNodeClick = (node: GraphNode) => {
    if (graphRef.current) {
      // Smoothly animate camera position to focus on clicked node
      const distance = 140;
      const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
      graphRef.current.cameraPosition(
        { x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio },
        { x: node.x || 0, y: node.y || 0, z: node.z || 0 },
        1000
      );
    }
    onSelectNode?.(node);
  };

  // Custom node Three.js object generator
  const createNodeObject = (node: GraphNode) => {
    const group = new THREE.Group();

    if (node.node_type === 'agent') {
      // Agent Node: Glowing Icosahedron with inner core
      const outerGeo = new THREE.IcosahedronGeometry(9, 1);
      const outerMat = new THREE.MeshPhongMaterial({
        color: '#8b5cf6',
        emissive: '#6d28d9',
        emissiveIntensity: 0.6,
        wireframe: true,
        transparent: true,
        opacity: 0.85,
      });
      const outerMesh = new THREE.Mesh(outerGeo, outerMat);

      const innerGeo = new THREE.SphereGeometry(4.5, 16, 16);
      const innerMat = new THREE.MeshBasicMaterial({ color: '#c084fc' });
      const innerMesh = new THREE.Mesh(innerGeo, innerMat);

      group.add(outerMesh);
      group.add(innerMesh);
    } else if (node.node_type === 'action') {
      // Action Node: Translucent sphere scaled by risk score
      const color = getVerdictColor(node.verdict);
      const riskScore = node.risk_score || 0;
      const radius = Math.max(6, Math.min(14, 6 + riskScore * 0.08));

      const sphereGeo = new THREE.SphereGeometry(radius, 20, 20);
      const sphereMat = new THREE.MeshPhongMaterial({
        color: color,
        emissive: color,
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.8,
        shininess: 90,
      });
      const sphereMesh = new THREE.Mesh(sphereGeo, sphereMat);
      group.add(sphereMesh);

      // Blocked Shield Wireframe Frame
      if (node.verdict === 'blocked') {
        const shieldGeo = new THREE.IcosahedronGeometry(radius + 4, 1);
        const shieldMat = new THREE.MeshBasicMaterial({
          color: '#ef4444',
          wireframe: true,
          transparent: true,
          opacity: 0.9,
        });
        const shieldMesh = new THREE.Mesh(shieldGeo, shieldMat);
        group.add(shieldMesh);
      } else if (node.verdict === 'quarantined') {
        const ringGeo = new THREE.RingGeometry(radius + 2.5, radius + 4, 24);
        const ringMat = new THREE.MeshBasicMaterial({
          color: '#f59e0b',
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.85,
        });
        const ringMesh = new THREE.Mesh(ringGeo, ringMat);
        group.add(ringMesh);
      }
    } else {
      // Resource Node: Cyan Box
      const boxGeo = new THREE.BoxGeometry(8, 8, 8);
      const boxMat = new THREE.MeshPhongMaterial({
        color: '#06b6d4',
        emissive: '#0891b2',
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.85,
      });
      const boxMesh = new THREE.Mesh(boxGeo, boxMat);
      group.add(boxMesh);
    }

    // Disable frustum culling & set intersectsFrustum polyfill for all objects in node group
    group.frustumCulled = false;
    group.traverse((obj: any) => {
      if (obj) {
        obj.frustumCulled = false;
        if (typeof obj.intersectsFrustum !== 'function') {
          obj.intersectsFrustum = () => true;
        }
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
        onEngineStop={handleEngineInit}
        nodeLabel={(node: GraphNode) => `
          <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.2); padding: 8px 12px; border-radius: 8px; font-family: monospace; font-size: 12px; color: #fff; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
            <div style="font-weight: bold; font-size: 13px; margin-bottom: 3px; color: #e2e8f0;">${node.label}</div>
            <div style="color: ${getVerdictColor(node.verdict)}; text-transform: uppercase; font-size: 11px; font-weight: bold;">
              Verdict: ${node.verdict} | Risk: ${node.risk_score}
            </div>
            ${node.agent_id ? `<div style="color: #94a3b8; font-size: 10px; margin-top: 2px;">Agent: ${node.agent_id}</div>` : ''}
          </div>
        `}
        onNodeClick={handleNodeClick}
        linkDirectionalParticles={(link: GraphLink) => (link.verdict === 'blocked' ? 5 : 2)}
        linkDirectionalParticleWidth={3}
        linkDirectionalParticleSpeed={0.008}
        linkDirectionalParticleColor={(link: GraphLink) => getVerdictColor(link.verdict)}
        linkColor={(link: GraphLink) => getVerdictColor(link.verdict)}
        linkOpacity={0.5}
        linkWidth={2}
        cooldownTicks={120}
        cooldownTime={3500}
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

