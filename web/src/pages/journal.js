/**
 * Trade Journal & Performance Analytics Page Controller for Swayam Capital (BUILD-11).
 *
 * Coordinates:
 * - 7-Tile KPI Strip
 * - Multi-criteria Filter Bar (Status, Outcome, Discipline, Strategy, Exit Reason, Dates)
 * - Detailed Trades Table with expandable rows & historical fields
 * - Edge Analytics (Cumulative P&L, Strategy breakdown, Exit reason, Trend stats)
 * - Lesson Ledger Scroll & Editor Modal
 */

import { api } from '../api.js';
import { KPIStripComponent } from '../components/kpi-strip.js';
import { TradesTableComponent } from '../components/trades-table.js';
import { AnalyticsCumulativePnlComponent } from '../components/analytics-cumulative-pnl.js';
import { AnalyticsPnlByStrategyComponent } from '../components/analytics-pnl-by-strategy.js';
import { AnalyticsExitReasonComponent } from '../components/analytics-exit-reason.js';
import { LessonsScrollComponent } from '../components/lessons-scroll.js';
import { LessonEditorModal } from '../components/lesson-editor.js';

export class JournalPage {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;

    // Filters state
    this.filters = {
      status: 'all',
      outcome: 'all',
      discipline: 'all',
      strategy: '',
      exit_reason: '',
      directional_view: '',
      from_date: '',
      to_date: '',
      sort_by: 'date_desc',
    };

    // Sub-components
    this.kpiStrip = null;
    this.tradesTable = null;
    this.cumulativeChart = null;
    this.strategyChart = null;
    this.exitReasonChart = null;
    this.lessonsScroll = null;
    this.lessonModal = null;

    this.isLoading = false;
  }

  async init() {
    this.render();
    this.mountComponents();
    this.setupEventListeners();
    await this.loadData();
  }

  render() {
    this.container.innerHTML = `
      <div class="journal-page-canvas" style="padding: 14px 24px; max-width: 1600px; margin: 0 auto; box-sizing: border-box; display: flex; flex-direction: column; gap: 12px;">
        
        <!-- Housekeeping Banner (Pre-launch test trades) -->
        <div id="journal-housekeeping-banner-container"></div>

        <!-- Header & Title Bar -->
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--dl-line); padding-bottom: 14px;">
          <div>
            <div style="display: flex; align-items: center; gap: 10px;">
              <h1 style="margin: 0; font-size: 1.35rem; font-weight: 700; color: var(--dl-fg); letter-spacing: -0.01em;">
                Trade Journal &amp; Performance Ledger
              </h1>
              <span id="journal-trades-badge" style="background: rgba(255,255,255,0.06); color: var(--accent-lilac); padding: 3px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600; font-family: var(--font-mono);">
                Loading...
              </span>
            </div>
            <p style="margin: 4px 0 0 0; font-size: 0.78rem; color: var(--dl-fg-3);">
              Historical Excel playbook + live paper trading log with automated AI lessons and disciplined edge analytics.
            </p>
          </div>

          <div style="display: flex; align-items: center; gap: 10px;">
            <button id="btn-refresh-journal" type="button" style="background: var(--dl-card); border: 1px solid var(--dl-line); color: var(--dl-fg-2); padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; cursor: pointer; display: flex; align-items: center; gap: 6px;">
              <span>🔄</span> Refresh
            </button>
          </div>
        </div>

        <!-- Top 7-Tile KPI Strip Container -->
        <div id="journal-kpi-strip-container"></div>

        <!-- Filter Bar -->
        <div class="journal-filter-bar" style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: var(--radius-card); padding: 12px 16px; display: flex; flex-direction: column; gap: 10px;">
          <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;">
            
            <!-- Quick Filter Pills -->
            <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
              
              <!-- Status Pills -->
              <div style="display: flex; align-items: center; gap: 4px; background: var(--bg-elevated); padding: 3px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <button type="button" class="filter-pill active" data-filter="status" data-value="all" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg); cursor: pointer;">All Status</button>
                <button type="button" class="filter-pill" data-filter="status" data-value="closed" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">Closed</button>
                <button type="button" class="filter-pill" data-filter="status" data-value="open" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">Open</button>
              </div>

              <!-- Outcome Pills -->
              <div style="display: flex; align-items: center; gap: 4px; background: var(--bg-elevated); padding: 3px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <button type="button" class="filter-pill active" data-filter="outcome" data-value="all" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg); cursor: pointer;">All Outcome</button>
                <button type="button" class="filter-pill" data-filter="outcome" data-value="win" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">Wins</button>
                <button type="button" class="filter-pill" data-filter="outcome" data-value="loss" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">Losses</button>
                <button type="button" class="filter-pill" data-filter="outcome" data-value="breakeven" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">Breakeven</button>
              </div>

              <!-- Discipline Pills -->
              <div style="display: flex; align-items: center; gap: 4px; background: var(--bg-elevated); padding: 3px; border-radius: 6px; border: 1px solid var(--dl-line);">
                <button type="button" class="filter-pill active" data-filter="discipline" data-value="all" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg); cursor: pointer;">All Rules</button>
                <button type="button" class="filter-pill" data-filter="discipline" data-value="followed" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">✓ Followed</button>
                <button type="button" class="filter-pill" data-filter="discipline" data-value="broken" style="background: transparent; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.74rem; font-weight: 600; color: var(--dl-fg-3); cursor: pointer;">✗ Broken</button>
              </div>

            </div>

            <!-- Sort By dropdown -->
            <div style="display: flex; align-items: center; gap: 8px; font-size: 0.74rem; color: var(--dl-fg-3);">
              <span>Sort:</span>
              <select id="journal-sort-select" style="background: var(--bg-elevated); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 4px 8px; border-radius: 4px; font-size: 0.74rem; outline: none;">
                <option value="date_desc">Latest First</option>
                <option value="date_asc">Oldest First</option>
                <option value="pnl_desc">Highest P&amp;L</option>
                <option value="pnl_asc">Lowest P&amp;L</option>
              </select>
            </div>

          </div>

          <!-- Secondary Filters Row -->
          <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 0.75rem; border-top: 1px solid rgba(255,255,255,0.04); padding-top: 8px;">
            <input type="text" id="filter-strategy" placeholder="Filter strategy..." value="${this.filters.strategy}" style="background: var(--bg-elevated); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; outline: none; width: 140px;" />
            <input type="text" id="filter-exit-reason" placeholder="Filter exit trigger..." value="${this.filters.exit_reason}" style="background: var(--bg-elevated); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; outline: none; width: 140px;" />
            <select id="filter-directional-view" style="background: var(--bg-elevated); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; outline: none;">
              <option value="">All Directions</option>
              <option value="Bullish">Bullish</option>
              <option value="Bearish">Bearish</option>
              <option value="Neutral">Neutral</option>
              <option value="Range-bound">Range-bound</option>
            </select>
            <div style="display: flex; align-items: center; gap: 6px; margin-left: auto;">
              <span style="color: var(--dl-fg-3); font-size: 0.72rem;">Date Range:</span>
              <input type="date" id="filter-from-date" value="${this.filters.from_date}" style="background: var(--bg-elevated); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 3px 6px; border-radius: 4px; font-size: 0.72rem; outline: none;" />
              <span style="color: var(--dl-fg-3);">to</span>
              <input type="date" id="filter-to-date" value="${this.filters.to_date}" style="background: var(--bg-elevated); border: 1px solid var(--dl-line); color: var(--dl-fg); padding: 3px 6px; border-radius: 4px; font-size: 0.72rem; outline: none;" />
              <button id="btn-clear-filters" type="button" style="background: transparent; border: 1px solid var(--dl-line); color: var(--dl-fg-3); padding: 3px 8px; border-radius: 4px; font-size: 0.7rem; cursor: pointer;">Clear</button>
            </div>
          </div>

        </div>

        <!-- Detailed Trades Table Container (Capped at 460px with custom scrollbar, fade overlay & footer) -->
        <div class="trades-ledger-outer-wrapper" style="display: flex; flex-direction: column; gap: 6px;">
          <div class="trades-ledger-scroll-wrapper swayam-scroll-thin" style="
            max-height: 460px;
            overflow-y: auto;
            position: relative;
            background: var(--dl-card);
            border: 1px solid var(--dl-line);
            border-radius: var(--radius-card);
          ">
            <div id="journal-trades-table-container"></div>
            <div id="journal-trades-bottom-fade" style="
              position: sticky;
              bottom: 0;
              left: 0;
              right: 0;
              height: 30px;
              background: linear-gradient(to bottom, transparent, var(--dl-card));
              pointer-events: none;
              z-index: 5;
              display: none;
            "></div>
          </div>
          <div id="journal-trades-scroll-footer" style="
            font-size: 0.7rem;
            color: var(--dl-fg-3);
            text-align: right;
            padding-right: 4px;
            display: none;
          "></div>
        </div>

        <!-- Edge Analytics Section -->
        <div style="margin-top: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h2 style="margin: 0; font-size: 1.05rem; font-weight: 700; color: var(--dl-fg); display: flex; align-items: center; gap: 8px;">
              <span>📈</span> Edge Analytics &amp; Lesson Ledger
            </h2>
            <div id="analytics-expectancy-chip" style="font-size: 0.72rem; font-family: var(--font-mono); color: var(--dl-fg-3);">
              Expectancy: ₹0.00 / trade
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 16px;">
            
            <!-- Left 2 Cols: Charts Grid -->
            <div style="display: flex; flex-direction: column; gap: 16px;">
              <div id="analytics-cumulative-curve-container"></div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div id="analytics-pnl-strategy-container"></div>
                <div id="analytics-exit-reason-container"></div>
              </div>
            </div>

            <!-- Right 1 Col: Lessons Ledger & Edge Summary -->
            <div style="display: flex; flex-direction: column; gap: 16px;">
              <div id="analytics-lessons-scroll-container"></div>
              
              <!-- Edge & Discipline Stat Card -->
              <div id="analytics-trend-card" style="background: var(--dl-card); border: 1px solid var(--dl-line); border-radius: var(--radius-card); padding: 14px 16px;">
                <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dl-fg-3); font-weight: 600; margin-bottom: 10px;">
                  🧭 Trend Alignment Edge
                </div>
                <div id="trend-alignment-breakdown" style="display: flex; flex-direction: column; gap: 8px; font-size: 0.76rem;">
                  <div style="color: var(--dl-fg-3);">Calculating edge...</div>
                </div>
              </div>

            </div>

          </div>
        </div>

        <!-- Lesson Editor Modal Container -->
        <div id="journal-lesson-modal-container"></div>

      </div>
    `;
  }

  mountComponents() {
    const kpiContainer = this.container.querySelector('#journal-kpi-strip-container');
    if (kpiContainer) this.kpiStrip = new KPIStripComponent(kpiContainer);

    const tableContainer = this.container.querySelector('#journal-trades-table-container');
    if (tableContainer) {
      this.tradesTable = new TradesTableComponent(tableContainer, {
        onEditLesson: (lesson) => {
          if (this.lessonModal) this.lessonModal.open(lesson);
        },
        onGenerateLesson: async (posId) => {
          try {
            await api.generateLesson(posId);
            await this.loadData();
          } catch (err) {
            console.error('Lesson generation failed:', err);
            alert(`Could not generate lesson: ${err.message}`);
          }
        },
      });
    }

    const cumContainer = this.container.querySelector('#analytics-cumulative-curve-container');
    if (cumContainer) this.cumulativeChart = new AnalyticsCumulativePnlComponent(cumContainer);

    const stratContainer = this.container.querySelector('#analytics-pnl-strategy-container');
    if (stratContainer) this.strategyChart = new AnalyticsPnlByStrategyComponent(stratContainer);

    const exitContainer = this.container.querySelector('#analytics-exit-reason-container');
    if (exitContainer) this.exitReasonChart = new AnalyticsExitReasonComponent(exitContainer);

    const lessonsContainer = this.container.querySelector('#analytics-lessons-scroll-container');
    if (lessonsContainer) {
      this.lessonsScroll = new LessonsScrollComponent(lessonsContainer, {
        onEditLesson: (lesson) => {
          if (this.lessonModal) this.lessonModal.open(lesson);
        },
      });
    }

    const modalContainer = this.container.querySelector('#journal-lesson-modal-container');
    if (modalContainer) {
      this.lessonModal = new LessonEditorModal(modalContainer, {
        onSave: async () => {
          await this.loadData();
        },
      });
    }
  }

  setupEventListeners() {
    // Refresh button
    this.container.querySelector('#btn-refresh-journal')?.addEventListener('click', () => this.loadData());

    // Filter pill buttons
    this.container.querySelectorAll('.filter-pill').forEach((btn) => {
      btn.addEventListener('click', () => {
        const filterType = btn.getAttribute('data-filter');
        const filterVal = btn.getAttribute('data-value');
        if (!filterType || !filterVal) return;

        // Update active class on siblings
        const parent = btn.parentElement;
        parent.querySelectorAll('.filter-pill').forEach(b => {
          b.classList.remove('active');
          b.style.color = 'var(--dl-fg-3)';
          b.style.background = 'transparent';
        });
        btn.classList.add('active');
        btn.style.color = 'var(--dl-fg)';
        btn.style.background = 'rgba(255,255,255,0.08)';

        this.filters[filterType] = filterVal;
        this.loadData();
      });
    });

    // Sort select
    this.container.querySelector('#journal-sort-select')?.addEventListener('change', (e) => {
      this.filters.sort_by = e.target.value;
      this.loadData();
    });

    // Text inputs (debounced or change)
    const debounce = (fn, delay = 300) => {
      let t;
      return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
    };

    const stratInput = this.container.querySelector('#filter-strategy');
    if (stratInput) {
      stratInput.addEventListener('input', debounce((e) => {
        this.filters.strategy = e.target.value.trim();
        this.loadData();
      }));
    }

    const exitInput = this.container.querySelector('#filter-exit-reason');
    if (exitInput) {
      exitInput.addEventListener('input', debounce((e) => {
        this.filters.exit_reason = e.target.value.trim();
        this.loadData();
      }));
    }

    const dirSelect = this.container.querySelector('#filter-directional-view');
    if (dirSelect) {
      dirSelect.addEventListener('change', (e) => {
        this.filters.directional_view = e.target.value;
        this.loadData();
      });
    }

    const fromDate = this.container.querySelector('#filter-from-date');
    if (fromDate) {
      fromDate.addEventListener('change', (e) => {
        this.filters.from_date = e.target.value;
        this.loadData();
      });
    }

    const toDate = this.container.querySelector('#filter-to-date');
    if (toDate) {
      toDate.addEventListener('change', (e) => {
        this.filters.to_date = e.target.value;
        this.loadData();
      });
    }

    // Clear filters
    this.container.querySelector('#btn-clear-filters')?.addEventListener('click', () => {
      this.filters = {
        status: 'all',
        outcome: 'all',
        discipline: 'all',
        strategy: '',
        exit_reason: '',
        directional_view: '',
        from_date: '',
        to_date: '',
        sort_by: 'date_desc',
      };
      this.render();
      this.mountComponents();
      this.setupEventListeners();
      this.loadData();
    });
  }

  async loadData() {
    if (this.isLoading) return;
    this.isLoading = true;

    try {
      // 1. Fetch trades + 7 KPIs
      const tradesData = await api.getJournalTrades(this.filters);
      
      const badge = this.container.querySelector('#journal-trades-badge');
      if (badge) {
        badge.textContent = `${tradesData.total_count} Trades`;
      }

      // Housekeeping banner for pre-launch test trades
      const preLaunchCount = tradesData.pre_launch_test_trades_count || 0;
      const isDismissed = localStorage.getItem('swayam_journal_test_banner_dismissed') === 'true';
      const bannerContainer = this.container.querySelector('#journal-housekeeping-banner-container');
      if (bannerContainer) {
        if (preLaunchCount > 0 && !isDismissed) {
          bannerContainer.innerHTML = `
            <div id="journal-test-trades-banner" style="
              background: rgba(201, 160, 74, 0.12);
              border: 1px solid var(--accent-amber);
              border-radius: var(--radius-card);
              padding: 12px 18px;
              display: flex;
              justify-content: space-between;
              align-items: center;
              flex-wrap: wrap;
              gap: 12px;
            ">
              <div style="display: flex; align-items: center; gap: 10px; font-size: 0.82rem; color: var(--dl-fg);">
                <span style="font-size: 1.1rem;">⚠️</span>
                <span><strong>${preLaunchCount} pre-launch test paper trades detected.</strong> These are Antigravity's automated seed data.</span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <button type="button" id="btn-archive-test-trades" style="
                  background: var(--accent-amber);
                  color: #101116;
                  font-weight: 600;
                  border: none;
                  padding: 6px 14px;
                  border-radius: 6px;
                  font-size: 0.76rem;
                  cursor: pointer;
                ">
                  Archive test data
                </button>
                <button type="button" id="btn-dismiss-test-banner" style="
                  background: transparent;
                  border: 1px solid var(--dl-line);
                  color: var(--dl-fg-2);
                  padding: 6px 12px;
                  border-radius: 6px;
                  font-size: 0.76rem;
                  cursor: pointer;
                ">
                  Dismiss
                </button>
              </div>
            </div>
            <div id="journal-archive-error-msg" style="display: none; color: var(--accent-coral); font-size: 0.76rem; margin-top: 6px; padding: 0 4px;"></div>
          `;

          bannerContainer.querySelector('#btn-dismiss-test-banner')?.addEventListener('click', () => {
            localStorage.setItem('swayam_journal_test_banner_dismissed', 'true');
            bannerContainer.innerHTML = '';
          });

          const btnArchive = bannerContainer.querySelector('#btn-archive-test-trades');
          btnArchive?.addEventListener('click', async () => {
            btnArchive.disabled = true;
            btnArchive.textContent = 'Archiving...';
            const errEl = bannerContainer.querySelector('#journal-archive-error-msg');
            if (errEl) errEl.style.display = 'none';

            try {
              await api.archiveTestTrades();
              bannerContainer.innerHTML = '';
              await this.loadData();
            } catch (err) {
              btnArchive.disabled = false;
              btnArchive.textContent = 'Archive test data';
              if (errEl) {
                errEl.textContent = `Archive failed — ${err.message || 'Unknown error'}`;
                errEl.style.display = 'block';
              }
            }
          });
        } else {
          bannerContainer.innerHTML = '';
        }
      }

      if (this.kpiStrip) {
        this.kpiStrip.update(tradesData.kpis);
      }

      if (this.tradesTable) {
        this.tradesTable.update(tradesData.trades, this.filters.sort_by);
      }

      // Update scroll footer and bottom fade for trades table
      const scrollFooter = this.container.querySelector('#journal-trades-scroll-footer');
      const bottomFade = this.container.querySelector('#journal-trades-bottom-fade');
      const rowCount = tradesData.trades ? tradesData.trades.length : 0;
      if (scrollFooter) {
        if (rowCount > 0) {
          scrollFooter.textContent = `${rowCount} rows shown · scroll for more`;
          scrollFooter.style.display = 'block';
        } else {
          scrollFooter.style.display = 'none';
        }
      }
      if (bottomFade) {
        bottomFade.style.display = rowCount > 6 ? 'block' : 'none';
      }

      // 2. Fetch Analytics
      const analyticsParams = {};
      if (this.filters.from_date) analyticsParams.from_date = this.filters.from_date;
      if (this.filters.to_date) analyticsParams.to_date = this.filters.to_date;

      const analyticsData = await api.getJournalAnalytics(analyticsParams);

      if (this.cumulativeChart) {
        await this.cumulativeChart.update(analyticsData.cumulative_pnl_series);
      }

      if (this.strategyChart) {
        await this.strategyChart.update(analyticsData.pnl_by_strategy);
      }

      if (this.exitReasonChart) {
        await this.exitReasonChart.update(analyticsData.pnl_by_exit_reason);
      }

      if (this.lessonsScroll) {
        this.lessonsScroll.update(analyticsData.recent_lessons);
      }

      // Update expectancy & trend breakdown
      const expChip = this.container.querySelector('#analytics-expectancy-chip');
      if (expChip) {
        const exp = analyticsData.expectancy_per_trade_inr || 0;
        const maxDd = analyticsData.max_drawdown_inr || 0;
        expChip.innerHTML = `Expectancy: <strong style="color: ${exp >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)'};">${exp >= 0 ? '+' : ''}₹${exp.toLocaleString('en-IN')}</strong> / trade · Max DD: <strong style="color: var(--accent-coral);">-₹${Math.abs(maxDd).toLocaleString('en-IN')}</strong>`;
      }

      const trendDiv = this.container.querySelector('#trend-alignment-breakdown');
      if (trendDiv && analyticsData.win_rate_by_trend) {
        const tb = analyticsData.win_rate_by_trend;
        const withTrend = tb['With'] || { trades: 0, win_rate_pct: 0, pnl_inr: 0 };
        const againstTrend = tb['Against'] || { trades: 0, win_rate_pct: 0, pnl_inr: 0 };

        trendDiv.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 4px; background: rgba(255,255,255,0.02); border: 1px solid var(--dl-line);">
            <span>With Trend</span>
            <span style="font-family: var(--font-mono); font-weight: 600; color: ${withTrend.pnl_inr >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)'};">
              ${withTrend.win_rate_pct}% WR (${withTrend.trades}T) · ${withTrend.pnl_inr >= 0 ? '+' : ''}₹${Math.round(withTrend.pnl_inr).toLocaleString('en-IN')}
            </span>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; border-radius: 4px; background: rgba(255,255,255,0.02); border: 1px solid var(--dl-line);">
            <span>Against Trend</span>
            <span style="font-family: var(--font-mono); font-weight: 600; color: ${againstTrend.pnl_inr >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)'};">
              ${againstTrend.win_rate_pct}% WR (${againstTrend.trades}T) · ${againstTrend.pnl_inr >= 0 ? '+' : ''}₹${Math.round(againstTrend.pnl_inr).toLocaleString('en-IN')}
            </span>
          </div>
        `;
      }

    } catch (err) {
      console.error('Failed to load journal data:', err);
    } finally {
      this.isLoading = false;
    }
  }
}