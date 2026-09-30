<!-- designed by mew -->
<script setup lang="ts">
import { computed } from 'vue';
import { useEditorStore } from './store';

const props = defineProps<{ media: { title: string; url: string; sourceUrl: string } }>();
const store = useEditorStore();
const photo = computed(() =>
  store.records.find(
    (record) =>
      record.kind === 'photo' &&
      !record.deleted &&
      (record.data.image === props.media.url ||
        (!!props.media.sourceUrl && record.data.image === props.media.sourceUrl)),
  ),
);
const carousel = computed(() =>
  store.records
    .filter(
      (record) =>
        record.kind === 'photo' &&
        !record.deleted &&
        (record.data.show_home || record.data.show_people),
    )
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id)),
);
const index = computed(() => carousel.value.findIndex((record) => record.id === photo.value?.id));

function toggle(field: 'show_home' | 'show_people', event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  let record = photo.value;
  if (!record) {
    if (!checked || !store.kinds.find((kind) => kind.key === 'photo')?.canAdd) return;
    record = store.create('photo');
    for (const [name, value] of Object.entries({
      title_zh: props.media.title,
      title_en: props.media.title,
      image: props.media.url,
      show_home: false,
      show_people: false,
    }))
      store.update(record, name, value, false);
  }
  store.update(record, field, checked);
  if (!record.data.show_home && !record.data.show_people && record.version === null)
    store.discard(record);
}
function update(field: string, value: string) {
  if (photo.value) store.update(photo.value, field, value);
}
function move(action: 'up' | 'down' | 'top') {
  if (photo.value) store.move(photo.value, action, carousel.value);
}
</script>

<template>
  <section class="ve-carousel-controls" :aria-label="media.title + '轮播设置'">
    <div class="ve-carousel-flags">
      <label
        ><input
          type="checkbox"
          :checked="Boolean(photo?.data.show_home)"
          :disabled="
            store.busy || (!photo && !store.kinds.find((kind) => kind.key === 'photo')?.canAdd)
          "
          @change="toggle('show_home', $event)"
        />首页轮播</label
      >
      <label
        ><input
          type="checkbox"
          :checked="Boolean(photo?.data.show_people)"
          :disabled="
            store.busy || (!photo && !store.kinds.find((kind) => kind.key === 'photo')?.canAdd)
          "
          @change="toggle('show_people', $event)"
        />成员页轮播</label
      >
    </div>
    <template v-if="photo">
      <div v-if="index >= 0" class="ve-carousel-position">
        <span>第 {{ index + 1 }} / {{ carousel.length }} 张</span>
        <button :disabled="store.busy || index <= 0" @click="move('up')">上移</button>
        <button :disabled="store.busy || index >= carousel.length - 1" @click="move('down')">
          下移
        </button>
        <button :disabled="store.busy || index <= 0" @click="move('top')">置顶</button>
      </div>
      <p v-else class="ve-muted">未加入轮播</p>
      <details class="ve-carousel-details">
        <summary>中英文标题</summary>
        <label
          v-for="[field, label] in [
            ['title_zh', '中文标题'],
            ['title_en', '英文标题'],
          ]"
          :key="field"
        >
          {{ label }}
          <input
            type="text"
            :value="photo.data[field!]"
            :disabled="store.busy"
            @input="update(field!, ($event.target as HTMLInputElement).value)"
          />
        </label>
      </details>
    </template>
  </section>
</template>
