<!-- designed by mew -->
<script setup lang="ts">
import { content, pageContent, localHref } from '../composables/site';
import { pick } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import UiIcon from '../components/UiIcon.vue';
</script>
<template>
  <div>
    <PageHead slug="projects" fallback="Projects" />
    <section class="section projects-section">
      <div class="project-grid">
        <a
          v-for="p in content.project"
          :key="p.id"
          v-edit="['project', p.id]"
          class="project-card"
          :href="localHref('/projects/' + p.slug + '/')"
          ><div class="project-card-image">
            <img
              v-edit="['project', p.id, 'image']"
              :src="p.image"
              :alt="pick(p, 'name')"
              loading="lazy"
            />
          </div>
          <div class="project-card-copy">
            <span class="category">{{ pick(p, 'category') }}</span>
            <h2>
              <b class="editable-name" v-edit="['project', p.id, 'name']">{{ pick(p, 'name') }}</b
              ><span><UiIcon name="arrow-up-right" /></span>
            </h2>
            <p v-edit="['project', p.id, 'summary']">{{ pick(p, 'summary') }}</p>
          </div></a
        >
      </div>
      <div class="project-article" v-html="pick(pageContent('projects'), 'body')"></div>
    </section>
  </div>
</template>
