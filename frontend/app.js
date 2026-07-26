/**
 * fly2israel — dashboard JS
 * Zero dependencies. Fetches data.json and renders the table.
 */
(function () {
  'use strict';

  let DATA = null;
  let currentFilter = 'all';

  const statusOrder = { active: 0, partial: 1, seasonal: 2, suspended: 3, unknown: 4 };

  /* ── Utilities ── */
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }

  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function escapeHTML(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  /* ── Fetch & Render ── */
  async function load() {
    const loading = $('.loading');
    const content = $('.content');
    try {
      const resp = await fetch('data.json');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      DATA = await resp.json();

      loading.style.display = 'none';
      content.style.display = 'block';

      renderStats(DATA.stats);
      renderTable(DATA.airlines);
      renderUpdated(DATA.generated_at);
    } catch (err) {
      loading.textContent = `⚠ Failed to load data: ${err.message}`;
    }
  }

  function renderUpdated(iso) {
    if (!iso) return;
    const d = new Date(iso);
    const el = $('.updated');
    el.textContent = `Last updated: ${d.toLocaleString('en-IL', { timeZone: 'Asia/Jerusalem' })} Israel time`;
  }

  function renderStats(stats) {
    $('.kpi-total-airlines .kpi-value').textContent = stats.total_airlines;
    $('.kpi-active-airlines .kpi-value').textContent = stats.active_airlines;
    $('.kpi-suspended-airlines .kpi-value').textContent = stats.suspended_airlines;
    $('.kpi-total-routes .kpi-value').textContent = stats.total_routes;
    $('.kpi-active-routes .kpi-value').textContent = stats.active_routes;
    $('.kpi-suspended-routes .kpi-value').textContent = stats.suspended_routes;
  }

  function renderTable(airlines) {
    const tbody = $('.airline-table tbody');
    let filtered = airlines;

    if (currentFilter === 'active') {
      filtered = airlines.filter(a => a.active_routes > 0 && a.suspended_routes === 0);
    } else if (currentFilter === 'suspended') {
      filtered = airlines.filter(a => a.active_routes === 0 && a.suspended_routes > 0);
    } else if (currentFilter === 'partial') {
      filtered = airlines.filter(a => a.active_routes > 0 && a.suspended_routes > 0);
    }

    filtered.sort((a, b) => {
      // Sort by overall_status (active first), then active_routes desc
      const sa = a.active_routes > 0 && a.suspended_routes === 0 ? 0
              : a.active_routes === 0 && a.suspended_routes > 0 ? 2
              : a.active_routes > 0 && a.suspended_routes > 0 ? 1 : 3;
      const sb = b.active_routes > 0 && b.suspended_routes === 0 ? 0
              : b.active_routes === 0 && b.suspended_routes > 0 ? 2
              : b.active_routes > 0 && b.suspended_routes > 0 ? 1 : 3;
      if (sa !== sb) return sa - sb;
      return b.active_routes - a.active_routes;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-secondary);">No airlines match this filter</td></tr>`;
      return;
    }

    let html = '';
    for (const a of filtered) {
      const total = a.active_routes + a.suspended_routes + (a.seasonal_routes || 0);
      const activePct = total > 0 ? (a.active_routes / total * 100) : 0;
      const suspendedPct = total > 0 ? (a.suspended_routes / total * 100) : 0;

      const overallStatus = a.active_routes > 0 && a.suspended_routes === 0 ? 'active'
                          : a.active_routes === 0 && a.suspended_routes > 0 ? 'suspended'
                          : a.active_routes > 0 && a.suspended_routes > 0 ? 'partial'
                          : 'unknown';

      html += `<tr class="clickable" data-airline="${escapeHTML(a.name)}" data-iata="${escapeHTML(a.iata || '')}">`;
      html += `<td><span class="airline-name">${escapeHTML(a.name)}</span> <span class="airline-iata">${escapeHTML(a.iata || '')}</span></td>`;
      html += `<td>${escapeHTML(a.country || '—')}</td>`;
      html += `<td><span class="status-badge ${overallStatus}">${overallStatus}</span></td>`;
      html += `<td style="min-width:120px;"><div class="route-bar" title="${a.active_routes} active / ${a.suspended_routes} suspended">`;
      if (activePct > 0) html += `<div class="bar-active" style="width:${activePct}%"></div>`;
      if (suspendedPct > 0) html += `<div class="bar-suspended" style="width:${suspendedPct}%"></div>`;
      html += `</div></td>`;
      html += `<td class="route-count">${a.active_routes}</td>`;
      html += `<td class="route-count">${a.suspended_routes}</td>`;
      html += '</tr>';

      // Pre-render route detail rows (hidden)
      html += `<tr class="route-detail" style="display:none;" data-iata="${escapeHTML(a.iata || '')}" data-airline="${escapeHTML(a.name)}">`;
      html += `<td colspan="6"><div class="route-detail-inner"><div class="route-list" id="routes-${escapeHTML(a.iata || a.name)}"></div></div></td>`;
      html += '</tr>';
    }
    tbody.innerHTML = html;

    // Attach click handlers
    $$('.airline-table .clickable').forEach(row => {
      row.addEventListener('click', function () {
        const iata = this.dataset.iata;
        const detailRow = this.nextElementSibling;
        if (!detailRow || !detailRow.classList.contains('route-detail')) return;
        const isVisible = detailRow.style.display !== 'none';
        detailRow.style.display = isVisible ? 'none' : 'table-row';

        // Load routes on first expand
        if (!isVisible && !detailRow.dataset.loaded) {
          detailRow.dataset.loaded = 'true';
          const routesContainer = detailRow.querySelector('.route-list');
          const airlineName = this.dataset.airline;
          loadRoutes(routesContainer, airlineName);
        }
      });
    });
  }

  function loadRoutes(container, airlineName) {
    const routes = DATA.routes.filter(r => r.airline_name === airlineName);
    const origin = routes.length > 0 ? routes[0].origin : 'TLV';

    let html = '';
    // Sort: active first, then by destination
    routes.sort((a, b) => {
      const sa = a.status === 'active' ? 0 : a.status === 'seasonal' ? 1 : 2;
      const sb = b.status === 'active' ? 0 : b.status === 'seasonal' ? 1 : 2;
      if (sa !== sb) return sa - sb;
      return a.destination.localeCompare(b.destination);
    });

    for (const r of routes) {
      html += `<div class="route-item">
        <div class="route-dest">
          <span class="route-code">${escapeHTML(r.origin)}→${escapeHTML(r.destination)}</span>
          <span class="route-city">${escapeHTML(r.destination_name || '')}</span>
        </div>
        <span class="status-badge ${r.status}">${r.status}</span>
      </div>`;
    }
    container.innerHTML = html;
  }

  /* ── Filters ── */
  function initFilters() {
    const search = $('#search');
    const statusFilter = $('#status-filter');

    // Real-time search: filter rows client-side
    search.addEventListener('input', () => {
      const q = search.value.toLowerCase().trim();
      $$('.airline-table .clickable').forEach(row => {
        const name = row.dataset.airline?.toLowerCase() || '';
        const iata = row.dataset.iata?.toLowerCase() || '';
        const match = !q || name.includes(q) || iata.includes(q);
        row.style.display = match ? '' : 'none';
        // Also hide route detail if parent is hidden
        const detail = row.nextElementSibling;
        if (detail && detail.classList.contains('route-detail') && !match) {
          detail.style.display = 'none';
        }
      });
    });

    statusFilter.addEventListener('change', () => {
      currentFilter = statusFilter.value;
      renderTable(DATA.airlines);
      search.value = '';
    });
  }

  /* ── Init ── */
  document.addEventListener('DOMContentLoaded', () => {
    initFilters();
    load();
  });

})();
