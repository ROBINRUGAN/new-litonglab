<!-- designed by mew -->
<script setup lang="ts">
import { t } from '../composables/i18n';
import TextLink from '../components/TextLink.vue';
</script>
<template>
  <div>
    <section class="page-head">
      <h1>{{ t('Page not found') }}</h1>
    </section>
    <section class="section">
      <TextLink href="/">{{ t('Return home') }}</TextLink>
    </section>
  </div>
</template>
