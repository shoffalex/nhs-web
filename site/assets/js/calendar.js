/* ==========================================================================
   Public calendar — renders events from the API into the site's existing
   .meet-list markup, then hands off to NHS.markMeetings() for the past/next
   styling so there is exactly one copy of that logic.
   ========================================================================== */

(function () {
  'use strict';

  var list = document.querySelector('[data-events-list]');
  if (!list) return;

  var state = document.querySelector('[data-events-state]');
  var banner = document.querySelector('[data-schedule-banner]');

  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function setState(message, isError) {
    if (!state) return;
    state.hidden = !message;
    state.textContent = message || '';
    state.className = isError ? 'events-state is-error' : 'events-state';
  }

  // "2026-09-08" -> a local Date. Deliberately not new Date(str): that parses
  // a bare date as UTC and can render as the previous day west of Greenwich.
  function parseDate(value) {
    var parts = String(value).split('-');
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  }

  // "13:10:00" -> "1:10 pm"
  function formatTime(value) {
    if (!value) return '';
    var parts = String(value).split(':');
    var hours = Number(parts[0]);
    var minutes = parts[1] || '00';
    var suffix = hours >= 12 ? 'pm' : 'am';
    var display = hours % 12 === 0 ? 12 : hours % 12;
    return display + ':' + minutes + ' ' + suffix;
  }

  function formatLongDate(date) {
    return date.toLocaleDateString(undefined, {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
    });
  }

  function buildRow(event) {
    var when = parseDate(event.event_date);

    var item = document.createElement('li');
    item.className = 'meet';
    item.dataset.date = event.event_date;

    var stamp = document.createElement('span');
    stamp.className = 'date';
    stamp.innerHTML =
      '<span class="m">' + MONTHS[when.getMonth()] + '</span>' +
      '<span class="d">' + when.getDate() + '</span>';

    var body = document.createElement('span');

    var where = document.createElement('span');
    where.className = 'where';
    where.textContent = event.location ? event.title + ' — ' + event.location : event.title;

    var meta = document.createElement('span');
    meta.className = 'meta';
    var pieces = [formatLongDate(when)];
    var time = formatTime(event.start_time);
    if (time) {
      pieces.push(event.end_time ? time + '–' + formatTime(event.end_time) : time);
    }
    meta.textContent = pieces.join(' · ');

    body.appendChild(where);
    body.appendChild(meta);

    if (event.description) {
      var note = document.createElement('span');
      note.className = 'meta';
      note.textContent = event.description;
      body.appendChild(note);
    }

    var pill = document.createElement('span');
    pill.className = 'pill';
    pill.setAttribute('data-status', '');
    pill.textContent = 'Upcoming';

    item.appendChild(stamp);
    item.appendChild(body);
    item.appendChild(pill);
    return item;
  }

  async function load() {
    setState('Loading the schedule…', false);

    var events;
    try {
      events = await NHS_API.listEvents();
    } catch (error) {
      // The rest of the page is static and still useful, so fail quietly here.
      setState(
        error.status === 0
          ? 'The schedule is temporarily unavailable. Please check back shortly.'
          : 'Could not load the schedule (' + error.message + ').',
        true
      );
      return;
    }

    list.textContent = '';

    if (!events.length) {
      setState('No meetings are scheduled yet. Check back soon.', false);
      return;
    }

    setState('', false);
    events.forEach(function (event) {
      list.appendChild(buildRow(event));
    });

    // Reuse the shared past/next logic instead of duplicating it here.
    if (window.NHS && typeof window.NHS.markMeetings === 'function') {
      window.NHS.markMeetings();
    }

    if (banner) {
      var today = new Date();
      today.setHours(0, 0, 0, 0);
      var anyUpcoming = events.some(function (event) {
        return parseDate(event.event_date) >= today;
      });
      banner.hidden = anyUpcoming;
    }
  }

  load();
})();
