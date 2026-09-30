// designed by mew
export const imageCategories = [
  ['group-photo', '合照照片'],
  ['person-photo', '个人照片'],
  ['paper-figure', '论文配图'],
  ['project-figure', '项目配图'],
  ['other', '其他图片'],
] as const;

export type ImageCategory = (typeof imageCategories)[number][0];

export function categoryForRecord(kind: string, field = 'image'): ImageCategory | undefined {
  if (field !== 'image') return undefined;
  if (kind === 'photo') return 'group-photo';
  if (kind === 'person') return 'person-photo';
  if (kind === 'publication') return 'paper-figure';
  if (kind === 'project') return 'project-figure';
  return undefined;
}
