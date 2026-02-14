import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { CirpassLabStep } from '../../schema/storySchema';

interface ApiInspectorProps {
  api: CirpassLabStep['api'] | undefined;
  mode: 'mock' | 'live';
  variant: 'happy' | 'unauthorized' | 'not_found';
}

function buildCurlCommand(api: NonNullable<CirpassLabStep['api']>, mode: 'mock' | 'live'): string {
  const method = api.method.toUpperCase();
  const base = mode === 'live' ? 'https://dpp-platform.dev' : 'https://mock.dpp-platform.dev';
  const command: string[] = [`curl -X ${method}`, `'${base}${api.path}'`];

  if (api.auth !== 'none') {
    command.push(`-H 'Authorization: Bearer <token>'`);
  }
  command.push(`-H 'Content-Type: application/json'`);

  if (api.request_example && method !== 'GET') {
    command.push(`--data '${JSON.stringify(api.request_example)}'`);
  }

  return command.join(' \\\n  ');
}

export default function ApiInspector({ api, mode, variant }: ApiInspectorProps) {
  const [copied, setCopied] = useState(false);

  const curl = useMemo(() => {
    if (!api) {
      return '';
    }
    return buildCurlCommand(api, mode);
  }, [api, mode]);

  if (!api) {
    return (
      <section className="min-w-0 rounded-2xl border border-landing-ink/12 bg-white/75 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">
          API Inspector
        </p>
        <p className="mt-2 text-sm text-landing-muted">No API call metadata for this step.</p>
      </section>
    );
  }

  return (
    <section className="min-w-0 rounded-2xl border border-landing-ink/12 bg-white/75 p-4" data-testid="cirpass-api-inspector">
      <p className="text-xs font-semibold uppercase tracking-[0.13em] text-landing-muted">API Inspector</p>
      <p className="mt-2 text-sm text-landing-ink">
        <span className="font-semibold">{api.method}</span> {api.path}
      </p>
      <p className="mt-1 text-xs text-landing-muted">
        Auth: {api.auth} · Mode: {mode} · Variant: {variant}
      </p>

      <div className="mt-3 rounded-xl border border-landing-ink/10 bg-slate-950 p-3 text-xs text-slate-100">
        <pre className="overflow-x-auto whitespace-pre-wrap break-all" data-testid="cirpass-api-curl">
          {curl}
        </pre>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          className="h-8 rounded-full px-4 text-xs"
          onClick={async () => {
            await navigator.clipboard.writeText(curl);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1200);
          }}
          data-testid="cirpass-copy-curl"
        >
          {copied ? 'Copied' : 'Copy as curl'}
        </Button>
        {typeof api.expected_status === 'number' && (
          <span className="inline-flex items-center rounded-full border border-landing-ink/12 bg-white px-3 text-xs font-semibold text-landing-muted">
            Expected {api.expected_status}
          </span>
        )}
      </div>

      {(api.request_example || api.response_example) && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-landing-muted">
              Request
            </p>
            <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-slate-950 p-2 text-xs text-cyan-200">
              {JSON.stringify(api.request_example ?? {}, null, 2)}
            </pre>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-landing-muted">
              Response
            </p>
            <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-slate-950 p-2 text-xs text-emerald-200">
              {JSON.stringify(api.response_example ?? {}, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}
