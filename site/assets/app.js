/* Food search and risk filter.
   Progressive enhancement: with JS off, every card is already visible and the
   filter UI is hidden by CSS, so the page still answers the question. */
(function () {
  'use strict';

  var cards = Array.prototype.slice.call(document.querySelectorAll('#cards .card'));
  var search = document.getElementById('food-search');
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var status = document.getElementById('filter-status');
  var empty = document.getElementById('no-results');
  if (!cards.length || !search) return;

  document.documentElement.classList.add('has-js');

  var band = 'all';
  var query = '';

  function apply() {
    var shown = 0;
    cards.forEach(function (card) {
      var matchBand = band === 'all' || card.dataset.band === band;
      var matchText = !query || card.dataset.name.indexOf(query) !== -1;
      var show = matchBand && matchText;
      card.hidden = !show;
      if (show) shown++;
    });

    if (empty) empty.hidden = shown !== 0;
    if (status) {
      status.textContent = shown === cards.length
        ? 'Showing all ' + cards.length + ' foods.'
        : 'Showing ' + shown + ' of ' + cards.length + ' foods.';
    }
  }

  function setBand(next) {
    band = next;
    chips.forEach(function (c) {
      var on = c.dataset.filter === band;
      c.classList.toggle('is-on', on);
      c.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    apply();
  }

  chips.forEach(function (chip) {
    chip.setAttribute('aria-pressed', chip.classList.contains('is-on') ? 'true' : 'false');
    chip.addEventListener('click', function () { setBand(chip.dataset.filter); });
  });

  // "Show all" link inside the empty state clears both filters.
  document.querySelectorAll('.linklike[data-filter]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      search.value = '';
      query = '';
      setBand('all');
      search.focus();
    });
  });

  var debounce;
  search.addEventListener('input', function () {
    clearTimeout(debounce);
    debounce = setTimeout(function () {
      query = search.value.trim().toLowerCase();
      apply();
    }, 120);
  });

  // Escape clears the search box rather than leaving a stale filter behind.
  search.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && search.value) {
      ev.preventDefault();
      search.value = '';
      query = '';
      apply();
    }
  });

  apply();
})();
