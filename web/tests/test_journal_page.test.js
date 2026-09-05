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
        cumulative_pnl_pct_of_margin: 9.04,
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

    it('displays housekeeping banner when pre-launch test trades detected and allows archiving', async () => {
      localStorage.removeItem('swayam_journal_test_banner_dismissed');
      vi.spyOn(api, 'getJournalTrades').mockResolvedValue({
        trades: [],
        total_count: 58,
        pre_launch_test_trades_count: 58,
        kpis: { total_trades: 58 },
      });
      vi.spyOn(api, 'getJournalAnalytics').mockResolvedValue({
        cumulative_pnl_series: [],
        pnl_by_strategy: [],
        pnl_by_exit_reason: [],
        pnl_by_directional_view: [],
        win_rate_by_trend: {},
        recent_lessons: [],
      });
      vi.spyOn(api, 'archiveTestTrades').mockResolvedValue({ archived: 58 });

      const page = new JournalPage(container);
      await page.init();

      const bannerMount = container.querySelector('#journal-housekeeping-banner-container');
      expect(bannerMount).not.toBeNull();
      expect(bannerMount.innerHTML).toContain('58 pre-launch test paper trades detected');

      // Click archive
      const btnArchive = bannerMount.querySelector('#btn-archive-test-trades');
      expect(btnArchive).not.toBeNull();
      btnArchive.click();

      expect(api.archiveTestTrades).toHaveBeenCalled();
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