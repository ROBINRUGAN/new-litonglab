<!-- designed by mew -->
<script setup lang="ts">
import { pick } from '../composables/i18n';
import UiIcon from './UiIcon.vue';
defineProps<{ item: import('../types/content').News }>();
</script>
<template>
  <article v-edit="['news', item.id]" class="news-row">
    <time v-edit="['news', item.id, 'date']" :datetime="item.date">{{
      item.date.replaceAll('-', '.')
    }}</time>
    <div>
      <img
        v-edit="['news', item.id, 'image']"
        v-if="item.image"
        class="news-photo"
        :src="item.image"
        alt=""
        loading="lazy"
      />
      <p v-edit="['news', item.id, 'title']">{{ pick(item, 'title') }}</p>
      <div v-if="item.links?.length" class="news-links">
        <a
          v-for="(link, i) in item.links"
          :key="i"
          :href="link.url"
          class="paper-link"
          target="_blank"
          rel="noopener noreferrer"
          >{{ link.label }} <UiIcon name="arrow-up-right"
        /></a>
      </div>
    </div>
  </article>
</template>
