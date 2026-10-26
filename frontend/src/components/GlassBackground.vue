<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'

const cursor = ref<HTMLElement | null>(null)
let raf = 0
let tx = window.innerWidth / 2
let ty = window.innerHeight / 2
let cx = tx
let cy = ty

function onMove(e: MouseEvent) {
  tx = e.clientX
  ty = e.clientY
  if (cursor.value) cursor.value.style.opacity = '1'
}
function loop() {
  cx += (tx - cx) * 0.12
  cy += (ty - cy) * 0.12
  if (cursor.value) {
    cursor.value.style.left = cx + 'px'
    cursor.value.style.top = cy + 'px'
  }
  raf = requestAnimationFrame(loop)
}
onMounted(() => {
  window.addEventListener('mousemove', onMove)
  raf = requestAnimationFrame(loop)
})
onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMove)
  cancelAnimationFrame(raf)
})
</script>

<template>
  <div class="wallpaper" aria-hidden="true">
    <div class="base"></div>
    <div class="grid"></div>
    <div class="tint t1"></div>
    <div class="tint t2"></div>
    <div ref="cursor" class="cursor"></div>
  </div>
</template>

<style scoped>
.wallpaper {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}
/* 干净的浅灰白底 */
.base {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, #f7f9fb 0%, #eef1f5 100%);
}
/* 极淡网格：给玻璃折射提供参照，是玻璃质感的关键 */
.grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(20, 45, 55, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(20, 45, 55, 0.045) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(130% 100% at 50% 0%, #000 45%, transparent 92%);
}
/* 角落极淡的品牌色点缀，克制、不铺张 */
.tint {
  position: absolute;
  border-radius: 50%;
  filter: blur(110px);
}
.t1 {
  width: 460px; height: 460px;
  background: radial-gradient(circle, rgba(20, 184, 166, 0.22), transparent 70%);
  top: -200px; left: 50%;
  transform: translateX(-50%);
}
.t2 {
  width: 420px; height: 420px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.14), transparent 70%);
  bottom: -210px; right: -120px;
}
/* 鼠标位置的极淡高光 */
.cursor {
  position: fixed;
  width: 200px; height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.25), transparent 60%);
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.6s;
}
@media (prefers-reduced-motion: reduce) {
  .cursor { display: none; }
}
</style>
