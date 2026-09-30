<!-- designed by mew -->
<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { content, localHref } from '../composables/site';
import { pick } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import NotFoundView from './NotFoundView.vue';
const route = useRoute(),
  router = useRouter();
const page = computed(() =>
  content.page.find(
    (p) => p.slug === route.params.slug || p.aliases?.includes(String(route.params.slug)),
  ),
);
watch(
  page,
  (p) => {
    if (p && p.slug !== route.params.slug) router.replace(localHref('/' + p.slug + '/'));
  },
  { immediate: true },
);
</script>
<template>
  <div>
    <template v-if="page"
      ><PageHead :slug="page.slug" />
      <section
        class="section project-article custom-page"
        v-html="pick(page, 'body')"
      ></section></template
    ><NotFoundView v-else />
  </div>
</template>
