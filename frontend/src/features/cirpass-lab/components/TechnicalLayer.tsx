import '@xyflow/react/dist/style.css';
import { useMemo } from 'react';
import { Background, Controls, MarkerType, MiniMap, ReactFlow } from '@xyflow/react';
import type { Edge, Node } from '@xyflow/react';
import type { CirpassLevelKey } from '../machines/cirpassMachine';
import type { CirpassLabStep, CirpassLabStory } from '../schema/storySchema';
import type { CheckResult } from '../utils/checkEngine';

interface TechnicalLayerProps {
  currentLevel: CirpassLevelKey;
  completedLevels: Record<CirpassLevelKey, boolean>;
  story: CirpassLabStory;
  step: CirpassLabStep;
  payloadPreview: unknown;
  responsePreview: { status: number; body?: unknown } | null;
  checkResult: CheckResult | null;
}

const order: CirpassLevelKey[] = ['create', 'access', 'update', 'transfer', 'deactivate'];

export default function TechnicalLayer({
  currentLevel,
  completedLevels,
  story,
  step,
  payloadPreview,
  responsePreview,
  checkResult,
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
      position: { x: 150, y: 260 },
      data: {
        label: `Step Payload\n${JSON.stringify(payloadPreview ?? {}, null, 2)}`,
      },
      style: {
        borderRadius: 12,
        border: '1px solid rgba(56, 189, 248, 0.4)',
        background: 'rgba(2, 6, 23, 0.92)',
        color: '#67e8f9',
        width: 420,
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
    <div className="grid h-[460px] w-full gap-3 p-3 lg:grid-cols-[1.25fr_0.75fr]" data-testid="cirpass-technical-flow">
      <div className="min-w-0 overflow-hidden rounded-xl border border-white/10 bg-slate-950/70">
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

      <aside className="min-w-0 space-y-2 overflow-auto rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-200">
        <div>
          <p className="font-semibold uppercase tracking-[0.1em] text-slate-300">Active Step</p>
          <p className="mt-1 text-sm text-white">{story.title}</p>
          <p className="mt-1 text-cyan-200">{step.title}</p>
        </div>

        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-2">
          <p className="font-semibold uppercase tracking-[0.08em] text-slate-300">API</p>
          <p className="mt-1">
            {step.api ? `${step.api.method} ${step.api.path}` : 'No API metadata for this step.'}
          </p>
          <p className="mt-1 text-slate-400">
            Expected status: {step.api?.expected_status ?? 'n/a'} · Observed:{' '}
            {responsePreview?.status ?? 'n/a'}
          </p>
        </div>

        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-2">
          <p className="font-semibold uppercase tracking-[0.08em] text-slate-300">Policy</p>
          <p className="mt-1">
            Role: {step.policy?.required_role ?? 'n/a'} · Decision:{' '}
            {step.policy?.expected_decision ?? 'n/a'}
          </p>
          {step.policy?.note && <p className="mt-1 text-slate-400">{step.policy.note}</p>}
        </div>

        <div className="rounded-lg border border-white/10 bg-slate-900/70 p-2">
          <p className="font-semibold uppercase tracking-[0.08em] text-slate-300">Checks</p>
          <p className="mt-1 text-slate-300">
            {checkResult?.passed ? 'All checks passed.' : `${checkResult?.failures.length ?? 0} check(s) failed.`}
          </p>
          {!checkResult?.passed &&
            checkResult?.failures.map((failure, index) => (
              <p key={`${failure.type}-${index}`} className="mt-1 text-rose-300">
                {failure.message}
              </p>
            ))}
        </div>
      </aside>
    </div>
  );
}

