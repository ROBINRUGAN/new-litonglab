<!-- designed by mew -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '../api/client';
import { locale } from '../composables/i18n';
import { usePreferencesStore } from '../stores/preferences';
import { localHref } from '../composables/site';
import type { ContentKind } from '../types/content';
import { canvasEditing } from './target';
import { useEditorStore, errorMessage, recordKey } from './store';
import type { EditRecord, EditTarget, FieldChange, HistoryVersion } from './types';
import { richEditor, startInline, stopInline } from './inline';
import EditorFields from './EditorFields.vue';
import EditorDialog from './EditorDialog.vue';
import MediaPicker from './MediaPicker.vue';
import { categoryForRecord } from './mediaCategories';
import type { ImageCategory } from './mediaCategories';
import PreviewDialog from './PreviewDialog.vue';
import UiIcon from '../components/UiIcon.vue';
import './editor.css';
const store = useEditorStore(),
  preferences = usePreferencesStore(),
  route = useRoute(),
  router = useRouter();
const username = ref(''),
  password = ref(''),
  authBusy = ref(false),
  error = ref(''),
  notice = ref('');
const embedded = window.parent !== window;
const showChanges = ref(false);
const inspect = ref(true),
  drawer = ref<'library' | 'item' | null>(null),
  selection = ref<EditTarget | null>(null),
  libraryKind = ref<ContentKind>('news'),
  query = ref(''),
  trash = ref(false),
  formEpoch = ref(0);
const mediaTarget = ref<{ record: EditRecord; field: string } | null>(null),
  mediaManager = ref(false),
  mediaCategory = ref<ImageCategory>(),
  showPreview = ref(false),
  showPublish = ref(false),
  publishKeys = ref<string[]>([]),
  history = ref<HistoryVersion[] | null>(null),
  historyOpen = ref<number | null>(null);
const confirm = ref<{ title: string; body: string; action: () => void | Promise<void> } | null>(
  null,
);
async function confirmAction() {
  const action = confirm.value?.action;
  confirm.value = null;
  if (action) await run(async () => action());
}
const selected = computed(() =>
  selection.value ? store.find(selection.value.kind, selection.value.id) : undefined,
);
const selectedField = computed(() => selection.value?.field);
const names: Partial<Record<ContentKind, string>> = {
  publication: '论文',
  news: '新闻',
  person: '成员',
  project: '项目',
  photo: '合照轮播',
  direction: '研究方向',
  home: '首页展示',
  page: '加入我们',
  site: '联系信息',
  group: '成员分组',
  venue: '会刊目录',
};
const primary: ContentKind[] = ['news', 'publication', 'person', 'project', 'direction', 'home'];
const singleton = (kind: ContentKind) => ['home', 'page', 'site'].includes(kind);
const typeForRoute = computed<ContentKind>(() =>
  route.path.startsWith('/publications')
    ? 'publication'
    : route.path.startsWith('/people')
      ? 'person'
      : route.path.startsWith('/projects')
        ? 'project'
        : route.path.startsWith('/research')
          ? 'direction'
          : route.path === '/'
            ? 'home'
            : 'news',
);
const library = computed(() =>
  store.records
    .filter(
      (r) =>
        r.kind === libraryKind.value &&
        r.deleted === trash.value &&
        (!query.value ||
          [store.title(r), r.data.authors, r.data.year]
            .join(' ')
            .toLowerCase()
            .includes(query.value.toLowerCase())),
    )
    .sort((a, b) => {
      const dateKey =
        libraryKind.value === 'news' ? 'date' : libraryKind.value === 'publication' ? 'year' : '';
      return (
        (dateKey ? String(b.data[dateKey]).localeCompare(String(a.data[dateKey])) : 0) ||
        a.order - b.order ||
        a.id.localeCompare(b.id)
      );
    }),
);
const publishRecords = computed(() =>
  store.unpublished.filter((r) => publishKeys.value.includes(recordKey(r))),
);
const hasInline = ref(false);
let toast: ReturnType<typeof setTimeout> | undefined;
function message(text: string) {
  notice.value = text;
  clearTimeout(toast);
  toast = setTimeout(() => (notice.value = ''), 5000);
}
async function run(action: () => Promise<void>) {
  error.value = '';
  try {
    await action();
  } catch (e) {
    error.value = errorMessage(e);
  }
}
function finish() {
  stopInline();
  hasInline.value = false;
}
async function login() {
  authBusy.value = true;
  await run(async () => {
    await store.login(username.value, password.value);
    password.value = '';
    message('已进入页面编辑模式');
  });
  authBusy.value = false;
}
function resolveField(record: EditRecord, field?: string) {
  if (!field) return undefined;
  const localized = field + '_' + locale.value;
  return store.schemas[record.kind].some((f) => f.name === localized) ? localized : field;
}
function select(target: EditTarget, inline = false) {
  finish();
  const record = store.find(target.kind, target.id);
  if (!record) return;
  const field = resolveField(record, target.field);
  selection.value = { ...target, field };
  const spec = store.schemas[record.kind]?.find((f) => f.name === field);
  if (inline && spec?.type === 'asset') {
    drawer.value = null;
    mediaTarget.value = { record, field: field! };
    return;
  }
  if (inline && target.element && spec && ['text', 'textarea', 'rich'].includes(spec.type)) {
    drawer.value = null;
    hasInline.value = true;
    startInline(target.element, record, field!, store);
    return;
  }
  drawer.value = 'item';
  nextTick(() => {
    if (field)
      document
        .querySelector<HTMLElement>(`.ve-panel [data-field="${field}"]`)
        ?.scrollIntoView({ block: 'nearest' });
  });
}
function capture(event: MouseEvent) {
  if (!canvasEditing.value || store.busy) return;
  const element = event.target as HTMLElement;
  if (element.closest('.ve-ui') || element.closest('.ve-inline-active')) return;
  if (element.closest('summary')) {
    finish();
    return;
  }
  const target = element.closest<HTMLElement>('[data-edit-kind][data-edit-id]');
  if (!target) {
    finish();
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  select(
    {
      kind: target.dataset.editKind as ContentKind,
      id: target.dataset.editId!,
      field: target.dataset.editField,
      element: target,
    },
    true,
  );
}
function keyboard(event: KeyboardEvent) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's' && store.user) {
    event.preventDefault();
    void save();
  }
  if (event.key === 'Escape' && hasInline.value) {
    finish();
  }
}
function leave(event: BeforeUnloadEvent) {
  if (store.dirty.size) {
    event.preventDefault();
    event.returnValue = '';
  }
}
function openLibrary(kind: ContentKind = typeForRoute.value) {
  finish();
  libraryKind.value =
    primary.includes(kind) || ['group', 'venue'].includes(kind) ? kind : typeForRoute.value;
  query.value = '';
  trash.value = false;
  drawer.value = 'library';
}
function mediaAspectFor(record: EditRecord) {
  if (record.kind === 'photo') return 1.85;
  if (record.kind !== 'person') return undefined;
  return 1;
}
function create(kind: ContentKind) {
  finish();
  const record = store.create(kind);
  selection.value = { kind, id: record.id };
  drawer.value = 'item';
  message(`新增${names[kind]}草稿，填写后即可在页面中预览`);
}
function openRecord(record: EditRecord) {
  selection.value = { kind: record.kind, id: record.id };
  drawer.value = 'item';
}
function returnToLibrary() {
  if (selected.value?.kind === 'photo') {
    finish();
    drawer.value = null;
    mediaCategory.value = 'group-photo';
    mediaManager.value = true;
  } else if (selected.value && singleton(selected.value.kind) && selected.value.kind !== 'home') {
    finish();
    drawer.value = null;
  } else if (selected.value) openLibrary(selected.value.kind);
}
function focusField(record: EditRecord, field?: string) {
  const language = field?.endsWith('_zh') ? 'zh' : field?.endsWith('_en') ? 'en' : null;
  if (language) {
    preferences.setLocale(language);
    preferences.selectedLanguage = language;
  }
  select({ kind: record.kind, id: record.id, field });
}
function inspectChange(record: EditRecord, change: FieldChange) {
  finish();
  showChanges.value = false;
  focusField(record, change.field);
}
function receiveMessage(event: MessageEvent) {
  if (
    !embedded ||
    event.origin !== location.origin ||
    event.source !== window.parent ||
    !store.user
  )
    return;
  const payload = event.data;
  if (!payload || payload.type !== 'litong-editor-locate' || typeof payload.id !== 'string') return;
  if (!store.kinds.some((kind) => kind.key === payload.kind)) return;
  const record = store.find(payload.kind, payload.id);
  if (!record) {
    message('此条目已不存在，可在内容库中查看其他内容');
    return;
  }
  const field =
    store.schemas[record.kind].some((candidate) => candidate.name === payload.field) ||
    payload.field === '$order'
      ? payload.field
      : undefined;
  finish();
  showChanges.value = false;
  showPublish.value = false;
  showPreview.value = false;
  history.value = null;
  void run(async () => {
    if (!record.deleted) {
      await router.push(localHref(targetPath(record)));
      setTimeout(() => {
        document
          .querySelector<HTMLElement>(
            `[data-edit-kind="${record.kind}"][data-edit-id="${CSS.escape(record.id)}"]`,
          )
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 350);
    }
    focusField(record, field);
  });
}
function undoChange(record: EditRecord, change: FieldChange) {
  finish();
  store.restoreField(record, change);
  formEpoch.value++;
  message(
    change.stage === 'unsaved' ? '已撤销这个字段的未保存修改' : '已恢复为线上值，保存草稿后生效',
  );
}
function duplicate(record: EditRecord) {
  const next = store.create(record.kind);
  next.data = JSON.parse(JSON.stringify(record.data));
  if (next.data.slug) next.data.slug = String(next.data.slug) + '-copy-' + next.id.slice(0, 4);
  store.paint(next);
  openRecord(next);
  message('已复制为新草稿，请修改名称和内容');
}
function targetPath(record: EditRecord) {
  return record.kind === 'project'
    ? '/projects/' + record.data.slug + '/'
    : record.kind === 'publication'
      ? '/publications/' + record.id + '/'
      : record.kind === 'person' || record.kind === 'photo' || record.kind === 'group'
        ? '/people/'
        : record.kind === 'venue'
          ? '/publications/'
          : record.kind === 'direction'
            ? '/research/#' + record.id
            : record.kind === 'home'
              ? '/'
              : record.kind === 'page' || record.kind === 'site'
                ? '/join/'
                : '/news/';
}
function locate(record: EditRecord) {
  finish();
  drawer.value = null;
  void router.push(localHref(targetPath(record))).then(() =>
    setTimeout(() => {
      const element = document.querySelector<HTMLElement>(
        `[data-edit-kind="${record.kind}"][data-edit-id="${record.id}"]`,
      );
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 350),
  );
}
async function save() {
  finish();
  if (!store.pending.length) {
    message('当前修改已保存为草稿');
    return;
  }
  await run(async () => {
    await store.save('draft');
    message('草稿已保存，公开官网保持原来的内容');
  });
}
function publishReview() {
  finish();
  publishKeys.value = store.unpublished
    .filter((r) => store.touched.has(recordKey(r)))
    .map(recordKey);
  showPublish.value = true;
}
async function publish() {
  await run(async () => {
    await store.save('publish', publishRecords.value);
    showPublish.value = false;
    message('发布成功，访客刷新页面即可看到更新');
  });
}
function reset(record: EditRecord) {
  finish();
  confirm.value = {
    title: '撤销未保存的修改',
    body: `“${store.title(record)}”将恢复到最近保存的状态。其他条目的修改会保留。`,
    action: () => {
      store.discard(record);
      formEpoch.value++;
      if (!store.find(record.kind, record.id)) drawer.value = 'library';
      message('已撤销该条目的本次修改');
    },
  };
}
function remove(record: EditRecord, action = 'trash') {
  finish();
  confirm.value = {
    title: action === 'restore' ? '恢复草稿' : action === 'unpublish' ? '下线内容' : '移入回收站',
    body:
      action === 'restore'
        ? '恢复后需要重新发布，才会显示在官网。'
        : `“${store.title(record)}”将从公开官网移除。历史记录会保留。`,
    action: () =>
      run(async () => {
        await store.action(record, action);
        drawer.value = 'library';
        message('操作完成');
      }),
  };
}
async function openHistory(record: EditRecord) {
  finish();
  await run(async () => {
    const { data } = await api.get<{ versions: HistoryVersion[] }>(
      `editor/items/${record.kind}/${record.id}/history/`,
    );
    history.value = data.versions;
  });
}
async function restoreVersion(version: HistoryVersion) {
  if (!selected.value) return;
  await run(async () => {
    await store.action(selected.value!, 'revision', version.id);
    history.value = null;
    formEpoch.value++;
    message('历史版本已恢复为草稿，确认后再发布');
  });
}
async function exit() {
  finish();
  if (store.dirty.size) {
    confirm.value = {
      title: '离开编辑模式',
      body: '有未保存的修改。离开后这些修改将丢失；已保存的草稿会保留。',
      action: () => {
        window.removeEventListener('beforeunload', leave);
        location.href = route.path;
      },
    };
  } else location.href = route.path;
}
function reload() {
  finish();
  confirm.value = {
    title: '重新加载最新内容',
    body: '当前未保存的修改将丢失。若发生编辑冲突，请先复制需要保留的文字。',
    action: () => {
      window.removeEventListener('beforeunload', leave);
      location.reload();
    },
  };
}
watch(
  [() => store.user, inspect, () => store.busy, showPreview],
  () => {
    canvasEditing.value = Boolean(store.user) && inspect.value && !store.busy && !showPreview.value;
    document.body.classList.toggle('ve-editing', canvasEditing.value);
    document.body.classList.toggle('ve-session', Boolean(store.user));
  },
  { immediate: true },
);
watch(
  () => route.path,
  () => {
    finish();
    if (drawer.value === 'library') libraryKind.value = typeForRoute.value;
  },
);
watch(
  [() => store.dirty.size, () => store.unpublished.length, () => store.ready],
  () => {
    if (embedded && store.ready)
      window.parent.postMessage(
        {
          type: 'litong-editor-state',
          dirtyCount: store.dirty.size,
          pendingCount: store.unpublished.length,
        },
        window.location.origin,
      );
  },
  { immediate: true },
);
onMounted(async () => {
  document.addEventListener('click', capture, true);
  document.addEventListener('keydown', keyboard);
  window.addEventListener('beforeunload', leave);
  window.addEventListener('message', receiveMessage);
  await run(() => store.initialize());
});
onBeforeUnmount(() => {
  finish();
  document.removeEventListener('click', capture, true);
  document.removeEventListener('keydown', keyboard);
  window.removeEventListener('beforeunload', leave);
  window.removeEventListener('message', receiveMessage);
  document.body.classList.remove('ve-editing', 've-session');
  canvasEditing.value = false;
  clearTimeout(toast);
});
</script>
<template>
  <Teleport to="body">
    <EditorDialog v-if="store.ready && !store.user" title="登录页面编辑" @close="exit">
      <div class="ve-login-brand">
        <img src="/icons/litonglab-logo-long.png" alt="LitongLab" />
        <p>维护实验室的最新进展</p>
      </div>
      <form class="ve-login-form" @submit.prevent="login">
        <label>用户名<input v-model="username" autocomplete="username" required autofocus /></label
        ><label
          >密码<input v-model="password" type="password" autocomplete="current-password" required
        /></label>
        <p v-if="error" class="ve-error" role="alert">{{ error }}</p>
        <button class="ve-button ve-primary ve-wide" :disabled="authBusy">
          {{ authBusy ? '正在登录…' : '登录并开始编辑' }}
          <UiIcon v-if="!authBusy" name="arrow-right" />
        </button>
        <p class="ve-muted">账号由实验室管理者分配。</p>
      </form>
    </EditorDialog>
    <div v-if="!store.ready" class="ve-ui ve-toast" role="status">
      {{ error || '正在准备页面编辑…' }}
    </div>
    <template v-if="store.user">
      <div v-if="notice" class="ve-ui ve-toast" role="status">{{ notice }}</div>
      <div v-if="error" class="ve-ui ve-error-banner" role="alert">
        <span>{{ error }}</span
        ><button @click="reload">重新加载</button
        ><button aria-label="关闭错误提示" @click="error = ''">×</button>
      </div>
      <div v-if="hasInline && selected" class="ve-ui ve-inline-tools">
        <span>{{ names[selected.kind] }} · {{ locale === 'zh' ? '中文' : 'English' }}</span>
        <template v-if="richEditor"
          ><button @click="richEditor.chain().focus().toggleBold().run()"><b>B</b></button
          ><button @click="richEditor.chain().focus().toggleItalic().run()"><i>I</i></button
          ><button @click="richEditor.chain().focus().toggleHeading({ level: 2 }).run()">
            标题</button
          ><button @click="richEditor.chain().focus().toggleBulletList().run()">列表</button
          ><button @click="richEditor.chain().focus().undo().run()">撤销</button></template
        >
        <button
          @click="
            finish();
            drawer = 'item';
          "
        >
          更多信息 <UiIcon name="arrow-up-right" /></button
        ><button class="ve-primary" @click="finish">完成编辑</button>
      </div>
      <nav class="ve-ui ve-bar" aria-label="网站编辑工具栏">
        <div class="ve-workspace">
          <span class="ve-brand-dot"></span><strong>网页编辑</strong>
          <span class="ve-status">{{
            store.dirty.size ? store.dirty.size + ' 项未保存' : '草稿已同步'
          }}</span>
        </div>
        <div class="ve-bar-divider"></div>
        <button
          :aria-pressed="inspect"
          @click="
            finish();
            inspect = !inspect;
            drawer = null;
          "
        >
          {{ inspect ? '编辑中' : '浏览中' }}
        </button>
        <button @click="openLibrary()">内容库</button>
        <button
          @click="
            finish();
            showChanges = true;
          "
        >
          变更清单 <span v-if="store.changeList.length">{{ store.changeList.length }}</span>
        </button>
        <button
          @click="
            finish();
            showPreview = true;
          "
        >
          预览
        </button>
        <div class="ve-bar-end">
          <button :disabled="store.busy || !store.dirty.size" @click="save">
            {{ store.busy ? '处理中…' : '保存草稿' }}</button
          ><button
            v-if="store.user.canPublish"
            class="ve-primary"
            :disabled="store.busy || !store.unpublished.length"
            @click="publishReview"
          >
            发布 <span v-if="store.unpublished.length">{{ store.unpublished.length }}</span>
          </button>
          <a v-if="!embedded" class="ve-management-link" href="/admin/" target="_top"
            >管理中心 <UiIcon name="arrow-up-right"
          /></a>
        </div>
      </nav>
      <aside v-if="drawer" class="ve-ui ve-panel" aria-label="内容侧栏" :inert="store.busy">
        <header class="ve-panel-heading">
          <div>
            <span>{{ drawer === 'library' ? '日常维护' : names[selected?.kind || 'news'] }}</span>
            <h2>
              {{ drawer === 'library' ? '内容库' : selected ? store.title(selected) : '编辑条目' }}
            </h2>
          </div>
          <button
            class="ve-icon"
            aria-label="关闭内容侧栏"
            @click="
              finish();
              drawer = null;
            "
          >
            ×
          </button>
        </header>
        <template v-if="drawer === 'library'">
          <div class="ve-library-tabs">
            <button
              v-for="kind in primary"
              :key="kind"
              :aria-pressed="libraryKind === kind"
              @click="
                libraryKind = kind;
                query = '';
                trash = false;
              "
            >
              {{ names[kind] }}
            </button>
            <button
              @click="
                finish();
                drawer = null;
                mediaCategory = undefined;
                mediaManager = true;
              "
            >
              素材库
            </button>
          </div>
          <div class="ve-library-controls">
            <input
              v-model="query"
              aria-label="搜索内容"
              placeholder="搜索名称、作者或年份…"
            /><button
              v-if="!singleton(libraryKind)"
              class="ve-button ve-primary"
              @click="create(libraryKind)"
            >
              ＋ 新增
            </button>
          </div>
          <div class="ve-library-sub">
            <span>{{ library.length }} 个{{ names[libraryKind] }}</span
            ><button v-if="!singleton(libraryKind)" :aria-pressed="trash" @click="trash = !trash">
              {{ trash ? '查看正常内容' : '回收站' }}
            </button>
          </div>
          <div class="ve-record-list">
            <button
              v-for="record in library"
              :key="record.id"
              class="ve-record-card"
              @click="openRecord(record)"
            >
              <img
                v-if="record.data.image"
                :src="String(record.data.image)"
                alt=""
                loading="lazy"
              />
              <div>
                <strong>{{ store.title(record) }}</strong
                ><small
                  ><span
                    :class="{
                      've-dot-draft': record.hasDraft || store.dirty.has(recordKey(record)),
                    }"
                    class="ve-state-dot"
                  ></span
                  >{{ store.dirty.has(recordKey(record)) ? '未保存' : record.state
                  }}<span v-if="record.data.year"> · {{ record.data.year }}</span></small
                >
              </div>
              <span><UiIcon name="arrow-up-right" /></span>
            </button>
            <p v-if="!library.length" class="ve-empty">
              {{ trash ? '回收站是空的' : '没有找到内容，试试其他关键词或新建条目。' }}
            </p>
          </div>
          <footer class="ve-library-footer">
            <span>配套目录</span
            ><button
              @click="
                libraryKind = 'group';
                query = '';
                trash = false;
              "
            >
              成员分组</button
            ><button
              @click="
                libraryKind = 'venue';
                query = '';
                trash = false;
              "
            >
              会议与期刊
            </button>
          </footer>
        </template>
        <template v-else-if="selected">
          <div class="ve-item-context">
            <button @click="returnToLibrary">
              <UiIcon name="arrow-left" />
              {{
                selected.kind === 'photo'
                  ? '返回合照照片'
                  : singleton(selected.kind) && selected.kind !== 'home'
                    ? '返回页面'
                    : '返回列表'
              }}</button
            ><span>{{ store.dirty.has(recordKey(selected)) ? '未保存' : selected.state }}</span>
          </div>
          <div v-if="selected.deleted" class="ve-empty">
            <p>此条目在回收站中。</p>
            <button class="ve-button ve-primary" @click="remove(selected, 'restore')">
              恢复为草稿
            </button>
          </div>
          <div v-else class="ve-panel-scroll">
            <EditorFields
              :key="selected.id + String(selected.version) + formEpoch"
              :record="selected"
              :focus-field="selectedField"
            />
            <div class="ve-item-actions">
              <button @click="locate(selected)">
                在页面中查看 <UiIcon name="arrow-up-right" /></button
              ><button v-if="!singleton(selected.kind)" @click="duplicate(selected)">
                复制为新条目</button
              ><button
                v-if="selected.version !== null && !singleton(selected.kind)"
                @click="openHistory(selected)"
              >
                历史版本</button
              ><button v-if="store.dirty.has(recordKey(selected))" @click="reset(selected)">
                撤销本次修改</button
              ><button
                v-if="selected.published && !singleton(selected.kind)"
                @click="remove(selected, 'unpublish')"
              >
                下线</button
              ><button
                v-if="selected.version !== null && !singleton(selected.kind)"
                class="ve-danger-text"
                @click="remove(selected)"
              >
                移入回收站
              </button>
            </div>
          </div>
          <footer v-if="!selected.deleted" class="ve-panel-footer">
            <button class="ve-button" :disabled="store.busy || !store.dirty.size" @click="save">
              保存草稿</button
            ><button
              class="ve-button ve-primary"
              :disabled="store.busy || !store.unpublished.length"
              @click="publishReview"
            >
              检查并发布 <UiIcon name="arrow-right" />
            </button>
          </footer>
        </template>
      </aside>
    </template>
  </Teleport>
  <MediaPicker
    v-if="mediaTarget || mediaManager"
    :manage="mediaManager"
    :aspect="mediaTarget ? mediaAspectFor(mediaTarget.record) : undefined"
    :initial-category="
      mediaTarget ? categoryForRecord(mediaTarget.record.kind, mediaTarget.field) : mediaCategory
    "
    @close="
      mediaTarget = null;
      mediaManager = false;
    "
    @select="
      (url) => {
        store.update(mediaTarget!.record, mediaTarget!.field, url);
        if (
          mediaTarget!.record.kind === 'person' &&
          mediaTarget!.field === 'image' &&
          url !== '/images/person-placeholder.svg'
        )
          store.update(mediaTarget!.record, 'placeholder', false);
        mediaTarget = null;
        message('已替换素材，发布后对访客生效');
      }
    "
  />
  <EditorDialog v-if="showChanges" title="变更清单" wide @close="showChanges = false">
    <p class="ve-muted">
      未保存：与最近保存的草稿比较。已保存未发布：与公开官网比较。恢复线上值后，需要保存草稿；发布后才会影响官网。
    </p>
    <p v-if="!store.changeList.length" class="ve-empty">目前没有内容变更。</p>
    <article
      v-for="entry in store.changeList"
      :key="recordKey(entry.record)"
      class="ve-change-entry"
    >
      <header>
        <div>
          <span class="ve-muted">{{
            names[entry.record.kind] ||
            store.kinds.find((kind) => kind.key === entry.record.kind)?.label
          }}</span>
          <h3>{{ store.title(entry.record) }}</h3>
        </div>
        <button
          @click="
            showChanges = false;
            openRecord(entry.record);
          "
        >
          编辑条目 <UiIcon name="arrow-up-right" />
        </button>
      </header>
      <section v-for="stage in ['unsaved', 'saved'] as const" :key="stage">
        <template v-if="entry[stage].length">
          <h4>{{ stage === 'unsaved' ? '未保存的修改' : '已保存 · 尚未发布' }}</h4>
          <p v-if="stage === 'saved' && !entry.record.published" class="ve-muted">
            新内容，官网尚未显示。
          </p>
          <div v-for="change in entry[stage]" :key="change.field" class="ve-change-field">
            <div class="ve-change-heading">
              <strong>{{ change.label }}</strong>
              <div>
                <button @click="inspectChange(entry.record, change)">定位字段</button>
                <button @click="undoChange(entry.record, change)">
                  {{
                    stage === 'unsaved'
                      ? '撤销此修改'
                      : entry.record.published
                        ? '恢复线上值'
                        : '清空此字段'
                  }}
                </button>
              </div>
            </div>
            <div class="ve-change-values">
              <div>
                <span>{{ stage === 'unsaved' ? '上次保存的草稿' : '当前官网' }}</span>
                <p>{{ store.formatValue(entry.record, change.field, change.before) }}</p>
              </div>
              <div>
                <span>{{ stage === 'unsaved' ? '当前编辑' : '已保存草稿' }}</span>
                <p>{{ store.formatValue(entry.record, change.field, change.after) }}</p>
              </div>
            </div>
          </div>
        </template>
      </section>
    </article>
    <footer class="ve-dialog-footer">
      <button class="ve-button" @click="showChanges = false">继续编辑</button
      ><button
        class="ve-button ve-primary"
        :disabled="!store.dirty.size || store.busy"
        @click="save"
      >
        保存草稿
      </button>
    </footer>
  </EditorDialog>
  <PreviewDialog v-if="showPreview" @close="showPreview = false" />
  <EditorDialog v-if="showPublish" title="发布前确认" @close="!store.busy && (showPublish = false)"
    ><p class="ve-muted">仅发布选中的条目。其余草稿会继续保留。</p>
    <button
      class="ve-button ve-wide"
      @click="
        showPublish = false;
        showChanges = true;
      "
    >
      查看字段变更及修改前后 <UiIcon name="arrow-right" />
    </button>
    <div class="ve-publish-list">
      <label v-for="record in store.unpublished" :key="recordKey(record)"
        ><input v-model="publishKeys" type="checkbox" :value="recordKey(record)" />
        <div>
          <strong>{{ store.title(record) }}</strong
          ><small
            >{{ names[record.kind] }} ·
            {{ store.dirty.has(recordKey(record)) ? '包含未保存的修改' : '已保存草稿' }}</small
          >
        </div></label
      >
    </div>
    <p v-if="error" class="ve-error" role="alert">{{ error }}</p>
    <footer class="ve-dialog-footer">
      <button class="ve-button" :disabled="store.busy" @click="showPublish = false">继续编辑</button
      ><button
        class="ve-button ve-primary"
        :disabled="!publishRecords.length || store.busy"
        @click="publish"
      >
        {{ store.busy ? '正在发布…' : '确认发布 ' + publishRecords.length + ' 项' }}
      </button>
    </footer></EditorDialog
  >
  <EditorDialog v-if="history" title="历史版本" @close="history = null"
    ><p class="ve-muted">恢复为草稿，确认无误后再发布。</p>
    <div v-for="version in history" :key="version.id" class="ve-history">
      <button
        class="ve-history-title"
        @click="historyOpen = historyOpen === version.id ? null : version.id"
      >
        <strong>{{ version.action }}</strong
        ><span>{{ new Date(version.date).toLocaleString('zh-CN') }} · {{ version.actor }}</span>
      </button>
      <div v-if="historyOpen === version.id">
        <dl>
          <template v-for="field in store.schemas[selected!.kind]" :key="field.name"
            ><template v-if="version.data[field.name]"
              ><dt>{{ field.label }}</dt>
              <dd>
                {{
                  typeof version.data[field.name] === 'object'
                    ? JSON.stringify(version.data[field.name])
                    : version.data[field.name]
                }}
              </dd></template
            ></template
          >
        </dl>
        <button class="ve-button" @click="restoreVersion(version)">恢复此版本为草稿</button>
      </div>
    </div>
    <p v-if="error" class="ve-error">{{ error }}</p></EditorDialog
  >
  <EditorDialog v-if="confirm" :title="confirm.title" @close="confirm = null"
    ><p class="ve-confirm-body">{{ confirm.body }}</p>
    <footer class="ve-dialog-footer">
      <button class="ve-button" @click="confirm = null">取消</button
      ><button class="ve-button ve-primary" @click="confirmAction">确认</button>
    </footer></EditorDialog
  >
</template>
