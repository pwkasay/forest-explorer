<script setup>
import { onMounted, watch, ref, computed } from 'vue'
import { useCarbonStore } from '@/stores/carbon'

const store = useCarbonStore()
const mapRef = ref(null)
const mapReady = ref(false)
const mapLoading = ref(false)
const activeLayer = ref('clusters') // 'clusters' | 'heatmap'
const minCarbon = ref(0)
const selectedSpecies = ref(null)

let L, map, clusterGroup, heatLayer

// ── Carbon color scale ──────────────────────────────────────────────────
const TIERS = [
  { min: 50, color: '#16a34a', label: '≥ 50 t/acre' },
  { min: 30, color: '#22c55e', label: '30 – 50' },
  { min: 15, color: '#eab308', label: '15 – 30' },
  { min: 5, color: '#f97316', label: '5 – 15' },
  { min: 0, color: '#ef4444', label: '< 5' },
]

function carbonColor(lbs) {
  if (!lbs) return '#6b7280'
  const tons = lbs / 2000
  if (tons >= 50) return '#16a34a'
  if (tons >= 30) return '#22c55e'
  if (tons >= 15) return '#eab308'
  if (tons >= 5) return '#f97316'
  return '#ef4444'
}

function carbonRadius(lbs) {
  if (!lbs) return 4
  const tons = lbs / 2000
  return Math.min(12, Math.max(4, 4 + (tons / 10)))
}

// ── Computed ────────────────────────────────────────────────────────────
const plotCount = computed(() => store.plotsGeoJSON?.features?.length ?? 0)

const carbonSliderLabel = computed(() =>
  minCarbon.value === 0 ? 'All' : `≥ ${minCarbon.value} t/ac`
)

// ── Map init ────────────────────────────────────────────────────────────
async function initMap() {
  const leaflet = await import('leaflet')
  L = leaflet.default || leaflet
  window.L = L
  await import('leaflet.markercluster')
  await import('leaflet.heat')

  map = L.map(mapRef.value, {
    zoomControl: false,
  }).setView([35.5, -79.5], 7)

  // Zoom control in bottom-left to avoid colliding with layer toggle
  L.control.zoom({ position: 'bottomleft' }).addTo(map)

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 19,
  }).addTo(map)

  mapReady.value = true
}

// ── Render layers ───────────────────────────────────────────────────────
function clearLayers() {
  if (clusterGroup) { map.removeLayer(clusterGroup); clusterGroup = null }
  if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null }
}

function renderClusters() {
  if (!map || !store.plotsGeoJSON) return
  clearLayers()

  clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    iconCreateFunction: (cluster) => {
      const count = cluster.getChildCount()
      const children = cluster.getAllChildMarkers()
      let totalCarbon = 0
      for (const m of children) {
        totalCarbon += m.options.carbonValue || 0
      }
      const avgCarbon = children.length > 0 ? totalCarbon / children.length : 0
      const color = carbonColor(avgCarbon)
      return L.divIcon({
        html: `<div style="background:${color};">${count}</div>`,
        className: 'marker-cluster',
        iconSize: L.point(40, 40),
      })
    },
  })

  for (const feature of store.plotsGeoJSON.features) {
    const [lng, lat] = feature.geometry.coordinates
    const p = feature.properties
    const color = carbonColor(p.carbon_ag_total)
    const radius = carbonRadius(p.carbon_ag_total)

    const marker = L.circleMarker([lat, lng], {
      radius,
      fillColor: color,
      fillOpacity: 0.85,
      color: 'rgba(255,255,255,0.15)',
      weight: 1,
      carbonValue: p.carbon_ag_total ?? 0,
    })

    const tonsAcre = p.carbon_ag_total ? (p.carbon_ag_total / 2000).toFixed(1) : 'N/A'
    marker.bindPopup(`
      <div class="plot-popup">
        <div class="popup-header">Plot ${p.cn}</div>
        <div class="popup-row">
          <span class="popup-label">Carbon (AG)</span>
          <span class="popup-value">${tonsAcre} t/ac</span>
        </div>
        <div class="popup-row">
          <span class="popup-label">Trees</span>
          <span class="popup-value">${p.tree_count ?? '—'}</span>
        </div>
        <div class="popup-row">
          <span class="popup-label">Species</span>
          <span class="popup-value">${p.dominant_species ?? 'Unknown'}</span>
        </div>
        <div class="popup-row">
          <span class="popup-label">Stand age</span>
          <span class="popup-value">${p.stand_age ? p.stand_age + ' yrs' : '—'}</span>
        </div>
        <div class="popup-row">
          <span class="popup-label">Inventory</span>
          <span class="popup-value">${p.invyr}</span>
        </div>
      </div>
    `, { maxWidth: 220, className: 'dark-popup' })

    clusterGroup.addLayer(marker)
  }

  map.addLayer(clusterGroup)
}

function renderHeatmap() {
  if (!map || !store.plotsGeoJSON) return
  clearLayers()

  const features = store.plotsGeoJSON.features
  const maxCarbon = Math.max(...features.map(f => f.properties.carbon_ag_total || 0), 1)

  const points = features
    .filter(f => f.properties.carbon_ag_total)
    .map(f => {
      const [lng, lat] = f.geometry.coordinates
      const intensity = f.properties.carbon_ag_total / maxCarbon
      return [lat, lng, intensity]
    })

  heatLayer = L.heatLayer(points, {
    radius: 25,
    blur: 20,
    maxZoom: 12,
    max: 1.0,
    gradient: {
      0.0: '#1a1d27',
      0.2: '#ef4444',
      0.4: '#f97316',
      0.6: '#eab308',
      0.8: '#22c55e',
      1.0: '#16a34a',
    },
  }).addTo(map)
}

function renderActive() {
  if (activeLayer.value === 'heatmap') renderHeatmap()
  else renderClusters()
}

// ── Fit bounds ──────────────────────────────────────────────────────────
function fitToPlots() {
  if (!map || !store.plotsGeoJSON?.features?.length) return
  const coords = store.plotsGeoJSON.features.map(f => {
    const [lng, lat] = f.geometry.coordinates
    return [lat, lng]
  })
  map.fitBounds(L.latLngBounds(coords), { padding: [30, 30] })
}

// ── Filters ─────────────────────────────────────────────────────────────
let filterDebounce = null

async function applyFilters() {
  mapLoading.value = true
  const options = { limit: 500 }
  if (minCarbon.value > 0) options.minCarbon = minCarbon.value * 2000 // slider is tons, API is lbs
  if (selectedSpecies.value) options.species = selectedSpecies.value
  await store.fetchPlots(options)
  renderActive()
  mapLoading.value = false
}

function onSliderInput() {
  clearTimeout(filterDebounce)
  filterDebounce = setTimeout(applyFilters, 400)
}

function clearFilters() {
  minCarbon.value = 0
  selectedSpecies.value = null
  applyFilters()
}

function setLayer(layer) {
  activeLayer.value = layer
  renderActive()
}

// ── Lifecycle ───────────────────────────────────────────────────────────
onMounted(async () => {
  await initMap()
  mapLoading.value = true
  if (!store.speciesData.length) await store.fetchSpecies()
  if (!store.plotsGeoJSON) await store.fetchPlots()
  renderActive()
  fitToPlots()
  mapLoading.value = false
})

watch(() => store.selectedState, async () => {
  mapLoading.value = true
  minCarbon.value = 0
  selectedSpecies.value = null
  await Promise.all([store.fetchPlots(), store.fetchSpecies()])
  renderActive()
  fitToPlots()
  mapLoading.value = false
})
</script>

<template>
  <div class="map-wrapper">
    <!-- Map container -->
    <div ref="mapRef" style="width: 100%; height: 100%"></div>

    <!-- Loading overlay -->
    <div v-if="mapLoading" class="map-loading-overlay">
      <div class="map-spinner"></div>
    </div>

    <!-- Filter panel (top-left) -->
    <div class="map-filter-panel">
      <div>
        <div class="filter-label">State</div>
        <select v-model="store.selectedState">
          <option v-for="s in store.availableStates" :key="s.code" :value="s.code">
            {{ s.abbr }} — {{ s.name }}
          </option>
        </select>
      </div>

      <div>
        <div class="filter-label">Min Carbon Density</div>
        <input
          type="range"
          v-model.number="minCarbon"
          min="0"
          max="100"
          step="5"
          class="carbon-slider"
          @input="onSliderInput"
        />
        <div class="filter-value">{{ carbonSliderLabel }}</div>
      </div>

      <div>
        <div class="filter-label">Species Filter</div>
        <select v-model="selectedSpecies" @change="applyFilters">
          <option :value="null">All species</option>
          <option v-for="sp in store.speciesData" :key="sp.spcd" :value="sp.spcd">
            {{ sp.species_name }} ({{ sp.plot_count }} plots)
          </option>
        </select>
      </div>

      <div class="plot-count">
        Showing <strong>{{ plotCount }}</strong> plots
      </div>

      <button
        v-if="minCarbon > 0 || selectedSpecies"
        class="clear-filters-btn"
        @click="clearFilters"
      >
        Clear filters
      </button>
    </div>

    <!-- Layer toggle (top-right) -->
    <div class="map-layer-toggle">
      <button :class="{ active: activeLayer === 'clusters' }" @click="setLayer('clusters')">
        Clusters
      </button>
      <button :class="{ active: activeLayer === 'heatmap' }" @click="setLayer('heatmap')">
        Heatmap
      </button>
    </div>

    <!-- Legend (bottom-right) -->
    <div v-if="activeLayer === 'clusters'" class="map-legend">
      <div class="legend-title">Carbon Density (t/acre)</div>
      <div v-for="tier in TIERS" :key="tier.label" class="legend-item">
        <span class="legend-dot" :style="{ background: tier.color }"></span>
        <span class="legend-label">{{ tier.label }}</span>
      </div>
    </div>
    <div v-else class="map-legend">
      <div class="legend-title">Carbon Heatmap</div>
      <div style="display: flex; align-items: center; gap: 0.4rem; margin-top: 0.25rem">
        <span style="font-size: 0.75rem; color: var(--color-text-muted)">Low</span>
        <div style="
          flex: 1; height: 8px; border-radius: 4px;
          background: linear-gradient(to right, #ef4444, #f97316, #eab308, #22c55e, #16a34a);
        "></div>
        <span style="font-size: 0.75rem; color: var(--color-text-muted)">High</span>
      </div>
    </div>
  </div>
</template>

<style>
/* Unscoped — Leaflet injects popup HTML outside Vue's component tree */
.plot-popup {
  font-size: 13px; line-height: 1.5;
}
.popup-header {
  font-weight: 700; font-size: 14px;
  padding-bottom: 0.4rem; margin-bottom: 0.4rem;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-accent);
}
.popup-row {
  display: flex; justify-content: space-between; gap: 1rem;
  padding: 0.1rem 0;
}
.popup-label { color: var(--color-text-muted); }
.popup-value { font-family: var(--font-mono); font-weight: 500; }
</style>
