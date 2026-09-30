// designed by mew
import { reducedMotion } from './transitions';
export function bindHomeMotion(root: HTMLElement | null) {
  if (!root) return () => {};
  const controller = new AbortController(),
    { signal } = controller;
  const hero = root.querySelector<HTMLElement>('.hero-stack'),
    story = root.querySelector<HTMLElement>('.research-story');
  let frame = 0;
  const images = [...root.querySelectorAll<HTMLElement>('.feature-image')],
    captions = [...root.querySelectorAll<HTMLElement>('.feature-caption')],
    dots = [...root.querySelectorAll<HTMLElement>('[data-jump-scene]')];
  const last = Math.max(0, images.length - 1),
    clamp = (n: number) => Math.max(0, Math.min(1, n)),
    smooth = (a: number, b: number, n: number) => {
      const t = clamp((n - a) / (b - a));
      return t * t * (3 - 2 * t);
    };
  const update = () => {
    frame = 0;
    const stat = reducedMotion() || innerWidth <= 850;
    document.documentElement.classList.toggle('static-motion', stat);
    if (hero) {
      const p = clamp(-hero.getBoundingClientRect().top / (innerHeight * 1.2));
      hero.style.setProperty('--scene-progress', String(stat ? 0 : p));
      hero.style.setProperty('--copy-opacity', String(stat ? 1 : 1 - smooth(0.43, 0.83, p)));
      hero.style.setProperty('--copy-shift', `${stat ? 0 : -18 * smooth(0.43, 0.83, p)}px`);
    }
    if (story) {
      const p = stat
        ? 0
        : clamp(
            -story.getBoundingClientRect().top / Math.max(1, story.offsetHeight - innerHeight),
          ) * last;
      captions.forEach((caption, i) => {
        const enter = i === 0 ? 1 : smooth(i - 0.65, i - 0.35, p),
          exit = i === last ? 0 : smooth(i + 0.35, i + 0.65, p),
          opacity = enter * (1 - exit),
          image = images[i];
        caption.style.opacity = String(stat ? 1 : opacity);
        caption.style.transform = stat ? 'none' : `translateY(${(1 - enter) * 14 - exit * 10}px)`;
        caption.inert = !stat && opacity < 0.5;
        if (image) {
          image.style.opacity = String(stat ? 1 : opacity);
          image.style.transform = stat
            ? 'none'
            : `translateY(${(1 - enter) * 20 - exit * 12}px) scale(${1.015 + (1 - enter) * 0.03})`;
        }
      });
      dots.forEach((b, i) =>
        b.setAttribute('aria-pressed', String(i === Math.min(last, Math.round(p)))),
      );
    }
  };
  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(update);
  };
  addEventListener('scroll', schedule, { passive: true, signal });
  addEventListener('resize', schedule, { signal });
  matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', schedule, { signal });
  dots.forEach((button, i) =>
    button.addEventListener(
      'click',
      () =>
        scrollTo({
          top:
            scrollY +
            (story?.getBoundingClientRect().top || 0) +
            (((story?.offsetHeight || innerHeight) - innerHeight) * i) / Math.max(1, last),
          behavior: reducedMotion() ? 'instant' : 'smooth',
        }),
      { signal },
    ),
  );
  update();
  return () => {
    controller.abort();
    cancelAnimationFrame(frame);
  };
}
