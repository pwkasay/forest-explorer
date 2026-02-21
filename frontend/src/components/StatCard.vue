<script setup>
defineProps({
  label: String,
  value: [String, Number],
  accent: { type: Boolean, default: false },
})
</script>

<template>
  <div class="card">
    <div class="card-header">{{ label }}</div>
    <div class="card-value" :class="{ accent }">{{ value }}</div>
  </div>
</template>
