/**
 * Frontend Unit Tests for Trade Journal, KPIs, and Lesson Ledger (BUILD-11).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { KPIStripComponent } from '../src/components/kpi-strip.js';
import { TradesTableComponent } from '../src/components/trades-table.js';
import { LessonsScrollComponent } from '../src/components/lessons-scroll.js';
import { LessonEditorModal } from '../src/components/lesson-editor.js';
import { JournalPage } from '../src/pages/journal.js';
import { api } from '../src/api.js';

describe('BUILD-11 Trade Journal & Lesson Ledger Components', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    if (global.sessionStorage) global.sessionStorage.clear();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  describe('KPIStripComponent', () => {
    it('renders all 7 KPI cards with proper formatting and badges', () => {
      const kpis = {
        total_trades: 12,
        wins_count: 8,
        losses_count: 3,
        breakeven_count: 1,
        win_rate_pct: 66.7,
        avg_rr_actual: 1.42,
        cumulative_net_pnl_inr: 45200.0,
        cumulative_gross_pnl_inr: 48000.0,
        cumulative_pnl_pct_of_capital: 9.04,
        discipline_rate_pct: 91.7,
        charges_drag_inr: 2800.0,
        charges_drag_pct: 5.8,
        max_profit_trade: { pnl: 14500.0 },
        max_loss_trade: { pnl: -6200.0 },
      };

      const kpiStrip = new KPIStripComponent(container, { kpis });
      kpiStrip.render();

      expect(container.innerHTML).toContain('Total Trades');
      expect(container.innerHTML).toContain('12');
      expect(container.innerHTML).toContain('8W');
      expect(container.innerHTML).toContain('3L');
      expect(container.innerHTML).toContain('Win Rate');
      expect(container.innerHTML).toContain('66.7%');
      expect(container.innerHTML).toContain('Realised R:R');
      expect(container.innerHTML).toContain('1 : 1.42');
      expect(container.innerHTML).toContain('Net P&amp;L');
      expect(container.innerHTML).toContain('₹45,200');
      expect(container.innerHTML).toContain('Discipline Rate');
      expect(container.innerHTML).toContain('91.7%');
      expect(container.innerHTML).toContain('Charges Drag');
      expect(container.innerHTML).toContain('₹2,800');
      expect(container.innerHTML).toContain('Outliers');
      expect(container.innerHTML).toContain('14,500');
    });

    it('renders em-dashes for rate and ratio metrics when total_trades is 0', () => {
      const kpis = {
        total_trades: 0,
        wins_count: 0,
        losses_count: 0,
        breakeven_count: 0,
        // The API returns null rather than 0.0 and 100.0 on an empty book now.
        // The old values are left in the second case below to prove the strip
        // refuses them even if a stale server sends them.
        win_rate_pct: null,
        avg_rr_actual: null,
        cumulative_net_pnl_inr: 0,
        cumulative_gross_pnl_inr: 0,
        discipline_rate_pct: null,
      };

      const kpiStrip = new KPIStripComponent(container, { kpis });
      kpiStrip.render();

      expect(container.innerHTML).toContain('Total Trades');
      expect(container.innerHTML).toContain('Win Rate');
      expect(container.innerHTML).toContain('—');
      expect(container.innerHTML).not.toContain('0.0%');
      expect(container.innerHTML).not.toContain('1 : 0.00');
    });

    it('refuses a 0% win rate and a 100% discipline rate even if the API sends them', () => {
      // The shape the endpoint used to return on an empty book. Both figures
      // render as real results on his screen, and neither was ever measured.
      const kpis = {
        total_trades: 0,
        wins_count: 0,
        losses_count: 0,
        breakeven_count: 0,
        win_rate_pct: 0.0,
        avg_rr_actual: 0.0,
        cumulative_net_pnl_inr: 0,
        cumulative_gross_pnl_inr: 0,
        discipline_rate_pct: 100.0,
        charges_drag_pct: 0.0,
      };

      const kpiStrip = new KPIStripComponent(container, { kpis });
      kpiStrip.render();

      expect(container.innerHTML).not.toContain('0.0%');
      expect(container.innerHTML).not.toContain('100.0%');
      expect(container.innerHTML).toContain('—');
    });
  });

  describe('TradesTableComponent', () => {
    const mockTrades = [
      {
        position_id: 'pos-101',
        opened_at: '2026-09-02T10:30:00Z',
        closed_at: '2026-09-02T13:45:00Z',
        strategy_name: 'Bear Put Spread',
        setup_technical: 'Head & Shoulders',
        setup_location: 'Prior Day Low',
        directional_view: 'Bearish',
        time_in_trade_str: '3h 15m',
        points_in_trade: -65.0,
        charges_inr: 160.0,
        net_pnl_inr: 6800.0,
        gross_pnl_inr: 6960.0,
        rr_actual: 1.85,
        rr_planned: 2.0,
        rules_followed: true,
        rules_broken_reason: null,
        status: 'closed',
        lesson_id: 'les-101',
        lesson_text: 'Bear Put Spread captured target profit after breakdown.',
        lesson_source: 'ai_generated',
      },
      {
        position_id: 'pos-102',
        opened_at: '2026-09-03T11:00:00Z',
        closed_at: '2026-09-03T14:30:00Z',
        strategy_name: 'Bull Call Spread',
        setup_technical: 'Breakout',
        setup_location: 'VWAP',
        directional_view: 'Bullish',
        time_in_trade_str: '3h 30m',
        points_in_trade: -40.0,
        charges_inr: 160.0,
        net_pnl_inr: -3500.0,
        gross_pnl_inr: -3340.0,
        rr_actual: -1.0,
        rr_planned: 1.5,
        rules_followed: false,
        rules_broken_reason: 'Widened stop loss past planned limit',
        status: 'closed',
        lesson_id: 'les-102',
        lesson_text: 'Bull Call Spread failed discipline check; stop loss was widened.',
        lesson_source: 'user_edited',
      }
    ];

    it('renders trade rows with correct discipline indicators', () => {
      const table = new TradesTableComponent(container, { trades: mockTrades });
      table.render();

      expect(container.innerHTML).toContain('Bear Put Spread');
      expect(container.innerHTML).toContain('Bull Call Spread');
      expect(container.innerHTML).toContain('+₹6,800');
      expect(container.innerHTML).toContain('-₹3,500');
      expect(container.innerHTML).toContain('✓'); // followed
      expect(container.innerHTML).toContain('✗'); // broken
    });

    it('expands row details on click and renders lesson card', () => {
      const table = new TradesTableComponent(container, { trades: mockTrades });
      table.render();

      // Click to expand first trade
      table.toggleExpand('pos-101');

      expect(container.innerHTML).toContain('Trade Context &amp; Rationale');
      expect(container.innerHTML).toContain('Method &amp; Discipline Audit');
      expect(container.innerHTML).toContain('Lesson Ledger');
      expect(container.innerHTML).toContain('Bear Put Spread captured target profit after breakdown.');
      expect(container.innerHTML).toContain('Refine Lesson');
    });

    it('shows what a trade cost leg by leg, and never invents a split', () => {
      const trade = {
        position_id: 'pos-cost',
        opened_at: '2026-09-08T10:15:00Z',
        strategy_name: 'Bear Put Spread',
        legs_summary: 'BUY 24850 PE / SELL 24100 PE (1 lot)',
        gross_pnl_inr: 7500,
        charges_inr: 150.3,
        net_pnl_inr: 7349.7,
        rules_followed: true,
        cost_legs: [
          { direction: 'buy', strike: 24850, option_type: 'PE', gross_pnl_inr: 5250, charges_inr: 92.73, net_pnl_inr: 5157.27 },
          { direction: 'sell', strike: 24100, option_type: 'PE', gross_pnl_inr: 2250, charges_inr: 57.57, net_pnl_inr: 2192.43 },
        ],
      };

      const table = new TradesTableComponent(container, { trades: [trade] });
      table.expandedTradeId = 'pos-cost';
      table.render();

      const html = container.innerHTML;
      expect(html).toContain('What it cost, leg by leg');
      expect(html).toContain('BUY 24850 PE');
      expect(html).toContain('SELL 24100 PE');
      // The two legs cost different amounts, which is the whole point.
      expect(html).toContain('92.73');
      expect(html).toContain('57.57');
      expect(html).toContain('150.30');
    });

    it('renders no cost card at all for a trade with no per-leg breakdown', () => {
      const trade = {
        position_id: 'pos-old',
        opened_at: '2026-09-01T10:15:00Z',
        strategy_name: 'Iron Condor',
        net_pnl_inr: 1000,
        cost_legs: [],
      };

      const table = new TradesTableComponent(container, { trades: [trade] });
      table.expandedTradeId = 'pos-old';
      table.render();

      expect(container.innerHTML).not.toContain('What it cost, leg by leg');
    });

    it('does not put words in his mouth about a setup he never described', () => {
      const trade = {
        position_id: 'pos-blank',
        opened_at: '2026-09-08T10:15:00Z',
        strategy_name: 'Iron Condor',
        net_pnl_inr: 500,
        cost_legs: [],
      };

      const table = new TradesTableComponent(container, { trades: [trade] });
      table.expandedTradeId = 'pos-blank';
      table.render();

      const html = container.innerHTML;
      for (const invented of [
        'Standard breakout',
        'Key support/resistance level',
        'Standard option spread',
        'With Trend',
        'Manual / Target',
        '100% Rules Followed',
      ]) {
        expect(html).not.toContain(invented);
      }
      expect(html).toContain('Not recorded');
    });
  });

  describe('LessonsScrollComponent', () => {
    it('renders scrollable lesson feed with outcome tags', () => {
      const lessons = [
        {
          id: 'les-01',
          trade_closed_at: '2026-09-02T13:45:00Z',
          strategy_name: 'Iron Condor',
          outcome: 'WIN',
          lesson_text: 'Iron Condor captured premium decay within range.',
          lesson_source: 'ai_generated',
        }
      ];

      const scroll = new LessonsScrollComponent(container, { lessons });
      scroll.render();

      expect(container.innerHTML).toContain('Recent Lesson Ledger');
      expect(container.innerHTML).toContain('WIN');
      expect(container.innerHTML).toContain('Iron Condor');
      expect(container.innerHTML).toContain('Iron Condor captured premium decay within range.');
    });
  });

  describe('LessonEditorModal', () => {
    it('opens with current text and triggers save on click', async () => {
      const onSaveMock = vi.fn();
      const modal = new LessonEditorModal(container, { onSave: onSaveMock });

      modal.open({
        id: 'les-test-1',
        lesson_text: 'Initial lesson text.',
      });

      expect(container.innerHTML).toContain('Refine Lesson Takeaway');
      const textarea = container.querySelector('#lesson-textarea');
      expect(textarea.value).toBe('Initial lesson text.');

      // Mock api.updateLesson
      vi.spyOn(api, 'updateLesson').mockResolvedValue({
        id: 'les-test-1',
        lesson_text: 'Updated refined text.',
      });

      textarea.value = 'Updated refined text.';
      await modal.handleSave();

      expect(api.updateLesson).toHaveBeenCalledWith('les-test-1', 'Updated refined text.');
      expect(onSaveMock).toHaveBeenCalled();
    });
  });

  describe('JournalPage orchestration', () => {
    it('mounts subcomponents and filter pills', async () => {
      vi.spyOn(api, 'getJournalTrades').mockResolvedValue({
        trades: [],
        total_count: 0,
        kpis: { total_trades: 0 },
      });
      vi.spyOn(api, 'getJournalAnalytics').mockResolvedValue({
        cumulative_pnl_series: [],
        pnl_by_strategy: [],
        pnl_by_exit_reason: [],
        pnl_by_directional_view: [],
        win_rate_by_trend: {},
        recent_lessons: [],
      });

      const page = new JournalPage(container);
      await page.init();

      expect(container.innerHTML).toContain('Trade Journal &amp; Performance Ledger');
      expect(container.innerHTML).toContain('All Status');
      expect(container.innerHTML).toContain('All Outcome');
      expect(container.innerHTML).toContain('All Rules');
      expect(container.innerHTML).toContain('Edge Analytics');
      expect(api.getJournalTrades).toHaveBeenCalled();
      expect(api.getJournalAnalytics).toHaveBeenCalled();
    });

    it('writes nothing to his database when the page is opened', async () => {
      // Opening the Trade Journal used to fire POST /api/journal/archive-test-trades
      // at his live record on the first load of each browser session, with
      // nothing clicked. Reading a record must never write to it.
      expect(api.archiveTestTrades).toBeUndefined();

      vi.spyOn(api, 'getJournalTrades').mockResolvedValue({
        trades: [],
        total_count: 0,
        excluded_test_rows: 0,
        unpriced_closed_trades: 0,
        capital_base_inr: 971002.38,
        capital_base_source: 'FYERS funds() id 1 Total Balance',
        kpis: { total_trades: 0 },
      });
      vi.spyOn(api, 'getJournalAnalytics').mockResolvedValue({
        cumulative_pnl_series: [],
        pnl_by_strategy: [],
        pnl_by_exit_reason: [],
        pnl_by_directional_view: [],
        win_rate_by_trend: {},
        recent_lessons: [],
      });

      const page = new JournalPage(container);
      await page.init();

      // Nothing excluded and capital readable, so the note stays silent.
      const bannerMount = container.querySelector('#journal-housekeeping-banner-container');
      expect(bannerMount.innerHTML).toBe('');
    });

    it('says on screen which rows it left out of his record, and why', async () => {
      vi.spyOn(api, 'getJournalTrades').mockResolvedValue({
        trades: [],
        total_count: 0,
        excluded_test_rows: 81,
        unpriced_closed_trades: 2,
        capital_base_inr: null,
        capital_base_source: 'live capital unavailable: FYERS token rejected',
        kpis: { total_trades: 0 },
      });
      vi.spyOn(api, 'getJournalAnalytics').mockResolvedValue({
        cumulative_pnl_series: [],
        pnl_by_strategy: [],
        pnl_by_exit_reason: [],
        pnl_by_directional_view: [],
        win_rate_by_trend: {},
        recent_lessons: [],
      });

      const page = new JournalPage(container);
      await page.init();

      const banner = container.querySelector('#journal-housekeeping-banner-container');
      expect(banner.innerHTML).toContain('81 rows excluded as build tests');
      expect(banner.innerHTML).toContain('2 closed trades could not be valued');
      expect(banner.innerHTML).toContain('not counted as zero');
      expect(banner.innerHTML).toContain('FYERS token rejected');
    });

    it('renders trades table inside 460px max-height container with swayam-scroll-thin', async () => {
      vi.spyOn(api, 'getJournalTrades').mockResolvedValue({
        trades: [
          { position_id: 'p1', opened_at: '2026-09-02T10:00:00Z', strategy_name: 'Iron Condor', status: 'closed' }
        ],
        total_count: 1,
        pre_launch_test_trades_count: 0,
        kpis: { total_trades: 1 },
      });
      vi.spyOn(api, 'getJournalAnalytics').mockResolvedValue({
        cumulative_pnl_series: [],
        pnl_by_strategy: [],
        pnl_by_exit_reason: [],
        pnl_by_directional_view: [],
        win_rate_by_trend: {},
        recent_lessons: [],
      });

      const page = new JournalPage(container);
      await page.init();

      expect(container.innerHTML).toContain('trades-ledger-scroll-wrapper');
      expect(container.innerHTML).toContain('swayam-scroll-thin');
      expect(container.innerHTML).toContain('max-height: 460px');

      const footer = container.querySelector('#journal-trades-scroll-footer');
      expect(footer).not.toBeNull();
      expect(footer.textContent).toContain('1 rows shown · scroll for more');
    });
  });
});