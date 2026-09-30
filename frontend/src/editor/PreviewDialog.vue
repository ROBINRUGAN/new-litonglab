<!-- designed by mew -->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useContentStore } from '../stores/content';
import { usePreferencesStore } from '../stores/preferences';
import EditorDialog from './EditorDialog.vue';
const emit = defineEmits<{ close: [] }>();
const route = useRoute(),
  site = useContentStore(),
  preferences = usePreferencesStore(),
  mobile = ref(false),
  frame = ref<HTMLIFrameElement>();
const url = computed(() => route.path + '?preview=1');
function send() {
  frame.value?.contentWindow?.postMessage(
    {
      type: 'litong-editor-preview',
      content: JSON.parse(JSON.stringify(site.content)),
      locale: preferences.locale,
      theme: preferences.theme,
    },
    location.origin,
  );
}
function ready(event: MessageEvent) {
  if (
    event.origin === location.origin &&
    event.source === frame.value?.contentWindow &&
    event.data?.type === 'litong-preview-ready'
  )
    send();
}
watch(mobile, () => nextTick(send));
onMounted(() => addEventListener('message', ready));
onBeforeUnmount(() => removeEventListener('message', ready));
</script>
<template>
  <EditorDialog title="预览当前页面" wide @close="emit('close')"
    ><div class="ve-preview-options">
      <div class="ve-segment">
        <button :aria-pressed="!mobile" @click="mobile = false">桌面</button
        ><button :aria-pressed="mobile" @click="mobile = true">手机 · 390px</button>
      </div>
      <span class="ve-muted">包含当前未保存的修改，仅你可见</span>
    </div>
    <div class="ve-preview-stage">
      <iframe
        ref="frame"
        title="官网实时预览"
        :src="url"
        :class="{ 'is-mobile': mobile }"
        @load="send"
      ></iframe></div
  ></EditorDialog>
</template>
