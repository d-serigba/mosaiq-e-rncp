/* Grille Masonry : chaque nouveau billet est inséré dans la colonne la plus courte.
 * Principe inspiré de desandro/masonry, en JavaScript vanilla avec colonnes Flexbox. */
(function () {
  'use strict';

  const grid = document.getElementById('masonry');
  if (!grid) { return; }

  const loadMoreButton = document.getElementById('load-more');
  const statusLine = document.getElementById('grid-status');
  const mobileQuery = window.matchMedia('(max-width: 700px)');

  const state = { page: 1, loading: false, cards: [], columns: [], total: 0 };

  // ---------------------------------------------------------------- colonnes
  const columnCount = function () { return mobileQuery.matches ? 1 : 3; };

  function buildColumns(count) {
    grid.replaceChildren();
    const columns = [];
    for (let i = 0; i < count; i += 1) {
      const column = document.createElement('div');
      column.className = 'masonry-column';
      grid.appendChild(column);
      columns.push(column);
    }
    return columns;
  }

  // Colonne la plus courte ; en cas d'égalité, la plus à gauche (ordre de lecture)
  function shortestColumn() {
    return state.columns.reduce(function (shortest, column) {
      return column.offsetHeight < shortest.offsetHeight ? column : shortest;
    });
  }

  function relayout() {
    state.columns = buildColumns(columnCount());
    state.cards.forEach(function (card) { shortestColumn().appendChild(card); });
  }

  // ------------------------------------------------------------------ cartes
  // Toutes les données serveur sont insérées avec textContent / propriétés DOM (jamais innerHTML) : anti-XSS
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = text; }
    return node;
  }

  function link(href, text, className) {
    const a = el('a', className, text);
    a.href = href;
    return a;
  }

  function actionButton(action, symbol, count, post, active) {
    const button = el('button', 'act' + (active ? ' active' : ''));
    button.type = 'button';
    button.dataset.action = action;
    button.dataset.postId = String(post.id);
    if (action === 'like') { button.setAttribute('aria-pressed', active ? 'true' : 'false'); }
    button.append(symbol + ' ', el('span', 'count', String(count)));
    return button;
  }

  function createCard(post) {
    const card = el('article', 'card card-' + post.type);

    if (post.reblog_de) {
      const origin = el('p', 'card-reblog', '↻ reblogué depuis ');
      origin.appendChild(link(post.reblog_de.auteur_url, '@' + post.reblog_de.auteur));
      card.appendChild(origin);
    }

    if (post.image) {
      const img = el('img', 'card-media');
      img.alt = post.titre || 'Image du billet';
      img.src = post.image;
      card.appendChild(img);
    }

    if (post.titre) {
      const title = el('h3', 'card-title');
      title.appendChild(link(post.url, post.titre));
      card.appendChild(title);
    }

    if (post.contenu) {
      card.appendChild(el(post.type === 'citation' ? 'blockquote' : 'p',
        post.type === 'citation' ? 'card-quote' : 'card-text', post.contenu));
    }

    // Double contrôle côté client : seuls les liens http(s) deviennent cliquables
    if (post.lien && /^https?:\/\//i.test(post.lien)) {
      const external = link(post.lien, post.lien, 'card-link');
      external.target = '_blank';
      external.rel = 'noopener noreferrer nofollow';
      card.appendChild(external);
    }

    if (post.tags.length) {
      const tags = el('p', 'tags');
      post.tags.forEach(function (tag) { tags.appendChild(link(tag.url, '#' + tag.nom)); });
      card.appendChild(tags);
    }

    const footer = el('footer', 'card-footer');
    footer.appendChild(link(post.auteur_url, '@' + post.auteur));
    footer.appendChild(el('span', 'muted', post.date));
    const actions = el('span', 'actions');
    actions.appendChild(actionButton('like', '♥', post.likes, post, post.liked));
    actions.appendChild(actionButton('reblog', '↻', post.reblogs, post, false));
    const comments = link(post.url + '#commentaires', '💬 ' + post.commentaires, 'act');
    actions.appendChild(comments);
    footer.appendChild(actions);
    card.appendChild(footer);

    return card;
  }

  // Attend le chargement des images pour connaître la vraie hauteur avant de placer la carte
  function whenImagesLoaded(card) {
    const pending = Array.from(card.querySelectorAll('img')).map(function (img) {
      if (img.complete) { return Promise.resolve(); }
      return new Promise(function (resolve) {
        img.addEventListener('load', resolve, { once: true });
        img.addEventListener('error', resolve, { once: true });
      });
    });
    return Promise.all(pending);
  }

  // ------------------------------------------------------- chargement (fetch)
  async function loadPage() {
    if (state.loading) { return; }
    state.loading = true;
    loadMoreButton.disabled = true;
    statusLine.textContent = 'Chargement…';

    try {
      const params = new URLSearchParams({ page: String(state.page) });
      ['feed', 'tag', 'user'].forEach(function (key) {
        if (grid.dataset[key]) { params.set(key, grid.dataset[key]); }
      });

      const response = await fetch(grid.dataset.endpoint + '?' + params.toString(), {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      });
      if (!response.ok) { throw new Error('HTTP ' + response.status); }
      const data = await response.json();

      // Placement séquentiel : l'ordre chronologique est préservé
      for (const post of data.posts) {
        const card = createCard(post);
        await whenImagesLoaded(card);
        state.cards.push(card);
        shortestColumn().appendChild(card);
        state.total += 1;
      }

      state.page += 1;
      loadMoreButton.hidden = !data.has_next;
      statusLine.textContent = state.total === 0 ? 'Aucun billet pour le moment.' : '';
    } catch (error) {
      statusLine.textContent = 'Impossible de charger les billets. Réessayez.';
      loadMoreButton.hidden = false;
    } finally {
      state.loading = false;
      loadMoreButton.disabled = false;
    }
  }

  // ---------------------------------------------------------------- démarrage
  state.columns = buildColumns(columnCount());
  loadMoreButton.addEventListener('click', loadPage);

  let lastCount = columnCount();
  mobileQuery.addEventListener('change', function () {
    if (columnCount() !== lastCount) {
      lastCount = columnCount();
      relayout();
    }
  });

  loadPage();
})();
