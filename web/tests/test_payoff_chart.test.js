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
});
