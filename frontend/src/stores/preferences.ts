// designed by mew
import { defineStore } from 'pinia';
import { ref } from 'vue';
export type Locale = 'en' | 'zh';
export type Theme = 'light' | 'dark';
export function storedPreference(key: string): string | null {
  try {
    return localStorage.getItem('litonglab-' + key);
  } catch {
    return null;
  }
}
export const usePreferencesStore = defineStore('preferences', () => {
  const locale = ref<Locale>(storedPreference('language') === 'zh' ? 'zh' : 'en');
  const selectedLanguage = ref<Locale>(locale.value);
  const theme = ref<Theme>(storedPreference('theme') === 'dark' ? 'dark' : 'light');
  function setLocale(value: Locale, persist = true) {
    locale.value = value;
    document.documentElement.lang = value === 'zh' ? 'zh-CN' : 'en';
    if (persist)
      try {
        localStorage.setItem('litonglab-language', value);
      } catch {
        /* Storage may be disabled. */
      }
  }
  function setTheme(value: Theme, persist = true) {
    theme.value = value;
    document.documentElement.dataset.theme = value;
    if (persist)
      try {
        localStorage.setItem('litonglab-theme', value);
      } catch {
        /* Storage may be disabled. */
      }
  }
  return { locale, selectedLanguage, theme, setLocale, setTheme };
});
