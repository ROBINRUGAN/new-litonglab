<!-- designed by mew -->
<script setup lang="ts">
import { ref, computed } from 'vue';
import { content, pageContent } from '../composables/site';
import { t, pick, locale } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import PaperRow from '../components/PaperRow.vue';
import UiIcon from '../components/UiIcon.vue';
const search = ref(''),
  year = ref('all'),
  category = ref('All');
const categories = [
  'All',
  'Conference Papers',
  'Journal Papers',
  'Chinese Papers',
  'Preprints',
  'Granted Patents',
];
const years = computed(() => [...new Set(content.publication.map((p) => p.year))].sort().reverse());
const filtered = computed(() =>
  content.publication.filter(
    (p) =>
      (category.value === 'All' || p.category === category.value) &&
      (year.value === 'all' || p.year === year.value) &&
      (!search.value.trim() ||
        [p.title, p.authors, p.citation, p.venueFull, p.venueShort, p.track, p.ccfRating]
          .join(' ')
          .toLowerCase()
          .includes(search.value.toLowerCase().trim())),
  ),
);
const visibleYears = computed(() => [...new Set(filtered.value.map((p) => p.year))]),
  isFiltered = computed(() => search.value || year.value !== 'all' || category.value !== 'All');
function reset() {
  search.value = '';
  year.value = 'all';
  category.value = 'All';
}
</script>
<template>
  <div>
    <PageHead slug="publications" fallback="Publications" />
    <section class="section archive">
      <div class="archive-controls">
        <label class="search-input"
          ><span><UiIcon name="search" /></span
          ><input
            v-model="search"
            type="search"
            id="pub-search"
            :placeholder="t('Search title, author, venue…')"
            :aria-label="t('Search publications')" /></label
        ><label class="select-wrap"
          >{{ t('Year')
          }}<select v-model="year" id="pub-year" :aria-label="t('Publication year')">
            <option value="all">{{ t('All years') }}</option>
            <option v-for="y in years" :key="y">{{ y }}</option>
          </select></label
        >
      </div>
      <div class="filter-tabs" role="group" :aria-label="t('Publication category')">
        <button
          v-for="c in categories"
          :key="c"
          :data-pub-category="c"
          :aria-pressed="c === category"
          @click="category = c"
        >
          {{ t(c === 'All' ? 'All publications' : c) }}
        </button>
      </div>
      <div class="results-line">
        <span id="pub-count" aria-live="polite">{{
          locale === 'zh'
            ? `${filtered.length} 项论文与专利`
            : `${filtered.length} publications & patents`
        }}</span
        ><button v-show="isFiltered" id="reset-pubs" class="reset-filters" @click="reset">
          {{ t('Reset filters') }}
        </button>
      </div>
      <div id="pub-results">
        <section v-for="y in visibleYears" :key="y" class="year-group">
          <h2>{{ y }}</h2>
          <div>
            <PaperRow v-for="p in filtered.filter((p) => p.year === y)" :key="p.id" :paper="p" />
          </div>
        </section>
        <div v-if="!filtered.length" class="empty-results">
          <h3>{{ t('No matching publications.') }}</h3>
          <p>{{ t('Try another title, author, venue, or year.') }}</p>
        </div>
      </div>
      <div
        v-if="pick(pageContent('publications'), 'body')"
        class="project-article"
        v-html="pick(pageContent('publications'), 'body')"
      ></div>
    </section>
  </div>
</template>
