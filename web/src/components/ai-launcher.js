/**
 * Floating AI Launcher Component for Swayam Capital (BUILD-9).
 * Persistent 48px lilac circular orb in bottom-right viewport with sparkle icon.
 * Clicking toggles the AI Trading Partner drawer.
 */

export class AIFloatingLauncher {
  constructor(options = {}) {
    this.options = options; // { onToggle }
    this.el = null;
  }

  init() {
    // Check if already mounted
    if (document.getElementById('floating-ai-launcher-btn')) {
      return;
    }

    const btn = document.createElement('button');
    btn.id = 'floating-ai-launcher-btn';
    btn.className = 'ai-floating-launcher';
    btn.title = 'Open AI Trading Partner';
    btn.setAttribute('aria-label', 'Open AI Trading Partner');
    btn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      </svg>
    `;

    btn.addEventListener('click', () => {
      if (this.options.onToggle) {
        this.options.onToggle();
      }
    });

    document.body.appendChild(btn);
    this.el = btn;
  }

  destroy() {
    if (this.el && this.el.parentElement) {
      this.el.parentElement.removeChild(this.el);
      this.el = null;
    }
  }
}
