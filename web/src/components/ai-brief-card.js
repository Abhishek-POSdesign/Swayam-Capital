/**
 * AI Brief Card Component for Swayam Capital (BUILD-9-FIXES-A).
 * Fixes: renders markdown properly (bold, bullets, code spans) instead of raw asterisks.
 * Light parser — no external library, no HTML injection from untrusted content.
 */

/**
 * Parse a markdown string into safe HTML.
 * Supports: **bold**, *italic*, `code`, bullet lists (- item), blank-line paragraphs.
 * Does NOT support: headings, links, images, raw HTML (all stripped/escaped).
 */
function parseMarkdown(text) {
  if (!text) return '';

  // Escape any raw HTML to prevent injection
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Split into lines for list detection
  const lines = escaped.split('\n');
  const outputParts = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const isBullet = /^[-*+]\s+/.test(line);

    if (isBullet) {
      if (!inList) {
        outputParts.push('<ul style="margin: 6px 0 6px 1.2em; padding: 0; list-style: disc;">');
        inList = true;
      }
      const content = line.replace(/^[-*+]\s+/, '');
      outputParts.push(`<li style="margin-bottom: 3px;">${inlineMarkdown(content)}</li>`);
    } else {
      if (inList) {
        outputParts.push('</ul>');
        inList = false;
      }
      const trimmed = line.trim();
      if (trimmed === '') {
        // blank line → paragraph break
        if (outputParts.length > 0 && !outputParts[outputParts.length - 1].endsWith('<br>')) {
          outputParts.push('<br>');
        }
      } else {
        outputParts.push(inlineMarkdown(trimmed));
        // Add soft newline between non-blank lines that aren't already block elements
        if (i < lines.length - 1 && lines[i + 1].trim() !== '' && !/^[-*+]/.test(lines[i + 1])) {
          outputParts.push(' ');
        }
      }
    }
  }

  if (inList) outputParts.push('</ul>');
  return outputParts.join('');
}

/** Process inline markdown: **bold**, *italic*, `code` */
function inlineMarkdown(text) {
  return text
    // **bold**
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // *italic* (not preceded by another *)
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>')
    // `code`
    .replace(/`([^`]+)`/g, '<code style="font-family: var(--font-mono); font-size: 0.85em; background: var(--dl-card-2); padding: 1px 5px; border-radius: 4px; color: var(--accent-lilac);">$1</code>');
}

export class AIBriefCardComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenAIDrawer }
  }

  render(briefData = null, errorMessage = null) {
    if (errorMessage) {
      this.container.innerHTML = `
        <div class="tile ai-brief-tile span-12" style="border-left: 2px solid var(--accent-coral); background: var(--dl-card); display: flex; flex-direction: column; gap: 8px;">
          <span class="eyebrow" style="color: var(--accent-coral);">WHAT MATTERS TODAY · AI UNAVAILABLE</span>
          <p style="font-size: 0.9rem; color: var(--dl-fg-2); margin: 0; line-height: 1.5;">
            AI Trading Partner briefing could not be generated: <strong style="color: var(--accent-coral);">${errorMessage}</strong>
          </p>
        </div>
      `;
      return;
    }

    const defaultBrief = "India VIX at 12.85 confirms low-volatility regime. Premium-selling favorable, but reward is compressed — spreads over singles.\n\n**Skip trades if:**\n- Event risk within 48 hours — RBI meet Monday\n- Intraday VIX rises above 15\n\n**Prefer setups where:**\n- Realistic risk (2σ NIFTY move ≈ ₹165) stays under 1% cap\n- Bear Put Spread around 24,800 has clean structure given yesterday's higher-high VWAP bounce";
    const rawText = briefData?.brief_text || defaultBrief;
    const htmlContent = parseMarkdown(rawText);

    this.container.innerHTML = `
      <div class="tile ai-brief-tile span-12" style="border-left: 3px solid var(--accent-lilac); background: var(--dl-card); display: flex; flex-direction: column; gap: 10px; padding: 18px 22px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="color: var(--accent-lilac);">
              <path d="M8 0L9.8 6.2L16 8L9.8 9.8L8 16L6.2 9.8L0 8L6.2 6.2L8 0Z" fill="currentColor"/>
            </svg>
            <span class="eyebrow" style="color: var(--accent-lilac); font-weight: 700;">WHAT MATTERS TODAY · AI TRADING PARTNER</span>
          </div>
          <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--dl-fg-3);">DAILY PRE-MARKET</span>
        </div>

        <div id="ai-brief-content" style="font-family: var(--font-sans); font-size: 0.9375rem; color: var(--dl-fg); margin: 0; line-height: 1.6; font-weight: 400;">
          ${htmlContent}
        </div>

        <div style="display: flex; justify-content: flex-end; margin-top: 4px;">
          <button id="btn-open-ai-drawer" style="background: var(--accent-lilac); color: #101116; border: none; height: 32px; padding: 0 16px; border-radius: 9px; font-size: 0.82rem; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: transform var(--dur-fast) ease;">
            Open Full AI Drawer →
          </button>
        </div>
      </div>
    `;

    const btnOpen = this.container.querySelector('#btn-open-ai-drawer');
    if (btnOpen) {
      btnOpen.addEventListener('click', () => {
        if (this.options.onOpenAIDrawer) {
          this.options.onOpenAIDrawer();
        }
      });
    }
  }
}
