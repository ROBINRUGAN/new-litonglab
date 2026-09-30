<!-- designed by mew -->
<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import { errorMessage, useEditorStore } from '../editor/store';
import type { ContentKind } from '../types/content';
import EditorDialog from '../editor/EditorDialog.vue';
import UiIcon from '../components/UiIcon.vue';
import '../editor/editor.css';
import './management.css';

const PasswordPanel = defineAsyncComponent(() => import('./PasswordPanel.vue'));
const AccountsPanel = defineAsyncComponent(() => import('./AccountsPanel.vue'));
const BackupPanel = defineAsyncComponent(() => import('./BackupPanel.vue'));
const HistoryPanel = defineAsyncComponent(() => import('./HistoryPanel.vue'));
const store = useEditorStore();
const tabs = [
  { id: 'website', label: '网页编辑' },
  { id: 'password', label: '修改密码' },
  { id: 'accounts', label: '创建账户' },
  { id: 'backup', label: '备份还原' },
  { id: 'history', label: '编辑记录' },
] as const;
type Tab = (typeof tabs)[number]['id'];
const active = ref<Tab>('website');
const visited = ref(new Set<Tab>(['website']));
const initializing = ref(true),
  busy = ref(false),
  error = ref('');
const username = ref(''),
  password = ref('');
const frame = ref<HTMLIFrameElement>();
const editorReady = ref(false);
let pendingLocation: { kind: ContentKind; id: string; field?: string } | undefined;
function sendLocation() {
  if (!pendingLocation || !editorReady.value) return;
  frame.value?.contentWindow?.postMessage(
    { type: 'litong-editor-locate', ...pendingLocation },
    location.origin,
  );
  pendingLocation = undefined;
}
function locate(target: { kind: ContentKind; id: string; field?: string }) {
  pendingLocation = target;
  selectTab('website');
  sendLocation();
}
const frameVersion = ref(0),
  dirtyCount = ref(0),
  confirmLogout = ref(false);

function selectTab(tab: Tab) {
  visited.value.add(tab);
  active.value = tab;
}
function tabKey(event: KeyboardEvent, index: number) {
  let next = index;
  if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
  else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = tabs.length - 1;
  else return;
  event.preventDefault();
  selectTab(tabs[next]!.id);
  document.getElementById(`manage-tab-${tabs[next]!.id}`)?.focus();
}
async function initialize() {
  initializing.value = true;
  error.value = '';
  try {
    await store.initialize();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    initializing.value = false;
  }
}
async function login() {
  busy.value = true;
  error.value = '';
  try {
    await store.login(username.value, password.value);
    password.value = '';
    selectTab('website');
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function logout() {
  busy.value = true;
  error.value = '';
  try {
    await store.logout();
    dirtyCount.value = 0;
    confirmLogout.value = false;
    visited.value = new Set(['website']);
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
function editorState(event: MessageEvent) {
  if (event.origin !== location.origin || event.source !== frame.value?.contentWindow) return;
  if (event.data?.type === 'litong-editor-state') {
    editorReady.value = true;
    sendLocation();
    const count = Number(event.data.dirtyCount);
    if (Number.isFinite(count) && count >= 0) dirtyCount.value = count;
  }
}
function restored() {
  dirtyCount.value = 0;
  editorReady.value = false;
  frameVersion.value++;
}
onMounted(() => {
  addEventListener('message', editorState);
  void initialize();
});
onBeforeUnmount(() => removeEventListener('message', editorState));
</script>

<template>
  <div class="mg-app">
    <div v-if="initializing" class="mg-loading" role="status">
      <img src="/icons/litonglab-logo-long.png" alt="LitongLab" />
      <p>正在打开管理中心…</p>
    </div>
    <main v-else-if="!store.user" class="mg-login">
      <div class="mg-login-photo">
        <img src="/assets/campus-gate.jpg" alt="中国人民大学校园" />
        <div>
          <span>LITONGLAB</span>
          <h1>记录研究，<br />也记录我们。</h1>
          <p>中国人民大学 · 计算机网络研究小组</p>
        </div>
      </div>
      <section class="mg-login-form-wrap">
        <a href="/" class="mg-login-logo"
          ><img src="/icons/litonglab-logo-long.png" alt="LitongLab"
        /></a>
        <div class="mg-login-intro">
          <span class="mg-eyebrow">内容管理</span>
          <h2>欢迎回来</h2>
          <p>登录后，维护实验室的最新进展。</p>
        </div>
        <form class="mg-form" @submit.prevent="login">
          <label for="manage-username"
            >用户名<input
              id="manage-username"
              v-model="username"
              autocomplete="username"
              required
              autofocus
          /></label>
          <label for="manage-password"
            >密码<input
              id="manage-password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              required
          /></label>
          <p v-if="error" class="mg-alert mg-alert-error" role="alert">{{ error }}</p>
          <button class="mg-button mg-primary" :disabled="busy || !store.csrfToken">
            {{ busy ? '正在登录…' : '登录管理中心' }} <UiIcon v-if="!busy" name="arrow-right" />
          </button>
          <button v-if="!store.csrfToken" type="button" class="mg-button" @click="initialize">
            重新连接
          </button>
        </form>
        <p class="mg-login-note">账号由实验室管理者分配。</p>
        <a href="/" class="mg-back"><UiIcon name="arrow-left" /> 返回官网</a>
      </section>
    </main>
    <template v-else>
      <header class="mg-header">
        <a class="mg-brand" href="/" target="_blank" rel="noopener"
          ><img src="/icons/litonglab-logo-long.png" alt="LitongLab" /><span>内容管理</span></a
        >
        <nav class="mg-tabs" role="tablist" aria-label="管理功能">
          <button
            v-for="(tab, index) in tabs"
            :id="`manage-tab-${tab.id}`"
            :key="tab.id"
            role="tab"
            :aria-selected="active === tab.id"
            :aria-controls="`manage-panel-${tab.id}`"
            :tabindex="active === tab.id ? 0 : -1"
            @click="selectTab(tab.id)"
            @keydown="tabKey($event, index)"
          >
            {{ tab.label }}
          </button>
        </nav>
        <div class="mg-user">
          <span
            >{{ store.user.name
            }}<small>{{ store.user.manager ? '管理员' : '编辑人员' }}</small></span
          ><button
            class="mg-text-button"
            :disabled="busy"
            @click="dirtyCount ? (confirmLogout = true) : logout()"
          >
            退出
          </button>
        </div>
      </header>
      <p v-if="error" class="mg-global-error mg-alert mg-alert-error" role="alert">{{ error }}</p>
      <section
        id="manage-panel-website"
        v-show="active === 'website'"
        class="mg-canvas"
        role="tabpanel"
        aria-labelledby="manage-tab-website"
      >
        <iframe
          ref="frame"
          :key="frameVersion"
          src="/news/?edit=1&embedded=1"
          title="官网页面编辑"
          class="mg-editor-frame"
        ></iframe>
      </section>
      <section
        id="manage-panel-password"
        v-if="visited.has('password')"
        v-show="active === 'password'"
        class="mg-page"
        role="tabpanel"
        aria-labelledby="manage-tab-password"
      >
        <PasswordPanel />
      </section>
      <section
        id="manage-panel-accounts"
        v-if="visited.has('accounts')"
        v-show="active === 'accounts'"
        class="mg-page"
        role="tabpanel"
        aria-labelledby="manage-tab-accounts"
      >
        <AccountsPanel :manager="store.user.manager" />
      </section>
      <section
        id="manage-panel-backup"
        v-if="visited.has('backup')"
        v-show="active === 'backup'"
        class="mg-page"
        role="tabpanel"
        aria-labelledby="manage-tab-backup"
      >
        <BackupPanel :dirty-count="dirtyCount" @restored="restored" @edit="selectTab('website')" />
      </section>
      <section
        id="manage-panel-history"
        v-if="visited.has('history')"
        v-show="active === 'history'"
        class="mg-page"
        role="tabpanel"
        aria-labelledby="manage-tab-history"
      >
        <HistoryPanel :active="active === 'history'" @locate="locate" />
      </section>
    </template>
    <EditorDialog v-if="confirmLogout" title="退出管理中心" @close="confirmLogout = false">
      <p class="ve-confirm-body">
        网页编辑中还有 {{ dirtyCount }} 项未保存修改。退出后这些修改会丢失。
      </p>
      <div class="ve-dialog-footer">
        <button
          class="ve-button"
          @click="
            confirmLogout = false;
            selectTab('website');
          "
        >
          返回继续编辑</button
        ><button class="ve-button ve-primary" :disabled="busy" @click="logout">
          放弃修改并退出
        </button>
      </div>
    </EditorDialog>
  </div>
</template>
