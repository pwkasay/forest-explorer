<script setup>
import { useCarbonStore } from '@/stores/carbon'

const store = useCarbonStore()
</script>

<template>
  <div class="state-selector">
    <label for="state-select">State:</label>
    <select id="state-select" v-model="store.selectedState">
      <option
        v-for="state in store.availableStates"
        :key="state.code"
        :value="state.code"
      >
        {{ state.name }} ({{ state.abbr }})
      </option>
    </select>
    <span style="font-size: 0.8rem; color: var(--color-text-muted)">
      SE US states — primary operational region for SE US forestry
    </span>
  </div>
</template>
