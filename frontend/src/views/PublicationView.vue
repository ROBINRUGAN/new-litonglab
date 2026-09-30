<!-- designed by mew -->
<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { content, localHref } from '../composables/site';
import { locale, pick, t } from '../composables/i18n';
import PublicationMeta from '../components/PublicationMeta.vue';
import NotFoundView from './NotFoundView.vue';
import UiIcon from '../components/UiIcon.vue';

const route = useRoute();
const paper = computed(() => content.publication.find((item) => item.id === route.params.id));
const abstract = computed(() => {
  if (!paper.value) return '';
  return locale.value === 'zh'
    ? paper.value.abstract_zh || paper.value.abstract_en
    : paper.value.abstract_en || paper.value.abstract_zh;
});
const caption = computed(() => {
  if (!paper.value) return '';
  return locale.value === 'zh'
    ? paper.value.imageCaption_zh || paper.value.imageCaption_en
    : paper.value.imageCaption_en || paper.value.imageCaption_zh;
});
const next = computed(() => {
  if (!paper.value || content.publication.length < 2) return null;
  const index = content.publication.findIndex((item) => item.id === paper.value?.id);
  return content.publication[(index + 1) % content.publication.length];
});
const projects = computed(() =>
  content.project.filter((project) => project.publications?.includes(paper.value?.id || '')),
);
</script>

<template>
  <div v-if="paper">
    <section v-edit="['publication', paper.id]" class="paper-detail-head">
      <a class="back-link" :href="localHref('/publications/')"
        ><UiIcon name="arrow-left" /> {{ t('All publications') }}</a
      >
      <PublicationMeta :paper="paper" />
      <h1 v-edit="['publication', paper.id, 'title']">{{ paper.title }}</h1>
      <p v-edit="['publication', paper.id, 'authors']" class="paper-detail-authors">
        {{ paper.authors }}
      </p>
      <div class="project-resource-links">
        <a
          v-for="(link, i) in paper.links"
          :key="i"
          class="text-link"
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          >{{ link.label || 'Link' }} <span><UiIcon name="arrow-up-right" /></span
        ></a>
      </div>
    </section>
    <section class="paper-detail-body">
      <article>
        <h2>{{ locale === 'zh' ? '摘要' : 'Abstract' }}</h2>
        <p v-if="abstract" v-edit="['publication', paper.id, 'abstract']">{{ abstract }}</p>
        <p v-else v-edit="['publication', paper.id, 'abstract']" class="paper-detail-pending">
          {{ locale === 'zh' ? '摘要待补充' : 'Abstract to be added' }}
        </p>
      </article>
      <figure v-edit="['publication', paper.id, 'image']">
        <img :src="paper.image || '/images/paper-placeholder.svg'" :alt="caption || paper.title" />
        <figcaption v-if="caption" v-edit="['publication', paper.id, 'imageCaption']">
          {{ caption }}
        </figcaption>
      </figure>
      <aside v-if="paper.citation">
        <h2>{{ t('Full citation') }}</h2>
        <p v-edit="['publication', paper.id, 'citation']">{{ paper.citation }}</p>
      </aside>
      <aside v-if="projects.length">
        <h2>{{ locale === 'zh' ? '相关项目' : 'Related projects' }}</h2>
        <div class="paper-detail-projects">
          <a
            v-for="project in projects"
            :key="project.id"
            :href="localHref('/projects/' + project.slug + '/')"
          >
            <img :src="project.image" :alt="pick(project, 'name')" loading="lazy" />
            <span>{{ pick(project, 'name') }} <UiIcon name="arrow-up-right" /></span>
          </a>
        </div>
      </aside>
    </section>
    <a v-if="next" class="next-project" :href="localHref('/publications/' + next.id + '/')">
      <div>
        <span class="category">{{ locale === 'zh' ? '下一篇论文' : 'Next publication' }}</span>
        <h2>{{ next.title }}</h2>
      </div>
      <span><UiIcon name="arrow-up-right" /></span>
    </a>
  </div>
  <NotFoundView v-else />
</template>
