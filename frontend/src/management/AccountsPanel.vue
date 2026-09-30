<!-- designed by mew -->
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api/client';
import { errorMessage, useEditorStore } from '../editor/store';
import EditorDialog from '../editor/EditorDialog.vue';
import { managementPost, type ManagedUser } from './api';
const props = defineProps<{ manager: boolean }>();
const store = useEditorStore();
const editing = ref<ManagedUser | null>(null),
  deleting = ref<ManagedUser | null>(null),
  active = ref(true);
const users = ref<ManagedUser[]>([]),
  loading = ref(false),
  busy = ref(false);
const username = ref(''),
  name = ref(''),
  password = ref(''),
  confirmPassword = ref(''),
  manager = ref(false);
const error = ref(''),
  success = ref('');
function reset() {
  editing.value = null;
  username.value = name.value = password.value = confirmPassword.value = '';
  manager.value = false;
  active.value = true;
}
function edit(user: ManagedUser) {
  reset();
  error.value = '';
  success.value = '';
  editing.value = user;
  username.value = user.username;
  name.value = user.name;
  manager.value = user.manager;
  active.value = user.active;
  document.getElementById('account-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  document.getElementById('account-name')?.focus({ preventScroll: true });
}
async function load() {
  loading.value = true;
  try {
    users.value = (await api.get<{ users: ManagedUser[] }>('manage/users/')).data.users;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
async function create() {
  error.value = '';
  success.value = '';
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致。';
    return;
  }
  busy.value = true;
  try {
    const updating = editing.value;
    const payload = {
      username: username.value,
      name: name.value,
      manager: manager.value,
      ...(updating
        ? {
            active: active.value,
            ...(password.value
              ? { newPassword: password.value, confirmPassword: confirmPassword.value }
              : {}),
          }
        : { password: password.value, confirmPassword: confirmPassword.value }),
    };
    const data = await managementPost<{ user: ManagedUser; message: string; csrfToken?: string }>(
      updating ? `users/${updating.id}/` : 'users/',
      payload,
    );
    if (data.csrfToken) store.csrfToken = data.csrfToken;
    success.value = data.message;
    reset();
    if (updating?.current) await store.initialize();
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function remove() {
  if (!deleting.value) return;
  busy.value = true;
  error.value = '';
  success.value = '';
  try {
    const target = deleting.value;
    const { data } = await api.delete<{ message: string }>(`manage/users/${target.id}/`, {
      headers: { 'X-CSRFToken': store.csrfToken },
    });
    success.value = data.message;
    deleting.value = null;
    if (editing.value?.id === target.id) reset();
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
onMounted(() => {
  if (props.manager) void load();
});
</script>
<template>
  <div class="mg-page-heading">
    <span class="mg-eyebrow">团队协作</span>
    <h1>创建账户</h1>
    <p>为实验室成员分配独立账号，所有编辑人员都可以发布内容。</p>
  </div>
  <section v-if="!props.manager" class="mg-card mg-narrow">
    <h2>由管理员分配账号</h2>
    <p class="mg-muted">当前账号可以编辑和发布网站内容。新增账号请联系实验室管理员。</p>
  </section>
  <div v-else class="mg-columns">
    <section id="account-form" class="mg-card">
      <div class="mg-card-title">
        <h2>{{ editing ? '编辑团队账户' : '新增团队账户' }}</h2>
        <button v-if="editing" class="mg-text-button" :disabled="busy" @click="reset">
          取消编辑
        </button>
      </div>
      <form class="mg-form" @submit.prevent="create">
        <label for="account-name"
          >姓名<input
            id="account-name"
            v-model="name"
            autocomplete="off"
            placeholder="用于显示编辑者姓名"
            required
        /></label>
        <label for="account-username"
          >登录用户名<input
            id="account-username"
            v-model="username"
            autocomplete="off"
            placeholder="如 zhangsan"
            required
        /></label>
        <div class="mg-form-pair">
          <label for="account-password"
            >{{ editing ? '新密码（留空保留）' : '初始密码'
            }}<input
              id="account-password"
              v-model="password"
              type="password"
              autocomplete="new-password"
              minlength="12"
              :required="!editing" /></label
          ><label for="account-confirm"
            >确认密码<input
              id="account-confirm"
              v-model="confirmPassword"
              type="password"
              autocomplete="new-password"
              :required="!editing || Boolean(password)"
          /></label>
        </div>
        <label class="mg-check"
          ><input v-model="manager" type="checkbox" :disabled="editing?.current" /><span
            >设为管理员<small>可创建账户、下载备份和还原网站。</small></span
          ></label
        >
        <label v-if="editing" class="mg-check"
          ><input v-model="active" type="checkbox" :disabled="editing.current" /><span
            >允许此账户登录<small
              >取消后暂停该账户访问。当前登录账号的角色与状态不可在此更改。</small
            ></span
          ></label
        >
        <p v-if="error" class="mg-alert mg-alert-error" role="alert">{{ error }}</p>
        <p v-if="success" class="mg-alert mg-alert-success" role="status">{{ success }}</p>
        <div class="mg-form-footer">
          <button class="mg-button mg-primary" :disabled="busy">
            {{ busy ? '正在保存…' : editing ? '保存账户修改' : '创建账户' }}
          </button>
        </div>
      </form>
    </section>
    <section class="mg-card">
      <div class="mg-card-title">
        <h2>团队账户</h2>
        <span class="mg-count">{{ users.length }}</span>
      </div>
      <p v-if="loading" class="mg-muted" role="status">正在读取账户…</p>
      <ul v-else class="mg-user-list">
        <li v-for="user in users" :key="user.id">
          <span class="mg-avatar">{{ (user.name || user.username).slice(0, 1).toUpperCase() }}</span
          ><span class="mg-user-info"
            ><strong>{{ user.name || user.username }}</strong
            ><small>{{ user.username }}</small></span
          ><span class="mg-role" :class="{ 'mg-role-muted': !user.active }">{{
            !user.active ? '已停用' : user.manager ? '管理员' : '编辑人员'
          }}</span>
          <div class="mg-row-actions">
            <button
              class="mg-text-button"
              :disabled="busy"
              :aria-label="'编辑账户 ' + user.username"
              @click="edit(user)"
            >
              编辑</button
            ><button
              v-if="!user.current"
              class="mg-text-button mg-danger-text"
              :disabled="busy"
              :aria-label="'删除账户 ' + user.username"
              @click="
                deleting = user;
                error = '';
              "
            >
              删除</button
            ><span v-else class="mg-self">本人</span>
          </div>
        </li>
      </ul>
    </section>
  </div>
  <EditorDialog v-if="deleting" title="删除账户" @close="!busy && (deleting = null)"
    ><p class="ve-confirm-body">
      确认删除“{{ deleting.name }}”（{{
        deleting.username
      }}）？该账户将无法登录，已有网站内容和编辑记录会保留。
    </p>
    <p v-if="error" class="ve-error" role="alert">{{ error }}</p>
    <div class="ve-dialog-footer">
      <button class="ve-button" :disabled="busy" @click="deleting = null">取消</button
      ><button class="ve-button ve-primary" :disabled="busy" @click="remove">
        {{ busy ? '正在删除…' : '确认删除账户' }}
      </button>
    </div></EditorDialog
  >
</template>
