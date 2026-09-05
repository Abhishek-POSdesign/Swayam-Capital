import { describe, it, expect, beforeEach } from 'vitest';
import { setupTestDOM } from './setup_test_dom.js';
import { PayoffChartComponent } from '../src/components/payoff-chart.js';

describe('PayoffChartComponent', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  it('renders chart canvas container and risk thresholds legend', async () => {
    const chart = new PayoffChartComponent(container);
    await chart.init();

    expect(container.textContent).toContain('STRATEGY PAYOFF');
    expect(container.textContent).toContain('Expiry');
    expect(container.textContent).toContain('T+0');
    expect(container.querySelector('#payoff-plotly-canvas')).not.toBeNull();
  });

  it('updates data with curve points and spot level', async () => {
    const chart = new PayoffChartComponent(container);
    await chart.init();

    await chart.updateData({
      curveData: {
        points: [
          { spot: 24700, pnl_expiry: -3750, pnl_today: -2200 },
          { spot: 24850, pnl_expiry: 2500, pnl_today: 1800 },
          { spot: 25000, pnl_expiry: 7500, pnl_today: 4500 },
        ],
        breakevens: [24790],
      },
      currentSpot: 24850,
      maxLoss: 3750,
      maxProfit: 7500,
      breakevens: [24790],
      realisticRisk: 3000,
    });

    expect(chart.currentSpot).toBe(24850);
    expect(chart.maxLoss).toBe(3750);
    expect(chart.maxProfit).toBe(7500);
  });

  it('renders time slider, IV slider, and triggers onSliderChange callback', async () => {
    let lastSliderParams = null;
    const chart = new PayoffChartComponent(container, {
      onSliderChange: (params) => {
        lastSliderParams = params;
      },
    });
    await chart.init();

    const timeSlider = container.querySelector('#payoff-time-slider');
    const ivSlider = container.querySelector('#payoff-iv-slider');
    const btnReset = container.querySelector('#btn-reset-payoff-sliders');

    expect(timeSlider).not.toBeNull();
    expect(ivSlider).not.toBeNull();
    expect(btnReset).not.toBeNull();

    // Fire time slider change
    timeSlider.value = '3';
    timeSlider.dispatchEvent(new Event('input'));
    expect(lastSliderParams).not.toBeNull();
    expect(lastSliderParams.targetDays).toBe(3);

    // Fire IV slider change
    ivSlider.value = '15';
    ivSlider.dispatchEvent(new Event('input'));
    expect(lastSliderParams.ivShiftPct).toBe(15);

    // Reset button
    btnReset.click();
    expect(timeSlider.value).toBe('0');
    expect(ivSlider.value).toBe('0');
    expect(lastSliderParams.targetDays).toBe(0);
    expect(lastSliderParams.ivShiftPct).toBe(0);
  });

  it('renders portfolio Greeks strip with values and warning icon when missing', async () => {
    const chart = new PayoffChartComponent(container);
    await chart.init();

    // Partial greeks
    chart.updateData({
      greeks: {
        delta: 0.42,
        theta: -185,
        // gamma missing
        vega: 840,
      },
      pop: 62.5,
    });

    const strip = container.querySelector('#payoff-greeks-strip');
    expect(strip).not.toBeNull();
    expect(strip.textContent).toContain('+0.42');
    expect(strip.textContent).toContain('185');
    expect(strip.textContent).toContain('840');
    expect(strip.textContent).toContain('63%');
    // Gamma should show warning ⚠
    expect(strip.textContent).toContain('⚠');
  });

  it('preserves slider DOM elements and event listeners across updateData calls', async () => {
    let sliderChangeCount = 0;
    const chart = new PayoffChartComponent(container, {
      onSliderChange: () => {
        sliderChangeCount++;
      },
    });
    await chart.init();

    const timeSliderInitial = container.querySelector('#payoff-time-slider');
    const ivSliderInitial = container.querySelector('#payoff-iv-slider');
    expect(timeSliderInitial).not.toBeNull();
    expect(ivSliderInitial).not.toBeNull();

    // Call updateData with new curve and metrics
    await chart.updateData({
      curveData: {
        points: [{ spot: 24850, pnl_expiry: 1000, pnl_today: 500 }],
        breakevens: [24800],
      },
      currentSpot: 24850,
      maxLoss: 5000,
      maxProfit: 10000,
      breakevens: [24800],
      expiryDate: '2026-09-24',
    });

    // Verify DOM identity is preserved (elements were not destroyed or re-rendered)
    const timeSliderAfter = container.querySelector('#payoff-time-slider');
    const ivSliderAfter = container.querySelector('#payoff-iv-slider');
    expect(timeSliderAfter).toBe(timeSliderInitial);
    expect(ivSliderAfter).toBe(ivSliderInitial);

    // Verify event listeners still fire
    timeSliderAfter.value = '4';
    timeSliderAfter.dispatchEvent(new Event('input'));
    expect(sliderChangeCount).toBe(1);

    ivSliderAfter.value = '10';
    ivSliderAfter.dispatchEvent(new Event('input'));
    expect(sliderChangeCount).toBe(2);
  });
});
