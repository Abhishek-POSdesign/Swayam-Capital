/**
 * Header component: Swayam Capital logo, live NIFTY quote, and Reload Rules button.
 */

import { formatINR } from '../utils/format.js';

export function initHeader(container, onReloadRules) {
  container.innerHTML = `
    <header>
      <div class="brand">
        <div class="logo">SWAYAM CAPITAL</div>
        <div class="header-spot" id="header-spot-display">
          NIFTY: <span class="mono" id="header-spot-val">Loading...</span>
        </div>
      </div>
      <div class="header-actions">
        <button id="btn-reload-rules" title="Reload Method rules from Obsidian vault">
          ⟳ Reload Rules
        </button>
      </div>
    </header>
  `;

  document.getElementById('btn-reload-rules').addEventListener('click', async () => {
    const btn = document.getElementById('btn-reload-rules');
    btn.disabled = true;
    btn.textContent = 'Reloading...';
    try {
      await onReloadRules();
    } finally {
      btn.disabled = false;
      btn.textContent = '⟳ Reload Rules';
    }
  });
}

export function updateHeaderSpot(spot, changePct = 0) {
  const el = document.getElementById('header-spot-val');
  if (!el) return;
  const changeStr = changePct !== 0 ? ` (${changePct > 0 ? '+' : ''}${changePct.toFixed(2)}%)` : '';
  el.textContent = `${formatINR(spot).replace('₹', '')}${changeStr}`;
  el.style.color = changePct >= 0 ? 'var(--green)' : 'var(--red)';
}
