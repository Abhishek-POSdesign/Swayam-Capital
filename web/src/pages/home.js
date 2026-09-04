/**
 * Home Page Controller for Swayam Capital (BUILD-9-FIXES-A).
 * Layout change: NIFTY chart full-width (span-12), India VIX own row below it.
 */

import { api } from '../api.js';
import { ReadinessRitualComponent } from '../components/readiness-ritual.js';
import { VerdictCardComponent } from '../components/verdict-card.js';
import { KPIHistoryCardComponent } from '../components/kpi-history-card.js';
import { OvernightStripComponent } from '../components/overnight-strip.js';
import { VixCardComponent } from '../components/vix-card.js';
import { NiftyChartCardComponent } from '../components/nifty-chart-card.js';
import { MacroEventsCardComponent } from '../components/macro-events-card.js';
import { ReadingQueueCardComponent } from '../components/reading-queue-card.js';
import { ChatSurfaceComponent } from '../components/chat-surface.js';

export class HomePage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenAIDrawer, onOpenSettings, onNavigateStrategy }
    this.countdownInterval = null;
  }

  async init() {
    this.render();
    this.mountComponents();
    this.setupSidebarCollapse();
    this.startMarketCountdown();
    await this.loadData();
  }

  render() {
    this.container.innerHTML = `
      <div class="home-canvas" style="max-width: 1720px; margin: 0 auto; padding: 20px 24px; display: flex; gap: 20px; align-items: flex-start; transition: all var(--dur-base, 200ms) ease;">
        <!-- LEFT COLUMN: Readiness Ritual & History — Foldable/Collapsible (Fix A7) -->
        <aside class="home-left-col" id="home-left-sidebar" style="flex: 0 0 360px; width: 360px; display: flex; flex-direction: column; gap: 13px; transition: flex-basis 0.22s ease, width 0.22s ease; position: relative;">
          
          <!-- Collapsed thin bar strip (shown when collapsed) -->
          <div id="left-col-collapsed-strip" style="display: none; width: 56px; height: 500px; background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: 12px; flex-direction: column; align-items: center; padding: 14px 6px; cursor: pointer;" title="Expand Morning Ritual">
            <button id="btn-expand-ritual" type="button" style="background: var(--dl-card-2); border: 1px solid var(--dl-line); color: var(--dl-fg); width: 34px; height: 34px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.85rem;" title="Expand Sidebar">
              ▶
            </button>
            <div style="writing-mode: vertical-rl; transform: rotate(180deg); margin-top: 24px; font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.1em; color: var(--accent-sage); font-weight: 700; white-space: nowrap;">
              MORNING RITUAL · READY
            </div>
          </div>

          <!-- Expanded content wrapper -->
          <div id="left-col-expanded-content" style="display: flex; flex-direction: column; gap: 13px; width: 100%;">
            <!-- Header bar with collapse chevron -->
            <div style="display: flex; justify-content: flex-end; padding-right: 2px;">
              <button id="btn-collapse-ritual" type="button" title="Collapse Morning Ritual to slim strip" style="background: var(--dl-card-2); border: 1px solid var(--dl-line); color: var(--dl-fg-2); border-radius: 6px; padding: 3px 8px; font-size: 0.75rem; cursor: pointer; display: flex; align-items: center; gap: 4px;">
                <span>Fold</span> ◀
              </button>
            </div>
            <div id="home-ritual-container"></div>
            <div id="home-verdict-container"></div>
            <div id="home-kpi-container" style="display: flex; flex-direction: column; gap: 13px;"></div>
          </div>
        </aside>

        <!-- RIGHT COLUMN (Flex grow): Market Prep & Intelligence -->
        <main class="home-right-col" style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px;">
          <!-- Section Header with Countdown -->
          <div style="display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 2px;">
            <h1 style="font-family: var(--font-serif); font-size: 1.45rem; font-weight: 500; color: var(--dl-fg); margin: 0;">
              Market Prep
            </h1>
            <div id="home-market-countdown" class="eyebrow" style="color: var(--accent-amber); font-family: var(--font-mono); font-size: 0.8rem;">
              MARKET OPENS 09:15 IST · 2h 47m
            </div>
          </div>

          <!-- 12-Column Bento Grid for Market Prep Tiles -->
          <div class="bento-grid">
            <!-- Row 1: Overnight Global Strip (Span 12) — big numbers -->
            <div id="home-overnight-container" class="span-12"></div>

            <!-- Row 2: NIFTY 50 Chart — FULL WIDTH (Span 12) with interactive tabs -->
            <div id="home-nifty-container" class="span-12"></div>

            <!-- Row 3: India VIX — OWN FULL-WIDTH ROW (Span 12) with percentile band -->
            <div id="home-vix-container" class="span-12"></div>

            <!-- Row 4: Macro Events (Span 6) + Reading Queue (Span 6) -->
            <div id="home-macro-container" class="span-6"></div>
            <div id="home-reading-container" class="span-6"></div>
          </div>

          <!-- Row 5: AI Trading Partner Full-Width Workspace (~1000-1400px) -->
          <section id="home-ai-brief-container" style="width: 100%; min-width: 0;"></section>
        </main>
      </div>
    `;
  }

  setupSidebarCollapse() {
    const sidebar = this.container.querySelector('#home-left-sidebar');
    const expandedContent = this.container.querySelector('#left-col-expanded-content');
    const collapsedStrip = this.container.querySelector('#left-col-collapsed-strip');
    const btnCollapse = this.container.querySelector('#btn-collapse-ritual');
    const btnExpand = this.container.querySelector('#btn-expand-ritual');

    if (!sidebar || !expandedContent || !collapsedStrip) return;

    const setCollapsed = (collapsed) => {
      if (collapsed) {
        sidebar.style.flex = '0 0 56px';
        sidebar.style.width = '56px';
        expandedContent.style.display = 'none';
        collapsedStrip.style.display = 'flex';
        try { localStorage.setItem('swayam_ritual_collapsed', 'true'); } catch (_) {}
      } else {
        sidebar.style.flex = '0 0 360px';
        sidebar.style.width = '360px';
        expandedContent.style.display = 'flex';
        collapsedStrip.style.display = 'none';
        try { localStorage.setItem('swayam_ritual_collapsed', 'false'); } catch (_) {}
      }
    };

    if (btnCollapse) btnCollapse.addEventListener('click', () => setCollapsed(true));
    if (btnExpand) btnExpand.addEventListener('click', () => setCollapsed(false));
    if (collapsedStrip) collapsedStrip.addEventListener('click', () => setCollapsed(false));

    // Restore saved state
    try {
      const saved = localStorage.getItem('swayam_ritual_collapsed');
      if (saved === 'true') {
        setCollapsed(true);
      }
    } catch (_) {}
  }

  mountComponents() {
    // 1. Readiness Ritual
    const ritualContainer = this.container.querySelector('#home-ritual-container');
    this.ritualComponent = new ReadinessRitualComponent(ritualContainer, {
      onVerdictChanged: (verdict) => {
        if (this.verdictComponent) {
          this.verdictComponent.setVerdict(verdict);
        }
      },
      onSubmitted: async () => {
        await this.loadKpiData();
      },
    });
    this.ritualComponent.init();

    // 2. Verdict Card
    const verdictContainer = this.container.querySelector('#home-verdict-container');
    this.verdictComponent = new VerdictCardComponent(verdictContainer);
    this.verdictComponent.init();

    // 3. KPI History Cards
    const kpiContainer = this.container.querySelector('#home-kpi-container');
    this.kpiComponent = new KPIHistoryCardComponent(kpiContainer);
    this.kpiComponent.render({});

    // 4. Overnight Strip — big numbers
    const overnightContainer = this.container.querySelector('#home-overnight-container');
    this.overnightComponent = new OvernightStripComponent(overnightContainer);
    this.overnightComponent.render();

    // 5. NIFTY Chart — full-width, interactive tabs
    const niftyContainer = this.container.querySelector('#home-nifty-container');
    this.niftyChartComponent = new NiftyChartCardComponent(niftyContainer);
    this.niftyChartComponent.render();

    // 6. India VIX — own row with percentile band
    const vixContainer = this.container.querySelector('#home-vix-container');
    this.vixComponent = new VixCardComponent(vixContainer);
    this.vixComponent.render();

    // 7. Macro Events
    const macroContainer = this.container.querySelector('#home-macro-container');
    this.macroEventsComponent = new MacroEventsCardComponent(macroContainer);
    this.macroEventsComponent.render();

    // 8. Reading Queue
    const readingContainer = this.container.querySelector('#home-reading-container');
    this.readingQueueComponent = new ReadingQueueCardComponent(readingContainer);
    this.readingQueueComponent.render();

    // 9. AI Trading Partner Full-Width Conversational Workspace
    const briefContainer = this.container.querySelector('#home-ai-brief-container');
    if (briefContainer) {
      this.aiBriefComponent = new ChatSurfaceComponent(briefContainer, {
        onOpenSettings: () => {
          if (this.options.onOpenSettings) {
            this.options.onOpenSettings();
          }
        },
        onNavigateStrategy: (dest) => {
          if (this.options.onNavigateStrategy) {
            this.options.onNavigateStrategy(dest);
          } else {
            window.location.href = dest;
          }
        },
      });
      this.aiBriefComponent.init();
    }
  }

  async loadData() {
    await Promise.allSettled([
      this.loadKpiData(),
      this.loadAIBrief(),
      this.loadVixData(),
    ]);
  }

  async loadKpiData() {
    try {
      const kpis = await api.getReadinessKPIs();
      if (this.kpiComponent && kpis) {
        this.kpiComponent.render(kpis);
      }
    } catch (err) {
      console.warn('Could not fetch readiness KPIs:', err);
    }
  }

  async loadVixData() {
    try {
      const vixData = await api.getVixHistory();
      if (this.vixComponent && vixData) {
        this.vixComponent.render(vixData);
      }
    } catch (err) {
      console.warn('Could not load VIX history, using defaults:', err);
    }
  }

  async loadAIBrief() {
    try {
      const brief = await api.getAIBrief();
      if (this.aiBriefComponent && brief) {
        this.aiBriefComponent.render(brief);
        if (brief.reading_queue && this.readingQueueComponent) {
          this.readingQueueComponent.render(brief.reading_queue);
        }
        if (brief.macro_events_next_5_days && this.macroEventsComponent) {
          this.macroEventsComponent.render(brief.macro_events_next_5_days);
        }
        if (brief.overnight_global && this.overnightComponent) {
          const mapped = {};
          for (const [k, v] of Object.entries(brief.overnight_global)) {
            mapped[k] = {
              value: typeof v.value === 'number' ? v.value.toLocaleString('en-US') : v.value,
              pct: v.pct !== undefined ? `${v.pct > 0 ? '+' : ''}${v.pct}%` : (v.abs_change !== undefined ? `${v.abs_change > 0 ? '+' : ''}${v.abs_change}` : ''),
              positive: v.pct !== undefined ? v.pct >= 0 : (v.abs_change !== undefined ? v.abs_change >= 0 : true),
              neutral: k === 'USDINR',
            };
          }
          this.overnightComponent.render(mapped);
        }
        if (brief.india_vix && this.vixComponent) {
          // AI brief may include a simplified vix snapshot — only use if no full history loaded
          // (loadVixData runs in parallel and takes priority)
        }
      }
    } catch (err) {
      console.warn('Could not load AI brief, rendering notice:', err);
      if (this.aiBriefComponent) {
        this.aiBriefComponent.render(null, err.message || 'Service unavailable');
      }
    }
  }

  startMarketCountdown() {
    const el = this.container.querySelector('#home-market-countdown');
    if (!el) return;

    const update = () => {
      const now = new Date();
      // IST is UTC+5:30
      const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
      const istDate = new Date(utcMs + 5.5 * 3600000);

      const target = new Date(istDate);
      target.setHours(9, 15, 0, 0);

      let diff = target.getTime() - istDate.getTime();
      if (diff < 0) {
        if (istDate.getHours() < 15 || (istDate.getHours() === 15 && istDate.getMinutes() <= 30)) {
          el.textContent = 'MARKET OPEN · CLOSES 15:30 IST';
          el.style.color = 'var(--accent-sage)';
          return;
        } else {
          target.setDate(target.getDate() + 1);
          diff = target.getTime() - istDate.getTime();
        }
      }

      const hours = Math.floor(diff / 3600000);
      const mins = Math.floor((diff % 3600000) / 60000);
      el.textContent = `MARKET OPENS 09:15 IST · ${hours}h ${mins}m`;
      el.style.color = 'var(--accent-amber)';
    };

    update();
    this.countdownInterval = setInterval(update, 60000);
  }

  destroy() {
    if (this.countdownInterval) {
      clearInterval(this.countdownInterval);
      this.countdownInterval = null;
    }
  }
}
