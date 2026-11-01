(() => {
  const hover = window.matchMedia('(hover: hover) and (pointer: fine)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  document.querySelectorAll('[data-hover-video]').forEach((frame) => {
    const video = frame.querySelector('video');
    const figure = frame.closest('figure');
    const selector = figure.querySelector('.art-video-switch');
    const modes = [...figure.querySelectorAll('[data-video-mode]')];
    let activeMode = modes.find((mode) => mode.getAttribute('aria-pressed') === 'true');
    let wanted = false;
    let visible = true;
    let request = 0;

    const syncControl = () => {
      const action = video.paused ? 'Play' : 'Pause';
      const label = activeMode?.dataset.videoLabel || 'Stochastic iron echoes';
      frame.setAttribute('aria-label', `${action} ${label.toLowerCase()} video`);
    };

    const update = () => {
      const currentRequest = ++request;
      if (!wanted || !visible || document.hidden) {
        video.pause();
        syncControl();
        return;
      }
      video.play().then(() => {
        if (currentRequest !== request) return;
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

    modes.forEach((mode) => mode.addEventListener('click', () => {
      if (mode === activeMode) return;
      // Invalidate a pending play request before replacing its media resource.
      stop();
      activeMode = mode;
      modes.forEach((option) => option.setAttribute('aria-pressed', String(option === mode)));
      video.poster = mode.dataset.videoPoster;
      video.querySelector('source').src = mode.dataset.videoSrc;
      video.querySelector('a').href = mode.dataset.videoSrc;
      figure.querySelector('.art-file-link').href = mode.dataset.videoSrc;
      video.setAttribute('aria-label', `${mode.dataset.videoLabel}: side-by-side MAD and SANE animation, with a scale bar of ten gravitational radii`);
      video.load();
      // Choosing a mode is an explicit playback request, including on touchscreens.
      wanted = true;
      update();
    }));

    frame.addEventListener('pointerenter', (event) => {
      if (event.pointerType === 'touch' || !hover.matches || reducedMotion.matches) return;
      wanted = true;
      update();
    });
    frame.addEventListener('pointerleave', (event) => {
      if (event.pointerType !== 'touch') stop();
    });
    const togglePlayback = () => {
      wanted = !wanted;
      update();
    };
    frame.addEventListener('click', togglePlayback);
    frame.addEventListener('keydown', (event) => {
      if (event.key !== ' ' && event.key !== 'Enter') return;
      event.preventDefault();
      if (!event.repeat) togglePlayback();
    });
    frame.addEventListener('blur', stop);
    video.addEventListener('play', syncControl);
    video.addEventListener('pause', syncControl);
    video.addEventListener('error', stop);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop();
    });
    window.addEventListener('pagehide', stop);
    hover.addEventListener('change', stop);
    reducedMotion.addEventListener('change', stop);

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting && entry.intersectionRatio >= .05;
        if (!visible) stop();
      }, { threshold: [0, .05] }).observe(frame);
    }

    video.muted = true;
    video.controls = false;
    frame.setAttribute('role', 'button');
    frame.tabIndex = 0;
    stop();
    if (selector) selector.hidden = false;
  });
})();
