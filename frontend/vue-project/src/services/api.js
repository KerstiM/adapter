/**
 * Adapter pipeline API service.
 *
 * Calls the real Flask backend (POST /api/run) and uses the actual
 * pipeline processing time.  ML/LLM preview data is still mocked
 * because the backend summary does not include presentation layers.
 */

const MODELS = [
  { id: 'ml', outputType: 'CSV', icon: 'chart' },
  { id: 'llm', outputType: 'JSON', icon: 'brain' },
]

// ── Mock presentation helpers (backend doesn't produce these) ──

function _mockMlPreview(emitted) {
  return {
    headers: [
      'account_id', 'record_id', 'booking_date', 'amount',
      'currency', 'direction', 'creditor', 'category',
    ],
    rows: [
      ['EE123456', 'TX-001', '2025-01-15', '-42.50', 'EUR', 'DEBIT', 'Selver AS', 'groceries'],
      ['EE123456', 'TX-002', '2025-01-16', '2500.00', 'EUR', 'CREDIT', 'Tööandja OÜ', 'salary'],
      ['EE123456', 'TX-003', '2025-01-17', '-89.99', 'EUR', 'DEBIT', 'Telia Eesti', 'telecom'],
      ['EE789012', 'TX-004', '2025-01-18', '-15.00', 'EUR', 'DEBIT', 'Bolt Technology', 'transport'],
      ['EE789012', 'TX-005', '2025-01-19', '-320.00', 'EUR', 'DEBIT', 'Üritaja OÜ', 'rent'],
    ],
    totalRows: emitted,
  }
}

function _mockLlmPreview(accountsTotal, datasetName, emitted) {
  return {
    accountSummary: {
      accountCount: accountsTotal,
      currency: 'EUR',
      periodStart: '2025-01-01',
      periodEnd: '2025-01-31',
      totalIncome: 4850.0,
      totalExpenses: -3247.5,
      netFlow: 1602.5,
    },
    topCategories: [
      { category: 'salary', total: 2500.0, count: 1 },
      { category: 'groceries', total: -685.3, count: 12 },
      { category: 'rent', total: -640.0, count: 2 },
      { category: 'telecom', total: -89.99, count: 1 },
      { category: 'transport', total: -245.0, count: 8 },
    ],
    narrative: `Client has ${accountsTotal} account(s). During period ${datasetName}, ${emitted} transactions were processed. Primary income: salary (2 500 EUR/month). Top expense categories: groceries, rent, transport. Net cash flow is positive (+1 602.50 EUR).`,
  }
}

function _buildStageLog(bySeverity, dropped) {
  return [
    { stage: 'READ_INPUT', errors: 0, warnings: 0, status: 'OK' },
    { stage: 'STANDARDIZE_TO_SV', errors: 0, warnings: dropped > 0 ? dropped : 0, status: dropped > 0 ? 'WARN' : 'OK' },
    { stage: 'VALIDATE_SCHEMA', errors: 0, warnings: 0, status: 'OK' },
    {
      stage: 'CHECK_INVARIANTS',
      errors: bySeverity.ERROR || 0,
      warnings: bySeverity.WARN || 0,
      status: (bySeverity.ERROR || 0) > 0 ? 'ERROR' : (bySeverity.WARN || 0) > 0 ? 'WARN' : 'OK',
    },
    { stage: 'PROJECT_ML', errors: 0, warnings: 0, status: 'OK' },
    { stage: 'PROJECT_LLM', errors: 0, warnings: 0, status: 'OK' },
    { stage: 'WRITE_OUTPUTS', errors: 0, warnings: 0, status: 'OK' },
  ]
}

// ── Public API ──

const DATASETS = [
  { id: 'D1', name: 'D1_public_valid_small', records: 50 },
  { id: 'D2', name: 'D2_public_mixed_large', records: 500 },
  { id: 'D3', name: 'D3_synth_valid_seed42', records: 200 },
  { id: 'D4', name: 'D4_synth_errors_seed42', records: 200 },
  { id: 'D5', name: 'D5_synth_edges_seed99', records: 150 },
  { id: 'D6', name: 'D6_synth_dupes_seed99', records: 180 },
  { id: 'D7', name: 'D7_standing_orders_seed77', records: 120 },
]

export function getDatasets() {
  return [...DATASETS]
}

export function getModels() {
  return [...MODELS]
}

/**
 * Run the adapter pipeline for the given dataset and model.
 * Returns { result, elapsed_ms } with real backend processing time.
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

  const { result: backendResult, elapsed_ms } = await res.json()

  const counts = backendResult.counts
  const bySeverity = backendResult.by_severity || {}

  const result = {
    outcome: backendResult.outcome,
    stopReason: backendResult.stop_reason,
    runId: backendResult.run_id,
    createdAt: new Date().toISOString(),
    datasetId,
    datasetName: datasetId,
    modelId,
    counts,
    bySeverity: {
      ERROR: bySeverity.ERROR || 0,
      WARN: bySeverity.WARN || 0,
      INFO: bySeverity.INFO || 0,
    },
    stageLog: _buildStageLog(bySeverity, counts.transactions_dropped),
    issues: backendResult.issues || [],
    mlPreview: modelId === 'ml' ? _mockMlPreview(counts.transactions_emitted_sv) : null,
    llmPreview: modelId === 'llm' ? _mockLlmPreview(counts.accounts_total, datasetId, counts.transactions_emitted_sv) : null,
  }

  return { result, elapsed_ms }
}
