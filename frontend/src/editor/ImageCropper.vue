<!-- designed by mew -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';

const props = defineProps<{ file: File; aspect?: number }>();
const emit = defineEmits<{ save: [file: File]; original: []; cancel: [] }>();
type Rect = { x: number; y: number; w: number; h: number };
const source = URL.createObjectURL(props.file);
const image = ref<HTMLImageElement | null>(null);
const stage = ref<HTMLElement | null>(null);
const selection = ref<Rect>({ x: 0, y: 0, w: 1, h: 1 });
const ratio = ref(props.aspect ? String(props.aspect) : 'free');
const ratios = computed(() => {
  const presets = [
    ['free', '自由'],
    ['1', '1:1'],
    ['1.333333', '4:3'],
    ['1.777778', '16:9'],
    ['1.85', '合照 1.85:1'],
  ];
  return props.aspect
    ? [
        [String(props.aspect), '页面比例'],
        ...presets.filter(([value]) => Math.abs(Number(value) - props.aspect!) > 0.01),
      ]
    : presets;
});
const working = ref(false);
const error = ref('');
let origin: { x: number; y: number } | null = null;
onBeforeUnmount(() => URL.revokeObjectURL(source));

const frameStyle = computed(() => ({
  left: `${selection.value.x * 100}%`,
  top: `${selection.value.y * 100}%`,
  width: `${selection.value.w * 100}%`,
  height: `${selection.value.h * 100}%`,
}));
function setRatio(value: string) {
  ratio.value = value;
  if (!image.value) return;
  const target = Number(value);
  if (!target) {
    selection.value = { x: 0, y: 0, w: 1, h: 1 };
    return;
  }
  const imageRatio = image.value.naturalWidth / image.value.naturalHeight;
  const w = Math.min(1, target / imageRatio);
  const h = Math.min(1, imageRatio / target);
  selection.value = { x: (1 - w) / 2, y: (1 - h) / 2, w, h };
}
function point(event: PointerEvent) {
  const bounds = stage.value!.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
    y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
  };
}
function begin(event: PointerEvent) {
  if (!stage.value) return;
  origin = point(event);
  stage.value.setPointerCapture(event.pointerId);
}
function move(event: PointerEvent) {
  if (!origin || !stage.value) return;
  const current = point(event);
  const bounds = stage.value.getBoundingClientRect();
  const signX = current.x >= origin.x ? 1 : -1;
  const signY = current.y >= origin.y ? 1 : -1;
  let width = Math.abs(current.x - origin.x) * bounds.width;
  let height = Math.abs(current.y - origin.y) * bounds.height;
  const fixedRatio = Number(ratio.value);
  if (fixedRatio) {
    if (width / Math.max(height, 1) > fixedRatio) height = width / fixedRatio;
    else width = height * fixedRatio;
    const availableWidth = (signX > 0 ? 1 - origin.x : origin.x) * bounds.width;
    const availableHeight = (signY > 0 ? 1 - origin.y : origin.y) * bounds.height;
    const scale = Math.min(1, availableWidth / width, availableHeight / height);
    width *= scale;
    height *= scale;
  }
  if (width < 8 || height < 8) return;
  const w = width / bounds.width;
  const h = height / bounds.height;
  selection.value = {
    x: signX > 0 ? origin.x : origin.x - w,
    y: signY > 0 ? origin.y : origin.y - h,
    w,
    h,
  };
}
function end() {
  origin = null;
}
async function save() {
  if (!image.value || working.value) return;
  working.value = true;
  try {
    const rect = selection.value;
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.value.naturalWidth * rect.w));
    canvas.height = Math.max(1, Math.round(image.value.naturalHeight * rect.h));
    canvas
      .getContext('2d')!
      .drawImage(
        image.value,
        image.value.naturalWidth * rect.x,
        image.value.naturalHeight * rect.y,
        image.value.naturalWidth * rect.w,
        image.value.naturalHeight * rect.h,
        0,
        0,
        canvas.width,
        canvas.height,
      );
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (result) => (result ? resolve(result) : reject(new Error('图片裁切失败'))),
        'image/webp',
        0.9,
      ),
    );
    emit(
      'save',
      new File([blob], props.file.name.replace(/\.[^.]+$/, '') + '-crop.webp', { type: blob.type }),
    );
  } catch {
    error.value = '图片裁切失败，请上传原图或重试。';
  } finally {
    working.value = false;
  }
}
</script>

<template>
  <div class="ve-cropper">
    <p>拖动框选需要显示的区域，或选择比例。裁切会生成新图片，原文件不会修改。</p>
    <div class="ve-crop-presets" role="group" aria-label="裁切比例">
      <button
        v-for="[value, label] in ratios"
        :key="value"
        :aria-pressed="ratio === value"
        @click="setRatio(value)"
      >
        {{ label }}
      </button>
    </div>
    <div class="ve-crop-area">
      <div
        ref="stage"
        class="ve-crop-stage"
        @pointerdown="begin"
        @pointermove="move"
        @pointerup="end"
        @pointercancel="end"
      >
        <img ref="image" :src="source" alt="待裁切图片" draggable="false" @load="setRatio(ratio)" />
        <div class="ve-crop-frame" :style="frameStyle"></div>
      </div>
    </div>
    <p v-if="error" class="ve-error" role="alert">{{ error }}</p>
    <div class="ve-crop-actions">
      <button class="ve-button" @click="emit('cancel')">返回素材库</button>
      <button class="ve-button" @click="emit('original')">上传原图</button>
      <button class="ve-button ve-primary" :disabled="working" @click="save">
        {{ working ? '正在裁切…' : '裁切并上传' }}
      </button>
    </div>
  </div>
</template>
