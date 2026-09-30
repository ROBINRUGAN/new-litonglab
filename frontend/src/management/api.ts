// designed by mew
import { api } from '../api/client';
import { useEditorStore } from '../editor/store';

export function managementHeaders() {
  return { 'X-CSRFToken': useEditorStore().csrfToken };
}

export async function managementPost<T>(path: string, body: unknown) {
  const { data } = await api.post<T>(`manage/${path}`, body, {
    headers: managementHeaders(),
    timeout: 120_000,
  });
  return data;
}

export interface ManagedUser {
  id: number;
  username: string;
  name: string;
  manager: boolean;
  active: boolean;
  created: string;
  current: boolean;
}

export interface BackupInfo {
  scope: string[];
  maxUploadBytes: number;
  canBackup: boolean;
  canRestore: boolean;
}

export interface RestorePreview {
  token: string;
  scope: string[];
  expiresAt: string;
  summary: {
    createdAt: string;
    contentCount: number;
    revisionCount: number;
    mediaCount: number;
    totalBytes: number;
    counts: { kind: string; label: string; count: number }[];
  };
}
