/**
 * Adapter pipeline API service.
 *
 * In prototype mode uses mock data that mirrors the backend pipeline output.
 * The runPipeline() function signature is designed so that swapping to a real
 * HTTP backend later requires changing only the fetch call.
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

/**
 * Simulate pipeline execution with realistic mock data.
 */
function _generateMockResult(datasetId, modelId) {
  const dataset = DATASETS.find((d) => d.id === datasetId)
  const hasErrors = datasetId === 'D4'
  const hasDupes = datasetId === 'D6'
  const hasEdges = datasetId === 'D5'

  const accountsTotal = datasetId === 'D2' ? 5 : 2
  const txTotal = { D1: 48, D2: 487, D3: 195, D4: 210, D5: 148, D6: 183, D7: 122 }[datasetId] || 100
  const dropped = hasErrors ? 14 : hasDupes ? 9 : hasEdges ? 3 : 0
  const emitted = txTotal - dropped

  const outcome = hasErrors ? 'PARTIAL_SUCCESS' : 'SUCCESS'
  const stopReason = hasErrors ? 'error_ratio_below_threshold' : 'all_stages_passed'

  const issues = []
  if (hasErrors) {
    issues.push(
      { code: 'INV-03', severity: 'ERROR', message: 'bookingDate is in the future', count: 5 },
      { code: 'INV-05', severity: 'WARN', message: 'transactionAmount.amount is zero', count: 4 },
      { code: 'INV-07', severity: 'ERROR', message: 'Missing creditorName for CREDIT', count: 5 },
    )
  }
  if (hasDupes) {
    issues.push({ code: 'INV-09', severity: 'WARN', message: 'Duplicate (account_id, record_id)', count: 9 })
  }
  if (hasEdges) {
    issues.push({ code: 'INV-02', severity: 'WARN', message: 'Currency mismatch EUR vs USD', count: 3 })
  }

  const bySeverity = { ERROR: 0, WARN: 0, INFO: 0 }
  issues.forEach((i) => {
    bySeverity[i.severity] = (bySeverity[i.severity] || 0) + (i.count || 1)
  })

  const stageLog = [
    { stage: 'READ_INPUT', errors: hasErrors ? 0 : 0, warnings: 0, status: 'OK' },
    { stage: 'STANDARDIZE_TO_SV', errors: 0, warnings: dropped > 0 ? dropped : 0, status: dropped > 0 ? 'WARN' : 'OK' },
    { stage: 'VALIDATE_SCHEMA', errors: 0, warnings: 0, status: 'OK' },
    {
      stage: 'CHECK_INVARIANTS',
      errors: bySeverity.ERROR,
      warnings: bySeverity.WARN,
      status: bySeverity.ERROR > 0 ? 'ERROR' : bySeverity.WARN > 0 ? 'WARN' : 'OK',
    },
    { stage: 'PROJECT_ML', errors: 0, warnings: 0, status: 'OK' },
    { stage: 'PROJECT_LLM', errors: 0, warnings: 0, status: 'OK' },
    { stage: 'WRITE_OUTPUTS', errors: 0, warnings: 0, status: 'OK' },
  ]

  // ML-specific mock
  const mlPreview =
    modelId === 'ml'
      ? {
          headers: [
            'account_id',
            'record_id',
            'booking_date',
            'amount',
            'currency',
            'direction',
            'creditor',
            'category',
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
      : null

  // LLM-specific mock
  const llmPreview =
    modelId === 'llm'
      ? {
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
          narrative: `Client has ${accountsTotal} account(s). During period ${dataset?.name || datasetId}, ${emitted} transactions were processed. Primary income: salary (2 500 EUR/month). Top expense categories: groceries, rent, transport. Net cash flow is positive (+1 602.50 EUR).`,
        }
      : null

  const runId = `run_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
  const createdAt = new Date().toISOString()

  return {
    outcome,
    stopReason,
    runId,
    createdAt,
    datasetId,
    datasetName: dataset?.name || datasetId,
    modelId,
    counts: {
      accounts_total: accountsTotal,
      transactions_total: txTotal,
      transactions_emitted_sv: emitted,
      transactions_dropped: dropped,
      ml_rows: modelId === 'ml' ? emitted : 0,
      llm_contexts: modelId === 'llm' ? accountsTotal : 0,
    },
    bySeverity,
    stageLog,
    issues,
    mlPreview,
    llmPreview,
  }
}

/**
 * Simulate network + processing delay.
 */
function _simulateDelay() {
  const ms = 800 + Math.random() * 2200
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ── Public API ──

export function getDatasets() {
  return [...DATASETS]
}

export function getModels() {
  return [...MODELS]
}

/**
 * Run the adapter pipeline for the given dataset and model.
 * Returns { result, elapsed_ms }.
 */
export async function runPipeline(datasetId, modelId) {
  await _simulateDelay()
  const t0 = performance.now()
  const result = _generateMockResult(datasetId, modelId)
  const elapsed_ms = Math.round(performance.now() - t0)
  return { result, elapsed_ms }
}
