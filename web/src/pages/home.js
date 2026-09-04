/**
 * Home Page Controller for Swayam Capital (BUILD-9).
 * Composes the Readiness Ritual (left column) and Market Prep (right column).
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
import { AIBriefCardComponent } from '../components/ai-brief-card.js';

export class HomePage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onOpenAIDrawer }
    this.countdownInterval = null;
  }

  async init() {
    this.render();
    this.mountComponents();
    this.startMarketCountdown();
    await this.loadData();
  }

  render() {
    this.container.innerHTML = `
      <div class="home-canvas" style="max-width: 1720px; margin: 0 auto; padding: 20px 24px; display: flex; gap: 20px; align-items: flex-start;">
        <!-- LEFT COLUMN (380px fixed width): Readiness Ritual & History -->
        <aside class="home-left-col" style="flex: 0 0 380px; width: 380px; display: flex; flex-direction: column; gap: 13px;">
          <div id="home-ritual-container"></div>
          <div id="home-verdict-container"></div>
          <div id="home-kpi-container" style="display: flex; flex-direction: column; gap: 13px;"></div>
        </aside>

        <!-- RIGHT COLUMN (Flex grow): Market Prep & Intelligence -->
        <main class="home-right-col" style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 13px;">
          <!-- Section Header with Countdown -->
          <div style="display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 4px;">
            <h1 style="font-family: var(--font-serif); font-size: 1.45rem; font-weight: 500; color: var(--dl-fg); margin: 0;">
              Market Prep
            </h1>
            <div id="home-market-countdown" class="eyebrow" style="color: var(--accent-amber); font-family: var(--font-mono); font-size: 0.8rem;">
              MARKET OPENS 09:15 IST · 2h 47m
            </div>
          </div>

          <!-- 12-Column Bento Grid -->
          <div class="bento-grid">
            <!-- Row 1: Overnight Global Strip (Span 12) -->
            <div id="home-overnight-container" class="span-12"></div>

            <!-- Row 2: VIX Card (Span 4) + NIFTY Chart (Span 8) -->
            <div id="home-vix-container" class="span-4"></div>
            <div id="home-nifty-container" class="span-8"></div>

            <!-- Row 3: Macro Events (Span 6) + Reading Queue (Span 6) -->
            <div id="home-macro-container" class="span-6"></div>
            <div id="home-reading-container" class="span-6"></div>

            <!-- Row 4: AI Trading Partner Brief (Span 12) -->
            <div id="home-ai-brief-container" class="span-12"></div>
          </div>
        </main>
      </div>
    `;
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

    // 4. Overnight Strip
    const overnightContainer = this.container.querySelector('#home-overnight-container');
    this.overnightComponent = new OvernightStripComponent(overnightContainer);
    this.overnightComponent.render();

    // 5. VIX Card
    const vixContainer = this.container.querySelector('#home-vix-container');
    this.vixComponent = new VixCardComponent(vixContainer);
    this.vixComponent.render();

    // 6. NIFTY Chart
    const niftyContainer = this.container.querySelector('#home-nifty-container');
    this.niftyChartComponent = new NiftyChartCardComponent(niftyContainer);
    this.niftyChartComponent.render();

    // 7. Macro Events
    const macroContainer = this.container.querySelector('#home-macro-container');
    this.macroEventsComponent = new MacroEventsCardComponent(macroContainer);
    this.macroEventsComponent.render();

    // 8. Reading Queue
    const readingContainer = this.container.querySelector('#home-reading-container');
    this.readingQueueComponent = new ReadingQueueCardComponent(readingContainer);
    this.readingQueueComponent.render();

    // 9. AI Brief Card
    const briefContainer = this.container.querySelector('#home-ai-brief-container');
    this.aiBriefComponent = new AIBriefCardComponent(briefContainer, {
      onOpenAIDrawer: () => {
        if (this.options.onOpenAIDrawer) {
          this.options.onOpenAIDrawer();
        }
      },
    });
    this.aiBriefComponent.render();
  }

  async loadData() {
    await Promise.allSettled([
      this.loadKpiData(),
      this.loadAIBrief(),
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
          this.vixComponent.render(brief.india_vix);
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
        // Market is open or closed for the day
        if (istDate.getHours() < 15 || (istDate.getHours() === 15 && istDate.getMinutes() <= 30)) {
          el.textContent = 'MARKET OPEN · CLOSES 15:30 IST';
          el.style.color = 'var(--accent-sage)';
          return;
        } else {
          // Closed, target tomorrow 09:15
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
