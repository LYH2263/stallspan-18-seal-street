<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const rows = ref<any[]>([])
const err = ref('')
const editId = ref<number | null>(null)
const editStart = ref('')
const editEnd = ref('')

async function load() {
  err.value = ''
  try { rows.value = await api('/days') } catch (e: any) { err.value = e.message }
}
function startEdit(r: any) {
  editId.value = r.id
  editStart.value = r.alloc_start
  editEnd.value = r.alloc_end
}
async function save(r: any) {
  err.value = ''
  try {
    await api(`/days/${r.id}`, {
      method: 'PUT',
      body: JSON.stringify({ alloc_start: editStart.value, alloc_end: editEnd.value }),
    })
    editId.value = null
    await load() // 保存后按新窗重新判定
  } catch (e: any) { err.value = e.message }
}
onMounted(load)
</script>
<template>
  <h1>集日</h1>
  <p class="sub">开市日程 · 可分配时段内才能确认与试摆</p>
  <p v-if="err" class="badge badge-bad">{{ err }}</p>
  <div class="card">
    <table>
      <thead>
        <tr><th>名称</th><th>日期</th><th>可分配时段</th><th>状态</th><th>运行条数</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.name }}</td>
          <td>{{ r.day }}</td>
          <td>
            <template v-if="editId === r.id">
              <input type="time" v-model="editStart" /> –
              <input type="time" v-model="editEnd" />
            </template>
            <template v-else>{{ r.alloc_start }}–{{ r.alloc_end }}</template>
          </td>
          <td>
            <span class="badge" :class="r.writable ? 'badge-ok' : 'badge-warn'">
              {{ r.writable ? '窗内可分配' : '窗外只读' }}
            </span>
          </td>
          <td>{{ r.run_count }}</td>
          <td>
            <template v-if="editId === r.id">
              <button class="btn" @click="save(r)">保存</button>
              <button class="btn btn-ghost" @click="editId = null">取消</button>
            </template>
            <button v-else class="btn" @click="startEdit(r)">改时段</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="muted">状态与确认/试摆入口为同一套窗内判定；当前时刻在窗外时，确认与试摆都会被后端拒绝。</p>
  </div>
</template>
