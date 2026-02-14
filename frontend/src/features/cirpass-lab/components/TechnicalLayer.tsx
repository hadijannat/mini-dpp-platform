import '@xyflow/react/dist/style.css';
import { useMemo } from 'react';
import type { CirpassLevelKey } from '../machines/cirpassMachine';
import { Background, Controls, MarkerType, MiniMap, ReactFlow } from '@xyflow/react';
import type { Edge, Node } from '@xyflow/react';

interface TechnicalLayerProps {
  currentLevel: CirpassLevelKey;
  completedLevels: Record<CirpassLevelKey, boolean>;
  payloadPreview: unknown;
}

const order: CirpassLevelKey[] = ['create', 'access', 'update', 'transfer', 'deactivate'];

export default function TechnicalLayer({
  currentLevel,
  completedLevels,
  payloadPreview,
}: TechnicalLayerProps) {
  const { nodes, edges } = useMemo(() => {
    const builtNodes: Node[] = order.map((level, idx) => {
      const complete = completedLevels[level];
      const active = level === currentLevel;
      return {
        id: level,
        position: { x: 40 + idx * 220, y: 90 },
        data: {
          label: `${level.toUpperCase()}${complete ? ' · OK' : active ? ' · ACTIVE' : ''}`,
        },
        style: {
          borderRadius: 16,
          border: active ? '2px solid #22d3ee' : '1px solid rgba(148, 163, 184, 0.35)',
          background: complete
            ? 'linear-gradient(140deg, rgba(16, 185, 129, 0.26), rgba(15, 23, 42, 0.75))'
            : 'linear-gradient(140deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.84))',
          color: '#f8fafc',
          padding: '10px 14px',
          fontSize: 12,
          width: 190,
          fontWeight: 700,
          letterSpacing: '0.03em',
        },
      };
    });

    builtNodes.push({
      id: 'payload',
      position: { x: 240, y: 260 },
      data: {
        label: `JSON-LD Preview\n${JSON.stringify(payloadPreview ?? {}, null, 2)}`,
      },
      style: {
        borderRadius: 12,
        border: '1px solid rgba(56, 189, 248, 0.4)',
        background: 'rgba(2, 6, 23, 0.92)',
          color: '#67e8f9',
          width: 560,
          whiteSpace: 'pre-wrap',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: 11,
        lineHeight: 1.4,
        padding: '10px 12px',
      },
    });

    const builtEdges: Edge[] = order.slice(0, -1).map((level, idx) => ({
      id: `${level}-${order[idx + 1]}`,
      source: level,
      target: order[idx + 1],
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: level === currentLevel,
      style: {
        stroke: completedLevels[level] ? '#10b981' : '#64748b',
        strokeWidth: completedLevels[level] ? 3 : 2,
      },
    }));

    builtEdges.push({
      id: `${currentLevel}-payload`,
      source: currentLevel,
      target: 'payload',
      markerEnd: { type: MarkerType.ArrowClosed },
      animated: true,
      style: { stroke: '#22d3ee', strokeWidth: 2.5 },
    });

    return { nodes: builtNodes, edges: builtEdges };
  }, [completedLevels, currentLevel, payloadPreview]);

  return (
    <div className="h-[460px] w-full" data-testid="cirpass-technical-flow">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        minZoom={0.55}
        maxZoom={1.4}
      >
        <MiniMap
          pannable
          zoomable
          style={{ background: '#020617', border: '1px solid rgba(148, 163, 184, 0.22)' }}
        />
        <Controls showInteractive={false} />
        <Background color="rgba(148, 163, 184, 0.2)" gap={22} />
      </ReactFlow>
    </div>
  );
}
