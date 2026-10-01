<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const data = ref<any>(null)
const status = ref<any>(null)
const vendors = ref<any[]>([])
const runs = ref<{ id: number; created_at: string }[]>([])
const mode = ref<'latest' | 'trial' | 'run'>('latest')
const error = ref('')
const busy = ref('')

async function refreshStatus() {
  status.value = await api('/allocate/status?segment_id=1')
}
async function refreshRuns() {
  runs.value = await api('/allocate/runs?segment_id=1')
}
async function loadLatest() {
  // 只读：绝不因打开页面而新增运行
  const d = await api('/allocate/latest?segment_id=1')
  data.value = d
  status.value = {
    window_start: d.window_start, window_end: d.window_end,
    server_now: d.server_now, writable: d.writable, run_count: d.run_count,
  }
  mode.value = 'latest'
}

async function trial() {
  busy.value = 'trial'; error.value = ''
  try {
    const d = await api('/allocate/trial?segment_id=1', { method: 'POST' })
    data.value = d
    status.value = { window_start: d.window_start, window_end: d.window_end,
      server_now: d.server_now, writable: d.writable, run_count: d.run_count }
    mode.value = 'trial'
  } catch (e: any) {
    // 窗外：后端 403 拦住，行数不变；原因点明不在可分配时段
    error.value = e?.message || String(e)
    await refreshStatus()
  } finally { busy.value = '' }
}

async function confirmRun() {
  busy.value = 'run'; error.value = ''
  try {
    const d = await api('/allocate/run?segment_id=1', { method: 'POST' })
    data.value = d
    status.value = { window_start: d.window_start, window_end: d.window_end,
      server_now: d.server_now, writable: d.writable, run_count: d.run_count }
    mode.value = 'latest'
    await refreshRuns() // 窗内确认成功，条数恰好多一条
  } catch (e: any) {
    error.value = e?.message || String(e)
    await Promise.all([refreshStatus(), refreshRuns()]) // 半成功自检：行数应不变
  } finally { busy.value = '' }
}

async function openRun(id: number) {
  busy.value = 'run-' + id; error.value = ''
  try {
    data.value = await api('/allocate/runs/' + id)
    mode.value = 'run'
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally { busy.value = '' }
}

onMounted(async () => {
  vendors.value = await api('/vendors')
  await loadLatest()
  await refreshRuns()
})

const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']
const cells = computed(() => {
  if (!data.value?.segment) return []
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

    <div class="card" v-if="status" style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
      <span class="badge" :class="status.writable ? 'badge-ok' : 'badge-bad'">
        服务器现在 {{ status.server_now }} ·
        可分配时段 {{ status.window_start }}–{{ status.window_end }} ·
        {{ status.writable ? '窗内·可写' : '窗外·只读' }}
      </span>
      <span>运行条数：<strong>{{ status.run_count }}</strong></span>
      <!-- 窗外按钮仍在：点下由后端拦截，绝不允许前端半成功 -->
      <button class="btn" :disabled="busy === 'trial'" @click="trial">
        {{ busy === 'trial' ? '试摆中…' : '试摆（不落库）' }}
      </button>
      <button class="btn" :disabled="busy === 'run'" @click="confirmRun">
        {{ busy === 'run' ? '确认中…' : '确认开市（新增一条运行）' }}
      </button>
      <button class="btn" v-if="mode !== 'latest'" style="background:var(--ss-curb)" @click="loadLatest">回到最新</button>
    </div>
    <p v-if="error" class="badge badge-bad" style="padding:.5rem .75rem">{{ error }}</p>

    <p class="muted" v-if="mode === 'trial'">当前为<strong>试摆预览</strong>：未落库，运行条数不变；满意后请点「确认开市」。</p>
    <p class="muted" v-else-if="mode === 'run'">当前为<strong>旧运行 #{{ data?.id }}（只读）</strong>：可看色块，不能改写。</p>
    <p class="muted" v-else-if="data?.id">当前为已确认运行 #{{ data.id }}。</p>
    <p class="muted" v-else>该街段尚无运行；窗内确认后这里才会出现色块。</p>

    <div class="ss-band-ruler" v-if="data?.segment">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data?.segment">
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

    <div class="card">
      <strong>历史运行（只读可开）</strong>
      <p v-if="!runs.length" class="muted">暂无运行。</p>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.5rem">
        <button v-for="r in runs" :key="r.id" class="btn"
                style="background:var(--ss-curb)" :disabled="busy === 'run-' + r.id"
                @click="openRun(r.id)">
          #{{ r.id }} · {{ r.created_at }}
        </button>
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
