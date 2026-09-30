<!-- designed by mew -->
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue';
defineProps<{ title: string; wide?: boolean }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>();
onMounted(() => dialog.value?.showModal());
onBeforeUnmount(() => dialog.value?.close());
</script>
<template>
  <Teleport to="body">
    <dialog
      ref="dialog"
      class="ve-ui ve-dialog"
      :class="{ 've-dialog-wide': wide }"
      :aria-label="title"
      @cancel.prevent="emit('close')"
    >
      <header class="ve-dialog-heading">
        <h2>{{ title }}</h2>
        <button type="button" class="ve-icon" aria-label="关闭对话框" @click="emit('close')">
          ×
        </button>
      </header>
      <slot />
    </dialog>
  </Teleport>
</template>
