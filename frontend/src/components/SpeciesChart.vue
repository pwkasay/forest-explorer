<script setup>
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const props = defineProps({
  data: { type: Array, default: () => [] },
})

const chartData = computed(() => ({
  labels: props.data.map(d => d.species_name || `SPCD ${d.spcd}`),
  datasets: [
    {
      label: 'Above-ground',
      data: props.data.map(d => d.avg_carbon_ag_per_acre),
      backgroundColor: '#22c55e',
      borderRadius: 3,
    },
    {
      label: 'Below-ground',
      data: props.data.map(d => d.avg_carbon_bg_per_acre),
      backgroundColor: '#16a34a',
      borderRadius: 3,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y',
  plugins: {
    legend: {
      position: 'top',
      labels: { color: '#8b90a0', font: { size: 11 } },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.x.toLocaleString()} lbs/acre`,
      },
    },
  },
  scales: {
    x: {
      stacked: true,
      ticks: { color: '#8b90a0' },
      grid: { color: '#2e3347' },
      title: { display: true, text: 'Carbon (lbs/acre)', color: '#8b90a0' },
    },
    y: {
      stacked: true,
      ticks: { color: '#8b90a0', font: { size: 11 } },
      grid: { display: false },
    },
  },
}
</script>

<template>
  <div v-if="data.length" style="height: 400px">
    <Bar :data="chartData" :options="chartOptions" />
  </div>
  <div v-else class="loading">No species data available</div>
</template>
