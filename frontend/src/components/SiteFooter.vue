<!-- designed by mew -->
<script setup lang="ts">
import { computed } from 'vue';
import { content, setting, localHref } from '../composables/site';
import { t, pick } from '../composables/i18n';
import Logo from './Logo.vue';
import UiIcon from './UiIcon.vue';
const site = computed(() => setting('site')),
  nav = computed(() => content.navigation.filter((n) => n.footer));
</script>
<template>
  <footer id="footer">
    <div class="site-footer">
      <div class="footer-top">
        <div>
          <a class="brand" :href="localHref('/')"><Logo /></a>
          <div class="footer-description" v-html="pick(site, 'footer')"></div>
        </div>
        <div class="footer-links">
          <div v-for="(start, index) in [0, Math.ceil(nav.length / 2)]" :key="index">
            <a
              v-for="n in nav.slice(start, start + Math.ceil(nav.length / 2))"
              :key="n.id"
              :href="localHref(n.url)"
              >{{ pick(n, 'title') }}</a
            >
          </div>
          <div>
            <a :href="'mailto:' + site.email">{{ site.email }}</a>
            <p class="preserve-lines">{{ pick(site, 'address') }}</p>
          </div>
        </div>
      </div>
      <div class="footer-bottom">
        <div class="footer-attribution">
          <span>© {{ new Date().getFullYear() }} {{ pick(site, 'name') }}</span>
          <span class="footer-credit">
            Website designed &amp; developed by
            <a href="https://github.com/ROBINRUGAN" target="_blank" rel="noopener noreferrer"
              >Rongbang Wu</a
            >
            · 2026
          </span>
        </div>
        <div>
          <a :href="site.university_url" target="_blank" rel="noopener noreferrer"
            >{{ pick(site, 'university') }} <UiIcon name="arrow-up-right" /></a
          ><a href="#main">{{ t('Back to top') }} <UiIcon name="arrow-up" /></a>
        </div>
      </div>
    </div>
  </footer>
</template>
