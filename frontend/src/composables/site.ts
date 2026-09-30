// designed by mew
import { storeToRefs } from 'pinia';
import { editorRequested } from '../editor/target';
import { pinia } from '../stores';
import { useContentStore } from '../stores/content';
import type { SiteContent, Page } from '../types/content';

const store = useContentStore(pinia);
export const content = store.content;
export const { loaded, loadError, preview } = storeToRefs(store);
export const loadSite = store.loadSite;
export function setting<K extends 'site' | 'home'>(kind: K): SiteContent[K][number] {
  return content[kind][0];
}
export const pageContent = (slug: string): Partial<Page> =>
  content.page.find((page) => page.slug === slug) || {};
export function heroAssetUrl(path: string): string {
  return path === '/assets/campus-film.mp4' || path === '/assets/campus-hero.jpg'
    ? `${path}?v=20260923-1`
    : path;
}
export function localHref(path: string): string {
  if ((!preview.value && !editorRequested.value) || !path.startsWith('/') || path.startsWith('//'))
    return path;
  const url = new URL(path, location.origin);
  url.searchParams.set(editorRequested.value ? 'edit' : 'preview', '1');
  return url.pathname + url.search + url.hash;
}
