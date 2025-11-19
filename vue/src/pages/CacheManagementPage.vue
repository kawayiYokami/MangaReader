<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useCacheStore } from '@/store/cache'
import { storeToRefs } from 'pinia'
import BatchCompressionDialog from '@/components/dialogs/BatchCompressionDialog.vue'

const cacheStore = useCacheStore()
const {
  cacheTypes,
  cacheStats,
  selectedCacheType,
  entries,
  pagination,
  isLoading,
  searchQuery
} = storeToRefs(cacheStore)

const batchCompressionDialogState = reactive({
  visible: false,
});

const selectedMangaKeys = ref<string[]>([]);

onMounted(() => {
  cacheStore.fetchInitialData()
})

const getSelectedCacheName = () => {
  return cacheTypes.value.find(t => t.key === selectedCacheType.value)?.name || ''
}

const showBatchCompressionDialog = () => {
  batchCompressionDialogState.visible = true;
}

const handleMangaSelectionChange = (selection: any[]) => {
  selectedMangaKeys.value = selection.map(item => item.key);
}

const getTableColspan = () => {
  if (selectedCacheType.value === 'manga_list') {
    return 7; // key, checkbox, variance, pages, size, tags, actions
  }
  return 3; // key, value, actions
}

</script>

<template>
  <div class="cache-management-minimal">
    <!-- Cache Overview -->
    <el-card class="cache-overview">
      <div class="cache-list">
        <div
          v-for="cacheType in cacheTypes"
          :key="cacheType.key"
          class="cache-item"
          :class="{ 'active': selectedCacheType === cacheType.key }"
          @click="cacheStore.selectCacheType(cacheType.key)"
        >
          <div class="cache-basic-info">
            <span class="cache-icon material-symbols-rounded">{{ cacheType.icon }}</span>
            <span class="cache-name">{{ cacheType.name }}</span>
          </div>
          <div class="cache-stats">
            <span>{{ cacheStats[cacheType.key]?.entries || 0 }} 条</span>
          </div>
          <div v-if="selectedCacheType === cacheType.key" class="cache-actions">
            <el-button size="small" type="danger" text @click.stop="cacheStore.clearCache(cacheType.key)">清空</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Cache Detail -->
    <el-card v-if="selectedCacheType" class="cache-detail">
      <!-- Search and Action Bar -->
      <div class="search-and-actions-bar">
        <el-input v-model="searchQuery" :placeholder="`在 ${getSelectedCacheName()} 中搜索...`" clearable class="search-input" @change="cacheStore.fetchEntries"/>
        
        <!-- Spacer -->
        <div class="spacer"></div>

        <!-- Action Buttons and Switches -->
        <!-- 漫画列表特有按钮 -->
        <template v-if="selectedCacheType === 'manga_list'">
          <el-button size="small" type="success" class="action-button" @click="showBatchCompressionDialog">
            <span class="material-symbols-rounded" style="vertical-align: middle; font-size: 1.1em; margin-right: 4px;">compress</span>
            批量压缩
          </el-button>
        </template>
      </div>

      <div v-loading="isLoading.entries" class="entries-container">
        <el-table
          v-if="selectedCacheType === 'manga_list'"
          :data="entries"
          style="width: 100%"
          row-key="key"
          @selection-change="handleMangaSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="key" label="漫画" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.key.split(/[/\\]/).pop() }}
            </template>
          </el-table-column>
          <el-table-column prop="variance" label="方差" width="100" sortable />
          <el-table-column prop="page_count" label="页数" width="100" sortable />
          <el-table-column prop="file_size" label="大小" width="120" sortable>
             <template #default="{ row }">
              {{ row.file_size ? (row.file_size / 1024 / 1024).toFixed(2) + ' MB' : 'N/A' }}
            </template>
          </el-table-column>
          <el-table-column prop="tags" label="标签" min-width="150" show-overflow-tooltip>
             <template #default="{ row }">
              {{ row.tags?.join(', ') }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
               <el-button size="small" type="danger" text @click="cacheStore.deleteEntry(selectedCacheType!, row.key)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <table v-else class="custom-cache-table">
          <thead>
            <tr>
              <th>键</th>
              <th>内容</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="entries.length === 0">
              <td :colspan="getTableColspan()">没有数据</td>
            </tr>
            <tr v-for="entry in entries" :key="entry.key">
              <td :title="entry.key">{{ entry.key.slice(0, 50) }}...</td>
              <td>{{ entry.value_preview }}</td>
              <td>
                <el-button size="small" type="danger" text @click="cacheStore.deleteEntry(selectedCacheType!, entry.key)">删除</el-button>
              </td>
            </tr>
          </tbody>
        </table>
        <el-pagination
          :current-page="pagination.currentPage"
          :page-size="pagination.pageSize"
          :total="pagination.totalEntries"
          layout="prev, pager, next"
          @current-change="cacheStore.changePage"
        />
      </div>
    </el-card>

    <BatchCompressionDialog
      v-model:visible="batchCompressionDialogState.visible"
    />
  </div>
</template>

<style scoped>
/* Add some basic styling */
.cache-management-minimal {
  display: flex;
  flex-direction: row; /*  从 column 改为 row */
  gap: var(--spacing-lg);
}

.cache-overview {
  flex: 0 0 320px; /* 设置一个固定的宽度，不拉伸也不收缩 */
}

.cache-detail {
  flex: 1; /* 占据剩余的空间 */
  display: flex;
  flex-direction: column;
}

.search-and-actions-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: 0 var(--el-card-padding) var(--el-card-padding);
  border-bottom: 1px solid var(--el-card-border-color);
  flex-wrap: wrap;
}

.search-input {
  max-width: 400px;
}

.spacer {
  flex: 1;
}

/* M3 Style Overrides */
.search-input :deep(.el-input__wrapper) {
  background-color: transparent;
  border-radius: 999px; /* Pill shape */
  box-shadow: none !important;
  border: 1px solid var(--color-border-default);
}
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-accent-default);
}

.action-button {
  border-radius: 999px; /* Pill shape */
  border: none;
  font-weight: 500;
}

.action-button.el-button--success {
  background-color: var(--color-success-subtle);
  color: var(--color-success-strong);
}
.action-button.el-button--success:hover {
  background-color: var(--color-success-subtle-hover);
}

.action-button.el-button--warning {
  background-color: var(--color-warning-subtle);
  color: var(--color-warning-strong);
}
.action-button.el-button--warning:hover {
  background-color: var(--color-warning-subtle-hover);
}

.search-and-actions-bar :deep(.el-switch .el-switch__core) {
  border-radius: 999px;
}

.search-and-actions-bar :deep(.el-switch .el-switch__action) {
  border-radius: 999px;
}

.entries-container {
  flex: 1;
  overflow-y: auto;
}

.cache-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}
.cache-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-md);
  border: 1px solid var(--color-border-default);
  border-radius: var(--border-radius);
  cursor: pointer;
  transition: background-color var(--transition);
}
.cache-item.active {
  background-color: var(--color-bg-elevated);
  border-color: var(--color-accent-default);
}
.cache-basic-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}
.custom-cache-table {
  width: 100%;
  border-collapse: collapse;
}
.custom-cache-table th, .custom-cache-table td {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-subtle);
  text-align: left;
}
</style>