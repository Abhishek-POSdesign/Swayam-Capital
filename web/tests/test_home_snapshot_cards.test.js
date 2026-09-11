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

      expect(container.textContent).toContain('So far today');
      expect(container.textContent).toContain('Generate');
      expect(container.textContent).toContain('0 of 8 today');
      // THE COST GATE. Nothing on this page may call the model on load.
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
      expect(container.textContent).toContain('1 of 8 today');
      // The stamp says when it was written and that it stays put.
      expect(container.textContent).toContain('it stays until you generate it again');
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
      expect(container.textContent).toContain('Cap reached for today');
      expect(container.textContent).toContain('8 of 8 today');
    });
  });

  // The NiftySnapshotCardComponent suite was deleted with the component in round 2.
});
