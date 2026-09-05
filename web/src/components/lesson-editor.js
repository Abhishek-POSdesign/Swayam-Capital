/**
 * Lesson Editor Modal Component for Swayam Capital (BUILD-11).
 *
 * Allows manual refinement of AI lessons and synchronizes to Supabase + Obsidian Vault.
 */

import { api } from '../api.js';

export class LessonEditorModal {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.onSave = options.onSave || (() => {});
    this.currentLesson = null;
    this.isOpen = false;
  }

  open(lesson) {
    this.currentLesson = lesson;
    this.isOpen = true;
    this.render();
  }

  close() {
    this.isOpen = false;
    this.currentLesson = null;
    if (this.container) this.container.innerHTML = '';
  }

  async handleSave() {
    const textarea = this.container.querySelector('#lesson-textarea');
    if (!textarea || !this.currentLesson) return;

    const newText = textarea.value.trim();
    if (!newText) return;

    const saveBtn = this.container.querySelector('#btn-save-lesson');
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';
    }

    try {
      const updated = await api.updateLesson(this.currentLesson.id, newText);
      this.close();
      this.onSave(updated);
    } catch (err) {
      console.error('Failed to save lesson:', err);
      alert(`Could not save lesson: ${err.message}`);
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Refined Lesson';
      }
    }
  }

  render() {
    if (!this.container || !this.isOpen || !this.currentLesson) return;

    const currentText = decodeURIComponent(this.currentLesson.lesson_text || '');

    this.container.innerHTML = `
      <div class="modal-overlay" style="position: fixed; inset: 0; background: rgba(0,0,0,0.65); display: flex; align-items: center; justify-content: center; z-index: 1200; backdrop-filter: blur(2px);">
        <div class="modal-content" style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: var(--radius-card); width: 500px; max-width: 90vw; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
          
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="margin: 0; font-size: 1rem; color: var(--dl-fg); display: flex; align-items: center; gap: 8px;">
              <span>💡</span> Refine Lesson Takeaway
            </h3>
            <button type="button" id="btn-close-lesson-modal" style="background: none; border: none; color: var(--dl-fg-3); font-size: 1.2rem; cursor: pointer;">✕</button>
          </div>

          <p style="font-size: 0.76rem; color: var(--dl-fg-3); margin-top: 0; margin-bottom: 12px; line-height: 1.4;">
            Refine the automated lesson to capture your specific insight. Updating this note also persists to your Obsidian Second Brain journal note.
          </p>

          <textarea id="lesson-textarea" rows="4" style="width: 100%; box-sizing: border-box; background: var(--bg-elevated); border: 1px solid var(--dl-line); border-radius: 6px; padding: 10px; color: var(--dl-fg); font-size: 0.85rem; font-family: inherit; resize: vertical; outline: none;">${currentText}</textarea>

          <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px;">
            <button type="button" id="btn-cancel-lesson" style="background: transparent; border: 1px solid var(--dl-line); color: var(--dl-fg-2); border-radius: 4px; padding: 6px 14px; font-size: 0.8rem; cursor: pointer;">
              Cancel
            </button>
            <button type="button" id="btn-save-lesson" style="background: var(--accent-lilac); border: none; color: #101116; font-weight: 600; border-radius: 4px; padding: 6px 16px; font-size: 0.8rem; cursor: pointer;">
              Save Refined Lesson
            </button>
          </div>

        </div>
      </div>
    `;

    const textarea = this.container.querySelector('#lesson-textarea');
    if (textarea) {
      textarea.value = currentText;
    }

    this.container.querySelector('#btn-close-lesson-modal')?.addEventListener('click', () => this.close());
    this.container.querySelector('#btn-cancel-lesson')?.addEventListener('click', () => this.close());
    this.container.querySelector('#btn-save-lesson')?.addEventListener('click', () => this.handleSave());
  }
}