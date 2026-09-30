<!-- designed by mew -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { api } from '../api/client';
import { useEditorStore, errorMessage, recordKey } from './store';
import EditorDialog from './EditorDialog.vue';
import ImageCropper from './ImageCropper.vue';
import CarouselPhotoControls from './CarouselPhotoControls.vue';
import { imageCategories, type ImageCategory } from './mediaCategories';

interface Media {
  id: number;
  title: string;
  url: string;
  sourceUrl: string;
  type: string;
  category: ImageCategory;
  size: number;
  bundled: boolean;
  inUse: boolean;
}
const props = defineProps<{
  manage?: boolean;
  aspect?: number;
  initialCategory?: ImageCategory;
  initialType?: 'image' | 'video' | 'pdf';
}>();
const emit = defineEmits<{ select: [url: string]; close: [] }>();
const store = useEditorStore();
const mediaType = ref<string>(props.initialType || 'image');
const imageCategory = ref<ImageCategory | ''>(props.initialCategory || '');
const uploadCategory = ref<ImageCategory>(props.initialCategory || 'other');
const query = ref('');
const items = ref<Media[]>([]);
const page = ref(1);
const more = ref(false);
const loading = ref(false);
const error = ref('');
const cropFile = ref<File | null>(null);
const renaming = ref<number | null>(null);
const title = ref('');
const deleting = ref<number | null>(null);
const notice = ref('');
const canEditPhotos = computed(() => store.kinds.some((kind) => kind.key === 'photo'));
const photoChanges = computed(() => store.unpublished.filter((record) => record.kind === 'photo'));
const photoPending = computed(() => store.pending.filter((record) => record.kind === 'photo'));
const sortedItems = computed(() => {
  if (!props.manage || imageCategory.value !== 'group-photo') return items.value;
  return [...items.value].sort((a, b) => {
    const left = photoRecord(a),
      right = photoRecord(b);
    const leftActive = left && (left.data.show_home || left.data.show_people);
    const rightActive = right && (right.data.show_home || right.data.show_people);
    return (
      Number(Boolean(rightActive)) - Number(Boolean(leftActive)) ||
      (leftActive && rightActive
        ? left.order - right.order || left.id.localeCompare(right.id)
        : b.id - a.id)
    );
  });
});
const draftReferences = computed(() =>
  JSON.stringify(store.records.filter((record) => !record.deleted).map((record) => record.data)),
);

async function load(reset = false) {
  if (reset) page.value = 1;
  loading.value = true;
  error.value = '';
  try {
    const { data } = await api.get<{ items: Media[]; more: boolean }>('media/', {
      params: {
        q: query.value,
        page: page.value,
        type: mediaType.value,
        category: mediaType.value === 'image' ? imageCategory.value : '',
      },
    });
    items.value = data.items;
    more.value = data.more;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
async function uploadFile(file: File) {
  loading.value = true;
  error.value = '';
  try {
    const data = new FormData();
    data.append('file', file);
    data.append('title', file.name);
    data.append('category', mediaType.value === 'image' ? uploadCategory.value : 'other');
    const result = await api.post<Media>('media/upload/', data, {
      headers: { 'X-CSRFToken': store.csrfToken },
      timeout: 120000,
    });
    cropFile.value = null;
    if (props.manage) {
      query.value = '';
      mediaType.value = result.data.type.startsWith('image/')
        ? 'image'
        : result.data.type.startsWith('video/')
          ? 'video'
          : 'pdf';
      if (mediaType.value === 'image') imageCategory.value = result.data.category;
      await load(true);
      if (!items.value.some((item) => item.id === result.data.id)) items.value.unshift(result.data);
      notice.value =
        result.data.category === 'group-photo' ? '上传完成，可勾选首页或成员页轮播。' : '上传完成';
    } else emit('select', result.data.url);
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
function chooseCategory(value: ImageCategory | '') {
  imageCategory.value = value;
  uploadCategory.value = value || 'other';
  void load(true);
}
function upload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  if (/\.(jpe?g|png|webp)$/i.test(file.name)) cropFile.value = file;
  else void uploadFile(file);
}
function beginRename(item: Media) {
  deleting.value = null;
  renaming.value = item.id;
  title.value = item.title;
}
async function rename(item: Media) {
  const value = title.value.trim();
  if (!value) {
    error.value = '请输入素材名称。';
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const result = await api.patch<Media>(
      `media/${item.id}/`,
      { title: value },
      {
        headers: { 'X-CSRFToken': store.csrfToken },
      },
    );
    Object.assign(item, result.data);
    renaming.value = null;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
async function changeCategory(item: Media, event: Event) {
  const select = event.target as HTMLSelectElement;
  const value = select.value as ImageCategory;
  loading.value = true;
  error.value = '';
  try {
    await api.patch(
      `media/${item.id}/`,
      { category: value },
      { headers: { 'X-CSRFToken': store.csrfToken } },
    );
    await load();
  } catch (e) {
    select.value = item.category;
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
async function remove(item: Media) {
  loading.value = true;
  error.value = '';
  try {
    await api.delete(`media/${item.id}/`, {
      headers: { 'X-CSRFToken': store.csrfToken },
    });
    deleting.value = null;
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
function inCurrentDraft(item: Media) {
  return (
    draftReferences.value.includes(item.url) ||
    !!(item.sourceUrl && draftReferences.value.includes(item.sourceUrl))
  );
}
function photoRecord(item: Media) {
  return store.records.find(
    (record) =>
      record.kind === 'photo' &&
      !record.deleted &&
      (record.data.image === item.url ||
        (!!item.sourceUrl && record.data.image === item.sourceUrl)),
  );
}
async function savePhotos(action: 'draft' | 'publish') {
  error.value = '';
  notice.value = '';
  try {
    await store.save(action, action === 'publish' ? photoChanges.value : photoPending.value);
    notice.value = action === 'publish' ? '合照轮播已发布' : '合照草稿已保存';
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  }
}
function mediaLabel(item: Media) {
  if (item.type.startsWith('video/')) return '视频';
  if (item.type === 'application/pdf') return 'PDF';
  return '文件';
}
onMounted(() => load());
</script>

<template>
  <EditorDialog :title="manage ? '素材库' : '选择或上传素材'" wide @close="emit('close')">
    <ImageCropper
      v-if="cropFile"
      :file="cropFile"
      :aspect="aspect"
      @cancel="cropFile = null"
      @original="uploadFile(cropFile!)"
      @save="uploadFile"
    />
    <template v-else>
      <div class="ve-library-tabs">
        <button
          v-for="[value, label] in [
            ['image', '图片'],
            ['video', '视频'],
            ['pdf', 'PDF'],
            ['', '全部'],
          ]"
          :key="value"
          :aria-pressed="mediaType === value"
          @click="
            mediaType = value;
            load(true);
          "
        >
          {{ label }}
        </button>
      </div>
      <div v-if="mediaType === 'image'" class="ve-library-subtabs" aria-label="图片分类">
        <button :aria-pressed="imageCategory === ''" @click="chooseCategory('')">全部图片</button>
        <button
          v-for="[value, label] in imageCategories"
          :key="value"
          :aria-pressed="imageCategory === value"
          @click="chooseCategory(value)"
        >
          {{ label }}
        </button>
      </div>
      <form class="ve-media-search" @submit.prevent="load(true)">
        <input v-model="query" aria-label="搜索素材" placeholder="搜索图片、视频、PDF…" />
        <button class="ve-button" :disabled="loading">搜索</button>
        <label v-if="mediaType === 'image'" class="ve-upload-category"
          >上传到
          <select v-model="uploadCategory" aria-label="上传素材分类">
            <option v-for="[value, label] in imageCategories" :key="value" :value="value">
              {{ label }}
            </option>
          </select>
        </label>
        <label class="ve-button ve-primary"
          >上传文件
          <input
            type="file"
            hidden
            accept=".jpg,.jpeg,.png,.webp,.gif,.ico,.mp4,.pdf"
            :disabled="loading"
            @change="upload"
          />
        </label>
      </form>
      <p class="ve-muted">
        上传图片时可先框选显示区域。内置素材随网站发布；未使用的上传文件可删除。
      </p>
      <div
        v-if="manage && canEditPhotos && mediaType === 'image' && imageCategory === 'group-photo'"
        class="ve-carousel-toolbar"
      >
        <span>勾选展示位置，调整轮播顺序。</span>
        <button
          class="ve-button"
          :disabled="store.busy || loading || !photoPending.length"
          @click="savePhotos('draft')"
        >
          保存合照草稿
        </button>
        <button
          v-if="store.user?.canPublish"
          class="ve-button ve-primary"
          :disabled="store.busy || loading || !photoChanges.length"
          @click="savePhotos('publish')"
        >
          发布合照<span v-if="photoChanges.length"> ({{ photoChanges.length }})</span>
        </button>
      </div>
      <p v-if="notice" class="ve-muted" role="status">{{ notice }}</p>
      <p v-if="error" class="ve-error" role="alert">{{ error }}</p>
      <p v-if="loading" class="ve-muted" role="status">正在处理素材…</p>
      <div
        v-else
        class="ve-media-grid"
        :class="{ 've-media-grid-carousel': manage && imageCategory === 'group-photo' }"
      >
        <div
          v-for="item in sortedItems"
          :key="item.id"
          class="ve-media-card"
          :class="{
            've-media-card-pending':
              photoRecord(item) && store.dirty.has(recordKey(photoRecord(item)!)),
          }"
        >
          <button
            v-if="!manage"
            class="ve-media-select"
            :aria-label="`选用 ${item.title}`"
            @click="emit('select', item.url)"
          >
            <img
              v-if="item.type.startsWith('image/')"
              :src="item.url"
              :alt="item.title"
              loading="lazy"
            />
            <span v-else class="ve-file">{{ mediaLabel(item) }}</span>
          </button>
          <a
            v-else
            class="ve-media-select"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="`预览 ${item.title}`"
          >
            <img
              v-if="item.type.startsWith('image/')"
              :src="item.url"
              :alt="item.title"
              loading="lazy"
            />
            <span v-else class="ve-file">{{ mediaLabel(item) }}</span>
          </a>
          <form v-if="renaming === item.id" class="ve-media-rename" @submit.prevent="rename(item)">
            <input v-model="title" aria-label="新素材名称" maxlength="200" autofocus />
            <button type="submit">保存</button>
            <button type="button" @click="renaming = null">取消</button>
          </form>
          <span v-else class="ve-media-title" :title="item.title">{{ item.title }}</span>
          <label
            v-if="manage && item.type.startsWith('image/') && item.category !== 'group-photo'"
            class="ve-media-category"
          >
            分类
            <select
              :value="item.category"
              :disabled="loading"
              @change="changeCategory(item, $event)"
            >
              <option v-for="[value, label] in imageCategories" :key="value" :value="value">
                {{ label }}
              </option>
            </select>
          </label>
          <CarouselPhotoControls
            v-if="
              manage &&
              canEditPhotos &&
              item.type.startsWith('image/') &&
              item.category === 'group-photo'
            "
            :media="item"
          />
          <div class="ve-media-actions">
            <button @click="beginRename(item)">重命名</button>
            <button v-if="deleting === item.id" class="ve-danger-text" @click="remove(item)">
              确认删除
            </button>
            <button
              v-else-if="!item.bundled"
              class="ve-danger-text"
              :disabled="item.inUse || !!inCurrentDraft(item)"
              :title="
                item.inUse || inCurrentDraft(item)
                  ? '正在使用，请先替换引用'
                  : '删除未使用的上传文件'
              "
              @click="deleting = item.id"
            >
              删除
            </button>
          </div>
        </div>
      </div>
      <p v-if="!loading && !items.length" class="ve-muted">没有找到素材，可以上传新文件。</p>
      <footer class="ve-dialog-footer">
        <button
          class="ve-button"
          :disabled="page <= 1 || loading"
          @click="
            page--;
            load();
          "
        >
          上一页
        </button>
        <span>第 {{ page }} 页</span>
        <button
          class="ve-button"
          :disabled="!more || loading"
          @click="
            page++;
            load();
          "
        >
          下一页
        </button>
      </footer>
    </template>
  </EditorDialog>
</template>
