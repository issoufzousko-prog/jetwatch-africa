import { useState, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
  addEdge,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { FileText, Building2, Plane, Home, Target, BrainCircuit } from 'lucide-react';

// Custom Animated Node for Databases
const DatabaseNode = ({ data }: { data: { label: string; active: boolean; icon: React.ReactNode } }) => {
  return (
    <div className={`px-4 py-3 rounded-lg border-2 transition-all duration-500 flex items-center gap-3 shadow-lg
      ${data.active ? 'bg-accent-blue/20 border-accent-blue shadow-[0_0_20px_rgba(59,130,246,0.5)] scale-110' : 'bg-slate-900 border-slate-700 opacity-70'}
    `}>
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-accent-blue" />
      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${data.active ? 'text-accent-blue bg-accent-blue/20' : 'text-slate-400 bg-slate-800'}`}>
        {data.icon}
      </div>
      <span className="font-semibold text-slate-200 text-sm">{data.label}</span>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-accent-blue" />
    </div>
  );
};

const AgentNode = ({ data }: { data: { active: boolean } }) => {
  return (
    <div className={`w-20 h-20 rounded-full border-4 flex items-center justify-center transition-all duration-500 shadow-2xl
      ${data.active ? 'bg-indigo-900/40 border-indigo-500 shadow-[0_0_30px_rgba(99,102,241,0.6)] animate-pulse' : 'bg-slate-900 border-slate-700'}
    `}>
      <img src="/icons/Agent IA Central.svg" className={`w-10 h-10 object-contain drop-shadow-lg ${data.active ? 'opacity-100' : 'opacity-50 grayscale'}`} alt="Agent IA Central" />
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-indigo-500" />
      <Handle type="target" position={Position.Left} className="!w-3 !h-3 !bg-indigo-500" />
      <Handle type="source" position={Position.Bottom} className="!w-3 !h-3 !bg-indigo-500" />
      <Handle type="source" position={Position.Top} className="!w-3 !h-3 !bg-indigo-500" />
    </div>
  );
};

const nodeTypes = {
  database: DatabaseNode,
  agent: AgentNode,
};

const defaultEdgeOptions = {
  animated: true,
  style: { stroke: '#6366f1', strokeWidth: 2 },
  markerEnd: {
    type: MarkerType.ArrowClosed,
    color: '#6366f1',
  },
};

export default function DatabaseConsultationFlow({ onComplete }: { onComplete?: () => void }) {
  const initialNodes: Node[] = [
    { id: 'agent', type: 'agent', position: { x: 50, y: 200 }, data: { active: true } },
    { id: 'db1', type: 'database', position: { x: 350, y: 50 }, data: { label: 'Offshore Leaks', icon: <img src="/icons/Offshore Leaks.svg" className="w-5 h-5 object-contain" alt="Offshore Leaks" />, active: false } },
    { id: 'db2', type: 'database', position: { x: 350, y: 150 }, data: { label: 'OpenCorporates', icon: <img src="/icons/OpenCorporates.svg" className="w-5 h-5 object-contain" alt="OpenCorporates" />, active: false } },
    { id: 'db3', type: 'database', position: { x: 350, y: 250 }, data: { label: 'ADS-B Exchange', icon: <img src="/icons/ADS-B Exchange.svg" className="w-5 h-5 object-contain" alt="ADS-B Exchange" />, active: false } },
    { id: 'db4', type: 'database', position: { x: 350, y: 350 }, data: { label: 'Registre Foncier', icon: <img src="/icons/Registre Foncier.svg" className="w-5 h-5 object-contain" alt="Registre Foncier" />, active: false } },
    { id: 'target', type: 'database', position: { x: -200, y: 200 }, data: { label: 'Cible d\'Investigation', icon: <img src="/icons/Cible d'Investigation.svg" className="w-5 h-5 object-contain" alt="Cible" />, active: true } },
  ];

  const initialEdges: Edge[] = [
    { id: 'e-target-agent', source: 'target', target: 'agent', animated: true, style: { stroke: '#ef4444', strokeWidth: 3 } },
  ];

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sequence d'animation de consultation
  useEffect(() => {
    
    const sequence = async () => {
      const dbs = ['db1', 'db2', 'db3', 'db4'];
      
      for (let i = 0; i < dbs.length; i++) {
        // Wait before querying next DB
        await new Promise(r => setTimeout(r, 1500));
        
        // Add edge from agent to DB
        setEdges((eds) => [...eds, {
          id: `e-agent-${dbs[i]}`,
          source: 'agent',
          target: dbs[i],
          animated: true,
          style: { stroke: '#3b82f6', strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' }
        }]);

        // Activate DB Node
        setNodes((nds) => nds.map(node => {
          if (node.id === dbs[i]) {
            return { ...node, data: { ...node.data, active: true } };
          }
          return node;
        }));
      }

      // After all DBs queried, finish
      await new Promise(r => setTimeout(r, 2000));
      if (onComplete) onComplete();
    };

    sequence();
  }, [setEdges, setNodes, onComplete]);

  const onConnect = useCallback(
    (params: any) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="w-full h-full rounded-xl border border-white/10 bg-black/50 overflow-hidden relative shadow-2xl">
      <div className="absolute top-4 left-4 z-10 px-3 py-1 bg-accent-blue/20 text-accent-blue rounded text-sm font-mono border border-accent-blue/30 backdrop-blur-sm">
        PHASE 1: OSINT DATABASE CRAWLING
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        colorMode="dark"
        fitView
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls className="!bg-slate-900 !border-slate-800 !fill-white" />
      </ReactFlow>
    </div>
  );
}
