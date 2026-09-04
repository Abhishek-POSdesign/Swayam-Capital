/**
 * Header component for Swayam Capital (BUILD-9-FIXES-A).
 * Added: Theme switcher (moon/auto/sun cycling toggle) immediately left of AS avatar.
 */

import { formatINR } from '../utils/format.js';

/** Returns the current theme stored in localStorage, defaulting to 'dark'. */
function getTheme() {
  return localStorage.getItem('swayam-theme') || 'dark';
}

/** Applies theme to <html data-theme> and persists to localStorage. */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('swayam-theme', theme);
}

/** SVG icons for each theme mode (matches Atlas theme-switcher.js exactly). */
const THEME_ICONS = {
  dark: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
  auto: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
  light: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`,
};

const THEME_CYCLE = { dark: 'auto', auto: 'light', light: 'dark' };
const THEME_LABELS = { dark: 'Dark', auto: 'Auto', light: 'Light' };

export function initHeader(container, options = {}) {
  const activePage = options.activePage || 'home';
  const onNavigate = options.onNavigate || (() => {});
  const onReloadRules = options.onReloadRules || (() => {});

  // Apply stored theme on init
  const storedTheme = getTheme();
  applyTheme(storedTheme);

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

      <div style="display: flex; align-items: center; gap: 8px;">
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
            Journal &amp; Analytics
          </button>
        </nav>

        <!-- Theme Switcher — cycles Dark → Auto → Light → Dark -->
        <button
          id="theme-switcher-btn"
          title="Theme: ${THEME_LABELS[storedTheme]}"
          style="
            display: flex; align-items: center; justify-content: center;
            width: 32px; height: 32px; border-radius: var(--radius-pill);
            background: var(--theme-switcher-bg);
            border: 1px solid var(--dl-line);
            color: var(--dl-fg-2);
            cursor: pointer;
            transition: color var(--dur-fast) ease, background var(--dur-fast) ease;
          "
          aria-label="Switch theme"
        >
          ${THEME_ICONS[storedTheme]}
        </button>

        <div class="user-avatar-pill" title="Abhishek Sikka">
          AS
        </div>
      </div>
    </header>
  `;

  // Nav pill clicks
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

  // Theme switcher click — cycles through dark → auto → light → dark
  const themeSwitcherBtn = container.querySelector('#theme-switcher-btn');
  if (themeSwitcherBtn) {
    themeSwitcherBtn.addEventListener('click', () => {
      const current = getTheme();
      const next = THEME_CYCLE[current] || 'dark';
      applyTheme(next);
      themeSwitcherBtn.innerHTML = THEME_ICONS[next];
      themeSwitcherBtn.title = `Theme: ${THEME_LABELS[next]}`;
      window.dispatchEvent(new CustomEvent('swayam-theme-change', { detail: { theme: next } }));
    });
  }
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
