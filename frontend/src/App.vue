<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <h1>🍄 <span>Forest Carbon</span> Explorer</h1>
      <nav class="nav-links">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/map">Map</RouterLink>
        <RouterLink to="/qa">QA/QC</RouterLink>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
