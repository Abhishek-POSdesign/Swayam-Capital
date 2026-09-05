import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { HomePage } from '../src/pages/home.js';
import { OvernightStripComponent } from '../src/components/overnight-strip.js';
import { VixCardComponent } from '../src/components/vix-card.js';
import { MacroEventsCardComponent } from '../src/components/macro-events-card.js';
import { ReadingQueueCardComponent } from '../src/components/reading-queue-card.js';
import { KPIHistoryCardComponent } from '../src/components/kpi-history-card.js';

describe('Home Page & Subsystem Composition', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('composes Home page layout with left readiness column and right market prep bento grid', () => {
    const page = new HomePage(container);
    page.render();

    expect(container.querySelector('.home-left-col')).not.toBeNull();
    expect(container.querySelector('.home-right-col')).not.toBeNull();
    expect(container.querySelector('.bento-grid')).not.toBeNull();
    expect(container.textContent).toContain('Market Prep');
  });

  it('renders OvernightStripComponent with 5 global tickers', () => {
    const strip = new OvernightStripComponent(container);
    strip.render();

    expect(container.textContent).toContain('DJI');
    expect(container.textContent).toContain('S&P 500');
    expect(container.textContent).toContain('NASDAQ');
    expect(container.textContent).toContain('USD/INR');
    expect(container.textContent).toContain('BRENT');
  });

  it('renders VixCardComponent with 20-day value and sparkline', () => {
    const vix = new VixCardComponent(container);
    vix.render({ value: 12.85, regime: 'Low Vol Regime', sparkline_20d: [13, 12.8, 12.85] });

    expect(container.textContent).toContain('INDIA VIX · 20-DAY');
    expect(container.textContent).toContain('12.85');
    expect(container.textContent).toContain('Low Vol Regime');
  });

  it('renders MacroEventsCardComponent with upcoming central bank dates', () => {
    const macro = new MacroEventsCardComponent(container);
    macro.render();

    expect(container.textContent).toContain('MACRO EVENTS · NEXT 5 DAYS');
    expect(container.textContent).toContain('RBI Policy Meet');
    expect(container.textContent).toContain('US CPI Print');
    expect(container.textContent).toContain('FOMC Minutes');
  });

  it('renders ReadingQueueCardComponent as honest SOON tile (BUILD-11.6)', () => {
    const queue = new ReadingQueueCardComponent(container);
    queue.render();

    expect(container.textContent).toContain('AI READING QUEUE');
    expect(container.textContent).toContain('SOON');
    expect(container.textContent).toContain('BUILD-13');
    // Confirm fake placeholder articles are gone
    expect(container.textContent).not.toContain('Motilal Oswal');
    expect(container.textContent).not.toContain('Zerodha Varsity');
    expect(container.textContent).not.toContain('Bloomberg');
  });

  it('renders KPIHistoryCardComponent with alcohol streak, 7-day dots, and routine %', () => {
    const kpi = new KPIHistoryCardComponent(container);
    kpi.render({
      alcohol_streak_days: 127,
      ramp_tier_label: 'Ramp tier 4 · 1.0% cap',
      readiness_last_7_days: ['green', 'green', 'green', 'green', 'green', 'green', 'yellow'],
      readiness_ratio_str: '6 / 7',
      morning_routine_pct: 92,
      morning_routine_sparkline: [85, 90, 92],
    });

    expect(container.textContent).toContain('ALCOHOL-FREE STREAK');
    expect(container.textContent).toContain('127');
    expect(container.textContent).toContain('Ramp tier 4 · 1.0% cap');
    expect(container.textContent).toContain('LAST 7 DAYS · READINESS');
    expect(container.textContent).toContain('6');
    expect(container.textContent).toContain('7');
    expect(container.textContent).toContain('MORNING ROUTINE COMPLETION');
    expect(container.textContent).toContain('92%');
  });
});
