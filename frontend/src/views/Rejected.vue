<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const noRun = ref(false)
onMounted(async () => {
  try {
    const data = await api('/allocate/latest?segment_id=1')
    rows.value = data.rejected || []
  } catch { noRun.value = true } // 暂无运行记录（只读，不新增）
})
</script>
<template>
  <h1>放不下</h1>
  <p class="sub">无法在连续空档内安置且不跨越挡柱的摊位</p>
  <div class="card">
    <table>
      <thead><tr><th>摊主</th><th>需求宽度</th><th>原因</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.vendor_id">
          <td>{{ r.vendor_name }}</td><td>{{ r.width_m }}</td><td>{{ r.reason }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="noRun" class="muted">暂无运行记录</p>
    <p v-else-if="!rows.length" class="muted">全部放下</p>
  </div>
</template>
