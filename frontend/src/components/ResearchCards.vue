<!-- designed by mew -->
<script setup lang="ts">
import { content, localHref } from '../composables/site';
import { pick } from '../composables/i18n';
import UiIcon from './UiIcon.vue';
</script>
<template>
  <div class="research-grid">
    <a
      v-for="d in content.direction"
      :key="d.id"
      v-edit="['direction', d.id]"
      class="research-card"
      :href="localHref('/research/#' + d.id)"
      ><h3 v-edit="['direction', d.id, 'title']">{{ pick(d, 'title') }}</h3>
      <img
        v-edit="['direction', d.id, 'image']"
        :src="d.image"
        :alt="pick(d, 'title')"
        loading="lazy"
        width="600"
        height="600" />
      <p v-edit="['direction', d.id, 'description']">{{ pick(d, 'description') }}</p>
      <span class="card-arrow"><UiIcon name="arrow-up-right" /></span
    ></a>
  </div>
</template>
