<!-- designed by mew -->
<script setup lang="ts">
import { localHref } from '../composables/site';
import UiIcon from './UiIcon.vue';
defineProps<{ href: string }>();
</script>
<template>
  <a class="text-link" :href="localHref(href || '/')"
    ><slot /><span><UiIcon name="arrow-up-right" /></span
  ></a>
</template>
