<script setup>
import { onMounted } from 'vue'
import { useCarbonStore } from '@/stores/carbon'
import StateSelector from '@/components/StateSelector.vue'

const store = useCarbonStore()

onMounted(() => {
  if (!store.qaResults) store.runQA()
})

function severityClass(severity, failed) {
  if (failed === 0) return 'ok'
  return severity
}

function formatPct(rate) {
  return (rate * 100).toFixed(2) + '%'
}
</script>

<template>
  <div class="dashboard">
    <div style="display: flex; align-items: center; justify-content: space-between">
      <h2 style="font-size: 1.1rem">Data Quality Validation</h2>
      <div style="display: flex; align-items: center; gap: 1rem">
        <StateSelector />
        <button
          @click="store.runQA()"
          :disabled="store.loading"
          style="padding: 0.5rem 1rem; background: var(--color-accent); color: var(--color-bg);
                 border: none; border-radius: var(--radius); cursor: pointer; font-weight: 600;
                 font-size: 0.85rem; opacity: 1; transition: opacity 0.15s"
          :style="{ opacity: store.loading ? 0.5 : 1 }"
        >
          {{ store.loading ? 'Running...' : 'Run QA Checks' }}
        </button>
      </div>
    </div>

    <div v-if="store.loading" class="loading">Running validation checks...</div>

    <template v-else-if="store.qaResults">
      <!-- Summary -->
      <div class="stats-grid">
        <div class="card">
          <div class="card-header">Total Checks</div>
          <div class="card-value">{{ store.qaResults.total_checks }}</div>
        </div>
        <div class="card">
          <div class="card-header">Errors</div>
          <div class="card-value" :style="{ color: store.qaResults.errors ? 'var(--color-error)' : 'var(--color-accent)' }">
            {{ store.qaResults.errors }}
          </div>
        </div>
        <div class="card">
          <div class="card-header">Warnings</div>
          <div class="card-value" :style="{ color: store.qaResults.warnings ? 'var(--color-warning)' : 'var(--color-accent)' }">
            {{ store.qaResults.warnings }}
          </div>
        </div>
        <div class="card">
          <div class="card-header">Run ID</div>
          <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-muted); word-break: break-all">
            {{ store.qaResults.run_id }}
          </div>
        </div>
      </div>

      <!-- Check details -->
      <div class="card">
        <div class="card-header">Validation Results</div>
        <div style="margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem">
          <div
            v-for="check in store.qaResults.checks"
            :key="check.check_name"
            style="padding: 0.75rem; background: var(--color-bg); border-radius: var(--radius);
                   display: grid; grid-template-columns: 1fr auto; gap: 1rem; align-items: center"
          >
            <div>
              <div style="display: flex; align-items: center; gap: 0.5rem">
                <span class="badge" :class="severityClass(check.severity, check.records_failed)">
                  {{ check.records_failed === 0 ? '✓ PASS' : check.severity.toUpperCase() }}
                </span>
                <strong style="font-size: 0.9rem">{{ check.check_name }}</strong>
              </div>
              <div style="font-size: 0.8rem; color: var(--color-text-muted); margin-top: 0.25rem">
                {{ check.details?.description }}
              </div>
              <div style="font-size: 0.8rem; color: var(--color-text-muted)">
                Table: <code>{{ check.table_name }}</code>
              </div>
            </div>
            <div style="text-align: right; font-family: var(--font-mono); font-size: 0.85rem">
              <div>{{ check.records_failed.toLocaleString() }} / {{ check.records_checked.toLocaleString() }}</div>
              <div style="color: var(--color-text-muted); font-size: 0.75rem">
                {{ formatPct(check.failure_rate) }} failure
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
