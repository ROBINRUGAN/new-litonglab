<!-- designed by mew -->
<script setup lang="ts">
import { content, pageContent, localHref } from '../composables/site';
import { t, pick } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import ResearchCards from '../components/ResearchCards.vue';
import PublicationMeta from '../components/PublicationMeta.vue';
import TextLink from '../components/TextLink.vue';
import UiIcon from '../components/UiIcon.vue';
const projects = (d: import('../types/content').Direction) =>
  (d.projects || [])
    .map((id) => content.project.find((p) => p.id === id))
    .filter((p) => p !== undefined);
const papers = (d: import('../types/content').Direction) =>
  (d.publications || [])
    .map((id) => content.publication.find((p) => p.id === id))
    .filter((p) => p !== undefined);
</script>
<template>
  <div>
    <PageHead slug="research" fallback="Research" />
    <section class="section research-overview"><ResearchCards /></section>
    <section
      v-for="d in content.direction"
      :key="d.id"
      v-edit="['direction', d.id]"
      class="section research-detail"
      :id="d.id"
    >
      <div class="research-detail-top">
        <img
          v-edit="['direction', d.id, 'image']"
          :src="d.image"
          :alt="pick(d, 'title')"
          loading="lazy"
        />
        <div>
          <h2 v-edit="['direction', d.id, 'title']">{{ pick(d, 'title') }}</h2>
          <p v-edit="['direction', d.id, 'description']">{{ pick(d, 'description') }}</p>
          <div class="research-tags">
            <TextLink v-for="p in projects(d)" :key="p.id" :href="'/projects/' + p.slug + '/'">{{
              pick(p, 'name')
            }}</TextLink>
          </div>
        </div>
      </div>
      <div class="related-papers">
        <a v-for="p in papers(d)" :key="p.id" :href="localHref('/publications/#' + p.id)"
          ><PublicationMeta :paper="p" />
          <h3>{{ p.title }}</h3>
          <span><UiIcon name="arrow-up-right" /></span
        ></a>
      </div>
    </section>
    <section
      v-if="pick(pageContent('research'), 'body')"
      class="section project-article"
      v-html="pick(pageContent('research'), 'body')"
    ></section>
  </div>
</template>
