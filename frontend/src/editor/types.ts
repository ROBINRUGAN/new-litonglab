// designed by mew
import type { ContentKind, ContentLink, SiteContent } from '../types/content';
export type Value = string | number | boolean | string[] | ContentLink[];
export interface Field {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  private?: boolean;
  default?: Value;
  help?: string;
  target?: ContentKind;
  choices?: [string, string][];
  min_value?: number;
  max_value?: number;
}
export interface EditRecord {
  id: string;
  kind: ContentKind;
  version: number | null;
  order: number;
  data: Record<string, Value>;
  deleted: boolean;
  published: boolean;
  hasDraft: boolean;
  state: string;
  liveData: Record<string, Value> | null;
  liveOrder: number | null;
}
export interface EditorSnapshot {
  user: { name: string; manager: boolean; canPublish: boolean } | null;
  csrfToken?: string;
  kinds: { key: ContentKind; label: string; canAdd: boolean }[];
  schemas: Record<ContentKind, Field[]>;
  records: EditRecord[];
  content: SiteContent;
}
export interface EditTarget {
  kind: ContentKind;
  id: string;
  field?: string;
  element?: HTMLElement;
}
export type EditBinding = [ContentKind, string | undefined, string?];
export interface HistoryVersion {
  id: number;
  action: string;
  date: string;
  actor: string;
  data: Record<string, Value>;
}

export type ChangeStage = 'unsaved' | 'saved';
export interface FieldChange {
  field: string;
  label: string;
  before: Value | undefined;
  after: Value | undefined;
  stage: ChangeStage;
}
