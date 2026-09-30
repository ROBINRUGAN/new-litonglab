<!-- designed by mew -->
<script setup lang="ts">
import { ref } from 'vue';
import { useEditorStore, errorMessage } from '../editor/store';
import { managementPost } from './api';
const store = useEditorStore();
const oldPassword = ref(''),
  newPassword = ref(''),
  confirmPassword = ref('');
const busy = ref(false),
  error = ref(''),
  success = ref('');
async function changePassword() {
  error.value = '';
  success.value = '';
  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的新密码不一致。';
    return;
  }
  busy.value = true;
  try {
    const data = await managementPost<{ message: string; csrfToken: string }>('password/', {
      oldPassword: oldPassword.value,
      newPassword: newPassword.value,
      confirmPassword: confirmPassword.value,
    });
    if (data.csrfToken) store.csrfToken = data.csrfToken;
    success.value = data.message;
    oldPassword.value = newPassword.value = confirmPassword.value = '';
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="mg-page-heading">
    <span class="mg-eyebrow">个人设置</span>
    <h1>修改密码</h1>
    <p>更新你的登录密码。</p>
  </div>
  <section class="mg-card mg-narrow">
    <form class="mg-form" @submit.prevent="changePassword">
      <label for="old-password"
        >当前密码<input
          id="old-password"
          v-model="oldPassword"
          type="password"
          autocomplete="current-password"
          required
      /></label>
      <label for="new-password"
        >新密码<input
          id="new-password"
          v-model="newPassword"
          type="password"
          autocomplete="new-password"
          minlength="12"
          required
        /><small>至少 12 位，避免使用常见密码、纯数字或用户名。</small></label
      >
      <label for="confirm-password"
        >确认新密码<input
          id="confirm-password"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          required
      /></label>
      <p v-if="error" class="mg-alert mg-alert-error" role="alert">{{ error }}</p>
      <p v-if="success" class="mg-alert mg-alert-success" role="status">{{ success }}</p>
      <div class="mg-form-footer">
        <button class="mg-button mg-primary" :disabled="busy">
          {{ busy ? '正在保存…' : '保存新密码' }}
        </button>
      </div>
    </form>
  </section>
</template>
