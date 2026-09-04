/**
 * AI Reading Queue Card Component for Swayam Capital (BUILD-9).
 * Displays curated overnight market reports and research notes scanned for the trader.
 */

export class ReadingQueueCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(queue = null) {
    const defaultQueue = [
      { source: 'Motilal Oswal', title: 'Options desk report', read_time_min: 3, url: '#' },
      { source: 'Zerodha Varsity', title: 'VIX interpretation', read_time_min: 8, url: '#' },
      { source: 'Bloomberg', title: 'Global vol regime shift', read_time_min: 5, url: '#' },
    ];

    const list = queue || defaultQueue;

    const rowsHtml = list.map((item, idx) => {
      const borderTop = idx > 0 ? 'border-top: 1px solid var(--dl-line);' : '';

      return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; ${borderTop}">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 20px; height: 20px; border-radius: 50%; background: var(--accent-lilac-tint); border: 1px solid var(--accent-lilac); display: flex; align-items: center; justify-content: center;">
              <div style="width: 6px; height: 6px; border-radius: 50%; background: var(--accent-lilac);"></div>
            </div>
            <div style="display: flex; flex-direction: column;">
              <span style="font-size: 0.85rem; font-weight: 500; color: var(--dl-fg);">
                ${item.source} <span style="color: var(--dl-fg-3);">—</span> ${item.title}
              </span>
            </div>
          </div>
          <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--dl-fg-3);">
            ${item.read_time_min} min
          </span>
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="tile reading-queue-tile" style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; min-height: 170px;">
        <span class="eyebrow" style="color: var(--dl-fg-3);">AI READING QUEUE · OVERNIGHT SCAN</span>
        <div style="display: flex; flex-direction: column; margin-top: 6px;">
          ${rowsHtml}
        </div>
      </div>
    `;
  }
}
