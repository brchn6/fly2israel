/**
 * fly2israel — Uptime Radar Dashboard
 * Card-based airline uptime tracker. Zero dependencies.
 *
 * Generates mock timeline data for demo. Ready for real timeline data.
 */
(function () {
  'use strict';

  let DATA = null;
  let currentFilter = 'all';

  /* ── Helpers ── */
  const $ = (sel, ctx) => (ctx || document).querySelector(sel);
  const $$ = (sel, ctx) => Array.from((ctx || document).querySelectorAll(sel));

  function esc(s) {
    if (s == null) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  /* ── Derived Data ── */

  /** Overall airline status based on active/suspended route counts */
  function airlineStatus(a) {
    if (a.active_routes > 0 && a.suspended_routes === 0) return 'active';
    if (a.active_routes === 0 && a.suspended_routes > 0) return 'suspended';
    if (a.active_routes > 0 && a.suspended_routes > 0) return 'partial';
    return 'unknown';
  }

  /** Uptime % based on active/total routes ratio */
  function calcUptime(a) {
    const t = a.total_routes || 0;
    if (t === 0) return 0;
    return Math.round(((a.active_routes + (a.seasonal_routes || 0) * 0.5) / t) * 100);
  }

  /** Reliability tier from uptime % */
  function reliabilityTier(pct) {
    if (pct >= 95) return { label: 'Excellent', emoji: '\u{1F7E2}', cls: 'excellent' };
    if (pct >= 80) return { label: 'Good', emoji: '\u{1F7E1}', cls: 'good' };
    if (pct >= 50) return { label: 'Average', emoji: '\u{1F7E0}', cls: 'average' };
    return { label: 'Unreliable', emoji: '\u{1F534}', cls: 'unreliable' };
  }

  /** Timeline heatmap color level */
  function timelineLevel(pct) {
    if (pct >= 80) return 'excellent';
    if (pct >= 60) return 'good';
    if (pct >= 40) return 'average';
    return 'unreliable';
  }

  /** CSS class for the uptime fill bar */
  function barClass(pct) {
    if (pct >= 80) return 'excellent';
    if (pct >= 60) return 'good';
    if (pct >= 50) return 'average';
    return 'unreliable';
  }

  /* ── Seeded PRNG for reproducible mock timeline data ── */
  function seededRand(seed) {
    let s = seed;
    return function () {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
  }

  /**
   * Generate mock monthly uptime data since October 2023.
   * Will be replaced by real timeline data from data.json when available.
   *
   * Expected real data format (per airline object):
   *   timeline: [{ month: '2023-10', uptime: 85, status: 'active' }, ...]
   *
   * @param {Object} a - airline from data.json
   * @returns {Array} monthly data objects
   */
  function genTimeline(a) {
    // If real timeline data exists, use it
    if (a.timeline && Array.isArray(a.timeline) && a.timeline.length > 0) {
      return a.timeline.map(function (t) {
        var parts = t.month.split('-');
        return {
          month: parseInt(parts[1], 10) - 1,
          year: parseInt(parts[0], 10),
          uptime: t.uptime,
          label: new Date(t.month + '-01').toLocaleString('en-US', { month: 'short', year: '2-digit' }),
          dateStr: t.month,
        };
      });
    }

    // No real data — return empty array, timeline section won't render
    return [];
  }

  /* ── Load Data ── */

  async function load() {
    var loading = $('#loading');
    var content = $('#content');
    try {
      var resp = await fetch('data.json?' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      DATA = await resp.json();

      loading.hidden = true;
      content.hidden = false;

      renderKPI(DATA.stats);
      renderUpdated(DATA.generated_at);
      renderCards(DATA.airlines);
      setupFilters();
      setupRecommend();
    } catch (e) {
      loading.innerHTML =
        '<div style="text-align:center;padding:60px 20px;color:var(--text-secondary)">' +
        '<div style="font-size:40px;margin-bottom:12px;">\u26A0\uFE0F</div>' +
        '<p style="font-weight:600;font-size:16px;">Failed to load data</p>' +
        '<p style="font-size:14px;margin-top:4px;">' + esc(e.message) + '</p></div>';
    }
  }

  function renderUpdated(iso) {
    if (!iso) return;
    var d = new Date(iso);
    $('.updated').textContent =
      'Last updated: ' +
      d.toLocaleString('en-US', { timeZone: 'Asia/Jerusalem', dateStyle: 'medium', timeStyle: 'short' }) +
      ' Israel time';
  }

  /* ── KPI Cards ── */

  function renderKPI(stats) {
    setKPI('total-airlines', stats.total_airlines, 'accent');
    setKPI('active-airlines', stats.active_airlines, 'green');
    setKPI('suspended-airlines', stats.suspended_airlines, 'red');
    // Hide avg reliability KPI — no real timeline data yet
    var avgCard = $('[data-kpi="avg-reliability"]');
    if (avgCard) avgCard.hidden = true;
  }

  function setKPI(id, val, cls) {
    var card = $('[data-kpi="' + id + '"]');
    if (!card) return;
    var el = card.querySelector('.kpi-value');
    if (el) {
      el.textContent = val;
      el.className = 'kpi-value ' + cls;
    }
  }

  /* ── Airline Cards ── */

  function renderCards(airlines) {
    var grid = $('#airline-grid');
    var filtered = filterAirlines(airlines);

    if (filtered.length === 0) {
      grid.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-state-icon">\uD83D\uDD0D</div>' +
        '<h3>No airlines match your search</h3>' +
        '<p>Try a different search term or filter.</p></div>';
      updateStatsBar(0, airlines.length);
      return;
    }

    // Sort: active first, then by uptime desc, then total routes desc
    filtered.sort(function (a, b) {
      var ord = { active: 0, partial: 1, suspended: 2, unknown: 3 };
      var sa = ord[airlineStatus(a)] || 3;
      var sb = ord[airlineStatus(b)] || 3;
      if (sa !== sb) return sa - sb;
      var ua = calcUptime(a),
        ub = calcUptime(b);
      if (ua !== ub) return ub - ua;
      return (b.total_routes || 0) - (a.total_routes || 0);
    });

    grid.innerHTML = filtered.map(function (a) { return cardHTML(a); }).join('');
    updateStatsBar(filtered.length, airlines.length);

    // Click handlers for expand/collapse
    $$('.airline-card').forEach(function (card) {
      card.addEventListener('click', function (e) {
        if (e.target.closest('.route-detail-item')) return;
        toggleCard(this);
      });
    });
  }

  function cardHTML(a) {
    var hasRealData = DATA.scores && DATA.scores.length > 0 && DATA.timeline && DATA.timeline.length > 0;
    var status = airlineStatus(a);
    var total = a.total_routes || 0;
    var active = a.active_routes || 0;
    var suspended = a.suspended_routes || 0;

    var html = '<div class="airline-card" data-airline="' + esc(a.name) + '" data-iata="' + esc(a.iata || '') + '">' +
      '<div class="card-header">' +
      '<div class="card-title">' +
      '<span class="airline-name">' + esc(a.name) + '</span>' +
      '<span class="airline-iata">' + esc(a.iata || '') + '</span>' +
      '</div>' +
      '<div class="card-status"><span class="status-badge ' + status + '">' + status + '</span></div>' +
      '</div>';

    // Only show uptime bar when real historical data exists
    if (hasRealData && a.reliability_score != null) {
      var uptime = a.uptime_pct || 0;
      var score = a.reliability_score || 0;
      var label = a.score_label || 'unknown';
      var emojiMap = { excellent: '\u{1F7E2}', good: '\u{1F7E1}', average: '\u{1F7E0}', unreliable: '\u{1F534}', unknown: '\u26AA' };
      var emoji = emojiMap[label] || '\u26AA';
      html +=
        '<div class="uptime-section">' +
        '<div class="uptime-bar" title="' + uptime + '% uptime">' +
        '<div class="uptime-fill ' + label + '" style="width:' + uptime + '%"></div></div>' +
        '<div class="uptime-label">' +
        '<span class="uptime-text">' + uptime + '% uptime</span>' +
        '<span class="uptime-since">since Oct \'23</span>' +
        '</div></div>' +
        '<div class="card-meta">' +
        '<span class="reliability-badge ' + label + '">' + emoji + ' ' + label.charAt(0).toUpperCase() + label.slice(1) + '</span>';
    } else {
      // No historical data yet — show route counts only
      html += '<div class="card-meta" style="padding: 14px 16px 12px;">';
    }

    html +=
      '<span class="route-count-label"><strong>' + total + '</strong> route' + (total !== 1 ? 's' : '') +
      ' \u00B7 ' + active + ' active' +
      (suspended > 0 ? ', ' + suspended + ' suspended' : '') +
      '</span>' +
      '<span class="card-expand-icon">\u25BC</span>' +
      '</div>' +
      '<div class="card-expanded" hidden>' +
      '<div class="card-expanded-inner" data-airline="' + esc(a.name) + '"></div></div>' +
      '</div>';

    return html;
  }

  /* ── Expand / Collapse ── */

  function toggleCard(card) {
    var expanded = card.querySelector('.card-expanded');
    var isVisible = !expanded.hidden;

    if (isVisible) {
      expanded.hidden = true;
      card.classList.remove('expanded');
      return;
    }

    // Accordion: collapse other open cards
    $$('.airline-card.expanded').forEach(function (c) {
      if (c !== card) {
        c.classList.remove('expanded');
        c.querySelector('.card-expanded').hidden = true;
      }
    });

    expanded.hidden = false;
    card.classList.add('expanded');

    // Lazy-load on first expand
    var inner = expanded.querySelector('.card-expanded-inner');
    if (!inner.dataset.loaded) {
      inner.dataset.loaded = 'true';
      loadExpanded(inner, inner.dataset.airline);
    }
  }

  function loadExpanded(container, airlineName) {
    var airline = null;
    for (var i = 0; i < DATA.airlines.length; i++) {
      if (DATA.airlines[i].name === airlineName) { airline = DATA.airlines[i]; break; }
    }
    if (!airline) return;

    var timeline = genTimeline(airline);
    var routes = DATA.routes.filter(function (r) { return r.airline_name === airlineName; });

    container.innerHTML = timelineHTML(timeline) + routesHTML(routes);
  }

  /* ── Timeline Heatmap ── */

  function timelineHTML(months) {
    var html =
      '<div class="timeline-section">' +
      '<div class="timeline-header">' +
      '<span class="timeline-title">Monthly Uptime</span>' +
      '<div class="timeline-legend">' +
      '<span class="timeline-legend-item"><span class="timeline-legend-swatch" style="background:var(--green)"></span> \u226580%</span>' +
      '<span class="timeline-legend-item"><span class="timeline-legend-swatch" style="background:var(--amber)"></span> \u226560%</span>' +
      '<span class="timeline-legend-item"><span class="timeline-legend-swatch" style="background:var(--orange)"></span> \u226540%</span>' +
      '<span class="timeline-legend-item"><span class="timeline-legend-swatch" style="background:var(--red)"></span> &lt;40%</span>' +
      '</div></div><div class="timeline-grid">';

    for (var i = 0; i < months.length; i++) {
      var m = months[i];
      var level = timelineLevel(m.uptime);
      html +=
        '<div class="timeline-month ' + level + '">' +
        '<span class="timeline-tooltip">' + esc(m.label) + '<br>' + m.uptime + '%</span></div>';
    }

    html += '</div></div>';
    return html;
  }

  /* ── Routes List ── */

  function routesHTML(routes) {
    routes.sort(function (a, b) {
      var sa = a.status === 'active' ? 0 : a.status === 'seasonal' ? 1 : 2;
      var sb = b.status === 'active' ? 0 : b.status === 'seasonal' ? 1 : 2;
      if (sa !== sb) return sa - sb;
      return (a.destination || '').localeCompare(b.destination || '');
    });

    var html =
      '<div class="route-detail-section">' +
      '<h4>Routes (' + routes.length + ')</h4>' +
      '<div class="route-detail-list">';

    for (var i = 0; i < routes.length; i++) {
      var r = routes[i];
      html +=
        '<div class="route-detail-item">' +
        '<div class="route-dest">' +
        '<span class="route-code">' + esc(r.origin) + '</span>' +
        '<span class="route-arrow">\u2192</span>' +
        '<span class="route-code">' + esc(r.destination) + '</span>' +
        '<span class="route-city">' + esc(r.destination_name || '') + '</span>' +
        '</div>' +
        '<div class="route-status"><span class="status-badge ' + r.status + '">' + r.status + '</span></div>' +
        '</div>';
    }

    html += '</div></div>';
    return html;
  }

  /* ── Filtering ── */

  function filterAirlines(airlines) {
    var filtered = airlines;

    if (currentFilter === 'active') {
      filtered = filtered.filter(function (a) { return a.active_routes > 0 && a.suspended_routes === 0; });
    } else if (currentFilter === 'suspended') {
      filtered = filtered.filter(function (a) { return a.active_routes === 0 && a.suspended_routes > 0; });
    } else if (currentFilter === 'partial') {
      filtered = filtered.filter(function (a) { return a.active_routes > 0 && a.suspended_routes > 0; });
    }

    // Search is handled separately (client-side hide/show)
    return filtered;
  }

  function updateStatsBar(visible, total) {
    var countEl = $('#visible-count');
    var textEl = $('#stats-bar-text');
    if (visible === total) {
      countEl.textContent = total + ' airlines';
      textEl.textContent = '';
    } else {
      countEl.textContent = visible + ' of ' + total + ' airlines';
      textEl.textContent = '(filtered)';
    }
  }

  /* ── Filters ── */

  function setupFilters() {
    var search = $('#search');
    var filterSel = $('#status-filter');

    var timeout;
    search.addEventListener('input', function () {
      clearTimeout(timeout);
      timeout = setTimeout(function () {
        var q = search.value.toLowerCase().trim();
        $$('.airline-card').forEach(function (card) {
          var name = (card.dataset.airline || '').toLowerCase();
          var iata = (card.dataset.iata || '').toLowerCase();
          var match = !q || name.indexOf(q) !== -1 || iata.indexOf(q) !== -1;
          card.style.display = match ? '' : 'none';
          if (!match) {
            var exp = card.querySelector('.card-expanded');
            if (exp) exp.hidden = true;
            card.classList.remove('expanded');
          }
        });
      }, 150);
    });

    filterSel.addEventListener('change', function () {
      currentFilter = filterSel.value;
      renderCards(DATA.airlines);
      search.value = '';
    });
  }

  /* ── Recommendation ── */

  function setupRecommend() {
    $('#recommend-btn').addEventListener('click', recommendAirline);
    $('#rec-close').addEventListener('click', function () {
      $('#recommendation').hidden = true;
    });
  }

  function recommendAirline() {
    var candidates = DATA.airlines.filter(function (a) { return a.active_routes > 0; });

    if (candidates.length === 0) {
      $('#rec-airline').textContent = 'No active airlines found';
      $('#rec-detail').textContent = 'All airlines are currently suspended.';
      $('#recommendation').hidden = false;
      return;
    }

    // Check if real reliability scores exist
    var hasRealScores = DATA.scores && DATA.scores.length > 0;
    var hasRealTimeline = DATA.timeline && DATA.timeline.length > 0;

    if (hasRealScores && hasRealTimeline) {
      candidates.sort(function (a, b) {
        return (b.reliability_score || 0) - (a.reliability_score || 0);
      });
      var best = candidates[0];
      var score = best.reliability_score || 0;
      var label = best.score_label || 'unknown';
      var emojiMap = { excellent: '\u{1F7E2}', good: '\u{1F7E1}', average: '\u{1F7E0}', unreliable: '\u{1F534}', unknown: '\u26AA' };
      $('#rec-airline').innerHTML = esc(best.name) + ' (' + esc(best.iata || '') + ')';
      $('#rec-detail').innerHTML =
        (emojiMap[label] || '\u26AA') + ' ' + label.charAt(0).toUpperCase() + label.slice(1) +
        ' reliability \u00B7 ' + score +
        '% score \u00B7 ' + best.active_routes +
        ' active route' + (best.active_routes !== 1 ? 's' : '');
      $('#recommendation').hidden = false;
      return;
    }

    // Fallback: no real scores — recommend by route count only, be transparent
    candidates.sort(function (a, b) {
      return (b.active_routes || 0) - (a.active_routes || 0);
    });
    var best = candidates[0];
    $('#rec-airline').innerHTML = esc(best.name) + ' (' + esc(best.iata || '') + ')';
    $('#rec-detail').textContent =
      best.active_routes + ' active routes \u2022 Historical reliability data still being collected';
    $('#recommendation').hidden = false;
    $('#recommendation').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  /* ── Init ── */
  document.addEventListener('DOMContentLoaded', load);
})();
