<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const SEGMENT_ID = 1
const data = ref<any>(null)
const vendors = ref<any[]>([])
const day = ref<any>(null)
const err = ref('')
const mode = ref<'run' | 'preview' | ''>('')

async function refreshDay() {
  const [days, segments] = await Promise.all([api('/days'), api('/segments')])
  const seg = (segments as any[]).find(s => s.id === SEGMENT_ID)
  day.value = (days as any[]).find(d => d.id === seg?.market_day_id) || null
}
async function loadLatest() {
  // 只读加载旧运行：窗外也能看旧色块，且不会新增运行
  try {
    data.value = await api(`/allocate/latest?segment_id=${SEGMENT_ID}`)
    mode.value = 'run'
  } catch { data.value = null; mode.value = '' }
}
async function confirmRun() {
  err.value = ''
  try {
    data.value = await api(`/allocate/run?segment_id=${SEGMENT_ID}`, { method: 'POST' })
    mode.value = 'run'
    await refreshDay()
  } catch (e: any) { err.value = e.message } // 窗外被后端拦下，行数不变
}
async function preview() {
  err.value = ''
  try {
    data.value = await api(`/allocate/preview?segment_id=${SEGMENT_ID}`, { method: 'POST' })
    mode.value = 'preview'
  } catch (e: any) { err.value = e.message }
}
onMounted(async () => {
  vendors.value = await api('/vendors')
  await Promise.all([refreshDay(), loadLatest()])
})
const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']
const cells = computed(() => {
  if (!data.value) return []
  const width = data.value.segment.width_m
  const out: any[] = []
  for (const p of data.value.pillars || []) {
    out.push({ type: 'pillar', start: p.position_m - p.thickness_m/2, w: p.thickness_m, label: p.label || '挡柱' })
  }
  for (const [i, p] of (data.value.placements || []).entries()) {
    out.push({ type: 'stall', start: p.start_m, w: p.width_m, label: p.vendor_name, color: colors[i % colors.length] })
  }
  return out.sort((a,b) => a.start - b.start).map(c => ({ ...c, pct: Math.max((c.w / width) * 100, 2) }))
})
</script>
<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 挡柱为竖直阻断 · 底部为摊主排队</p>
    <p v-if="day" class="sub">
      可分配时段 {{ day.alloc_start }}–{{ day.alloc_end }}
      <span class="badge" :class="day.writable ? 'badge-ok' : 'badge-warn'">
        {{ day.writable ? '窗内可分配' : '窗外只读' }}
      </span>
      · 运行条数 {{ day.run_count }}
    </p>
    <div class="ss-actions">
      <button class="btn" @click="preview">试摆</button>
      <button class="btn" @click="confirmRun">确认分配</button>
      <span v-if="mode === 'preview'" class="badge badge-warn">试摆结果 · 未入库</span>
      <span v-else-if="mode === 'run' && data" class="badge badge-ok">运行 #{{ data.id }}</span>
    </div>
    <p v-if="err" class="badge badge-bad">{{ err }}</p>
    <p v-if="!data && !err" class="muted">暂无运行记录，窗内点击「确认分配」生成。</p>
    <div class="ss-band-ruler" v-if="data">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data">
      <div class="ss-street-inner">
        <div
          v-for="(c,i) in cells" :key="i"
          class="ss-band-cell"
          :class="{ 'ss-pillar': c.type === 'pillar' }"
          :style="{ width: c.pct + '%', background: c.type === 'pillar' ? undefined : c.color, flex: '0 0 ' + c.pct + '%' }"
        >{{ c.label }}</div>
      </div>
    </div>
    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
      </div>
    </div>
    <div class="card" v-if="data">
      <table>
        <thead><tr><th>摊主</th><th>起点</th><th>终点</th><th>宽度</th></tr></thead>
        <tbody>
          <tr v-for="p in data.placements" :key="p.vendor_id">
            <td>{{ p.vendor_name }}</td><td>{{ p.start_m }}</td><td>{{ p.end_m }}</td><td>{{ p.width_m }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
