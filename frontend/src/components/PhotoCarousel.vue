<!-- designed by mew -->
<script setup lang="ts">
import { canvasEditing } from '../editor/target';
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { pick, t } from '../composables/i18n';
import { setting } from '../composables/site';
import { reducedMotion } from '../composables/transitions';
import type { Photo } from '../types/content';
import UiIcon from './UiIcon.vue';
const props = withDefaults(defineProps<{ photos?: Photo[]; compact?: boolean }>(), {
  photos: () => [],
  compact: false,
});
const current = ref(0),
  paused = ref(reducedMotion()),
  root = ref<HTMLElement | null>(null),
  hover = ref(false),
  visible = ref(false);
let timer: ReturnType<typeof setInterval> | undefined, observer: IntersectionObserver | undefined;
const photo = computed(() => props.photos[current.value]);
const show = (n: number) => {
  if (props.photos.length) current.value = (n + props.photos.length) % props.photos.length;
};
watch(
  () => props.photos.length,
  () => show(0),
);
onMounted(() => {
  observer = new IntersectionObserver(([e]) => (visible.value = e.isIntersecting), {
    threshold: 0.15,
  });
  if (root.value) observer.observe(root.value);
  timer = setInterval(
    () => {
      if (
        !canvasEditing.value &&
        visible.value &&
        !paused.value &&
        !hover.value &&
        !document.hidden
      )
        show(current.value + 1);
    },
    (setting('home').carousel_seconds || 6) * 1000,
  );
});
onUnmounted(() => {
  clearInterval(timer);
  observer?.disconnect();
});
</script>
<template>
  <div
    v-if="photos.length"
    ref="root"
    class="photo-carousel"
    :class="{ 'compact-gallery': compact }"
    role="region"
    :aria-label="t('Lab group photos')"
    :data-index="current"
    @mouseenter="hover = true"
    @mouseleave="hover = false"
    @focusin="hover = true"
    @focusout="hover = false"
  >
    <div v-edit="['photo', photo?.id, 'image']" class="photo-viewport">
      <img
        v-for="(p, i) in photos"
        :key="p.id"
        :src="p.image"
        :alt="pick(p, 'title')"
        :class="{ visible: i === current }"
        :aria-hidden="i !== current"
        loading="lazy"
      />
    </div>
    <div class="photo-toolbar">
      <span v-edit="['photo', photo?.id, 'title']" class="photo-title">{{
        pick(photo, 'title')
      }}</span>
      <div class="photo-pagination" role="group" :aria-label="t('Select group photo')">
        <button
          v-for="(p, i) in photos"
          :key="p.id"
          :data-slide="i"
          :aria-label="pick(p, 'title')"
          :aria-pressed="i === current"
          @click="show(i)"
        >
          <span></span>
        </button>
      </div>
      <div class="photo-controls">
        <button
          class="photo-prev"
          :aria-label="t('Previous group photo')"
          @click="show(current - 1)"
        >
          <UiIcon name="arrow-left" /></button
        ><button
          class="photo-play"
          :aria-label="t(paused ? 'Play slideshow' : 'Pause slideshow')"
          :aria-pressed="paused"
          @click="paused = !paused"
        >
          <UiIcon :name="paused ? 'play' : 'pause'" /></button
        ><button class="photo-next" :aria-label="t('Next group photo')" @click="show(current + 1)">
          <UiIcon name="arrow-right" />
        </button>
      </div>
    </div>
  </div>
</template>
