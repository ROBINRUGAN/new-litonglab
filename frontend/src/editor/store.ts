// designed by mew
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import { api } from '../api/client';
import { locale } from '../composables/i18n';
import { useContentStore } from '../stores/content';
import type { ContentKind } from '../types/content';
import type { ChangeStage, EditRecord, EditorSnapshot, FieldChange, Value } from './types';
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));
const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const empty = (value: unknown) =>
  value == null ||
  value === '' ||
  value === false ||
  value === 0 ||
  (Array.isArray(value) && value.length === 0);
const sameValue = (left: unknown, right: unknown) =>
  (empty(left) && empty(right)) || equal(left, right);
export const recordKey = (record: Pick<EditRecord, 'kind' | 'id'>) => record.kind + ':' + record.id;
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const errors = error.response?.data?.errors;
    if (errors)
      return Array.isArray(errors) ? errors.join('；') : Object.values(errors).flat().join('；');
    if (error.response?.status === 403) return '登录已失效或没有权限。请重新登录后再试。';
    return '连接失败，当前修改仍保留在页面中，请稍后重试。';
  }
  return error instanceof Error ? error.message : '操作未完成，请重试。';
}
export const useEditorStore = defineStore('visual-editor', () => {
  const site = useContentStore();
  const user = ref<EditorSnapshot['user']>(null);
  const kinds = ref<EditorSnapshot['kinds']>([]);
  const schemas = ref<EditorSnapshot['schemas']>({} as EditorSnapshot['schemas']);
  const records = ref<EditRecord[]>([]);
  const dirty = ref<Set<string>>(new Set());
  const touched = ref<Set<string>>(new Set());
  const busy = ref(false);
  const ready = ref(false);
  const csrfToken = ref('');
  const baselines = new Map<string, EditRecord>();
  const initialOrders = new Map<string, number>();
  const pending = computed(() => records.value.filter((r) => dirty.value.has(recordKey(r))));
  const unpublished = computed(() =>
    records.value.filter((record) => {
      if (record.deleted) return false;
      if (!record.liveData) return true;
      return (
        record.order !== record.liveOrder ||
        (schemas.value[record.kind] || []).some(
          (field) => !sameValue(record.data[field.name], record.liveData?.[field.name]),
        )
      );
    }),
  );
  const title = (record: EditRecord) => {
    if (record.kind === 'home') return '首页展示';
    if (record.kind === 'page') return '加入我们';
    if (record.kind === 'site') return '联系信息';
    const localized =
      locale.value === 'en'
        ? [record.data.title_en, record.data.name_en, record.data.title_zh, record.data.name_zh]
        : [record.data.title_zh, record.data.name_zh, record.data.title_en, record.data.name_en];
    return String(
      record.data.title || localized.find(Boolean) || record.data.source || '未命名条目',
    );
  };
  const find = (kind: ContentKind, id: string) =>
    records.value.find((r) => r.kind === kind && r.id === id);
  function paint(record: EditRecord) {
    const rows = site.content[record.kind] as unknown as Record<string, unknown>[];
    const index = rows.findIndex((r) => r.id === record.id);
    if (record.deleted) {
      if (index >= 0) rows.splice(index, 1);
      return;
    }
    const next = {
      ...(index >= 0 ? rows[index] : {}),
      ...clone(record.data),
      id: record.id,
      order: record.order,
    };
    if (record.kind === 'publication') {
      const paper = next as Record<string, unknown>;
      const venue = find('venue', String(record.data.venue_key || ''));
      if (venue) {
        for (const [field, source] of Object.entries({
          venueShort: 'title',
          venueFull: 'full',
          ccfRating: 'rating',
          ccfEdition: 'edition',
          ccfSource: 'source',
          ratingNote: 'note',
        }))
          paper[field] = record.data[field] || venue.data[source] || '';
      }
      if (record.data.track) paper.ccfRating = 'unranked';
      if (record.data.category === 'Granted Patents') paper.ccfRating = '';
    }
    if (index >= 0) rows[index] = next;
    else rows.push(next);
    rows.sort((a, b) => Number(a.order) - Number(b.order));
    if (record.kind === 'venue')
      records.value
        .filter((r) => r.kind === 'publication' && r.data.venue_key === record.id)
        .forEach(paint);
    if (record.kind === 'news')
      rows.sort(
        (a, b) => String(b.date).localeCompare(String(a.date)) || Number(a.order) - Number(b.order),
      );
    if (record.kind === 'publication')
      rows.sort(
        (a, b) => String(b.year).localeCompare(String(a.year)) || Number(a.order) - Number(b.order),
      );
  }
  function absorb(data: EditorSnapshot, submitted: string[] = []) {
    const preserved = pending.value.filter((r) => !submitted.includes(recordKey(r))).map(clone);
    user.value = data.user;
    if (data.csrfToken) csrfToken.value = data.csrfToken;
    if (!data.user) return;
    kinds.value = data.kinds;
    schemas.value = data.schemas;
    records.value = data.records;
    baselines.clear();
    records.value.forEach((r) => baselines.set(recordKey(r), clone(r)));
    dirty.value = new Set(preserved.map(recordKey));
    Object.assign(site.content, data.content);
    site.preview = true;
    site.loaded = true;
    for (const record of preserved) {
      const index = records.value.findIndex((r) => recordKey(r) === recordKey(record));
      if (index >= 0) records.value[index] = record;
      else records.value.push(record);
      paint(record);
    }
    ready.value = true;
  }
  async function initialize() {
    const { data } = await api.get<EditorSnapshot>('editor/session/');
    absorb(data);
    if (!data.user) await site.loadSite();
    ready.value = true;
  }
  async function login(username: string, password: string) {
    const { data } = await api.post<EditorSnapshot>(
      'editor/login/',
      { username, password },
      { headers: { 'X-CSRFToken': csrfToken.value } },
    );
    absorb(data);
  }
  async function logout() {
    await api.post('editor/logout/', {}, { headers: { 'X-CSRFToken': csrfToken.value } });
    user.value = null;
    records.value = [];
    dirty.value.clear();
    touched.value.clear();
    baselines.clear();
    initialOrders.clear();
    site.preview = false;
    site.loaded = false;
    await site.loadSite();
    await initialize();
  }
  function mark(record: EditRecord) {
    const key = recordKey(record);
    const baseline = baselines.get(key);
    if (baseline && equal(record.data, baseline.data) && record.order === baseline.order)
      dirty.value.delete(key);
    else dirty.value.add(key);
    touched.value.add(key);
  }
  function update(record: EditRecord, field: string, value: Value, render = true) {
    record.data[field] = value;
    mark(record);
    if (render) paint(record);
  }
  function order(record: EditRecord, value: number) {
    record.order = value;
    mark(record);
    paint(record);
  }
  function orderGroup(record: EditRecord) {
    const key =
      record.kind === 'news'
        ? record.data.date
        : record.kind === 'publication'
          ? record.data.year
          : record.kind === 'person'
            ? record.data.group
            : '';
    return `${record.kind}:${key || ''}`;
  }
  function orderPeers(record: EditRecord) {
    return records.value
      .filter((row) => !row.deleted && orderGroup(row) === orderGroup(record))
      .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
  }
  function position(record: EditRecord) {
    const peers = orderPeers(record);
    return { index: peers.findIndex((row) => row.id === record.id), total: peers.length };
  }
  function move(record: EditRecord, action: 'up' | 'down' | 'top' | 'auto', scope?: EditRecord[]) {
    const peers = scope ? [...scope] : orderPeers(record);
    const index = peers.findIndex((row) => row.id === record.id);
    if (index < 0) return;
    const weights = peers.map((peer) => peer.order);
    const uniqueWeights = new Set(weights).size === weights.length;
    peers.splice(index, 1);
    const baselineWeight = (row: EditRecord) =>
      baselines.get(recordKey(row))?.order ?? Number.MAX_SAFE_INTEGER;
    const timeKey = record.data.date ? 'date' : record.data.year ? 'year' : null;
    const automatic = peers.findIndex((peer) => {
      if (timeKey) {
        const comparison = String(record.data[timeKey] || '').localeCompare(
          String(peer.data[timeKey] || ''),
        );
        if (comparison !== 0) return comparison > 0;
      }
      return baselineWeight(record) < baselineWeight(peer);
    });
    const next =
      action === 'top'
        ? 0
        : action === 'up'
          ? Math.max(0, index - 1)
          : action === 'down'
            ? Math.min(peers.length, index + 1)
            : automatic < 0
              ? peers.length
              : automatic;
    peers.splice(next, 0, record);
    // Reuse distinct positions, normalizing only old ties. Every affected row is saved.
    peers.forEach((row, index) => {
      const value = uniqueWeights ? weights[index]! : (index + 1) * 10;
      if (row.order !== value) order(row, value);
    });
  }
  function changes(record: EditRecord, stage: ChangeStage): FieldChange[] {
    const baseline = baselines.get(recordKey(record));
    const before = stage === 'unsaved' ? baseline?.data : baseline?.liveData;
    const after = stage === 'unsaved' ? record.data : baseline?.data;
    if (!after || (stage === 'saved' && !baseline?.hasDraft)) return [];
    const fields: FieldChange[] = (schemas.value[record.kind] || [])
      .filter((field) => {
        const previous = before?.[field.name],
          next = after[field.name];
        if (sameValue(previous, next)) return false;
        if (stage === 'saved' && sameValue(record.data[field.name], previous)) return false;
        if (previous !== undefined) return true;
        return (
          next != null &&
          next !== '' &&
          next !== false &&
          !(Array.isArray(next) && !next.length) &&
          !equal(next, field.default)
        );
      })
      .map((field) => ({
        field: field.name,
        label: field.label,
        before: before?.[field.name],
        after: after[field.name],
        stage,
      }));
    const beforeOrder = stage === 'unsaved' ? baseline?.order : baseline?.liveOrder;
    const afterOrder = stage === 'unsaved' ? record.order : baseline?.order;
    if (
      beforeOrder != null &&
      afterOrder != null &&
      beforeOrder !== afterOrder &&
      (stage !== 'saved' || record.order !== beforeOrder)
    ) {
      const rank = (previous: boolean) => {
        const peers = orderPeers(record)
          .map((peer) => {
            const saved = baselines.get(recordKey(peer));
            const value = previous
              ? stage === 'unsaved'
                ? saved?.order
                : saved?.liveOrder
              : stage === 'unsaved'
                ? peer.order
                : saved?.order;
            return { id: peer.id, order: value };
          })
          .filter((peer) => peer.order != null)
          .sort((a, b) => a.order! - b.order! || a.id.localeCompare(b.id));
        return `本组第 ${peers.findIndex((peer) => peer.id === record.id) + 1} 位`;
      };
      fields.push({
        field: '$order',
        label: '显示位置',
        before: rank(true),
        after: rank(false),
        stage,
      });
    }
    return fields;
  }
  const changeList = computed(() =>
    records.value
      .filter((record) => !record.deleted)
      .map((record) => ({
        record,
        unsaved: changes(record, 'unsaved'),
        saved: changes(record, 'saved'),
      }))
      .filter((entry) => entry.unsaved.length || entry.saved.length),
  );
  function restoreField(record: EditRecord, change: FieldChange) {
    if (change.field === '$order') {
      const peers = orderPeers(record);
      // Reverting a reorder restores the group together, preserving distinct positions.
      peers.forEach((row) => {
        const baseline = baselines.get(recordKey(row));
        const value =
          change.stage === 'unsaved'
            ? (baseline?.order ?? initialOrders.get(recordKey(row)))
            : baseline?.liveOrder;
        if (value != null) order(row, value);
      });
      return;
    }
    const spec = schemas.value[record.kind].find((field) => field.name === change.field);
    const value =
      change.before ??
      spec?.default ??
      (spec?.type === 'boolean'
        ? false
        : ['references', 'links'].includes(spec?.type || '')
          ? []
          : '');
    update(record, change.field, clone(value));
  }
  function formatValue(record: EditRecord, field: string, value: Value | undefined): string {
    if (field === '$order') return String(value || '自动位置');
    if (value === undefined || value === '' || (Array.isArray(value) && !value.length))
      return '未填写';
    if (typeof value === 'boolean') return value ? '开启' : '关闭';
    const spec = schemas.value[record.kind]?.find((candidate) => candidate.name === field);
    if (spec?.type === 'reference' && spec.target) {
      const related = find(spec.target, String(value));
      return related ? title(related) : String(value);
    }
    if (spec?.type === 'references' && Array.isArray(value))
      return (value as string[])
        .map((id) => (spec.target && find(spec.target, id) ? title(find(spec.target, id)!) : id))
        .join('、');
    if (spec?.type === 'choice')
      return spec.choices?.find(([key]) => key === value)?.[1] || String(value);
    if (Array.isArray(value))
      return value
        .map((row) => (typeof row === 'string' ? row : `${row.label}：${row.url}`))
        .join('\n');
    if (spec?.type === 'rich') {
      const document = new DOMParser().parseFromString(String(value), 'text/html');
      return document.body.textContent?.trim() || '空白正文';
    }
    return String(value);
  }
  function create(kind: ContentKind) {
    const fields = schemas.value[kind];
    const data = Object.fromEntries(
      fields.map((f) => [
        f.name,
        clone(
          f.default ??
            (f.type === 'boolean'
              ? false
              : ['links', 'references'].includes(f.type)
                ? []
                : f.type === 'choice'
                  ? (f.choices?.[0]?.[0] ?? '')
                  : ''),
        ),
      ]),
    );
    const record: EditRecord = {
      id: crypto.randomUUID(),
      kind,
      version: null,
      data,
      order: Math.max(0, ...records.value.filter((r) => r.kind === kind).map((r) => r.order)) + 10,
      deleted: false,
      published: false,
      hasDraft: true,
      state: '新草稿',
      liveData: null,
      liveOrder: null,
    };
    if (kind === 'person') {
      record.data.group =
        records.value.find(
          (item) => item.kind === 'group' && item.data.layout === 'cards' && !item.deleted,
        )?.id || '';
      record.data.image = '/images/person-placeholder.svg';
      record.data.placeholder = true;
    }
    records.value.push(record);
    initialOrders.set(recordKey(record), record.order);
    dirty.value.add(recordKey(record));
    touched.value.add(recordKey(record));
    // New incomplete records appear in the canvas after the first field edit.
    return record;
  }
  function discard(record: EditRecord) {
    const key = recordKey(record),
      original = baselines.get(key);
    if (original && original.order !== record.order)
      restoreField(record, {
        field: '$order',
        label: '显示位置',
        before: original.order,
        after: record.order,
        stage: 'unsaved',
      });
    dirty.value.delete(key);
    if (original) {
      const restored = clone(original);
      records.value.splice(records.value.indexOf(record), 1, restored);
      paint(restored);
    } else {
      const initialOrder = initialOrders.get(key);
      if (initialOrder != null && initialOrder !== record.order) {
        // Remove the temporary item's slot while retaining the other items' relative order.
        const peers = orderPeers(record);
        const weights = peers.map((peer) => peer.order);
        const slot = weights.indexOf(initialOrder);
        if (slot >= 0) {
          weights.splice(slot, 1);
          peers
            .filter((peer) => peer.id !== record.id)
            .forEach((peer, index) => order(peer, weights[index]!));
        }
      }
      records.value.splice(records.value.indexOf(record), 1);
      paint({ ...record, deleted: true });
      touched.value.delete(key);
      initialOrders.delete(key);
    }
  }
  async function save(action: 'draft' | 'publish', selection?: EditRecord[]) {
    const rows = selection ?? pending.value;
    if (!rows.length) return;
    if (action === 'publish') {
      const keys = new Set(rows.map(recordKey));
      for (const record of rows) {
        if (record.liveOrder != null && record.order === record.liveOrder) continue;
        const omitted = orderPeers(record).filter(
          (peer) =>
            peer.liveOrder != null && peer.order !== peer.liveOrder && !keys.has(recordKey(peer)),
        );
        if (omitted.length)
          throw new Error(
            `本次顺序调整还涉及“${title(omitted[0]!)}”等 ${omitted.length} 项。请一并勾选后发布，或先撤销这组顺序调整。`,
          );
      }
    }
    busy.value = true;
    try {
      const submitted = rows.map(recordKey);
      const { data } = await api.post<EditorSnapshot>(
        'editor/changes/',
        {
          action,
          items: rows.map((r) => ({
            id: r.id,
            kind: r.kind,
            version: r.version,
            order: r.order,
            data: r.data,
          })),
        },
        { headers: { 'X-CSRFToken': csrfToken.value } },
      );
      absorb(data, submitted);
      if (action === 'publish') submitted.forEach((key) => touched.value.delete(key));
    } finally {
      busy.value = false;
    }
  }
  async function action(record: EditRecord, action: string, revision?: number) {
    if (dirty.value.has(recordKey(record)))
      throw new Error('先保存或撤销这个条目的未保存修改，再执行此操作。');
    busy.value = true;
    try {
      const { data } = await api.post<EditorSnapshot>(
        `editor/items/${record.kind}/${record.id}/action/`,
        { action, revision, version: record.version },
        { headers: { 'X-CSRFToken': csrfToken.value } },
      );
      absorb(data, [recordKey(record)]);
    } finally {
      busy.value = false;
    }
  }
  return {
    user,
    kinds,
    schemas,
    records,
    dirty,
    touched,
    busy,
    ready,
    csrfToken,
    pending,
    unpublished,
    title,
    find,
    paint,
    initialize,
    login,
    logout,
    update,
    order,
    move,
    position,
    changes,
    changeList,
    restoreField,
    formatValue,
    create,
    discard,
    save,
    action,
  };
});
