import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '@/composables/useApi'

export const useCarbonStore = defineStore('carbon', () => {
  const api = useApi()

  // State
  const selectedState = ref(37) // NC by default (SE US loblolly country)
  const summary = ref(null)
  const speciesData = ref([])
  const plotsGeoJSON = ref(null)
  const qaResults = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // SE US states relevant to Funga's operations
  const availableStates = [
    { code: 1, abbr: 'AL', name: 'Alabama' },
    { code: 12, abbr: 'FL', name: 'Florida' },
    { code: 13, abbr: 'GA', name: 'Georgia' },
    { code: 22, abbr: 'LA', name: 'Louisiana' },
    { code: 28, abbr: 'MS', name: 'Mississippi' },
    { code: 37, abbr: 'NC', name: 'North Carolina' },
    { code: 45, abbr: 'SC', name: 'South Carolina' },
    { code: 47, abbr: 'TN', name: 'Tennessee' },
    { code: 48, abbr: 'TX', name: 'Texas' },
    { code: 51, abbr: 'VA', name: 'Virginia' },
  ]

  // Getters
  const currentStateName = computed(() =>
    availableStates.find(s => s.code === selectedState.value)?.name ?? 'Unknown'
  )

  const loblollySpecies = computed(() =>
    speciesData.value.find(s => s.spcd === 131)
  )

  // Actions
  async function fetchSummary() {
    loading.value = true
    error.value = null
    try {
      summary.value = await api.get(`/carbon/summary/${selectedState.value}`)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchSpecies() {
    try {
      speciesData.value = await api.get(`/carbon/species/${selectedState.value}?limit=15`)
    } catch (e) {
      error.value = e.message
    }
  }

  async function fetchPlots(options = {}) {
    try {
      const params = new URLSearchParams()
      if (options.minCarbon) params.set('min_carbon', options.minCarbon)
      if (options.species) params.set('species', options.species)
      params.set('limit', options.limit ?? 500)
      const qs = params.toString()
      plotsGeoJSON.value = await api.get(
        `/plots/${selectedState.value}/geojson${qs ? '?' + qs : ''}`
      )
    } catch (e) {
      error.value = e.message
    }
  }

  async function runQA() {
    loading.value = true
    try {
      qaResults.value = await api.post('/qa/run')
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function loadAll() {
    await Promise.all([fetchSummary(), fetchSpecies(), fetchPlots()])
  }

  return {
    selectedState, summary, speciesData, plotsGeoJSON, qaResults,
    loading, error, availableStates, currentStateName, loblollySpecies,
    fetchSummary, fetchSpecies, fetchPlots, runQA, loadAll,
  }
})
