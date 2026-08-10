/* ==========================================================================
   Admin — log in, then create / edit / delete calendar events.

   Auth is a single shared password (see backend/app/auth.py). The token lives
   in sessionStorage, so closing the tab logs you out.
   ========================================================================== */

(function () {
  'use strict';

  var loginPanel = document.querySelector('[data-login-panel]');
  var adminPanel = document.querySelector('[data-admin-panel]');
  if (!loginPanel || !adminPanel) return;

  var loginForm = document.querySelector('[data-login-form]');
  var loginMsg = document.querySelector('[data-login-msg]');
  var logoutBtn = document.querySelector('[data-logout]');

  var eventForm = document.querySelector('[data-event-form]');
  var formMsg = document.querySelector('[data-form-msg]');
  var formTitle = document.querySelector('[data-form-title]');
  var cancelBtn = document.querySelector('[data-cancel-edit]');
  var list = document.querySelector('[data-admin-list]');
  var listState = document.querySelector('[data-admin-state]');

  // null = creating; a number = editing that event.
  var editingId = null;

  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function show(element, visible) {
    element.hidden = !visible;
  }

  function message(target, text, kind) {
    if (!target) return;
    target.hidden = !text;
    target.textContent = text || '';
    target.className = 'form-msg' + (kind ? ' is-' + kind : '');
  }

  function parseDate(value) {
    var parts = String(value).split('-');
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  }

  /* ------------------------------------------------------------- session */

  function enterAdmin() {
    show(loginPanel, false);
    show(adminPanel, true);
    if (logoutBtn) show(logoutBtn, true);
    loadEvents();
  }

  function leaveAdmin() {
    NHS_API.logout();
    show(adminPanel, false);
    show(loginPanel, true);
    if (logoutBtn) show(logoutBtn, false);
    resetForm();
    message(loginMsg, '', null);
  }

  loginForm.addEventListener('submit', async function (submitEvent) {
    submitEvent.preventDefault();
    var password = loginForm.elements.password.value;
    message(loginMsg, 'Signing in…', null);

    try {
      await NHS_API.login(password);
    } catch (error) {
      message(
        loginMsg,
        error.status === 401 ? 'That password is not correct.' : error.message,
        'error'
      );
      return;
    }

    loginForm.reset();
    message(loginMsg, '', null);
    enterAdmin();
  });

  if (logoutBtn) logoutBtn.addEventListener('click', leaveAdmin);

  /* --------------------------------------------------------------- list */

  function buildRow(event) {
    var when = parseDate(event.event_date);

    var item = document.createElement('li');
    item.className = 'meet is-admin' + (event.is_published ? '' : ' is-draft');
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
    meta.textContent = event.event_date + (event.start_time ? ' · ' + event.start_time.slice(0, 5) : '');
    body.appendChild(where);
    body.appendChild(meta);

    var pill = document.createElement('span');
    pill.className = event.is_published ? 'pill' : 'pill is-mute';
    pill.textContent = event.is_published ? 'Published' : 'Draft';

    var actions = document.createElement('span');
    actions.className = 'meet-actions';

    var edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'btn-icon';
    edit.textContent = 'Edit';
    edit.addEventListener('click', function () {
      startEdit(event);
    });

    var remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn-icon is-danger';
    remove.textContent = 'Delete';
    remove.addEventListener('click', function () {
      confirmDelete(event);
    });

    actions.appendChild(edit);
    actions.appendChild(remove);

    item.appendChild(stamp);
    item.appendChild(body);
    item.appendChild(pill);
    item.appendChild(actions);
    return item;
  }

  async function loadEvents() {
    if (listState) {
      listState.hidden = false;
      listState.textContent = 'Loading events…';
      listState.className = 'events-state';
    }

    var events;
    try {
      events = await NHS_API.listAllEvents();
    } catch (error) {
      if (error.status === 401) {
        // Token expired while the tab sat open.
        leaveAdmin();
        message(loginMsg, 'Your session expired. Please sign in again.', 'error');
        return;
      }
      if (listState) {
        listState.textContent = 'Could not load events: ' + error.message;
        listState.className = 'events-state is-error';
      }
      return;
    }

    list.textContent = '';

    if (!events.length) {
      if (listState) {
        listState.textContent = 'No events yet. Add the first one with the form.';
        listState.className = 'events-state';
      }
      return;
    }

    if (listState) listState.hidden = true;
    events.forEach(function (event) {
      list.appendChild(buildRow(event));
    });
  }

  /* --------------------------------------------------------------- form */

  function resetForm() {
    editingId = null;
    eventForm.reset();
    eventForm.elements.is_published.checked = true;
    if (formTitle) formTitle.textContent = 'Add an event';
    if (cancelBtn) show(cancelBtn, false);
    message(formMsg, '', null);
  }

  function startEdit(event) {
    editingId = event.id;
    var fields = eventForm.elements;
    fields.title.value = event.title;
    fields.event_date.value = event.event_date;
    fields.start_time.value = event.start_time ? event.start_time.slice(0, 5) : '';
    fields.end_time.value = event.end_time ? event.end_time.slice(0, 5) : '';
    fields.location.value = event.location || '';
    fields.description.value = event.description || '';
    fields.is_published.checked = event.is_published;

    if (formTitle) formTitle.textContent = 'Edit event';
    if (cancelBtn) show(cancelBtn, true);
    message(formMsg, '', null);
    eventForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
    fields.title.focus();
  }

  if (cancelBtn) cancelBtn.addEventListener('click', resetForm);

  function readForm() {
    var fields = eventForm.elements;
    // Empty optional fields go as null, not "", so the API stores a real absence.
    return {
      title: fields.title.value.trim(),
      event_date: fields.event_date.value,
      start_time: fields.start_time.value || null,
      end_time: fields.end_time.value || null,
      location: fields.location.value.trim() || null,
      description: fields.description.value.trim() || null,
      is_published: fields.is_published.checked
    };
  }

  eventForm.addEventListener('submit', async function (submitEvent) {
    submitEvent.preventDefault();
    var payload = readForm();
    message(formMsg, 'Saving…', null);

    try {
      if (editingId === null) await NHS_API.createEvent(payload);
      else await NHS_API.updateEvent(editingId, payload);
    } catch (error) {
      if (error.status === 401) {
        leaveAdmin();
        message(loginMsg, 'Your session expired. Please sign in again.', 'error');
        return;
      }
      message(formMsg, error.message, 'error');
      return;
    }

    var wasEditing = editingId !== null;
    resetForm();
    message(formMsg, wasEditing ? 'Event updated.' : 'Event added.', 'ok');
    loadEvents();
  });

  async function confirmDelete(event) {
    if (!window.confirm('Delete "' + event.title + '" on ' + event.event_date + '?')) return;

    try {
      await NHS_API.deleteEvent(event.id);
    } catch (error) {
      if (error.status === 401) {
        leaveAdmin();
        message(loginMsg, 'Your session expired. Please sign in again.', 'error');
        return;
      }
      message(formMsg, 'Could not delete: ' + error.message, 'error');
      return;
    }

    // If the deleted row was loaded into the form, don't leave a stale edit open.
    if (editingId === event.id) resetForm();
    message(formMsg, 'Event deleted.', 'ok');
    loadEvents();
  }

  /* ------------------------------------------------------------ start-up */

  if (NHS_API.isLoggedIn()) enterAdmin();
  else show(loginPanel, true);
})();
