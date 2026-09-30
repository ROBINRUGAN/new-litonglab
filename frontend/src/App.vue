<!-- designed by mew -->
<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { editorRequested } from './editor/target';
import { useContentStore } from './stores/content';
const EditorShell = defineAsyncComponent(() => import('./editor/EditorShell.vue'));
import SiteHeader from './components/SiteHeader.vue';
import SiteFooter from './components/SiteFooter.vue';
import {
  content,
  loaded,
  loadError,
  loadSite,
  preview,
  pageContent,
  heroAssetUrl,
} from './composables/site';
import { pick, locale } from './composables/i18n';
import { reveal } from './composables/transitions';
import { usePreferencesStore, storedPreference } from './stores/preferences';

const framed = window.parent !== window;
const route = useRoute();
const managing = computed(() => route.path === '/admin' || route.path.startsWith('/admin/'));
const router = useRouter();
const preferences = usePreferencesStore();
const main = ref<HTMLElement | null>(null);
const ready = ref(false);
const firstScreenError = ref('');
let clearReveal: (() => void) | undefined;

async function waitForFonts() {
  if (!document.fonts) return;
  if (locale.value === 'en') {
    await Promise.all(
      [
        '400 16px "DM Sans"',
        '500 16px "DM Sans"',
        '600 16px "DM Sans"',
        '700 16px "DM Sans"',
        '400 16px Lora',
        '500 16px Lora',
        '600 16px Lora',
      ].map((face) => document.fonts.load(face, 'LitongLab')),
    );
  }
  await document.fonts.ready;
}

function reloadPage() {
  window.location.reload();
}

function waitForVideoStart(video: HTMLVideoElement): Promise<void> {
  return new Promise((resolve) => {
    const timeout = window.setTimeout(finish, 1800);
    function finish() {
      clearTimeout(timeout);
      video.removeEventListener('timeupdate', check);
      video.removeEventListener('playing', check);
      video.removeEventListener('error', finish);
      resolve();
    }
    function check() {
      if (
        video.paused ||
        video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
        video.currentTime < 0.1
      )
        return;
      finish();
    }
    video.addEventListener('timeupdate', check);
    video.addEventListener('playing', check);
    video.addEventListener('error', finish);
    check();
    video.play().catch(finish);
  });
}

async function waitForFirstScreen() {
  if (route.path !== '/') return;
  await nextTick();
  const home = content.home[0];
  const tasks: Promise<unknown>[] = [];
  if (home?.poster) {
    const poster = new Image();
    poster.src = heroAssetUrl(home.poster);
    tasks.push(poster.decode());
  }
  const logo = document.querySelector<HTMLImageElement>('#header .brand img');
  if (logo) tasks.push(logo.decode());
  tasks.push(waitForFonts());
  if (home?.video) {
    const video = main.value?.querySelector<HTMLVideoElement>('video.hero-media');
    if (!video) throw new Error('首页视频未加载。');
    tasks.push(waitForVideoStart(video));
  }
  await Promise.all(tasks);
}

function updateMetadata() {
  document.body.classList.toggle('inner', route.path !== '/');
  if (managing.value) {
    document.title = '内容管理 · LitongLab';
    return;
  }
  if (!loaded.value) return;
  const site = content.site[0];
  const page =
    route.path.startsWith('/projects/') && route.params.slug
      ? content.project.find((p) => p.slug === route.params.slug)
      : route.path.startsWith('/publications/') && route.params.id
        ? content.publication.find((p) => p.id === route.params.id)
        : pageContent(String(route.params.slug || route.path.split('/')[1]));
  document.title = [pick(page, 'title') || pick(page, 'name'), pick(site, 'name')]
    .filter(Boolean)
    .join(' · ');
  document
    .querySelector('meta[name="description"]')
    ?.setAttribute(
      'content',
      pick(page, 'seoDescription') || pick(page, 'description') || pick(site, 'seoDescription'),
    );
  document
    .querySelector('link[rel="icon"]')
    ?.setAttribute('href', site.favicon || '/assets/favicon.ico');
}

async function revealPage() {
  await nextTick();
  clearReveal?.();
  clearReveal = reveal(main.value);
}

function navigate(event: MouseEvent) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  const anchor = (event.target as Element)?.closest<HTMLAnchorElement>('a[href]');
  if (!anchor || anchor.target || anchor.hasAttribute('download')) return;
  const url = new URL(anchor.href);
  if (
    url.origin !== location.origin ||
    /^\/(admin|api|static|media|assets|images|icons)(\/|$)/.test(url.pathname) ||
    /\.[a-z0-9]+$/i.test(url.pathname)
  )
    return;
  event.preventDefault();
  void router.push(url.pathname + url.search + url.hash);
}

watch(
  () => route.query.edit,
  (value) => {
    editorRequested.value = value === '1';
  },
);
function previewMessage(event: MessageEvent) {
  if (
    window.parent === window ||
    !preview.value ||
    event.origin !== location.origin ||
    event.source !== window.parent ||
    event.data?.type !== 'litong-editor-preview'
  )
    return;
  if (!event.data.content?.site?.length || !event.data.content?.home?.length) return;
  Object.assign(content, event.data.content);
  useContentStore().loaded = true;
  ready.value = true;
  preferences.setLocale(event.data.locale === 'zh' ? 'zh' : 'en', false);
  preferences.selectedLanguage = preferences.locale;
  preferences.setTheme(event.data.theme === 'dark' ? 'dark' : 'light', false);
}
watch([() => route.fullPath, locale, loaded], updateMetadata, { immediate: true });
async function initialize() {
  ready.value = false;
  firstScreenError.value = '';
  await loadSite();
  if (!loaded.value) return;
  const site = content.site[0];
  const savedLanguage = storedPreference('language');
  preferences.setLocale(
    savedLanguage === 'zh' || savedLanguage === 'en'
      ? savedLanguage
      : site.default_language || 'en',
    false,
  );
  if (!storedPreference('theme')) preferences.setTheme(site.default_theme || 'light', false);
  if (!site.enable_theme) preferences.setTheme(site.default_theme || 'light', false);
  preferences.selectedLanguage = preferences.locale;
  updateMetadata();
  try {
    await waitForFirstScreen();
  } catch {
    firstScreenError.value =
      locale.value === 'zh'
        ? '首页资源加载失败，请重试。'
        : 'Homepage resources could not load. Please retry.';
    return;
  }
  ready.value = true;
  await revealPage();
  if (window.parent !== window && preview.value)
    window.parent.postMessage({ type: 'litong-preview-ready' }, location.origin);
}
onMounted(async () => {
  document.addEventListener('click', navigate);
  addEventListener('message', previewMessage);
  await router.isReady();
  if (editorRequested.value || managing.value) return;
  await initialize();
});
onUnmounted(() => {
  clearReveal?.();
  document.removeEventListener('click', navigate);
  removeEventListener('message', previewMessage);
});
</script>

<template>
  <RouterView v-if="managing" />
  <EditorShell v-if="editorRequested && !managing" />
  <div v-if="!managing && loaded" :inert="!ready && !editorRequested">
    <div v-if="preview && !editorRequested && !framed" class="preview-banner">
      草稿预览 · 仅已登录编辑可见 <a href="/admin/">返回后台</a>
    </div>
    <SiteHeader />
    <main id="main" ref="main">
      <RouterView v-slot="{ Component }">
        <Transition name="route" mode="out-in" @after-enter="revealPage">
          <component :is="Component" :key="route.path" />
        </Transition>
      </RouterView>
    </main>
    <SiteFooter />
  </div>
  <div
    v-if="!managing && !editorRequested && (!loaded || !ready)"
    class="loading-screen"
    role="status"
  >
    <img src="/icons/litonglab-logo-long.png" alt="LitongLab" />
    <template v-if="loadError || firstScreenError"
      ><p>{{ firstScreenError || loadError }}</p>
      <button @click="firstScreenError ? reloadPage() : initialize()">
        {{ locale === 'zh' ? '重新加载' : 'Reload' }}</button
      ><a v-if="preview" href="/admin/">登录后台</a></template
    >
    <span v-else class="loading-dot" aria-label="Loading"></span>
  </div>
</template>
