/* Actions sociales asynchrones : like, reblog, abonnement (API fetch + jeton CSRF) */
(function () {
  'use strict';

  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const loginUrl = document.body.dataset.loginUrl;
  const toast = document.getElementById('toast');
  let toastTimer = null;

  function showToast(message) {
    toast.textContent = message; // textContent : jamais d'HTML injecté
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, 2500);
  }

  async function apiPost(url) {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken, 'Accept': 'application/json' },
    });
    if (response.status === 401) {
      window.location.href = loginUrl + '?next=' + encodeURIComponent(window.location.pathname);
      return null;
    }
    let data = {};
    try { data = await response.json(); } catch (e) { /* réponse non JSON */ }
    if (!response.ok) { throw new Error(data.error || 'Une erreur est survenue.'); }
    return data;
  }

  function setCount(button, value) {
    const counter = button.querySelector('.count');
    if (counter) { counter.textContent = String(value); }
  }

  const handlers = {
    like: async function (button) {
      const data = await apiPost('/api/post/' + encodeURIComponent(button.dataset.postId) + '/like');
      if (!data) { return; }
      button.classList.toggle('active', data.liked);
      button.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
      setCount(button, data.likes);
    },
    reblog: async function (button) {
      const data = await apiPost('/api/post/' + encodeURIComponent(button.dataset.postId) + '/reblog');
      if (!data) { return; }
      setCount(button, data.reblogs);
      showToast(data.message || 'Billet reblogué.');
    },
    follow: async function (button) {
      const data = await apiPost('/api/user/' + encodeURIComponent(button.dataset.pseudo) + '/follow');
      if (!data) { return; }
      button.textContent = data.following ? 'Se désabonner' : "S'abonner";
      const counter = document.getElementById('followers-count');
      if (counter) { counter.textContent = String(data.followers); }
    },
  };

  // Délégation d'évènements : fonctionne aussi pour les cartes créées dynamiquement
  document.addEventListener('click', async function (event) {
    const button = event.target.closest('[data-action]');
    if (!button || !handlers[button.dataset.action]) { return; }
    event.preventDefault();
    button.disabled = true;
    try {
      await handlers[button.dataset.action](button);
    } catch (error) {
      showToast(error.message);
    } finally {
      button.disabled = false;
    }
  });
})();
