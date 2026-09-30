<!-- designed by mew -->
<script setup lang="ts">
import { computed } from 'vue';
import { setting } from '../composables/site';
const site = computed(() => setting('site'));
</script>
<template><img :src="site.logo" alt="LitongLab" width="1222" height="404" /></template>
