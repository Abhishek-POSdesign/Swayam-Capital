import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { SoFarTodayCardComponent } from '../src/components/so-far-today-card.js';
import { NiftySnapshotCardComponent } from '../src/components/nifty-snapshot-card.js';
import { api } from '../src/api.js';

describe('BUILD-11.9 Home Snapshot Components', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  describe('SoFarTodayCardComponent', () => {
    it('renders empty state initially without auto-firing generation', async () => {
      vi.spyOn(api, 'getSoFarToday').mockResolvedValue({
        has_data: false,
        call_count_today: 0,
        daily_cap: 8,
        cap_reached: false,
      });
      const genSpy = vi.spyOn(api, 'generateSoFarToday');

      const card = new SoFarTodayCardComponent(container);
      await card.init();

      expect(container.textContent).toContain('SO FAR TODAY');
      expect(container.textContent).toContain('Generate Summary');
      expect(container.textContent).toContain('Calls today: 0/8');
      expect(genSpy).not.toHaveBeenCalled();
    });

    it('generates summary on button click and renders text with sources and age chip', async () => {
      vi.spyOn(api, 'getSoFarToday').mockResolvedValue({ has_data: false });
      vi.spyOn(api, 'generateSoFarToday').mockResolvedValue({
        has_data: true,
        text: 'NIFTY tested 24,900 resistance. Setup: 24,900 double-rejection is prime for Bear Put Spread.',
        sources: [{ title: 'Moneycontrol Live', url: 'https://moneycontrol.com' }],
        generated_at: new Date().toISOString(),
        age_minutes: 0,
        call_count_today: 1,
        daily_cap: 8,
        cap_reached: false,
      });

      const card = new SoFarTodayCardComponent(container);
      await card.init();

      const btn = container.querySelector('#btn-generate-so-far');
      expect(btn).not.toBeNull();
      await card.generate(false);

      expect(container.textContent).toContain('24,900 resistance');
      expect(container.textContent).toContain('Bear Put Spread');
      expect(container.textContent).toContain('Moneycontrol Live');
      expect(container.textContent).toContain('Calls today: 1/8');
      expect(container.textContent).toContain('Generated Just now');
    });

    it('disables button when daily cap of 8 calls is reached', async () => {
      vi.spyOn(api, 'getSoFarToday').mockResolvedValue({
        has_data: false,
        call_count_today: 8,
        daily_cap: 8,
        cap_reached: true,
      });

      const card = new SoFarTodayCardComponent(container);
      await card.init();

      expect(container.innerHTML).toContain('disabled');
      expect(container.textContent).toContain('Daily cap reached');
      expect(container.textContent).toContain('Calls today: 8/8');
    });
  });

  describe('NiftySnapshotCardComponent', () => {
    it('renders both Cash and F&O panes with all four freshness states', () => {
      const card = new NiftySnapshotCardComponent(container);
      card.data = {
        cash_pane: {
          spot: 24864.20,
          day_change_pct: 0.09,
          week_change_pct: 0.85,
          month_change_pct: 2.10,
          spot_freshness: 'LIVE',
          range_20d: { low: 24200, high: 25100 },
          range_50d: { low: 23800, high: 25300 },
          spot_position_pct_20d: 65,
          dma_20: 24700,
          distance_20_dma_atr: 0.42,
          atr_20: 185.50,
          realized_vol_20: 11.8,
          sentiment: 'Bullish',
          advances: 32,
          declines: 18,
          breadth_freshness: 'LIVE',
          sector_rotation: [
            { name: 'BANK', change_pct: 0.45 },
            { name: 'IT', change_pct: -0.32 },
          ],
          sector_freshness: 'LIVE',
        },
        fno_pane: {
          weekly_expiry: '2026-09-08',
          weekly_dte: { formatted: '2 calendar days · 2 trading sessions' },
          monthly_expiry: '2026-09-29',
          monthly_dte: { formatted: '23 calendar days · 17 trading sessions' },
          expiry_freshness: 'CALCULATED',
          weekly_pcr: 1.05,
          monthly_pcr: 1.15,
          pcr_freshness: 'CALCULATED',
          max_pain: 24850,
          max_pain_freshness: 'CALCULATED',
          max_call_oi_strike: 25000,
          max_put_oi_strike: 24500,
          walls_freshness: 'CALCULATED',
          india_vix: 13.10,
          india_vix_change_pct: 1.95,
          vix_freshness: 'LIVE',
          institutional: {
            fii_cash_net_cr: -485.50,
            fii_cash_freshness: 'PREVIOUS SESSION',
            fii_fno_net_contracts: '+14,230',
            fii_fno_detail: '58% Long',
            dii_cash_net_cr: 1240.20,
            dii_cash_freshness: 'PREVIOUS SESSION',
            dii_fno_net_contracts: '-8,150',
            dii_fno_detail: '44% Long',
          },
          is_rollover_window: true,
          rollover_pct: 68.5,
          rollover_freshness: 'PREVIOUS SESSION',
        },
      };

      card.render();

      // Check Cash Pane contents
      expect(container.textContent).toContain('CASH MARKET');
      expect(container.textContent).toContain('24,864.20');
      expect(container.textContent).toContain('+0.09%');
      expect(container.textContent).toContain('+0.42 ATR');
      expect(container.textContent).toContain('Bullish');
      expect(container.textContent).toContain('BANK');
      expect(container.textContent).toContain('+0.5%');

      // Check F&O Pane contents
      expect(container.textContent).toContain('F&O DERIVATIVES');
      expect(container.textContent).toContain('2026-09-08');
      expect(container.textContent).toContain('2 calendar days · 2 trading sessions');
      expect(container.textContent).toContain('2026-09-29');
      expect(container.textContent).toContain('W: 1.05');
      expect(container.textContent).toContain('M: 1.15');
      expect(container.textContent).toContain('Pain: 24,850');
      expect(container.textContent).toContain('25000');
      expect(container.textContent).toContain('24500');
      expect(container.textContent).toContain('13.1');

      // Check STRICT SEPARATION of FII cash vs F&O
      expect(container.textContent).toContain('FII CASH (₹ Cr)');
      expect(container.textContent).toContain('-485.5 cr');
      expect(container.textContent).toContain('FII F&O (Contracts)');
      expect(container.textContent).toContain('+14,230');

      // Check STRICT SEPARATION of DII cash vs F&O
      expect(container.textContent).toContain('DII CASH (₹ Cr)');
      expect(container.textContent).toContain('+1,240.2 cr');
      expect(container.textContent).toContain('DII F&O (Contracts)');
      expect(container.textContent).toContain('-8,150');

      // Check Rollover window
      expect(container.textContent).toContain('Monthly Expiry Rollover Window Active');
      expect(container.textContent).toContain('68.5%');

      // Check Freshness Badges
      expect(container.textContent).toContain('LIVE');
      expect(container.textContent).toContain('CALCULATED');
      expect(container.textContent).toContain('PREVIOUS SESSION');

      // Test STALE badge during active refresh
      card.isRefreshing = true;
      expect(card.getBadgeHtml('LIVE')).toContain('STALE');
    });
  });
});
