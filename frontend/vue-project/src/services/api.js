/**
 * Adapter pipeline API service.
 *
 * All data comes from the real backend — zero mock data.
 * Backend: python -m entrypoints.api (stdlib http.server, port 5000)
 * Vite proxy forwards /api → http://localhost:5000
 */

const DATASETS = [
  { id: 'D1', name: 'D1_public_valid_small', records: 50 },
  { id: 'D2', name: 'D2_public_mixed_large', records: 500 },
  { id: 'D3', name: 'D3_synth_valid_seed42', records: 200 },
  { id: 'D4', name: 'D4_synth_errors_seed42', records: 200 },
  { id: 'D5', name: 'D5_synth_edges_seed99', records: 150 },
  { id: 'D6', name: 'D6_synth_dupes_seed99', records: 180 },
  { id: 'D7', name: 'D7_standing_orders_seed77', records: 120 },
]

const MODELS = [
  { id: 'ml', outputType: 'CSV', icon: 'chart' },
  { id: 'llm', outputType: 'JSON', icon: 'brain' },
]

// ── Public API ──

export function getDatasets() {
  return [...DATASETS]
}

export function getModels() {
  return [...MODELS]
}

/**
 * Run the adapter pipeline for the given dataset and model.
 * Returns { result, elapsed_ms } — all real data from the backend.
 */
export async function runPipeline(datasetId, modelId) {
  const res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ datasetId }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `Pipeline failed (${res.status})`)
  }

  const data = await res.json()
  const backendResult = data.result
  const bySeverity = backendResult.by_severity || {}

  // Map stage_log: add status field for frontend display
  const stageLog = (data.stageLog || []).map((s) => ({
    stage: s.stage,
    errors: s.errors,
    warnings: s.warnings,
    status: s.errors > 0 ? 'ERROR' : s.warnings > 0 ? 'WARN' : 'OK',
  }))

  const result = {
    outcome: backendResult.outcome,
    stopReason: backendResult.stop_reason,
    runId: backendResult.run_id,
    createdAt: new Date().toISOString(),
    datasetId,
    datasetName: datasetId,
    modelId,
    counts: backendResult.counts,
    bySeverity: {
      ERROR: bySeverity.ERROR || 0,
      WARN: bySeverity.WARN || 0,
      INFO: bySeverity.INFO || 0,
    },
    stageLog,
    issues: backendResult.issues || [],
    mlPreview: data.mlPreview,
    llmPreview: data.llmPreview,
  }

  return { result, elapsed_ms: data.elapsed_ms }
}
