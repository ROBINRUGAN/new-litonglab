<!-- designed by mew -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { locale } from '../composables/i18n';
import { usePreferencesStore } from '../stores/preferences';
import RichTextEditor from './RichTextEditor.vue';
import MediaPicker from './MediaPicker.vue';
import { useEditorStore } from './store';
import type { EditRecord, Field, Value } from './types';
import type { ContentLink } from '../types/content';
import UiIcon from '../components/UiIcon.vue';
import { categoryForRecord, type ImageCategory } from './mediaCategories';
const props = defineProps<{ record: EditRecord; focusField?: string }>();
const store = useEditorStore(),
  preferences = usePreferencesStore();
const advanced = ref(false),
  chooseMedia = ref<((url: string) => void) | null>(null),
  chooseCategory = ref<ImageCategory>(),
  chooseType = ref<'image' | 'pdf'>('image');
const basic: Record<string, string[]> = {
  publication: [
    'title',
    'authors',
    'year',
    'category',
    'venue_key',
    'track',
    'ccfRating',
    'citation',
    'abstract',
    'image',
    'imageCaption',
    'links',
  ],
  person: ['name', 'group', 'role', 'bio', 'image', 'links'],
  photo: ['title', 'image', 'show_home', 'show_people'],
  project: ['name', 'slug', 'category', 'summary', 'image', 'body', 'publications', 'links'],
  news: ['title', 'date', 'category', 'image', 'links'],
  group: ['title', 'layout'],
  venue: ['title', 'full', 'rating', 'edition', 'source', 'note'],
  direction: ['title', 'description', 'image', 'projects', 'publications'],
  home: ['featured_projects', 'featured_publications', 'carousel_seconds', 'join_image'],
  page: ['title', 'description', 'body', 'image'],
  site: ['email', 'address'],
};
const isFaculty = computed(
  () => store.find('group', String(props.record.data.group || ''))?.data.layout === 'faculty',
);
const availableFields = computed(() =>
  (store.schemas[props.record.kind] || []).filter(
    (field) =>
      localized(field) &&
      (props.record.kind !== 'person' ||
        (field.name !== 'placeholder' && (!field.name.startsWith('role_') || isFaculty.value))),
  ),
);
const localized = (field: Field) =>
  !/_en$|_zh$/.test(field.name) || field.name.endsWith('_' + locale.value);
const simple = (field: Field) =>
  (basic[props.record.kind] || []).includes(field.name.replace(/_(en|zh)$/, ''));
const fields = computed(() => {
  const available = availableFields.value;
  return available.filter((f) => simple(f) || advanced.value || f.name === props.focusField);
});
const hasLocalizedFields = computed(() =>
  availableFields.value.some((field) => /_(en|zh)$/.test(field.name)),
);
const placement = computed(() => store.position(props.record));
const extra = computed(() => availableFields.value.some((f) => !simple(f)));
const mediaAspect = computed(() => {
  if (props.record.kind === 'photo') return 1.85;
  if (props.record.kind !== 'person') return undefined;
  return 1;
});
function openMedia(
  callback: (url: string) => void,
  category?: ImageCategory,
  type: 'image' | 'pdf' = 'image',
) {
  chooseCategory.value = category;
  chooseType.value = type;
  chooseMedia.value = callback;
}
function update(field: string, value: Value) {
  store.update(props.record, field, value);
  if (
    props.record.kind === 'person' &&
    field === 'image' &&
    value !== '/images/person-placeholder.svg'
  )
    store.update(props.record, 'placeholder', false);
  if (field === 'venue_key') {
    for (const name of [
      'venueShort',
      'venueFull',
      'ccfRating',
      'ccfEdition',
      'ccfSource',
      'ratingNote',
    ])
      store.update(props.record, name, '', false);
    store.paint(props.record);
  }
}
function input(field: Field, event: Event) {
  const input = event.target as HTMLInputElement;
  update(
    field.name,
    field.type === 'boolean'
      ? input.checked
      : field.type === 'integer'
        ? Number(input.value)
        : input.value,
  );
}
const choices = (field: Field) =>
  store.records.filter((r) => r.kind === field.target && !r.deleted);
const choiceLabels: Record<string, string> = {
  'Conference Papers': '会议论文',
  'Journal Papers': '期刊论文',
  'Chinese Papers': '中文论文',
  Preprints: '预印本',
  'Granted Patents': '授权专利',
  Publication: '论文发表',
  Award: '获奖消息',
  'Lab update': '实验室动态',
  cards: '成员照片卡片',
  faculty: '导师介绍',
  unranked: '未评级',
  A: 'CCF-A',
  B: 'CCF-B',
  C: 'CCF-C',
};
function choiceLabel(field: Field, value: string, label: string) {
  if (!value) return field.name === 'track' ? '正式论文 / 不适用' : '沿用会刊目录 / 不适用';
  return choiceLabels[value] || label;
}
const links = (field: string) => (props.record.data[field] || []) as ContentLink[];
function updateLink(field: string, index: number, key: keyof ContentLink, value: string) {
  const next = links(field).map((l) => ({ ...l }));
  next[index]![key] = value;
  update(field, next);
}
function references(field: string, id: string, checked: boolean) {
  const next = [...((props.record.data[field] as string[]) || [])].filter((value) => value !== id);
  if (checked) next.push(id);
  update(field, next);
}
const referenceQueries = ref<Record<string, string>>({});
const selectedReferences = (field: Field) =>
  ((props.record.data[field.name] as string[]) || [])
    .map((id) => store.find(field.target!, id))
    .filter((record) => record && !record.deleted);
const matchingReferences = (field: Field) =>
  choices(field).filter((item) =>
    store
      .title(item)
      .toLowerCase()
      .includes((referenceQueries.value[field.name] || '').toLowerCase()),
  );
function moveReference(field: string, index: number, offset: number) {
  const ids = [...((props.record.data[field] as string[]) || [])];
  const [id] = ids.splice(index, 1);
  if (id) ids.splice(index + offset, 0, id);
  update(field, ids);
}
function language(value: 'en' | 'zh') {
  preferences.setLocale(value);
  preferences.selectedLanguage = value;
}
const isImage = (url: Value) =>
  typeof url === 'string' && /\.(png|jpe?g|webp|gif|ico|svg)(\?|$)/i.test(url);
watch(
  () => props.record.id,
  () => (advanced.value = false),
);
</script>
<template>
  <div v-if="hasLocalizedFields" class="ve-language">
    <span>正在编辑</span>
    <div>
      <button :aria-pressed="locale === 'zh'" @click="language('zh')">中文</button
      ><button :aria-pressed="locale === 'en'" @click="language('en')">English</button>
    </div>
  </div>
  <div
    v-for="field in fields"
    :key="record.id + field.name"
    class="ve-field"
    :class="{ 've-field-focused': focusField === field.name }"
    :data-field="field.name"
  >
    <label :for="'ve-' + field.name"
      >{{ field.label.replace(/（中文）|（英文）/g, '')
      }}<span v-if="field.required" class="ve-required"> *</span></label
    >
    <template v-if="field.type === 'asset'">
      <button
        class="ve-asset"
        @click="
          openMedia((url) => update(field.name, url), categoryForRecord(record.kind, field.name))
        "
      >
        <img
          v-if="isImage(record.data[field.name]!)"
          :src="String(record.data[field.name])"
          alt="当前图片"
        /><span v-else>{{ record.data[field.name] ? '已选择文件' : '选择照片或文件' }}</span
        ><b>{{ record.data[field.name] ? '替换素材' : '＋ 上传或选择' }}</b>
      </button>
      <div class="ve-field-line">
        <input
          :id="'ve-' + field.name"
          :value="record.data[field.name]"
          aria-label="素材地址"
          placeholder="也可以粘贴图片 / PDF 地址"
          @input="input(field, $event)"
        /><button
          v-if="record.data[field.name] && !field.required"
          class="ve-icon"
          aria-label="清空素材"
          @click="update(field.name, '')"
        >
          ×
        </button>
      </div>
    </template>
    <div v-else-if="field.type === 'rich'" class="ve-rich">
      <RichTextEditor
        :key="record.id + field.name"
        :initial="String(record.data[field.name] || '')"
        :on-update="(html) => update(field.name, html)"
        :select-image="
          (callback) => openMedia((url) => callback(url, ''), categoryForRecord(record.kind))
        "
      />
    </div>
    <textarea
      v-else-if="field.type === 'textarea'"
      :id="'ve-' + field.name"
      :value="String(record.data[field.name] || '')"
      rows="4"
      @input="input(field, $event)"
    ></textarea>
    <label v-else-if="field.type === 'boolean'" class="ve-toggle"
      ><input
        :id="'ve-' + field.name"
        type="checkbox"
        :checked="Boolean(record.data[field.name])"
        @change="input(field, $event)"
      /><span>{{ record.data[field.name] ? '已开启' : '未开启' }}</span></label
    >
    <select
      v-else-if="field.type === 'choice'"
      :id="'ve-' + field.name"
      :value="record.data[field.name]"
      @change="input(field, $event)"
    >
      <option v-for="[value, label] in field.choices" :key="value" :value="value">
        {{ choiceLabel(field, value, label) }}
      </option>
    </select>
    <select
      v-else-if="field.type === 'reference'"
      :id="'ve-' + field.name"
      :value="record.data[field.name]"
      @change="input(field, $event)"
    >
      <option value="">请选择</option>
      <option v-for="item in choices(field)" :key="item.id" :value="item.id">
        {{ store.title(item) }}
      </option>
    </select>
    <div v-else-if="field.type === 'references'">
      <div v-if="record.kind === 'home'" class="ve-selected-references">
        <div v-for="(item, index) in selectedReferences(field)" :key="item!.id">
          <span>{{ index + 1 }}. {{ store.title(item!) }}</span>
          <button :disabled="index === 0" @click="moveReference(field.name, index, -1)">
            上移
          </button>
          <button
            :disabled="index === selectedReferences(field).length - 1"
            @click="moveReference(field.name, index, 1)"
          >
            下移
          </button>
          <button @click="references(field.name, item!.id, false)">移除</button>
        </div>
        <p v-if="!selectedReferences(field).length" class="ve-muted">
          从下面勾选要在首页展示的内容。
        </p>
      </div>
      <input
        v-model="referenceQueries[field.name]"
        :aria-label="'搜索' + field.label"
        placeholder="搜索名称…"
      />
      <div class="ve-references">
        <label v-for="item in matchingReferences(field)" :key="item.id"
          ><input
            type="checkbox"
            :checked="((record.data[field.name] as string[]) || []).includes(item.id)"
            @change="references(field.name, item.id, ($event.target as HTMLInputElement).checked)"
          /><span>{{ store.title(item) }}</span></label
        >
        <p v-if="!choices(field).length" class="ve-muted">先创建对应条目，再选择关联。</p>
      </div>
    </div>
    <div v-else-if="field.type === 'links'" class="ve-links">
      <div v-for="(link, index) in links(field.name)" :key="index" class="ve-link-row">
        <input
          :value="link.label"
          aria-label="链接文字"
          placeholder="PDF / 代码 / 演示"
          @input="updateLink(field.name, index, 'label', ($event.target as HTMLInputElement).value)"
        /><input
          :value="link.url"
          aria-label="链接地址"
          placeholder="https://…"
          @input="updateLink(field.name, index, 'url', ($event.target as HTMLInputElement).value)"
        />
        <div>
          <button
            class="ve-small"
            @click="openMedia((url) => updateLink(field.name, index, 'url', url), undefined, 'pdf')"
          >
            选择文件</button
          ><button
            class="ve-small ve-danger-text"
            @click="
              update(
                field.name,
                links(field.name).filter((_, i) => i !== index),
              )
            "
          >
            移除
          </button>
        </div>
      </div>
      <button
        class="ve-button ve-wide"
        @click="update(field.name, [...links(field.name), { label: '', url: '' }])"
      >
        ＋ 添加链接
      </button>
    </div>
    <input
      v-else
      :id="'ve-' + field.name"
      :type="
        field.type === 'date'
          ? 'date'
          : ['integer', 'year'].includes(field.type)
            ? 'number'
            : 'text'
      "
      :value="record.data[field.name]"
      :min="field.min_value"
      :max="field.max_value"
      @input="input(field, $event)"
    />
    <small v-if="field.help">{{ field.help }}</small>
  </div>
  <button v-if="extra" class="ve-expand" :aria-expanded="advanced" @click="advanced = !advanced">
    {{ advanced ? '收起更多字段' : record.kind === 'publication' ? '更多发表信息' : '更多设置' }}
    <UiIcon :name="advanced ? 'arrow-up' : 'arrow-down'" />
  </button>
  <div
    v-if="!['home', 'page', 'site'].includes(record.kind)"
    class="ve-field ve-order-field"
    data-field="$order"
  >
    <label>显示位置</label>
    <p class="ve-muted">当前在本组第 {{ placement.index + 1 }} 位，共 {{ placement.total }} 项。</p>
    <div class="ve-order-actions">
      <button class="ve-button" :disabled="placement.index <= 0" @click="store.move(record, 'up')">
        <UiIcon name="arrow-up" /> 上移
      </button>
      <button
        class="ve-button"
        :disabled="placement.index >= placement.total - 1"
        @click="store.move(record, 'down')"
      >
        <UiIcon name="arrow-down" /> 下移
      </button>
      <button class="ve-button" :disabled="placement.index <= 0" @click="store.move(record, 'top')">
        置顶
      </button>
      <button
        v-if="record.kind !== 'photo'"
        class="ve-button"
        :disabled="placement.total < 2"
        @click="store.move(record, 'auto')"
      >
        自动位置
      </button>
    </div>
    <small v-if="record.kind === 'news'"
      >新闻始终按日期从新到旧排列。以上操作只调整同一天内的顺序；自动位置恢复最近保存的组内位置，新条目放到当天末尾。</small
    >
    <small v-else-if="record.kind === 'publication'"
      >论文始终按年份从新到旧排列。以上操作只调整同一年内的顺序；自动位置恢复最近保存的组内位置，新条目放到当年末尾。</small
    >
    <small v-else-if="record.kind === 'person'"
      >以上操作调整同一成员分组的顺序；自动位置恢复最近保存的组内位置，新条目放到本组末尾。</small
    >
    <small v-else-if="record.kind !== 'photo'">自动位置恢复最近保存的顺序；新条目放到末尾。</small>
    <small>顺序变化涉及的条目会一起标为未保存，保存草稿后再统一发布。</small>
  </div>
  <MediaPicker
    v-if="chooseMedia"
    :aspect="mediaAspect"
    :initial-category="chooseCategory"
    :initial-type="chooseType"
    @select="
      (url) => {
        chooseMedia?.(url);
        chooseMedia = null;
      }
    "
    @close="chooseMedia = null"
  />
</template>
