/**
 * Header component for Swayam Capital (BUILD-9).
 * Features:
 * - Brand with sage circular logo mark
 * - Center NIFTY 50 live quote with monospace tabular delta
 * - Right horizontal navigation pills ("Home", "Strategy Builder", "Backtesting Lab", "Journal & Analytics")
 * - User avatar pill "AS"
 */

import { formatINR } from '../utils/format.js';

export function initHeader(container, options = {}) {
  const activePage = options.activePage || 'home';
  const onNavigate = options.onNavigate || (() => {});
  const onReloadRules = options.onReloadRules || (() => {});

  container.innerHTML = `
    <header class="swayam-header">
      <div class="swayam-brand">
        <div class="swayam-logo-mark">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="4" fill="#101116"/>
          </svg>
        </div>
        <span>SWAYAM CAPITAL</span>
      </div>

      <div class="header-spot-pill" id="header-spot-display">
        <span style="color: var(--dl-fg-3);">NIFTY 50</span>
        <span style="color: var(--dl-line);">·</span>
        <span id="header-spot-val" style="color: var(--dl-fg); font-weight: 600;">24,842.65</span>
        <span style="color: var(--dl-line);">·</span>
        <span id="header-spot-delta" style="color: var(--accent-sage); font-weight: 600;">+12.35 (+0.05%)</span>
      </div>

      <div style="display: flex; align-items: center;">
        <nav class="nav-pill-row">
          <button type="button" class="nav-pill ${activePage === 'home' ? 'active' : ''}" data-page="home">
            Home
          </button>
          <button type="button" class="nav-pill ${activePage === 'strategy' ? 'active' : ''}" data-page="strategy">
            Strategy Builder
          </button>
          <button type="button" class="nav-pill ${activePage === 'backtest' ? 'active' : ''}" data-page="backtest" style="opacity: 0.6;" title="BUILD-11">
            Backtesting Lab
          </button>
          <button type="button" class="nav-pill ${activePage === 'journal' ? 'active' : ''}" data-page="journal" style="opacity: 0.6;" title="BUILD-12">
            Journal & Analytics
          </button>
        </nav>
        <div class="user-avatar-pill" title="Abhishek Sikka">
          AS
        </div>
      </div>
    </header>
  `;

  container.querySelectorAll('.nav-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const page = btn.getAttribute('data-page');
      if (page === 'backtest' || page === 'journal') {
        alert(`${page === 'backtest' ? 'Backtesting Lab' : 'Journal & Analytics'} will arrive in BUILD-11/12.`);
        return;
      }
      container.querySelectorAll('.nav-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      onNavigate(page);
    });
  });
}

export function updateHeaderSpot(spot, changeVal = 12.35, changePct = 0.05) {
  const elVal = document.getElementById('header-spot-val');
  const elDelta = document.getElementById('header-spot-delta');
  if (elVal && spot) {
    elVal.textContent = Number(spot).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (elDelta && changePct !== undefined) {
    const isUp = changePct >= 0;
    const sign = isUp ? '+' : '';
    elDelta.textContent = `${sign}${changeVal.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
    elDelta.style.color = isUp ? 'var(--accent-sage)' : 'var(--accent-coral)';
  }
}
