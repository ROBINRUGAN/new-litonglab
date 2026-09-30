<!-- designed by mew -->
<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import { content, setting, localHref } from '../composables/site';
import { t, pick } from '../composables/i18n';
import { theme, selectedLanguage, changeLanguage, changeTheme } from '../composables/transitions';
import Logo from './Logo.vue';
import UiIcon from './UiIcon.vue';
const route = useRoute(),
  open = ref(false),
  nav = computed(() => content.navigation.filter((n) => n.header && !n.highlight)),
  cta = computed(() => content.navigation.find((n) => n.header && n.highlight)),
  site = computed(() => setting('site'));
const close = () => {
  open.value = false;
};
watch(() => route.fullPath, close);
watch(open, (v) => {
  document.body.style.overflow = v ? 'hidden' : '';
});
const keys = (e: KeyboardEvent) => {
    if (e.key === 'Escape') close();
  },
  resize = () => {
    if (innerWidth > 850) close();
  };
onMounted(() => {
  addEventListener('keydown', keys);
  addEventListener('resize', resize);
});
onUnmounted(() => {
  removeEventListener('keydown', keys);
  removeEventListener('resize', resize);
});
</script>
<template>
  <a class="skip" href="#main">{{ t('Skip to content') }}</a>
  <header id="header">
    <a class="brand" :href="localHref('/')" aria-label="LitongLab"><Logo /></a>
    <nav :aria-label="t('Main navigation')">
      <a
        v-for="n in nav"
        :key="n.id"
        :href="localHref(n.url)"
        :class="{ active: route.path === n.url }"
        :data-nav="n.url.replaceAll('/', '') || 'home'"
        :aria-current="route.path === n.url ? 'page' : undefined"
        >{{ pick(n, 'title') }}</a
      >
    </nav>
    <a v-if="cta" class="nav-join" :href="localHref(cta.url)"
      >{{ pick(cta, 'title') }} <span><UiIcon name="arrow-up-right" /></span
    ></a>
    <div
      class="language-switch"
      role="group"
      :aria-label="t('Language')"
      :data-selected="selectedLanguage"
    >
      <button
        data-language="en"
        aria-label="Switch to English"
        :aria-pressed="selectedLanguage === 'en'"
        @click="changeLanguage('en')"
      >
        EN</button
      ><button
        data-language="zh"
        aria-label="切换为中文"
        :aria-pressed="selectedLanguage === 'zh'"
        @click="changeLanguage('zh')"
      >
        中文
      </button>
    </div>
    <button
      v-if="site.enable_theme"
      class="theme-toggle"
      :aria-label="t(theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode')"
      :aria-pressed="theme === 'dark'"
      @click="changeTheme"
    >
      <svg
        class="theme-sun"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="4" />
        <path
          d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"
        /></svg
      ><svg
        class="theme-moon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        aria-hidden="true"
      >
        <path d="M20.4 14.1A8.7 8.7 0 0 1 9.9 3.6a8.7 8.7 0 1 0 10.5 10.5Z" />
      </svg>
    </button>
    <button
      class="menu-toggle"
      :aria-expanded="open"
      aria-controls="mobile-nav"
      :aria-label="t(open ? 'Close navigation' : 'Open navigation')"
      @click="open = !open"
    >
      <span></span><span></span>
    </button>
  </header>
  <nav id="mobile-nav" :aria-label="t('Mobile navigation')" :hidden="!open">
    <a
      v-for="n in content.navigation.filter((n) => n.header)"
      :key="n.id"
      :href="localHref(n.url)"
      @click="close"
      >{{ pick(n, 'title') }}</a
    >
  </nav>
</template>
