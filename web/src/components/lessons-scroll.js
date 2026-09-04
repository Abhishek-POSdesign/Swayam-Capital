/**
 * Lesson Ledger Scroll Feed for Swayam Capital (BUILD-11).
 *
 * Displays chronologically ordered AI and user-refined lessons.
 */

export class LessonsScrollComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.lessons = options.lessons || [];
    this.onEditLesson = options.onEditLesson || (() => {});
  }

  update(lessons) {
    this.lessons = lessons || [];
    this.render();
  }

  render() {
    if (!this.container) return;

    if (!this.lessons.length) {
      this.container.innerHTML = `
        <div style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 14px 16px;">
          <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600; margin-bottom: 8px;">
            💡 Recent Lesson Ledger
          </div>
          <div style="font-size: 0.78rem; color: var(--dl-fg-3); font-style: italic;">
            No lessons recorded yet. Complete paper trades to automatically generate grounded lessons.
          </div>
        </div>
      `;
      return;
    }

    const itemsHtml = this.lessons.map(l => {
      const outcome = (l.outcome || 'BREAKEVEN').toUpperCase();
      const tagBg = outcome === 'WIN' ? 'var(--accent-sage-tint, rgba(134,171,146,0.15))' : outcome === 'LOSS' ? 'var(--accent-coral-tint, rgba(221,129,112,0.15))' : 'rgba(255,255,255,0.06)';
      const tagColor = outcome === 'WIN' ? 'var(--accent-sage, #86ab92)' : outcome === 'LOSS' ? 'var(--accent-coral, #dd8170)' : 'var(--dl-fg-3)';
      const dateStr = (l.trade_closed_at || l.created_at || '').substring(0, 10);
      const isEdited = l.lesson_source === 'user_edited';

      return `
        <div class="lesson-card" style="padding: 10px 12px; border-radius: 6px; background: rgba(255,255,255,0.02); border: 1px solid var(--dl-line); display: flex; flex-direction: column; gap: 6px;">
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.7rem;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-weight: 600; padding: 2px 6px; border-radius: 3px; font-size: 0.65rem; background: ${tagBg}; color: ${tagColor};">
                ${outcome}
              </span>
              <span style="font-weight: 600; color: var(--dl-fg);">${l.strategy_name}</span>
            </div>
            <span style="color: var(--dl-fg-3); font-family: var(--font-mono);">${dateStr}</span>
          </div>
          <p style="margin: 0; font-size: 0.78rem; color: var(--dl-fg-2); line-height: 1.4; font-style: italic;">
            "${l.lesson_text}"
          </p>
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.68rem; color: var(--dl-fg-3); margin-top: 2px;">
            <span>${isEdited ? '✏️ Refined' : '🤖 AI Generated'}</span>
            <button type="button" class="btn-scroll-edit" data-id="${l.id}" data-text="${encodeURIComponent(l.lesson_text)}" style="background: none; border: none; color: var(--accent-lilac); cursor: pointer; padding: 0; font-size: 0.68rem;">
              Edit
            </button>
          </div>
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div style="background: var(--dl-card, #191b21); border: 1px solid var(--dl-line, #282a33); border-radius: var(--radius-card, 8px); padding: 14px 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <span style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600;">
            💡 Recent Lesson Ledger
          </span>
          <span style="font-size: 0.7rem; color: var(--accent-lilac); font-weight: 600;">
            ${this.lessons.length} Lessons
          </span>
        </div>
        <div class="lessons-feed" style="display: flex; flex-direction: column; gap: 8px; max-height: 290px; overflow-y: auto; padding-right: 4px;">
          ${itemsHtml}
        </div>
      </div>
    `;

    this.container.querySelectorAll('.btn-scroll-edit').forEach(btn => {
      btn.addEventListener('click', () => {
        const lid = btn.getAttribute('data-id');
        const ltext = decodeURIComponent(btn.getAttribute('data-text'));
        this.onEditLesson({ id: lid, lesson_text: ltext });
      });
    });
  }
}