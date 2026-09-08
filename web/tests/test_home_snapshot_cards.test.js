import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { SoFarTodayCardComponent } from '../src/components/so-far-today-card.js';
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

  // The NiftySnapshotCardComponent suite was deleted with the component in round 2.
});
