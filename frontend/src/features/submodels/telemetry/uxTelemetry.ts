type MetricPayload = Record<string, unknown>;

export function emitSubmodelUxMetric(name: string, payload: MetricPayload): void {
  // Keep telemetry non-blocking; this can be wired to a real sink later.
  // eslint-disable-next-line no-console
  console.info('submodel_ux_metric', { name, ...payload });
}
