/**
 * Adapter pipeline API service.
 *
 * All data comes from the real backend — zero mock data.
 * Backend: python -m entrypoints.api (stdlib http.server, port 8000)
 * Vite proxy forwards /api → http://localhost:8000
 */

const DATASETS = [
  { id: 'D1', name: 'D1_synth_valid_small', records: 7 },
  { id: 'D2', name: 'D2_synth_mixed_large', records: 66 },
  { id: 'D3', name: 'D3_synth_valid_seed42', records: 150, accounts: 2 },
  { id: 'D4', name: 'D4_synth_errors_seed42', records: 39 },
  { id: 'D5', name: 'D5_synth_edges_seed99', records: 33 },
  { id: 'D6', name: 'D6_synth_dupes_seed99', records: 24 },
  { id: 'D7', name: 'D7_standing_orders_seed77', records: 4 },
  { id: 'D8', name: 'D8_load_test_10k_seed88', records: 10000 },
  { id: 'D9', name: 'D9_synth_perf_seed9', records: 1000 },
  { id: 'D10', name: 'D10_real_deid_oct16', records: 101 },
  { id: 'D11', name: 'D11_real_deid_2024', records: 148, accounts: 2 },
  { id: 'D12', name: 'D12_synth_partial_low_seed42', records: 200 },
  { id: 'D13', name: 'D13_synth_partial_mid_seed42', records: 100 },
  { id: 'D14', name: 'D14_synth_partial_high_seed42', records: 100 },
]

const MODELS = [
  { id: 'llama3.1-8b-instruct', label: 'Meta Llama 3.1 8B Instruct', type: 'llm' },
  { id: 'mistral-7b-instruct-v0.3', label: 'Mistral 7B Instruct v0.3', type: 'llm' },
  { id: 'qwen2.5-7b-instruct', label: 'Qwen2.5 7B Instruct', type: 'llm' },
  { id: 'gemma-2-2b-it', label: 'Google Gemma 2 2B', type: 'llm' },
  { id: 'xgboost', label: 'XGBoost', type: 'ml' },
  { id: 'catboost', label: 'CatBoost', type: 'ml' },
]

// ── Public API ──

export function getDatasets() {
  return [...DATASETS]
}

export function getModels() {
  return [...MODELS]
}

/**
 * Split selected model IDs into targetLlm / targetMl arrays for the backend.
 */
function buildModelPayload(selectedModelIds) {
  if (!selectedModelIds || selectedModelIds.length === 0) return {}
  const llmIds = selectedModelIds.filter((id) =>
    MODELS.some((m) => m.id === id && m.type === 'llm'),
  )
  const mlIds = selectedModelIds.filter((id) =>
    MODELS.some((m) => m.id === id && m.type === 'ml'),
  )
  const payload = {}
  if (llmIds.length > 0) payload.targetLlm = llmIds
  if (mlIds.length > 0) payload.targetMl = mlIds
  return payload
}

/**
 * Run the adapter pipeline for the given dataset and optional model selection.
 * Returns { result, elapsed_ms } — all real data from the backend.
 */
export async function runPipeline(datasetId, selectedModelIds) {
  // includeRaw: opt-in for the per-transaction LLM context. The dev frontend
  // displays it in the LLM viewer; production / non-localhost callers should
  // omit this flag so the backend strips counterparty/remittance text.
  const body = { datasetId, includeRaw: true, ...buildModelPayload(selectedModelIds) }

  const res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
    selectedModelIds: selectedModelIds || [],
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
    modelProjections: data.modelProjections || [],
  }

  return { result, elapsed_ms: data.elapsed_ms }
}
