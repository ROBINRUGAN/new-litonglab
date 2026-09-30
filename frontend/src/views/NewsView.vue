<!-- designed by mew -->
<script setup lang="ts">
import { ref, computed } from 'vue';
import { content, pageContent } from '../composables/site';
import { t, pick, locale } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import NewsRow from '../components/NewsRow.vue';
const year = ref('all'),
  years = computed(() => [...new Set(content.news.map((n) => n.date.slice(0, 4)))]),
  items = computed(() =>
    content.news.filter((n) => year.value === 'all' || n.date.startsWith(year.value)),
  ),
  visibleYears = computed(() => [...new Set(items.value.map((n) => n.date.slice(0, 4)))]);
</script>
<template>
  <div>
    <PageHead slug="news" fallback="News" />
    <section class="section news-archive">
      <div class="news-filter">
        <h2>{{ t('From the lab') }}</h2>
        <label class="select-wrap"
          >{{ t('Year')
          }}<select v-model="year" id="news-year" :aria-label="t('News year')">
            <option value="all">{{ t('All years') }}</option>
            <option v-for="y in years" :key="y">{{ y }}</option>
          </select></label
        >
      </div>
      <div id="news-count" class="results-line" aria-live="polite">
        {{ locale === 'zh' ? `${items.length} 条动态` : `${items.length} updates` }}
      </div>
      <div id="news-results">
        <section v-for="y in visibleYears" :key="y" class="news-year-group">
          <h2>{{ y }}</h2>
          <div>
            <NewsRow v-for="n in items.filter((n) => n.date.startsWith(y))" :key="n.id" :item="n" />
          </div>
        </section>
      </div>
      <div class="project-article" v-html="pick(pageContent('news'), 'body')"></div>
    </section>
  </div>
</template>
