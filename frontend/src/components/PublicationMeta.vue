<!-- designed by mew -->
<script setup lang="ts">
import { locale } from '../composables/i18n';
defineProps<{ paper: import('../types/content').Publication }>();
</script>
<template>
  <div class="paper-meta">
    <div class="venue-line">
      <span
        v-edit="['publication', paper.id, 'venue_key']"
        class="venue-name"
        :title="paper.venueFull"
        >{{ paper.venueShort }} {{ paper.conferenceYear || paper.year
        }}<span v-if="paper.track" class="paper-track"> · {{ paper.track }}</span></span
      >
      <span
        v-if="paper.ccfRating"
        v-edit="['publication', paper.id, 'ccfRating']"
        class="ccf-badge"
        :class="'ccf-' + paper.ccfRating.toLowerCase()"
        :title="[paper.ccfEdition, paper.ratingNote].filter(Boolean).join(' · ')"
        >{{
          paper.ccfRating === 'unranked'
            ? locale === 'zh'
              ? '未评级'
              : 'Unranked'
            : 'CCF-' + paper.ccfRating
        }}</span
      >
    </div>
  </div>
</template>
