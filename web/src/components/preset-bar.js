/**
 * Strategy Preset Bar Component for Swayam Capital (BUILD-10).
 *
 * Renders quick preset chips for options structures and an
 * "Import from AI conversation" action button.
 */

export const STRATEGY_PRESETS = [
  { id: 'bear-put', name: 'Bear Put Spread', type: 'debit' },
  { id: 'bull-call', name: 'Bull Call Spread', type: 'debit' },
  { id: 'iron-condor', name: 'Iron Condor', type: 'credit' },
  { id: 'iron-fly', name: 'Iron Fly', type: 'credit' },
  { id: 'bear-call', name: 'Bear Call Spread', type: 'credit' },
  { id: 'bull-put', name: 'Bull Put Spread', type: 'credit' },
  { id: 'calendar', name: 'Calendar Spread', type: 'time' },
  { id: 'custom', name: 'Custom', type: 'custom' },
];

export function generatePresetLegs(presetId, spotPrice = 24850, expiryDate = null) {
  // Round spot to nearest 50 for the strikes.
  const base = Math.round(spotPrice / 50) * 50;
  // No fabricated premiums, no guessed expiry. Legs ship with entry_premium 0 and a blank expiry;
  // the leg builder fills each leg's REAL expiry and REAL last-traded/live price on mount.
  // `back_month: true` tells the builder to put that leg on the SECOND real expiry (calendars).
  const exp = expiryDate || '';
  const L = (strike, option_type, direction, extra = {}) => ({
    strike,
    option_type,
    direction,
    quantity_lots: 1,
    lot_size: 75,
    expiry_date: exp,
    entry_premium: 0,
    ...extra,
  });

  switch (presetId) {
    case 'bear-put':
      return [L(base + 50, 'PE', 'buy'), L(base - 150, 'PE', 'sell')];
    case 'bull-call':
      return [L(base - 50, 'CE', 'buy'), L(base + 150, 'CE', 'sell')];
    case 'iron-condor':
      return [
        L(base - 350, 'PE', 'buy'),
        L(base - 150, 'PE', 'sell'),
        L(base + 150, 'CE', 'sell'),
        L(base + 350, 'CE', 'buy'),
      ];
    case 'iron-fly':
      return [
        L(base - 200, 'PE', 'buy'),
        L(base, 'PE', 'sell'),
        L(base, 'CE', 'sell'),
        L(base + 200, 'CE', 'buy'),
      ];
    case 'bear-call':
      return [L(base + 200, 'CE', 'buy'), L(base + 50, 'CE', 'sell')];
    case 'bull-put':
      return [L(base - 200, 'PE', 'buy'), L(base - 50, 'PE', 'sell')];
    case 'calendar':
      // Front-month short + back-month long at the same strike (different expiries).
      return [
        L(base, 'CE', 'sell'),
        L(base, 'CE', 'buy', { back_month: true }),
      ];
    default:
      return [L(base, 'PE', 'buy')];
  }
}

export function getNextWeeklyThursday() {
  const d = new Date();
  const day = d.getDay();
  const diff = (4 - day + 7) % 7 || 7; // nearest upcoming Thursday
  d.setDate(d.getDate() + diff);
  return d.toISOString().split('T')[0];
}

export function getFollowingThursday(dateStr) {
  const d = new Date(dateStr);
  d.setDate(d.getDate() + 7);
  return d.toISOString().split('T')[0];
}

export class PresetBarComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onSelectPreset, onImportAI, currentSpot }
    this.activePreset = 'bear-put';
  }

  render(activePreset = null) {
    if (activePreset) this.activePreset = activePreset;

    const chipsHtml = STRATEGY_PRESETS.map((p) => {
      const isActive = p.id === this.activePreset;
      return `
        <button
          type="button"
          id="preset-chip-${p.id}"
          class="preset-chip ${isActive ? 'active' : ''}"
          data-preset-id="${p.id}"
          style="
            padding: 6px 14px;
            border-radius: var(--radius-pill);
            font-size: 0.82rem;
            font-weight: ${isActive ? '600' : '500'};
            cursor: pointer;
            border: 1px solid ${isActive ? 'var(--accent-sage)' : 'var(--dl-line)'};
            background: ${isActive ? 'var(--accent-sage-tint)' : 'var(--dl-card)'};
            color: ${isActive ? 'var(--accent-sage)' : 'var(--dl-fg-2)'};
            transition: all var(--dur-fast) ease;
            white-space: nowrap;
          "
        >
          ${p.name}
        </button>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="preset-bar" style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 18px; background: var(--dl-card); border-radius: var(--radius-card); border: 1px solid var(--dl-line); overflow-x: auto;">
        <div style="display: flex; align-items: center; gap: 8px; flex: 1; overflow-x: auto; scrollbar-width: none;">
          <span class="eyebrow" style="margin-right: 4px; color: var(--dl-fg-3); white-space: nowrap;">PRESETS:</span>
          ${chipsHtml}
        </div>
        <div style="flex-shrink: 0;">
          <button
            type="button"
            id="btn-import-ai"
            style="
              display: flex;
              align-items: center;
              gap: 6px;
              padding: 6px 14px;
              border-radius: var(--radius-pill);
              font-size: 0.8rem;
              font-weight: 600;
              background: var(--accent-blue-tint);
              color: var(--accent-blue);
              border: 1px solid rgba(117, 154, 208, 0.35);
              cursor: pointer;
              transition: transform var(--dur-fast) ease;
            "
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0L9.8 6.2L16 8L9.8 9.8L8 16L6.2 9.8L0 8L6.2 6.2L8 0Z"/>
            </svg>
            Import from AI conversation
          </button>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    STRATEGY_PRESETS.forEach((p) => {
      const btn = this.container.querySelector(`#preset-chip-${p.id}`) || this.container.querySelector(`[data-preset-id="${p.id}"]`);
      if (btn) {
        btn.addEventListener('click', () => {
          this.activePreset = p.id;
          this.render(p.id);
          if (this.options.onSelectPreset) {
            const name = STRATEGY_PRESETS.find((item) => item.id === p.id)?.name || 'Custom';
            // Pass the preset ID only. The page builds strikes from the LIVE spot (never a
            // stale snapshot / fallback), and refuses to build them when there is no real price.
            this.options.onSelectPreset(name, p.id);
          }
        });
      }
    });

    const btnImport = this.container.querySelector('#btn-import-ai');
    if (btnImport) {
      btnImport.addEventListener('click', () => {
        if (this.options.onImportAI) {
          this.options.onImportAI();
        }
      });
    }
  }
}
