import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Edge,
  type Node,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import AgentNode from './AgentNode';
import { type AgentState } from '../../hooks/useCrewAI';

const nodeTypes = {
  agent: AgentNode,
};

interface InvestigationFlowProps {
  agents: AgentState[];
  targetName: string;
}

export default function InvestigationFlow({ agents, targetName }: InvestigationFlowProps) {
  
  const nodes: Node[] = useMemo(() => {
    const ns: Node[] = [];
    
    // Target Node (Start)
    ns.push({
      id: 'target',
      type: 'agent',
      position: { x: 50, y: 150 },
      data: { isTarget: true, targetName, phase: 'done', logs: [], id: 'target', name: 'Cible' },
    });

    // Agent Nodes
    const osintAgent = agents.find(a => a.id === 'osint');
    const cartographerAgent = agents.find(a => a.id === 'cartographer');
    const prosecutorAgent = agents.find(a => a.id === 'prosecutor');

    if (osintAgent) {
      ns.push({
        id: 'osint',
        type: 'agent',
        position: { x: 350, y: 50 },
        data: { ...osintAgent, isStart: false },
      });
    }

    if (cartographerAgent) {
      ns.push({
        id: 'cartographer',
        type: 'agent',
        position: { x: 700, y: 150 },
        data: { ...cartographerAgent, isStart: false },
      });
    }

    if (prosecutorAgent) {
      ns.push({
        id: 'prosecutor',
        type: 'agent',
        position: { x: 1050, y: 100 },
        data: { ...prosecutorAgent, isStart: false },
      });
    }

    return ns;
  }, [agents, targetName]);

  const edges: Edge[] = useMemo(() => {
    const es: Edge[] = [];
    
    const osintAgent = agents.find(a => a.id === 'osint');
    const cartographerAgent = agents.find(a => a.id === 'cartographer');
    const prosecutorAgent = agents.find(a => a.id === 'prosecutor');

    // Target -> OSINT
    es.push({
      id: 'e-target-osint',
      source: 'target',
      target: 'osint',
      animated: osintAgent?.phase === 'searching',
      style: { stroke: osintAgent?.phase === 'done' ? '#10b981' : osintAgent?.phase === 'searching' ? '#f59e0b' : '#334155', strokeWidth: 2 },
    });

    // Target -> Cartographer (Direct link for base flight data)
    es.push({
      id: 'e-target-carto',
      source: 'target',
      target: 'cartographer',
      animated: cartographerAgent?.phase === 'mapping',
      style: { stroke: '#334155', strokeWidth: 1, strokeDasharray: '5 5' },
    });

    // OSINT -> Cartographer
    es.push({
      id: 'e-osint-carto',
      source: 'osint',
      target: 'cartographer',
      animated: cartographerAgent?.phase === 'mapping',
      style: { stroke: cartographerAgent?.phase === 'done' ? '#10b981' : cartographerAgent?.phase === 'mapping' ? '#f59e0b' : '#334155', strokeWidth: 2 },
    });

    // Cartographer -> Prosecutor
    es.push({
      id: 'e-carto-pros',
      source: 'cartographer',
      target: 'prosecutor',
      animated: prosecutorAgent?.phase === 'analyzing',
      style: { stroke: prosecutorAgent?.phase === 'done' ? '#10b981' : prosecutorAgent?.phase === 'analyzing' ? '#f59e0b' : '#334155', strokeWidth: 2 },
    });

    return es;
  }, [agents]);

  return (
    <div className="w-full h-full min-h-[400px] bg-slate-950/50 rounded-xl border border-white/5 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        minZoom={0.5}
        maxZoom={1.5}
      >
        <Background color="#334155" gap={24} size={1} />
        <Controls className="!bg-slate-900 !border-slate-800 !fill-slate-400" showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
