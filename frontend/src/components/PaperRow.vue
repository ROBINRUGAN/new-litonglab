<!-- designed by mew -->
<script setup lang="ts">
import PublicationMeta from './PublicationMeta.vue';
import { t } from '../composables/i18n';
import { localHref } from '../composables/site';
import UiIcon from './UiIcon.vue';
defineProps<{ paper: import('../types/content').Publication }>();
</script>
<template>
  <article v-edit="['publication', paper.id]" class="paper-row" :id="paper.id">
    <PublicationMeta :paper="paper" />
    <div class="paper-content">
      <h3>
        <a
          v-edit="['publication', paper.id, 'title']"
          :href="localHref('/publications/' + paper.id + '/')"
          >{{ paper.title }}</a
        >
      </h3>
      <p v-edit="['publication', paper.id, 'authors']" class="authors">{{ paper.authors }}</p>
      <details v-if="paper.citation">
        <summary>{{ t('Full citation') }}</summary>
        <p v-edit="['publication', paper.id, 'citation']">{{ paper.citation }}</p>
      </details>
    </div>
    <div class="paper-actions">
      <a
        v-for="(link, i) in paper.links"
        :key="i"
        class="paper-link"
        :href="link.url"
        target="_blank"
        rel="noopener noreferrer"
        >{{ link.label || 'Paper' }} <UiIcon name="arrow-up-right"
      /></a>
    </div>
  </article>
</template>
