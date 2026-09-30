<!-- designed by mew -->
<script setup lang="ts">
import { ref, watch } from 'vue';
import { api } from '../api/client';
import { errorMessage, useEditorStore } from '../editor/store';
import type { ContentKind } from '../types/content';
import UiIcon from '../components/UiIcon.vue';
const props = defineProps<{ active: boolean }>();
const emit = defineEmits<{ locate: [target: { kind: ContentKind; id: string; field?: string }] }>();
interface Change {
  field: string;
  label: string;
  before: unknown;
  after: unknown;
}
interface Entry {
  id: number;
  kind: ContentKind;
  key: string;
  title: string;
  action: string;
  actor: string;
  created: string;
  changes: Change[];
  canLocate: boolean;
}
interface HistoryPage {
  items: Entry[];
  page: number;
  hasMore: boolean;
  kinds: { key: string; label: string }[];
}
const store = useEditorStore(),
  entries = ref<Entry[]>([]),
  kinds = ref<HistoryPage['kinds']>([]);
const query = ref(''),
  actor = ref(''),
  kind = ref(''),
  page = ref(1),
  hasMore = ref(false),
  loading = ref(false),
  error = ref('');
async function load(reset = false) {
  if (reset) page.value = 1;
  loading.value = true;
  error.value = '';
  try {
    const { data } = await api.get<HistoryPage>('manage/history/', {
      params: { page: page.value, q: query.value, kind: kind.value, actor: actor.value },
    });
    entries.value = data.items;
    kinds.value = data.kinds;
    page.value = data.page;
    hasMore.value = data.hasMore;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
function value(entry: Entry, field: string, data: unknown): string {
  if (data === undefined || data === null || data === '') return '未填写';
  if (typeof data === 'boolean') return data ? '是' : '否';
  const spec = store.schemas[entry.kind]?.find((item) => item.name === field);
  if (spec?.target && typeof data === 'string') {
    const related = store.find(spec.target, data);
    if (related) return store.title(related);
  }
  if (Array.isArray(data))
    return data.length ? data.map((item) => value(entry, field, item)).join('\n') : '未填写';
  if (typeof data === 'object') {
    const item = data as Record<string, unknown>;
    if ('url' in item) return [item.label, item.url].filter(Boolean).join(' · ');
    return Object.entries(item)
      .map(([key, val]) => `${key}：${String(val ?? '')}`)
      .join('\n');
  }
  const text = String(data);
  if (/<[a-z][\s\S]*>/i.test(text))
    return (
      new DOMParser()
        .parseFromString(text.replace(/<\/p>|<br\s*\/?>/gi, '\n'), 'text/html')
        .body.textContent?.trim() || '未填写'
    );
  return text;
}
const isImage = (field: string, data: unknown) =>
  typeof data === 'string' &&
  /image|poster|logo/.test(field) &&
  /\.(png|webp|jpe?g|gif)(\?|$)/i.test(data);
watch(
  () => props.active,
  (active) => {
    if (active) void load(true);
  },
  { immediate: true },
);
</script>
<template>
  <div class="mg-page-heading mg-history-heading">
    <div>
      <span class="mg-eyebrow">团队更新</span>
      <h1>编辑记录</h1>
      <p>查看正式发布、下线和删除的修改记录。</p>
    </div>
    <button class="mg-button" :disabled="loading" @click="load(true)">刷新记录</button>
  </div>
  <form class="mg-history-filters" @submit.prevent="load(true)">
    <input v-model="query" aria-label="搜索编辑记录" placeholder="搜索条目名称或操作…" /><input
      v-model="actor"
      aria-label="筛选编辑人员"
      placeholder="编辑人员姓名或用户名"
    /><select v-model="kind" aria-label="筛选记录类型">
      <option value="">全部类型</option>
      <option v-for="item in kinds" :key="item.key" :value="item.key">
        {{ item.label }}
      </option></select
    ><button class="mg-button mg-primary" :disabled="loading">筛选</button>
  </form>
  <p v-if="error" class="mg-alert mg-alert-error" role="alert">{{ error }}</p>
  <p v-if="loading" class="mg-muted" role="status">正在读取编辑记录…</p>
  <div v-else class="mg-history-list">
    <article v-for="entry in entries" :key="entry.id" class="mg-card mg-history-entry">
      <header>
        <span class="mg-avatar">{{ entry.actor.slice(0, 1) }}</span>
        <div class="mg-history-author">
          <strong>{{ entry.actor }}</strong
          ><span>{{ entry.action }}</span
          ><time :datetime="entry.created">{{
            new Date(entry.created).toLocaleString('zh-CN')
          }}</time>
        </div>
        <button
          v-if="entry.canLocate"
          class="mg-text-button"
          @click="emit('locate', { kind: entry.kind, id: entry.key })"
        >
          定位条目 <UiIcon name="arrow-up-right" />
        </button>
      </header>
      <h2>{{ entry.title }}</h2>
      <details v-if="entry.changes.length">
        <summary>查看 {{ entry.changes.length }} 项修改</summary>
        <div v-for="change in entry.changes" :key="change.field" class="mg-history-change">
          <div class="mg-card-title">
            <h3>{{ change.label }}</h3>
            <button
              v-if="entry.canLocate && !change.field.startsWith('$')"
              class="mg-text-button"
              @click="emit('locate', { kind: entry.kind, id: entry.key, field: change.field })"
            >
              定位字段
            </button>
          </div>
          <div class="mg-history-values">
            <div>
              <small>修改前</small
              ><img
                v-if="isImage(change.field, change.before)"
                :src="String(change.before)"
                alt="修改前的图片"
                loading="lazy"
              />
              <p>{{ value(entry, change.field, change.before) }}</p>
            </div>
            <div>
              <small>修改后</small
              ><img
                v-if="isImage(change.field, change.after)"
                :src="String(change.after)"
                alt="修改后的图片"
                loading="lazy"
              />
              <p>{{ value(entry, change.field, change.after) }}</p>
            </div>
          </div>
        </div>
      </details>
      <p v-else class="mg-muted mg-history-empty-diff">此操作没有字段变化。</p>
    </article>
    <p v-if="!entries.length" class="mg-card mg-muted">没有找到编辑记录，可以调整筛选条件。</p>
  </div>
  <footer class="mg-history-pagination">
    <button
      class="mg-button"
      :disabled="loading || page <= 1"
      @click="
        page--;
        load();
      "
    >
      上一页</button
    ><span>第 {{ page }} 页</span
    ><button
      class="mg-button"
      :disabled="loading || !hasMore"
      @click="
        page++;
        load();
      "
    >
      下一页
    </button>
  </footer>
</template>
