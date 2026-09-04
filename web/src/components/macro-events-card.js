/**
 * Macro Events Card Component for Swayam Capital (BUILD-9).
 * Displays high-impact economic and central bank calendar events for the next 5 days.
 */

export class MacroEventsCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(events = null) {
    const defaultEvents = [
      { event: 'RBI Policy Meet', date: 'Sep 8', severity: 'high', tagColor: 'var(--accent-amber)', tagBg: 'var(--accent-amber-tint)' },
      { event: 'US CPI Print', date: 'Sep 11', severity: 'medium', tagColor: 'var(--accent-blue)', tagBg: 'var(--accent-blue-tint)' },
      { event: 'FOMC Minutes', date: 'Sep 12', severity: 'medium', tagColor: 'var(--accent-blue)', tagBg: 'var(--accent-blue-tint)' },
    ];

    const list = events || defaultEvents;

    const rowsHtml = list.map((item, idx) => {
      const borderTop = idx > 0 ? 'border-top: 1px solid var(--dl-line);' : '';
      const tagBg = item.tagBg || (item.severity === 'high' ? 'var(--accent-amber-tint)' : 'var(--accent-blue-tint)');
      const tagColor = item.tagColor || (item.severity === 'high' ? 'var(--accent-amber)' : 'var(--accent-blue)');

      return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; ${borderTop}">
          <span style="font-size: 0.85rem; font-weight: 500; color: var(--dl-fg);">
            ${item.event}
          </span>
          <span style="font-family: var(--font-sans); font-size: 0.75rem; font-weight: 600; padding: 3px 10px; border-radius: 999px; background: ${tagBg}; color: ${tagColor}; border: 1px solid rgba(255,255,255,0.06);">
            ${item.date}
          </span>
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="tile macro-events-tile" style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; min-height: 170px;">
        <span class="eyebrow" style="color: var(--dl-fg-3);">MACRO EVENTS · NEXT 5 DAYS</span>
        <div style="display: flex; flex-direction: column; margin-top: 6px;">
          ${rowsHtml}
        </div>
      </div>
    `;
  }
}
