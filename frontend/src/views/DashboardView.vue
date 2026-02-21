<script setup>
import { onMounted, watch } from 'vue'
import { useCarbonStore } from '@/stores/carbon'
import StatCard from '@/components/StatCard.vue'
import SpeciesChart from '@/components/SpeciesChart.vue'
import StateSelector from '@/components/StateSelector.vue'

const store = useCarbonStore()

onMounted(() => store.loadAll())
watch(() => store.selectedState, () => store.loadAll())
</script>

<template>
  <div class="dashboard">
    <StateSelector />

    <div v-if="store.loading" class="loading">Loading carbon data...</div>

    <template v-else-if="store.summary">
      <!-- KPI cards -->
      <div class="stats-grid">
        <StatCard
          label="Total Plots"
          :value="store.summary.total_plots.toLocaleString()"
        />
        <StatCard
          label="Live Trees Measured"
          :value="store.summary.total_trees.toLocaleString()"
        />
        <StatCard
          label="Species Observed"
          :value="store.summary.species_count"
        />
        <StatCard
          label="Avg Carbon / Acre"
          :value="`${store.summary.avg_carbon_per_acre_tons.toFixed(2)} t`"
          accent
        />
        <StatCard
          label="Loblolly Pine %"
          :value="`${store.summary.loblolly_pine_pct}%`"
          :accent="store.summary.loblolly_pine_pct > 20"
        />
        <StatCard
          label="Most Recent Inventory"
          :value="store.summary.most_recent_inventory"
        />
      </div>

      <!-- Species comparison -->
      <div class="dashboard-row two-col">
        <div class="card">
          <div class="card-header">Carbon Density by Species (lbs/acre)</div>
          <SpeciesChart :data="store.speciesData" />
        </div>
        <div class="card">
          <div class="card-header">About This Data</div>
          <p style="color: var(--color-text-muted); font-size: 0.9rem; line-height: 1.7">
            Data from the <strong>USFS Forest Inventory & Analysis</strong> program —
            the ground-truth dataset behind US forest carbon accounting. Each plot
            represents a permanent field sample on a rotating 5–10 year measurement cycle.
          </p>
          <p style="color: var(--color-text-muted); font-size: 0.9rem; line-height: 1.7; margin-top: 0.75rem">
            Carbon values use the <strong>National Scale Volume and Biomass (NSVB)</strong>
            estimators adopted in 2023. Loblolly pine (SPCD 131) is highlighted because it's
            the dominant commercial timber species in the SE US — and Funga's primary
            inoculation target.
          </p>
        </div>
      </div>
    </template>

    <div v-else-if="store.error" class="card" style="color: var(--color-error)">
      Error: {{ store.error }}
    </div>
  </div>
</template>
