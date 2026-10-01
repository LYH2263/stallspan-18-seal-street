<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

interface DayRow {
  id: number
  name: string
  day: string
  window_start: string
  window_end: string
  server_now: string
  writable: boolean
}

const rows = ref<DayRow[]>([])
const drafts = ref<Record<number, { day: string; window_start: string; window_end: string }>>({})
const saving = ref<number | null>(null)
const error = ref('')
const okMsg = ref('')

async function load() {
  rows.value = await api<DayRow[]>('/days')
  for (const r of rows.value) {
    drafts.value[r.id] = { day: r.day, window_start: r.window_start, window_end: r.window_end }
  }
}

async function save(r: DayRow) {
  const d = drafts.value[r.id]
  saving.value = r.id
  error.value = ''
  okMsg.value = ''
  try {
    // 改时段后判定按刚改的窗：后端 PATCH 返回的就是新窗下的 writable。
    const updated = await api<DayRow>(`/days/${r.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ day: d.day, window_start: d.window_start, window_end: d.window_end }),
    })
    const idx = rows.value.findIndex(x => x.id === r.id)
    if (idx >= 0) rows.value[idx] = updated
    okMsg.value = updated.writable
      ? `已保存 · 当前 ${updated.server_now} 在可分配时段内，可确认/试摆`
      : `已保存 · 当前 ${updated.server_now} 不在可分配时段，确认与试摆均关闭`
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    saving.value = null
  }
}

onMounted(load)
</script>
<template>
  <h1>集日</h1>
  <p class="sub">开市日期与可分配时段（开/收市时钟）。窗内可确认与试摆，窗外只读旧运行。</p>
  <p v-if="error" class="badge badge-bad" style="padding:.5rem .75rem">{{ error }}</p>
  <p v-if="okMsg" class="badge" :class="okMsg.includes('窗内') ? 'badge-ok' : 'badge-warn'" style="padding:.5rem .75rem">{{ okMsg }}</p>
  <div class="card" v-for="r in rows" :key="r.id">
    <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
      <strong style="min-width:5rem">{{ r.name }}</strong>
      <label>日期
        <input type="date" v-model="drafts[r.id].day">
      </label>
      <label>可分配起
        <input type="time" v-model="drafts[r.id].window_start" step="60">
      </label>
      <label>可分配止
        <input type="time" v-model="drafts[r.id].window_end" step="60">
      </label>
      <button class="btn" :disabled="saving === r.id" @click="save(r)">
        {{ saving === r.id ? '保存中…' : '保存时段' }}
      </button>
      <span class="badge" :class="r.writable ? 'badge-ok' : 'badge-bad'">
        服务器现在 {{ r.server_now }} · {{ r.writable ? '窗内·可写' : '窗外·只读' }}
      </span>
    </div>
  </div>
</template>
