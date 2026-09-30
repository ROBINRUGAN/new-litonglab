<!-- designed by mew -->
<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { content, pageContent } from '../composables/site';
import { t, pick, locale } from '../composables/i18n';
import PageHead from '../components/PageHead.vue';
import UiIcon from '../components/UiIcon.vue';
const photos = computed(() => content.photo.filter((p) => p.show_people)),
  current = ref(0),
  photo = computed(() => photos.value[current.value]);
const show = (i: number) => {
  if (photos.value.length) current.value = (i + photos.value.length) % photos.value.length;
};
watch(
  () => photos.value.length,
  () => show(0),
);
const members = (group: import('../types/content').Group) =>
  content.person.filter((p) => p.group === group.id);
const portrait = (person: import('../types/content').Person) =>
  person.placeholder && (!person.image || person.image.startsWith('/images/people/'))
    ? '/images/person-placeholder.svg'
    : person.image;
</script>
<template>
  <div>
    <PageHead slug="people" fallback="Our people" />
    <template v-for="group in content.group" :key="group.id">
      <template v-if="group.layout === 'faculty'"
        ><section
          v-for="person in members(group)"
          :key="person.id"
          v-edit="['person', person.id]"
          class="section faculty"
        >
          <div class="faculty-portrait">
            <img
              v-edit="['person', person.id, 'image']"
              :src="portrait(person)"
              :alt="pick(person, 'name')"
              loading="lazy"
            />
          </div>
          <div class="faculty-info">
            <span class="category">{{ pick(group, 'title') }}</span>
            <h2>
              <b class="editable-name" v-edit="['person', person.id, 'name']">{{
                pick(person, 'name')
              }}</b>
              <span>{{ locale === 'zh' ? person.name_en : person.name_zh }}</span>
            </h2>
            <p v-edit="['person', person.id, 'role']" class="faculty-role">
              {{ pick(person, 'role') }}
            </p>
            <div v-edit="['person', person.id, 'bio']" v-html="pick(person, 'bio')"></div>
            <div class="faculty-links">
              <a
                v-for="(link, i) in person.links"
                :key="i"
                :href="link.url"
                class="text-link"
                target="_blank"
                rel="noopener noreferrer"
                >{{ t(link.label) }} <span><UiIcon name="arrow-up-right" /></span
              ></a>
            </div>
          </div></section
      ></template>
      <section v-else-if="members(group).length" class="section member-section">
        <div class="section-heading">
          <h2>{{ pick(group, 'title') }}</h2>
        </div>
        <div class="member-grid">
          <article
            v-for="person in members(group)"
            :key="person.id"
            v-edit="['person', person.id]"
            class="member"
          >
            <div v-edit="['person', person.id, 'image']" class="member-photo">
              <img
                :src="portrait(person)"
                :alt="pick(person, 'name')"
                width="720"
                height="720"
                loading="lazy"
              />
            </div>
            <h3>
              <b class="editable-name" v-edit="['person', person.id, 'name']">{{
                pick(person, 'name')
              }}</b
              ><span>{{ locale === 'zh' ? person.name_en : person.name_zh }}</span>
            </h3>
            <div
              v-edit="['person', person.id, 'bio']"
              class="member-bio"
              v-html="pick(person, 'bio')"
            ></div>
            <div class="member-links">
              <a
                v-for="(link, i) in person.links"
                :key="i"
                :href="link.url"
                target="_blank"
                rel="noopener noreferrer"
                >{{ t(link.label) }} <UiIcon name="arrow-up-right"
              /></a>
            </div>
          </article>
        </div>
      </section>
    </template>
    <section v-if="photos.length" class="section lab-life" id="lab-life">
      <div class="section-heading">
        <h2>{{ t('Life at LitongLab') }}</h2>
        <div class="gallery-controls">
          <button
            id="gallery-prev"
            :aria-label="t('Previous group photo')"
            @click="show(current - 1)"
          >
            <UiIcon name="arrow-left" /></button
          ><span id="gallery-count"
            >{{ String(current + 1).padStart(2, '0') }} /
            {{ String(photos.length).padStart(2, '0') }}</span
          ><button id="gallery-next" :aria-label="t('Next group photo')" @click="show(current + 1)">
            <UiIcon name="arrow-right" />
          </button>
        </div>
      </div>
      <figure class="gallery-figure">
        <img
          v-edit="['photo', photo?.id, 'image']"
          id="gallery-photo"
          :src="photo.image"
          :alt="pick(photo, 'title')"
          loading="lazy"
        />
        <figcaption id="gallery-caption">
          {{ pick(photo, 'title') }}
        </figcaption>
      </figure>
      <div class="gallery-thumbnails" role="group" :aria-label="t('Select group photo')">
        <button
          v-for="(p, i) in photos"
          :key="p.id"
          :data-photo="i"
          :aria-label="pick(p, 'title')"
          :aria-pressed="i === current"
          @click="show(i)"
        >
          <img :src="p.image" alt="" loading="lazy" /><span>{{ pick(p, 'title') }}</span>
        </button>
      </div>
    </section>
    <section
      v-if="pick(pageContent('people'), 'body')"
      class="section project-article"
      v-html="pick(pageContent('people'), 'body')"
    ></section>
  </div>
</template>
