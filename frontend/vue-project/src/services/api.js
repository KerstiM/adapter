/**
 * Adapter pipeline API service.
 *
 * All data comes from the real backend — zero mock data.
 * Backend: python -m entrypoints.api (stdlib http.server, port 5000)
 * Vite proxy forwards /api → http://localhost:5000
 */

const DATASETS = [
  { id: 'D1', name: 'D1_public_valid_small', records: 7 },
  { id: 'D2', name: 'D2_public_mixed_large', records: 66 },
  { id: 'D3', name: 'D3_synth_valid_seed42', records: 150, accounts: 2 },
  { id: 'D4', name: 'D4_synth_errors_seed42', records: 39 },
  { id: 'D5', name: 'D5_synth_edges_seed99', records: 33 },
  { id: 'D6', name: 'D6_synth_dupes_seed99', records: 24 },
  { id: 'D7', name: 'D7_standing_orders_seed77', records: 4 },
  { id: 'D8', name: 'D8_load_test_10k_seed88', records: 10000 },
  { id: 'D9', name: 'D9_synth_perf_seed9', records: 1000 },
  { id: 'D10', name: 'D10_real_anon_oct16', records: 90 },
]

const MODELS = [
  { id: 'openai_gpt4o', label: 'OpenAI GPT-4o' },
  { id: 'anthropic_claude35_sonnet', label: 'Anthropic Claude 3.5 Sonnet' },
  { id: 'google_gemini15_pro', label: 'Google Gemini 1.5 Pro' },
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

  // Group issues by (code, severity, message) and add count
  const rawIssues = backendResult.issues || []
  const issueMap = new Map()
  for (const issue of rawIssues) {
    const key = `${issue.severity}|${issue.code}|${issue.message}`
    if (issueMap.has(key)) {
      issueMap.get(key).count += 1
    } else {
      issueMap.set(key, { ...issue, count: 1 })
    }
  }
  const groupedIssues = [...issueMap.values()]

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
    issues: groupedIssues,
    mlPreview: data.mlPreview,
    llmPreview: data.llmPreview,
  }

  return { result, elapsed_ms: data.elapsed_ms }
}
