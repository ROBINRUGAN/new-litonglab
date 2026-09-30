<!-- designed by mew -->
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { content, setting, localHref, heroAssetUrl } from '../composables/site';
import { t, pick } from '../composables/i18n';
import { bindHomeMotion } from '../composables/motion';
import TextLink from '../components/TextLink.vue';
import ResearchCards from '../components/ResearchCards.vue';
import PhotoCarousel from '../components/PhotoCarousel.vue';
import PublicationMeta from '../components/PublicationMeta.vue';
import NewsRow from '../components/NewsRow.vue';
import UiIcon from '../components/UiIcon.vue';
const root = ref<HTMLElement | null>(null),
  video = ref<HTMLVideoElement | null>(null),
  paused = ref(true);
let cleanup: (() => void) | undefined, observer: IntersectionObserver | undefined;
function setVideo(el: unknown) {
  video.value = el instanceof HTMLVideoElement ? el : null;
}
const home = computed(() => setting('home')),
  features = computed(() =>
    (home.value.featured_projects || [])
      .map((id) => content.project.find((p) => p.id === id))
      .filter((p) => p !== undefined),
  ),
  papers = computed(() =>
    (home.value.featured_publications || [])
      .map((id) => content.publication.find((p) => p.id === id))
      .filter((p) => p !== undefined),
  ),
  photos = computed(() => content.photo.filter((p) => p.show_home));
const heading = (section: import('../types/content').Section, fallback: string) =>
  pick(section, 'title') || t(fallback);
function tryAutoplay() {
  if (!video.value) return;
  if (video.value.getBoundingClientRect().bottom <= 0) return;
  video.value.play().catch(() => {
    paused.value = true;
  });
}
function showVideoWhenReady() {
  if (video.value && video.value.currentTime > 0.05) paused.value = false;
}
onMounted(() => {
  cleanup = bindHomeMotion(root.value);
  if (video.value) {
    document.addEventListener('WeixinJSBridgeReady', tryAutoplay, { once: true });
    observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) video.value?.pause();
      else tryAutoplay();
    });
    observer.observe(video.value);
  }
});
onUnmounted(() => {
  cleanup?.();
  observer?.disconnect();
  document.removeEventListener('WeixinJSBridgeReady', tryAutoplay);
});
watch(
  () => features.value.map((project) => project.id).join(','),
  async () => {
    await nextTick();
    cleanup?.();
    cleanup = bindHomeMotion(root.value);
  },
);
</script>
<template>
  <div ref="root">
    <template v-for="section in content.section" :key="section.id">
      <div
        v-if="section.component === 'hero'"
        class="hero-stack"
        :style="{ '--hero-overlay': (home.overlay || 100) / 100 }"
      >
        <section class="hero-stage">
          <div class="hero-background">
            <img
              class="hero-poster"
              :class="{ 'is-animated': paused }"
              :src="heroAssetUrl(home.poster)"
              alt=""
              fetchpriority="high"
            />
            <video
              v-if="home.video"
              :ref="setVideo"
              class="hero-media"
              :class="{ 'is-playing': !paused }"
              autoplay
              muted
              loop
              playsinline
              webkit-playsinline
              x5-playsinline
              preload="auto"
              :poster="heroAssetUrl(home.poster)"
              :src="heroAssetUrl(home.video)"
              @playing="showVideoWhenReady"
              @timeupdate="showVideoWhenReady"
              @pause="paused = true"
              @waiting="paused = true"
              @canplay="tryAutoplay"
              @error="paused = true"
            ></video>
          </div>
          <div class="hero-wash"></div>
          <div class="hero-copy">
            <p class="hero-university">{{ pick(home, 'eyebrow') }}</p>
            <h1 class="preserve-lines">{{ pick(home, 'title') }}</h1>
            <p>{{ pick(home, 'description') }}</p>
            <TextLink href="/research/">{{ t('Our research') }}</TextLink>
          </div>
          <div class="hero-bottom">
            <a href="#research-home"
              >{{ t('Discover LitongLab') }} <span><UiIcon name="arrow-down" /></span
            ></a>
          </div>
        </section>
      </div>
      <section
        v-else-if="section.component === 'research'"
        class="section research-home"
        id="research-home"
      >
        <div class="section-heading centered">
          <h2>{{ heading(section, 'LitongLab Research') }}</h2>
        </div>
        <ResearchCards />
      </section>
      <section
        v-else-if="section.component === 'projects' && features.length"
        class="research-story"
        :style="{ '--story-height': Math.max(2, features.length) * 100 + 'svh' }"
      >
        <div class="research-stage">
          <div class="feature-heading">
            <h2 v-edit="['home', 'home', 'featured_projects']">
              {{ heading(section, 'Research in practice') }}
            </h2>
            <TextLink href="/projects/">{{ t('All projects') }}</TextLink>
          </div>
          <div class="feature-scenes">
            <div class="feature-copy">
              <article
                v-for="(p, i) in features"
                :key="p.id"
                v-edit="['project', p.id]"
                class="feature-caption"
                :class="{ current: i === 0 }"
                :data-scene="i"
              >
                <span class="category">{{ pick(p, 'category') }}</span>
                <h3 v-edit="['project', p.id, 'name']">{{ pick(p, 'name') }}</h3>
                <p v-edit="['project', p.id, 'summary']">{{ pick(p, 'summary') }}</p>
                <TextLink :href="'/projects/' + p.slug + '/'">{{ t('View project') }}</TextLink>
              </article>
            </div>
            <div class="feature-backgrounds">
              <div
                v-for="(p, i) in features"
                :key="p.id"
                class="feature-image"
                :class="{ current: i === 0 }"
                :data-scene-image="i"
              >
                <img
                  v-edit="['project', p.id, 'image']"
                  :src="p.image"
                  :alt="pick(p, 'name')"
                  loading="eager"
                />
              </div>
            </div>
          </div>
          <div class="feature-dots" role="group" :aria-label="t('Featured project')">
            <button
              v-for="(p, i) in features"
              :key="p.id"
              :data-jump-scene="i"
              :aria-label="pick(p, 'name')"
              :aria-pressed="i === 0"
            >
              <span></span>
            </button>
          </div>
        </div>
      </section>
      <section
        v-else-if="section.component === 'publications' && papers.length"
        class="section selected-work"
      >
        <div class="section-heading">
          <h2 v-edit="['home', 'home', 'featured_publications']">
            {{ heading(section, 'Selected publications') }}
          </h2>
          <TextLink href="/publications/">{{ t('All publications') }}</TextLink>
        </div>
        <div class="publication-cards">
          <article
            v-for="p in papers"
            :key="p.id"
            v-edit="['publication', p.id]"
            class="publication-card"
          >
            <a :href="localHref('/publications/' + p.id + '/')" class="publication-visual"
              ><img
                v-edit="['publication', p.id, 'image']"
                v-if="p.image"
                :src="p.image"
                alt=""
                loading="lazy"
              /><span v-else class="publication-monogram">{{ p.venueShort }}</span></a
            ><PublicationMeta :paper="p" />
            <h3>
              <a :href="localHref('/publications/' + p.id + '/')">{{ p.title }}</a>
            </h3>
          </article>
        </div>
      </section>
      <section
        v-else-if="section.component === 'people' && photos.length"
        class="section home-people"
      >
        <div class="section-heading">
          <h2>{{ heading(section, 'Our people') }}</h2>
          <TextLink href="/people/">{{ t('Meet the team') }}</TextLink>
        </div>
        <PhotoCarousel :photos="photos" />
      </section>
      <section v-else-if="section.component === 'news'" class="section home-news">
        <div class="section-heading">
          <h2>{{ heading(section, 'Latest news') }}</h2>
          <TextLink href="/news/">{{ t('All news') }}</TextLink>
        </div>
        <NewsRow v-for="n in content.news.slice(0, home.news_limit || 4)" :key="n.id" :item="n" />
      </section>
      <section v-else-if="section.component === 'join'" class="join-banner">
        <img
          v-edit="['home', 'home', 'join_image']"
          v-if="home.join_image"
          :src="home.join_image"
          alt=""
          loading="lazy"
        />
        <div>
          <h2>{{ pick(home, 'join_title') }}</h2>
          <p>{{ pick(home, 'join_description') }}</p>
          <TextLink href="/join/">{{ t('Join us') }}</TextLink>
        </div>
      </section>
      <section v-else-if="section.component === 'content'" class="section custom-section">
        <h2 v-if="pick(section, 'title')">{{ pick(section, 'title') }}</h2>
        <img v-if="section.image" :src="section.image" alt="" loading="lazy" />
        <div class="project-article" v-html="pick(section, 'body')"></div>
      </section>
    </template>
  </div>
</template>
