(() => {
  const hover = window.matchMedia('(hover: hover) and (pointer: fine)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  document.querySelectorAll('[data-hover-video]').forEach((frame) => {
    const video = frame.querySelector('video');
    const toggle = frame.querySelector('button');
    const hint = frame.closest('figure').querySelector('[data-video-hint]');
    let wanted = false;
    let visible = true;
    let request = 0;

    const syncControl = () => {
      const action = video.paused ? 'Play' : 'Pause';
      toggle.querySelector('span').textContent = action;
      toggle.setAttribute('aria-label', `${action} stochastic iron echoes video`);
    };

    const update = () => {
      const currentRequest = ++request;
      if (!wanted || !visible || document.hidden) {
        video.pause();
        syncControl();
        return;
      }
      video.play().then(() => {
        // A pointer may have left while the first frame was still loading.
        if (!wanted || !visible || document.hidden) video.pause();
      }).catch(() => {
        if (currentRequest !== request) return;
        wanted = false;
        syncControl();
      });
    };

    const stop = () => {
      wanted = false;
      update();
    };

    const updatePreference = () => {
      hint.textContent = hover.matches && !reducedMotion.matches
        ? 'Hover to play · click to pause.'
        : 'Tap or click to play and pause.';
      stop();
    };

    frame.addEventListener('pointerenter', (event) => {
      if (event.pointerType === 'touch' || !hover.matches || reducedMotion.matches) return;
      wanted = true;
      update();
    });
    frame.addEventListener('pointerleave', (event) => {
      if (event.pointerType !== 'touch') stop();
    });
    toggle.addEventListener('click', () => {
      wanted = !wanted;
      update();
    });
    toggle.addEventListener('blur', stop);
    video.addEventListener('play', syncControl);
    video.addEventListener('pause', syncControl);
    video.addEventListener('error', stop);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop();
    });
    window.addEventListener('pagehide', stop);
    hover.addEventListener('change', updatePreference);
    reducedMotion.addEventListener('change', updatePreference);

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting && entry.intersectionRatio >= .05;
        if (!visible) stop();
      }, { threshold: [0, .05] }).observe(frame);
    }

    video.muted = true;
    video.controls = false;
    toggle.hidden = false;
    updatePreference();
  });
})();
