/* ==========================================================================
   API client — the single place that knows where the backend lives.
   Loaded before calendar.js and admin.js; exposes window.NHS_API.
   ========================================================================== */

(function () {
  'use strict';

  // In production nginx proxies /api on the same origin, so a relative path is
  // all we need. When you open the site on :8000 and run uvicorn on :8001,
  // point at the API explicitly instead.
  var BASE = (function () {
    var isLocalStatic =
      location.port === '8000' || location.protocol === 'file:';
    return isLocalStatic ? 'http://127.0.0.1:8001' : '';
  })();

  var TOKEN_KEY = 'nhs_admin_token';

  function getToken() {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch (e) {
      // Private browsing can throw on storage access.
      return null;
    }
  }

  function setToken(token) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch (e) {
      /* nothing we can do; the session just won't persist across reloads */
    }
  }

  /**
   * Thin fetch wrapper. Resolves to parsed JSON (or null for 204), and rejects
   * with an Error whose .status is the HTTP code so callers can branch on 401.
   */
  async function request(path, options) {
    options = options || {};

    var headers = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.auth) {
      var token = getToken();
      if (token) headers.Authorization = 'Bearer ' + token;
    }

    var response;
    try {
      response = await fetch(BASE + path, {
        method: options.method || 'GET',
        headers: headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body)
      });
    } catch (networkError) {
      // Server down, DNS failure, offline. Callers show a friendly notice.
      var offline = new Error('Could not reach the server.');
      offline.status = 0;
      throw offline;
    }

    if (response.status === 204) return null;

    var payload = null;
    try {
      payload = await response.json();
    } catch (e) {
      /* empty or non-JSON body — leave payload null */
    }

    if (!response.ok) {
      var error = new Error(describe(payload) || 'Request failed (' + response.status + ')');
      error.status = response.status;
      throw error;
    }

    return payload;
  }

  // FastAPI reports errors as {detail: "..."} for HTTPException and
  // {detail: [{loc, msg, ...}]} for validation failures. Flatten both.
  function describe(payload) {
    if (!payload || !payload.detail) return null;
    var detail = payload.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(function (item) {
          var field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
          return field ? field + ': ' + item.msg : item.msg;
        })
        .join('; ');
    }
    return null;
  }

  window.NHS_API = {
    /* --- auth --- */
    async login(password) {
      var data = await request('/api/auth/login', {
        method: 'POST',
        body: { password: password }
      });
      setToken(data.token);
      return data;
    },
    logout: function () {
      setToken(null);
    },
    isLoggedIn: function () {
      return Boolean(getToken());
    },

    /* --- events --- */
    listEvents: function (params) {
      var query = new URLSearchParams();
      if (params && params.start) query.set('start', params.start);
      if (params && params.end) query.set('end', params.end);
      var suffix = query.toString();
      return request('/api/events' + (suffix ? '?' + suffix : ''));
    },
    listAllEvents: function () {
      return request('/api/events/all', { auth: true });
    },
    createEvent: function (event) {
      return request('/api/events', { method: 'POST', body: event, auth: true });
    },
    updateEvent: function (id, changes) {
      return request('/api/events/' + id, { method: 'PATCH', body: changes, auth: true });
    },
    deleteEvent: function (id) {
      return request('/api/events/' + id, { method: 'DELETE', auth: true });
    }
  };
})();
