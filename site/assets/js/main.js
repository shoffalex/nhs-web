/* Pine View School NHS — shared behaviour
   Vanilla JS, no dependencies. Every feature degrades gracefully. */

(function () {
  'use strict';

  /* ---------------------------------------------------------------- nav */

  const header = document.querySelector('.site-header');
  const toggle = document.querySelector('.nav-toggle');
  const menu = document.getElementById('nav-menu');

  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      menu.classList.toggle('is-open', !open);
    });

    // Close the mobile menu on outside click or Escape.
    document.addEventListener('click', function (e) {
      if (!menu.classList.contains('is-open')) return;
      if (menu.contains(e.target) || toggle.contains(e.target)) return;
      menu.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    });

    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !menu.classList.contains('is-open')) return;
      menu.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.focus();
    });
  }

  /* ------------------------------------------------- header shadow + top */

  const toTop = document.querySelector('.to-top');

  function onScroll() {
    const y = window.scrollY;
    if (header) header.classList.toggle('is-stuck', y > 8);
    if (toTop) toTop.classList.toggle('show', y > 600);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  /* ------------------------------------------------------------- reveal */

  const revealables = document.querySelectorAll('.reveal');

  if ('IntersectionObserver' in window && revealables.length) {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        // Stagger siblings so grids cascade instead of popping at once.
        const delay = Number(entry.target.dataset.revealDelay || 0);
        setTimeout(function () { entry.target.classList.add('in'); }, delay);
        io.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });

    revealables.forEach(function (el, i) {
      if (!el.dataset.revealDelay) {
        const sibs = el.parentElement ? el.parentElement.children : [];
        el.dataset.revealDelay = String(Math.min(Array.prototype.indexOf.call(sibs, el), 5) * 70);
      }
      io.observe(el);
    });
  } else {
    revealables.forEach(function (el) { el.classList.add('in'); });
  }

  /* --------------------------------------------------- meeting schedule */

  // Marks meetings that have already happened and highlights the next one.
  // Exposed as NHS.markMeetings so calendar.js can re-run it after rendering
  // rows fetched from the API — this logic should exist in exactly one place.
  function markMeetings() {
    const meetings = document.querySelectorAll('.meet[data-date]');
    if (!meetings.length) return;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let nextFound = false;

    meetings.forEach(function (el) {
      const parts = el.dataset.date.split('-');
      const when = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      const status = el.querySelector('[data-status]');

      // Reset first: on a re-run the element may already carry last pass's state.
      el.classList.remove('is-past', 'is-next');

      if (when < today) {
        el.classList.add('is-past');
        if (status) {
          status.textContent = 'Past';
          status.className = 'pill is-mute';
        }
      } else if (!nextFound) {
        nextFound = true;
        el.classList.add('is-next');
        if (status) {
          status.textContent = 'Next meeting';
          status.className = 'pill is-accent';
        }
      } else if (status) {
        status.textContent = 'Upcoming';
        status.className = 'pill';
      }
    });

    // If every listed meeting is in the past, say so rather than showing nothing.
    const banner = document.querySelector('[data-schedule-banner]');
    if (banner && !nextFound) banner.hidden = false;
  }

  markMeetings();

  window.NHS = window.NHS || {};
  window.NHS.markMeetings = markMeetings;

  /* ----------------------------------------------------------- footer year */

  const year = document.querySelector('[data-year]');
  if (year) year.textContent = String(new Date().getFullYear());
})();
