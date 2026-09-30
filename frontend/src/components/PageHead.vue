<!-- designed by mew -->
<script setup lang="ts">
import { computed } from 'vue';
import { content, pageContent } from '../composables/site';
import { pick, t } from '../composables/i18n';
import PhotoCarousel from './PhotoCarousel.vue';
const props = defineProps<{ slug: string; fallback?: string }>();
const page = computed(() => pageContent(props.slug));
const photos = computed(() => content.photo.filter((p) => p.show_people));
</script>
<template>
  <section
    class="page-head"
    :class="{ 'with-image': page.image || (slug === 'people' && photos.length) }"
  >
    <div>
      <h1 v-edit="['page', slug === 'join' ? page.id : undefined, 'title']">
        {{ pick(page, 'title') || t(fallback) }}
      </h1>
      <p
        v-if="pick(page, 'description')"
        v-edit="['page', slug === 'join' ? page.id : undefined, 'description']"
      >
        {{ pick(page, 'description') }}
      </p>
    </div>
    <PhotoCarousel v-if="slug === 'people' && photos.length" compact :photos="photos" /><img
      v-else-if="page.image"
      v-edit="['page', slug === 'join' ? page.id : undefined, 'image']"
      :src="page.image"
      alt=""
      fetchpriority="high"
    />
  </section>
</template>
