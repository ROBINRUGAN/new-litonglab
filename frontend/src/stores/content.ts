// designed by mew
import { defineStore } from 'pinia';
import { reactive, ref } from 'vue';
import axios from 'axios';
import { api } from '../api/client';
import type { SiteContent, SiteResponse } from '../types/content';

export const useContentStore = defineStore('content', () => {
  const content = reactive<SiteContent>({
    publication: [],
    person: [],
    group: [],
    photo: [],
    project: [],
    news: [],
    direction: [],
    venue: [],
    page: [],
    navigation: [],
    section: [],
    site: [],
    home: [],
    text: [],
  });
  const loaded = ref(false);
  const loadError = ref('');
  const preview = ref(new URLSearchParams(location.search).get('preview') === '1');

  async function loadSite() {
    loadError.value = '';
    try {
      const { data } = await api.get<SiteResponse>('site/', {
        params: preview.value ? { preview: '1' } : {},
      });
      if (data.schemaVersion !== 1 || !data.content.site.length || !data.content.home.length) {
        throw new Error('站点尚未初始化，或内容版本不兼容。');
      }
      Object.assign(content, data.content);
      loaded.value = true;
    } catch (error: unknown) {
      loadError.value =
        axios.isAxiosError(error) && error.response?.status === 403
          ? '草稿预览需要先登录后台。'
          : error instanceof Error && !axios.isAxiosError(error)
            ? error.message
            : '暂时无法读取内容，请稍后重试。';
    }
  }
  return { content, loaded, loadError, preview, loadSite };
});
