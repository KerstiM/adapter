// Static doc registry — markdown files bundled at compile time via Vite's ?raw imports

import specsRaw    from '../../../../docs/SPETSIFIKATSIOONID.md?raw'
import archRaw     from '../../../../docs/ARHITEKTUUR.md?raw'
import runbookRaw  from '../../../../docs/runbook.md?raw'

import d1Raw  from '../../../../datasets/D1_public_valid_small/README.md?raw'
import d2Raw  from '../../../../datasets/D2_public_mixed_large/README.md?raw'
import d3Raw  from '../../../../datasets/D3_synth_valid_seed42/README.md?raw'
import d4Raw  from '../../../../datasets/D4_synth_errors_seed42/README.md?raw'
import d5Raw  from '../../../../datasets/D5_synth_edges_seed99/README.md?raw'
import d6Raw  from '../../../../datasets/D6_synth_dupes_seed99/README.md?raw'
import d7Raw  from '../../../../datasets/D7_standing_orders_seed77/README.md?raw'
import d8Raw  from '../../../../datasets/D8_load_test_10k_seed88/README.md?raw'
import d9Raw  from '../../../../datasets/D9_synth_perf_seed9/README.md?raw'
import d10Raw from '../../../../datasets/D10_real_anon_oct16/README.md?raw'

export const CORE_DOCS = [
  {
    id: 'specs',
    title: 'Spetsifikatsioonid',
    subtitle: 'Skeemid · Lepingud · Reeglistikud',
    content: specsRaw,
  },
  {
    id: 'arch',
    title: 'Arhitektuur',
    subtitle: 'Pipeline · Sõltuvused · Failipuu',
    content: archRaw,
  },
  {
    id: 'runbook',
    title: 'Runbook',
    subtitle: 'Käivitamine · Artefaktid · CLI',
    content: runbookRaw,
  },
]

export const DATASET_DOCS = [
  { id: 'd1',  datasetId: 'D1',  title: 'D1 – Public, valid, small',     content: d1Raw  },
  { id: 'd2',  datasetId: 'D2',  title: 'D2 – Public, mixed, large',     content: d2Raw  },
  { id: 'd3',  datasetId: 'D3',  title: 'D3 – Synth, valid',             content: d3Raw  },
  { id: 'd4',  datasetId: 'D4',  title: 'D4 – Synth, with errors',       content: d4Raw  },
  { id: 'd5',  datasetId: 'D5',  title: 'D5 – Edge cases',               content: d5Raw  },
  { id: 'd6',  datasetId: 'D6',  title: 'D6 – With duplicates',          content: d6Raw  },
  { id: 'd7',  datasetId: 'D7',  title: 'D7 – Standing orders',          content: d7Raw  },
  { id: 'd8',  datasetId: 'D8',  title: 'D8 – Large dataset (10k)',      content: d8Raw  },
  { id: 'd9',  datasetId: 'D9',  title: 'D9 – Synth, performance',       content: d9Raw  },
  { id: 'd10', datasetId: 'D10', title: 'D10 – Real, anonymised',        content: d10Raw },
]

export const ALL_DOCS = [...CORE_DOCS, ...DATASET_DOCS]
