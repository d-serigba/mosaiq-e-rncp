/* Formulaire de billet : n'affiche que les champs pertinents pour le type choisi */
(function () {
  'use strict';

  const select = document.getElementById('type_post');
  const blocks = document.querySelectorAll('#post-form [data-types]');
  if (!select) { return; }

  function refresh() {
    blocks.forEach(function (block) {
      const types = block.dataset.types.split(' ');
      block.hidden = types.indexOf(select.value) === -1;
    });
  }

  select.addEventListener('change', refresh);
  refresh();
})();
