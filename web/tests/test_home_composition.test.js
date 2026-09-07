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

  it('OvernightStrip shows an honest not-connected state with no fabricated index levels', () => {
    const strip = new OvernightStripComponent(container);
    strip.render(); // no real feed → must NOT invent numbers

    expect(container.textContent.toLowerCase()).toContain('not connected');
    expect(container.textContent).not.toContain('45,203');
    expect(container.textContent).not.toContain('20,556');
  });

  it('renders the compact VixCardComponent with the real value, regime, and sparkline', () => {
    const vix = new VixCardComponent(container);
    vix.render({ value: 12.85, regime: 'Low Vol Regime', sparkline_20d: [13, 12.8, 12.85] });

    expect(container.textContent).toContain('INDIA VIX');
    expect(container.textContent).toContain('12.85');
    expect(container.textContent).toContain('Low Vol Regime');
    // day change computed from the real series (12.85 vs prior 12.8 → +0.05)
    expect(container.textContent).toContain('+0.05');
    expect(container.querySelector('svg')).not.toBeNull(); // sparkline
  });

  it('renders an honest unavailable state when there is no real VIX value (no fakes)', () => {
    const vix = new VixCardComponent(container);
    vix.render(null);

    expect(container.textContent).toContain('INDIA VIX');
    expect(container.textContent).toContain('—');
    expect(container.textContent.toLowerCase()).toContain('unavailable');
  });

  it('renders MacroEventsCardComponent header with NO fabricated fallback events (real table only)', () => {
    const macro = new MacroEventsCardComponent(container);
    macro.render(); // no events loaded → honest empty; never the old hardcoded fallback

    expect(container.textContent).toContain('MACRO EVENTS');
    // The old hardcoded fallback events must be gone when there is no real data.
    expect(container.textContent).not.toContain('US Fed Interest Rate Decision');
    expect(container.querySelector('.macro-event-row')).toBeNull();
  });

  it('renders real macro events when the real table provides them', () => {
    const macro = new MacroEventsCardComponent(container);
    macro.render({ events: [
      { event_key: 'IN_CPI_2026-09-14', event_name: 'India CPI Inflation (Aug)', event_date: '2026-09-14', country: 'IN', importance: 'high' },
    ] });
    expect(container.textContent).toContain('India CPI Inflation');
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
