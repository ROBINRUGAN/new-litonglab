<!-- designed by mew -->
<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { content, localHref } from '../composables/site';
import { t, pick } from '../composables/i18n';
import NotFoundView from './NotFoundView.vue';
import PaperRow from '../components/PaperRow.vue';
import UiIcon from '../components/UiIcon.vue';
const route = useRoute(),
  router = useRouter();
const project = computed(() =>
    content.project.find(
      (p) => p.slug === route.params.slug || p.aliases?.includes(String(route.params.slug)),
    ),
  ),
  next = computed(() =>
    content.project.length > 1
      ? content.project[
          (content.project.findIndex((p) => p.id === project.value?.id) + 1) %
            content.project.length
        ]
      : null,
  );
const papers = computed(() =>
  content.publication.filter((p) => project.value?.publications?.includes(p.id)),
);
watch(
  project,
  (p) => {
    if (p && p.slug !== route.params.slug) router.replace(localHref('/projects/' + p.slug + '/'));
  },
  { immediate: true },
);
</script>
<template>
  <div>
    <template v-if="project"
      ><section v-edit="['project', project.id]" class="project-head">
        <div>
          <a class="back-link" :href="localHref('/projects/')"
            ><UiIcon name="arrow-left" /> {{ t('All projects') }}</a
          ><span class="category">{{ pick(project, 'category') }}</span>
          <h1 v-edit="['project', project.id, 'name']">{{ pick(project, 'name') }}</h1>
          <p v-edit="['project', project.id, 'summary']">{{ pick(project, 'summary') }}</p>
          <div class="project-resource-links">
            <a
              v-for="(link, i) in project.links"
              :key="i"
              :href="link.url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-link"
              >{{ link.label }} <span><UiIcon name="arrow-up-right" /></span
            ></a>
          </div>
        </div>
        <figure>
          <img
            v-edit="['project', project.id, 'image']"
            :src="project.image"
            :alt="pick(project, 'name')"
            fetchpriority="high"
          />
        </figure>
      </section>
      <section class="project-article-wrap">
        <aside>
          <h3>{{ pick(project, 'name') }}</h3>
          <p>{{ pick(project, 'category') }}</p>
          <a :href="localHref('/projects/')"
            >{{ t('All projects') }} <UiIcon name="arrow-right"
          /></a>
        </aside>
        <article
          v-edit="['project', project.id, 'body']"
          class="project-article"
          v-html="pick(project, 'body')"
        ></article>
      </section>
      <section v-if="papers.length" class="section project-papers">
        <h2>{{ t('Publications') }}</h2>
        <PaperRow v-for="paper in papers" :key="paper.id" :paper="paper" />
      </section>
      <a v-if="next" class="next-project" :href="localHref('/projects/' + next.slug + '/')"
        ><div>
          <span class="category">{{ t('Next project') }}</span>
          <h2>{{ pick(next, 'name') }}</h2>
        </div>
        <img :src="next.image" alt="" loading="lazy" /><span
          ><UiIcon name="arrow-up-right" /></span></a></template
    ><NotFoundView v-else />
  </div>
</template>
