import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { MacroEventsCardComponent } from '../src/components/macro-events-card.js';
import { api } from '../src/api.js';

describe('BUILD-11.10 MacroEventsCardComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('renders curated macro events with country badges and click-to-expand impact brief', async () => {
    vi.spyOn(api, 'getMacroEvents').mockResolvedValue({
      events: [
        {
          event_key: 'IN_CPI_2026',
          event_name: 'India CPI Inflation (YoY)',
          event_date: '2026-09-10',
          country: 'IN',
          importance: 'high',
          highlighted: true,
          impact_brief: 'Key inflation marker for RBI rate path. Expect ATM straddle IV crush post-announcement.',
        },
        {
          event_key: 'US_FOMC_2026',
          event_name: 'US Fed Interest Rate Decision',
          event_date: '2026-09-13',
          country: 'US',
          importance: 'high',
          highlighted: true,
          impact_brief: 'Global risk sentiment trigger. Watch GIFT Nifty overnight gap potential.',
        },
      ],
      is_stale: false,
    });

    const card = new MacroEventsCardComponent(container);
    await card.init();

    expect(container.textContent).toContain('MACRO EVENTS · NEXT 7 DAYS');
    expect(container.textContent).toContain('India CPI Inflation (YoY)');
    expect(container.textContent).toContain('US Fed Interest Rate Decision');
    expect(container.textContent).toContain('IN');
    expect(container.textContent).toContain('US');

    // Initially collapsed: impact brief is not visible
    expect(container.textContent).not.toContain('Key inflation marker for RBI rate path');

    // Click on the first event row to expand
    card.toggleExpand('IN_CPI_2026');

    // Now expanded: impact brief is visible
    expect(container.textContent).toContain('Key inflation marker for RBI rate path');
    expect(container.textContent).toContain('NIFTY F&O Impact:');

    // Click again to collapse
    card.toggleExpand('IN_CPI_2026');
    expect(container.textContent).not.toContain('Key inflation marker for RBI rate path');
  });

  it('renders coral warning banner if calendar is stale (>8 days)', async () => {
    vi.spyOn(api, 'getMacroEvents').mockResolvedValue({
      events: [
        {
          event_key: 'IN_CPI_OLD',
          event_name: 'India CPI Inflation',
          event_date: '2026-09-02',
          country: 'IN',
          highlighted: true,
          impact_brief: 'Historical inflation print.',
        },
      ],
      is_stale: true,
      stale_warning: 'Calendar may be stale — last refreshed 28 Aug 2026',
    });

    const card = new MacroEventsCardComponent(container);
    await card.init();

    expect(container.textContent).toContain('Calendar may be stale — last refreshed 28 Aug 2026');
    const banner = container.querySelector('.macro-stale-banner');
    expect(banner).not.toBeNull();
  });
});
