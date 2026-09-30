// designed by mew
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import { TableKit } from '@tiptap/extension-table';
import { shallowRef } from 'vue';
import type { EditRecord } from './types';
import type { useEditorStore } from './store';
export const richEditor = shallowRef<Editor | null>(null);
let cleanup: (() => void) | undefined;
export function stopInline() {
  cleanup?.();
  cleanup = undefined;
}
export function startInline(
  element: HTMLElement,
  record: EditRecord,
  field: string,
  store: ReturnType<typeof useEditorStore>,
) {
  stopInline();
  const spec = store.schemas[record.kind].find((f) => f.name === field);
  if (!spec) return;
  element.classList.add('ve-inline-active');
  if (spec.type === 'rich') {
    const original = String(record.data[field] || '');
    element.innerHTML = '';
    const editor = new Editor({
      element,
      content: original,
      extensions: [StarterKit.configure({ link: { openOnClick: false } }), Image, TableKit],
      editorProps: {
        attributes: { class: 've-inline-rich', role: 'textbox', 'aria-label': spec.label },
      },
      onUpdate: ({ editor }) => store.update(record, field, editor.getHTML(), false),
    });
    richEditor.value = editor;
    editor.commands.focus('end');
    cleanup = () => {
      editor.destroy();
      richEditor.value = null;
      element.innerHTML = String(record.data[field] || '');
      element.classList.remove('ve-inline-active');
      store.paint(record);
    };
  } else {
    // Keep Vue's text nodes intact while the browser edits its own temporary node.
    // Restoring them before painting lets later undo/language updates patch the real DOM.
    const originalNodes = Array.from(element.childNodes);
    element.replaceChildren(document.createTextNode(element.textContent || ''));
    const originalTab = element.getAttribute('tabindex');
    element.contentEditable = 'plaintext-only';
    element.tabIndex = 0;
    element.setAttribute('role', 'textbox');
    element.setAttribute('aria-label', spec.label);
    const input = () => store.update(record, field, element.innerText.replace(/\r/g, ''), false);
    const paste = (event: ClipboardEvent) => {
      event.preventDefault();
      const text = event.clipboardData?.getData('text/plain') || '';
      const selection = getSelection();
      if (!selection?.rangeCount) return;
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const node = document.createTextNode(text);
      range.insertNode(node);
      range.setStartAfter(node);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
      input();
    };
    element.addEventListener('input', input);
    element.addEventListener('paste', paste);
    element.focus();
    cleanup = () => {
      element.removeEventListener('input', input);
      element.removeEventListener('paste', paste);
      element.replaceChildren(...originalNodes);
      element.removeAttribute('contenteditable');
      element.removeAttribute('role');
      element.removeAttribute('aria-label');
      if (originalTab === null) element.removeAttribute('tabindex');
      else element.setAttribute('tabindex', originalTab);
      element.classList.remove('ve-inline-active');
      store.paint(record);
    };
  }
}
