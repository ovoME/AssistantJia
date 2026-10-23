<script setup lang="ts">
import GlassBackground from '@/components/GlassBackground.vue'
import CuToastHost from '@/components/cu/CuToastHost.vue'
</script>

<template>
  <GlassBackground />
  <router-view />
  <CuToastHost />
</template>
