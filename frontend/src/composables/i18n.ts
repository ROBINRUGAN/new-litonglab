// designed by mew
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { content } from './site';
import { pinia } from '../stores';
import { usePreferencesStore } from '../stores/preferences';
import fallback from '../../../content/seed/interface.json';
const preferences = usePreferencesStore(pinia);
export const { locale } = storeToRefs(preferences);
export const setLocale = preferences.setLocale;
const dictionary = computed<Record<string, string>>(() =>
  Object.fromEntries(
    content.text.map((row) => [
      row.source,
      row[('value_' + locale.value) as 'value_en' | 'value_zh'] || row.source,
    ]),
  ),
);
export function t(source: unknown): string {
  const value = String(source ?? '');
  if (dictionary.value[value] !== undefined) return dictionary.value[value];
  const direct = (fallback[locale.value] as Record<string, string>)[value];
  if (direct !== undefined) return direct;
  if (locale.value === 'zh') {
    const photo = value.match(/^(\d{4}) (Spring|Autumn)$/);
    if (photo) return `${photo[1]} 年${photo[2] === 'Spring' ? '春季' : '秋季'}`;
  }
  return value;
}
export function pick(record: object | undefined | null, key: string): string {
  if (!record) return '';
  const values = record as Record<string, unknown>;
  const value =
    values[key + '_' + locale.value] ||
    values[key + '_' + (locale.value === 'zh' ? 'en' : 'zh')] ||
    values[key];
  return typeof value === 'string' ? value : '';
}
