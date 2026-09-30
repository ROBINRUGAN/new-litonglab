// designed by mew
/** Tiny public-page annotation layer; the editor itself is lazy-loaded. */
import { ref, type ObjectDirective } from 'vue';
import type { EditBinding } from './types';
export const editorRequested = ref(new URLSearchParams(location.search).get('edit') === '1');
export const canvasEditing = ref(false);
export const editDirective: ObjectDirective<HTMLElement, EditBinding> = {
  mounted: annotate,
  updated: annotate,
};
function annotate(element: HTMLElement, binding: { value: EditBinding }) {
  const [kind, id, field] = binding.value;
  if (!id) return;
  element.dataset.editKind = kind;
  element.dataset.editId = id;
  if (field) element.dataset.editField = field;
  else delete element.dataset.editField;
}
