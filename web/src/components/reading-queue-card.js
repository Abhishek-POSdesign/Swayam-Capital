/**
 * AI Reading Queue Card Component for Swayam Capital.
 *
 * BUILD-11.6: Removed fake placeholder articles with dead '#' links.
 * Renders an honest "coming soon" empty state until BUILD-13 (Knowledge Base + RAG).
 */

export class ReadingQueueCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render() {
    this.container.innerHTML = `
      <div class="tile reading-queue-tile" style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; min-height: 170px;">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <span class="eyebrow" style="color: var(--text-muted);">📚 AI READING QUEUE</span>
          <span style="font-size: 0.6rem; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--accent-lilac-tint); color: var(--accent-lilac); font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;">SOON</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px; align-items: flex-start; justify-content: center; flex: 1; padding-top: 12px;">
          <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0; line-height: 1.4;">
            Automated overnight scans + Gemini-summarized reading briefs.
          </p>
          <p style="font-size: 0.72rem; color: var(--text-muted); margin: 0; line-height: 1.4;">
            Lands with <strong style="color: var(--accent-lilac);">BUILD-13</strong> — Knowledge Base + RAG.
          </p>
        </div>
      </div>
    `;
  }
}
