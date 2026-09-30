<!-- designed by mew -->
<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { api } from '../api/client';
import { errorMessage } from '../editor/store';
import EditorDialog from '../editor/EditorDialog.vue';
import UiIcon from '../components/UiIcon.vue';
import { managementPost, managementHeaders, type BackupInfo, type RestorePreview } from './api';
const props = defineProps<{ dirtyCount: number }>();
const emit = defineEmits<{ restored: []; edit: [] }>();
const info = ref<BackupInfo>(),
  preview = ref<RestorePreview>();
const file = ref<File>(),
  busy = ref<'download' | 'validate' | 'restore' | null>(null);
const error = ref(''),
  success = ref(''),
  progress = ref(0),
  safetyBackup = ref('');
const confirm = ref(false),
  acknowledged = ref(false);
const size = (bytes: number) =>
  bytes >= 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(1)} GB`
    : `${(bytes / 1024 ** 2).toFixed(1)} MB`;
const date = (value: string) => new Date(value).toLocaleString('zh-CN');
async function load() {
  try {
    info.value = (await api.get<BackupInfo>('manage/backups/')).data;
  } catch (e) {
    error.value = errorMessage(e);
  }
}
async function download() {
  busy.value = 'download';
  error.value = '';
  success.value = '';
  try {
    const response = await api.get<Blob>('manage/backups/download/', {
      responseType: 'blob',
      timeout: 120_000,
    });
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = url;
    link.download =
      /filename="?([^";]+)/.exec(String(response.headers['content-disposition'] || ''))?.[1] ||
      `litonglab-web-${new Date().toISOString().slice(0, 10)}.zip`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    success.value = '备份已生成并开始下载，请妥善保存。';
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = null;
  }
}
function selectFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0];
  preview.value = undefined;
  acknowledged.value = false;
  error.value = '';
  success.value = '';
}
async function validate() {
  if (!file.value || !info.value) return;
  error.value = '';
  success.value = '';
  preview.value = undefined;
  if (file.value.size > info.value.maxUploadBytes) {
    error.value = `文件超过 ${size(info.value.maxUploadBytes)}，请选择较小的备份。`;
    return;
  }
  busy.value = 'validate';
  progress.value = 0;
  try {
    const form = new FormData();
    form.append('file', file.value);
    preview.value = (
      await api.post<RestorePreview>('manage/restore/', form, {
        headers: managementHeaders(),
        timeout: 120_000,
        onUploadProgress: (event) => {
          progress.value = Math.round((event.progress || 0) * 100);
        },
      })
    ).data;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = null;
  }
}
async function restore() {
  if (!preview.value || !acknowledged.value || props.dirtyCount) return;
  busy.value = 'restore';
  error.value = '';
  success.value = '';
  try {
    const data = await managementPost<{ message: string; safetyBackup?: string }>('restore/', {
      token: preview.value.token,
      confirm: true,
    });
    success.value = data.message;
    safetyBackup.value = data.safetyBackup || '';
    confirm.value = false;
    preview.value = undefined;
    acknowledged.value = false;
    emit('restored');
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = null;
  }
}
onMounted(load);
</script>
<template>
  <div class="mg-page-heading">
    <span class="mg-eyebrow">内容保护</span>
    <h1>备份还原</h1>
    <p>保存网站内容和素材，在需要时恢复到之前的状态。</p>
  </div>
  <p v-if="error" class="mg-alert mg-alert-error" role="alert">{{ error }}</p>
  <p v-if="success" class="mg-alert mg-alert-success" role="status">
    {{ success
    }}<a v-if="safetyBackup" :href="safetyBackup" download
      >下载还原前的备份 <UiIcon name="arrow-up-right"
    /></a>
  </p>
  <p v-if="!info && !error" class="mg-muted" role="status">正在读取备份设置…</p>
  <section v-if="info && !info.canBackup && !info.canRestore" class="mg-card mg-narrow">
    <h2>由管理员执行备份还原</h2>
    <p class="mg-muted">
      当前账号的编辑和发布权限不受影响。需要备份或恢复网站时，请联系实验室管理员。
    </p>
  </section>
  <div v-else-if="info" class="mg-backup-grid">
    <section class="mg-card">
      <span class="mg-step">01</span>
      <h2>下载当前备份</h2>
      <p class="mg-muted">将当前网站的内容和素材保存到电脑。</p>
      <ul class="mg-scope">
        <li v-for="item in info.scope" :key="item">{{ item }}</li>
      </ul>
      <p class="mg-small-note">账号、密码和服务器配置单独保留，不随网页备份还原。</p>
      <button
        class="mg-button mg-primary"
        :disabled="Boolean(busy) || !info.canBackup"
        @click="download"
      >
        {{ busy === 'download' ? '正在准备备份…' : '下载网站备份' }}
        <UiIcon v-if="busy !== 'download'" name="arrow-down" />
      </button>
    </section>
    <section class="mg-card">
      <span class="mg-step">02</span>
      <h2>选择备份并检查</h2>
      <p class="mg-muted">选择从此页面下载的 ZIP 备份，先检查内容，再决定是否还原。</p>
      <label class="mg-upload"
        ><input
          type="file"
          accept=".zip"
          aria-label="选择备份文件"
          :disabled="Boolean(busy)"
          @change="selectFile"
        /><span class="mg-upload-icon"><UiIcon name="arrow-up" /></span
        ><strong>{{ file?.name || '选择备份文件' }}</strong
        ><small>{{
          file ? size(file.size) : `ZIP · 最大 ${size(info.maxUploadBytes)}`
        }}</small></label
      >
      <button
        class="mg-button"
        :disabled="!file || Boolean(busy) || !info.canRestore"
        @click="validate"
      >
        {{
          busy === 'validate'
            ? progress < 100
              ? `正在上传 ${progress}%…`
              : '正在校验备份…'
            : '检查备份内容'
        }}
      </button>
    </section>
    <section v-if="preview" class="mg-card mg-restore-summary">
      <span class="mg-step">03</span>
      <div class="mg-card-title">
        <div>
          <h2>确认要还原的内容</h2>
          <p class="mg-muted">备份时间：{{ date(preview.summary.createdAt) }}</p>
        </div>
        <span class="mg-role">校验通过</span>
      </div>
      <div class="mg-backup-stats">
        <div>
          <strong>{{ preview.summary.contentCount }}</strong
          ><span>内容条目</span>
        </div>
        <div>
          <strong>{{ preview.summary.mediaCount }}</strong
          ><span>素材文件</span>
        </div>
        <div>
          <strong>{{ preview.summary.revisionCount }}</strong
          ><span>历史版本</span>
        </div>
        <div>
          <strong>{{ size(preview.summary.totalBytes) }}</strong
          ><span>还原大小</span>
        </div>
      </div>
      <div class="mg-backup-counts">
        <span v-for="item in preview.summary.counts" :key="item.kind"
          >{{ item.label }} <b>{{ item.count }}</b></span
        >
      </div>
      <p class="mg-small-note">
        还原将替换当前网站内容，保留备份中的发布状态。系统会先自动备份当前网站，账号和密码保持不变。
      </p>
      <p v-if="dirtyCount" class="mg-alert">
        网页编辑中还有 {{ dirtyCount }} 项未保存修改。请先保存或撤销，再还原。<button
          class="mg-text-button"
          @click="emit('edit')"
        >
          返回网页编辑 <UiIcon name="arrow-right" />
        </button>
      </p>
      <div class="mg-form-footer">
        <span class="mg-muted">检查有效期至 {{ date(preview.expiresAt) }}</span
        ><button
          class="mg-button mg-primary"
          :disabled="Boolean(busy) || dirtyCount > 0"
          @click="
            confirm = true;
            acknowledged = false;
          "
        >
          还原这个备份 <UiIcon name="arrow-right" />
        </button>
      </div>
    </section>
  </div>
  <EditorDialog v-if="confirm && preview" title="确认还原网站" @close="!busy && (confirm = false)">
    <p class="ve-confirm-body">
      网站将恢复到 {{ date(preview.summary.createdAt) }} 的内容，包括
      {{ preview.summary.contentCount }} 个条目和
      {{ preview.summary.mediaCount }} 个素材。还原前的内容会自动备份。
    </p>
    <label class="mg-check"
      ><input v-model="acknowledged" type="checkbox" :disabled="Boolean(busy)" /><span
        >我确认将当前网站内容替换为此备份</span
      ></label
    >
    <p v-if="error" class="ve-error" role="alert">{{ error }}</p>
    <div class="ve-dialog-footer">
      <button class="ve-button" :disabled="Boolean(busy)" @click="confirm = false">返回检查</button
      ><button
        class="ve-button ve-primary"
        :disabled="!acknowledged || Boolean(busy) || dirtyCount > 0"
        @click="restore"
      >
        {{ busy === 'restore' ? '正在还原…' : '确认还原' }}
      </button>
    </div>
  </EditorDialog>
</template>
