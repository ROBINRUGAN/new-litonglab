<!-- designed by mew -->
<script setup lang="ts">
import { onBeforeUnmount } from 'vue';
import { EditorContent, useEditor } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import { TableKit } from '@tiptap/extension-table';

const props = defineProps<{
  initial: string;
  onUpdate: (html: string) => void;
  selectImage: (callback: (url: string, title: string) => void) => void;
}>();
const editor = useEditor({
  content: props.initial,
  extensions: [
    StarterKit.configure({
      link: {
        openOnClick: false,
        HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
      },
    }),
    Image,
    TableKit,
  ],
  editorProps: {
    attributes: {
      class: 'rich-editor',
      role: 'textbox',
      'aria-multiline': 'true',
      'aria-label': '正文编辑器',
    },
  },
  onUpdate: ({ editor }) => props.onUpdate(editor.getHTML()),
});
function addLink() {
  const url = prompt(
    '输入链接地址（https:// 或站内路径）：',
    editor.value?.getAttributes('link').href || '',
  );
  if (url === null) return;
  if (!url) editor.value?.chain().focus().unsetLink().run();
  else editor.value?.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
}
onBeforeUnmount(() => editor.value?.destroy());
</script>
<template>
  <div v-if="editor" class="rich-toolbar">
    <button type="button" @click="editor.chain().focus().setParagraph().run()">正文</button>
    <button type="button" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()">
      二级标题
    </button>
    <button type="button" @click="editor.chain().focus().toggleHeading({ level: 3 }).run()">
      三级标题
    </button>
    <button
      type="button"
      :aria-pressed="editor.isActive('bold')"
      @click="editor.chain().focus().toggleBold().run()"
    >
      粗体
    </button>
    <button
      type="button"
      :aria-pressed="editor.isActive('italic')"
      @click="editor.chain().focus().toggleItalic().run()"
    >
      斜体
    </button>
    <button type="button" @click="editor.chain().focus().toggleBulletList().run()">列表</button>
    <button type="button" @click="editor.chain().focus().toggleOrderedList().run()">编号</button>
    <button type="button" @click="addLink">链接</button>
    <button
      type="button"
      @click="selectImage((src, alt) => editor?.chain().focus().setImage({ src, alt }).run())"
    >
      图片
    </button>
    <button
      type="button"
      @click="editor.chain().focus().insertTable({ rows: 3, cols: 2, withHeaderRow: true }).run()"
    >
      表格
    </button>
    <template v-if="editor.isActive('table')">
      <button type="button" @click="editor.chain().focus().addRowAfter().run()">加一行</button>
      <button type="button" @click="editor.chain().focus().addColumnAfter().run()">加一列</button>
      <button type="button" @click="editor.chain().focus().deleteRow().run()">删行</button>
      <button type="button" @click="editor.chain().focus().deleteColumn().run()">删列</button>
      <button type="button" @click="editor.chain().focus().deleteTable().run()">删除表格</button>
    </template>
    <button type="button" @click="editor.chain().focus().undo().run()">撤销</button>
    <button type="button" @click="editor.chain().focus().redo().run()">重做</button>
  </div>
  <EditorContent :editor="editor" />
</template>
