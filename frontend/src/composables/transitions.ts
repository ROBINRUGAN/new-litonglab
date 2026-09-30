// designed by mew
import { nextTick } from 'vue';
import { setLocale, locale } from './i18n';
import { storeToRefs } from 'pinia';
import { pinia } from '../stores';
import { usePreferencesStore } from '../stores/preferences';
import type { Locale } from '../stores/preferences';
const preferences = usePreferencesStore(pinia);
export const { theme, selectedLanguage } = storeToRefs(preferences);
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
let active: ViewTransition | null = null;
let languageSerial = 0;
export async function transition(kind: string, update: () => void | Promise<void>) {
  active?.skipTransition();
  document.documentElement.dataset.transition = kind;
  if (reducedMotion()) {
    await update();
    await nextTick();
    delete document.documentElement.dataset.transition;
    return;
  }
  if (document.startViewTransition) {
    const view = document.startViewTransition(async () => {
      await update();
      await nextTick();
    });
    active = view;
    await view.finished.catch(() => {});
    if (active === view) {
      active = null;
      delete document.documentElement.dataset.transition;
    }
  } else {
    await update();
    await nextTick();
    document.querySelector('main')?.animate(
      [
        { opacity: 0, transform: 'translateY(8px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ],
      { duration: 320, easing: 'ease-out' },
    );
    delete document.documentElement.dataset.transition;
  }
}
export async function changeLanguage(value: Locale) {
  const serial = ++languageSerial;
  selectedLanguage.value = value;
  const elements = [document.querySelector('main'), document.querySelector('footer')].filter(
    (el): el is HTMLElement => el !== null,
  );
  elements.forEach((el) => el.getAnimations().forEach((a) => a.cancel()));
  if (!reducedMotion())
    await Promise.allSettled(
      elements.map(
        (el) =>
          el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 130, fill: 'forwards' })
            .finished,
      ),
    );
  if (serial !== languageSerial) return;
  setLocale(value);
  await nextTick();
  elements.forEach((el) => {
    el.getAnimations().forEach((a) => a.cancel());
    if (!reducedMotion())
      el.animate(
        [
          { opacity: 0, transform: 'translateY(6px)' },
          { opacity: 1, transform: 'translateY(0)' },
        ],
        { duration: 340, easing: 'cubic-bezier(.22,1,.36,1)' },
      );
  });
}
export function changeTheme() {
  return transition('theme', () => {
    preferences.setTheme(theme.value === 'dark' ? 'light' : 'dark');
  });
}
export function reveal(root: HTMLElement | null) {
  if (!root || reducedMotion()) return () => {};
  const observer = new IntersectionObserver(
    (entries) =>
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible');
          observer.unobserve(e.target);
        }
      }),
    { threshold: 0.05 },
  );
  root
    .querySelectorAll<HTMLElement>(
      '.section-heading,.research-card,.publication-card,.project-card,.member,.contact-card,.faculty-portrait,.join-banner',
    )
    .forEach((el, i) => {
      if (el.getBoundingClientRect().top > innerHeight * 0.92) {
        el.classList.add('reveal-pending');
        el.style.setProperty('--reveal-delay', `${(i % 3) * 45}ms`);
        observer.observe(el);
      }
    });
  return () => observer.disconnect();
}
