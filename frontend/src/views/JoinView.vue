<!-- designed by mew -->
<script setup lang="ts">
import { computed } from 'vue';
import { setting, pageContent } from '../composables/site';
import { t, pick } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import UiIcon from '../components/UiIcon.vue';
const site = computed(() => setting('site')),
  page = computed(() => pageContent('join'));
</script>
<template>
  <div>
    <PageHead slug="join" fallback="Join us" />
    <section class="section join-content">
      <div
        v-edit="['page', 'join', 'body']"
        class="project-article"
        v-html="pick(page, 'body')"
      ></div>
      <div class="contact-card">
        <h3>{{ t('Contact') }}</h3>
        <a class="contact-email" :href="'mailto:' + site.email"
          ><span v-edit="['site', 'general', 'email']">{{ site.email }}</span>
          <UiIcon name="arrow-up-right"
        /></a>
        <p v-edit="['site', 'general', 'address']" class="preserve-lines">
          {{ pick(site, 'address') }}
        </p>
      </div>
    </section>
    <section v-if="page.image" class="section campus-picture">
      <img
        v-edit="['page', 'join', 'image']"
        :src="page.image"
        :alt="pick(site, 'university')"
        loading="lazy"
      />
    </section>
  </div>
</template>
