import { useEffect } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import * as dagre from 'dagre';

// --- Types ---
interface NodeData {
  label: string;
  type: string;
  country?: string;
  description?: string;
}

// --- Custom Nodes ---
const PersonNode = ({ data }: { data: NodeData }) => {
  const isTarget = data.type === 'cible';
  return (
    <div className={`px-4 py-2 shadow-xl rounded-xl border-2 transition-all duration-300 ${isTarget ? 'bg-red-900/40 border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)]' : 'bg-slate-800/80 border-slate-600'}`}>
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-white" />
      <div className="flex flex-col items-center">
        <span className="text-xl mb-1">{isTarget ? '🎯' : '👤'}</span>
        <span className="font-bold text-white text-sm whitespace-nowrap">{data.label}</span>
        {data.country && <span className="text-xs text-slate-400 mt-1">{data.country}</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-white" />
    </div>
  );
};

const CompanyNode = ({ data }: { data: NodeData }) => (
  <div className="px-4 py-2 shadow-xl rounded-xl border-2 bg-orange-900/40 border-orange-500 shadow-[0_0_15px_rgba(249,115,22,0.3)]">
    <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-white" />
    <div className="flex flex-col items-center">
      <span className="text-xl mb-1">🏢</span>
      <span className="font-bold text-white text-sm whitespace-nowrap">{data.label}</span>
      {data.description && <span className="text-xs text-orange-200/70 mt-1 max-w-[150px] text-center truncate">{data.description}</span>}
    </div>
    <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-white" />
  </div>
);

const PropertyNode = ({ data }: { data: NodeData }) => (
  <div className="px-4 py-2 shadow-xl rounded-xl border-2 bg-green-900/40 border-green-500 shadow-[0_0_15px_rgba(34,197,94,0.3)]">
    <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-white" />
    <div className="flex flex-col items-center">
      <span className="text-xl mb-1">🏠</span>
      <span className="font-bold text-white text-sm whitespace-nowrap">{data.label}</span>
      {data.description && <span className="text-xs text-green-200/70 mt-1 max-w-[150px] text-center truncate">{data.description}</span>}
    </div>
    <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-white" />
  </div>
);

const DocumentNode = ({ data }: { data: NodeData }) => (
  <div className="px-4 py-2 shadow-xl rounded-xl border-2 bg-blue-900/40 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
    <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-white" />
    <div className="flex flex-col items-center">
      <span className="text-xl mb-1">📑</span>
      <span className="font-bold text-white text-sm whitespace-nowrap">{data.label}</span>
      {data.description && <span className="text-xs text-blue-200/70 mt-1 max-w-[150px] text-center truncate">{data.description}</span>}
    </div>
    <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-white" />
  </div>
);

const nodeTypes = {
  PersonNode,
  CompanyNode,
  PropertyNode,
  DocumentNode,
};

// --- Dagre Layout ---
const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const nodeWidth = 172;
  const nodeHeight = 80;

  dagreGraph.setGraph({ rankdir: direction, ranker: 'longest-path' });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
      style: { opacity: 0, transform: 'scale(0.8)' }, // Pour l'animation initiale
    };
  });

  return { nodes: layoutedNodes, edges };
};

// --- Composant Principal ---
interface GraphData {
  nodes: any[];
  links: any[];
}

export const InvestigationFlowGraph = ({ data }: { data: GraphData }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);

  useEffect(() => {
    if (!data || !data.nodes || data.nodes.length === 0) return;

    // Transformation des données pour React Flow
    const flowNodes = data.nodes.map((n) => {
      let type = 'PersonNode';
      if (n.type === 'company' || n.type === 'societe') type = 'CompanyNode';
      if (n.type === 'property' || n.type === 'bien') type = 'PropertyNode';
      if (n.type === 'document' || n.type === 'offshore') type = 'DocumentNode';

      return {
        id: n.id.toString(),
        type,
        data: { label: n.label, type: n.type, country: n.country, description: n.description },
        position: { x: 0, y: 0 },
      };
    });

    const flowEdges = data.links.map((l, idx) => ({
      id: `e${l.source.id || l.source}-${l.target.id || l.target}-${idx}`,
      source: typeof l.source === 'object' ? l.source.id.toString() : l.source.toString(),
      target: typeof l.target === 'object' ? l.target.id.toString() : l.target.toString(),
      label: l.label,
      animated: true,
      style: { stroke: l.color || '#94a3b8', strokeWidth: l.confidence ? l.confidence * 2 : 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: l.color || '#94a3b8',
      },
      labelStyle: { fill: '#cbd5e1', fontWeight: 600, fontSize: 12 },
      labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8, rx: 4, ry: 4 },
      labelBgPadding: [8, 4],
    }));

    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(flowNodes, flowEdges);
    
    // Animer l'apparition
    const animatedNodes = layoutedNodes.map(n => ({
      ...n,
      style: { ...n.style, opacity: 1, transform: 'scale(1)', transition: 'all 0.5s ease-out' }
    }));

    setNodes(animatedNodes);
    setEdges(layoutedEdges);
  }, [data, setNodes, setEdges]);

  return (
    <div className="w-full h-full relative rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-[0_0_30px_rgba(0,0,0,0.5)]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        colorMode="dark"
      >
        <Background color="#334155" gap={24} size={2} />
        <Controls className="!bg-slate-900 !border-slate-800 !fill-white" />
        <MiniMap 
          className="!bg-slate-900 !border-slate-800"
          maskColor="rgba(15, 23, 42, 0.7)"
          nodeColor={(n) => {
            if (n.type === 'PersonNode') return '#ef4444';
            if (n.type === 'CompanyNode') return '#f97316';
            if (n.type === 'PropertyNode') return '#22c55e';
            if (n.type === 'DocumentNode') return '#3b82f6';
            return '#64748b';
          }}
        />
      </ReactFlow>
      
      {/* Overlay vignette pour le look cinématique */}
      <div className="absolute inset-0 pointer-events-none rounded-xl" style={{ boxShadow: 'inset 0 0 100px rgba(0,0,0,0.8)' }} />
    </div>
  );
};
