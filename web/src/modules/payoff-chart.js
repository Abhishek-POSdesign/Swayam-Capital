/**
 * Plotly.js Payoff Curve Visualizer for Swayam Capital.
 */

import Plotly from 'plotly.js-dist-min';

export function renderPayoffChart(containerId, payoffData, currentSpot) {
  const container = document.getElementById(containerId);
  if (!container || !payoffData || !payoffData.points || payoffData.points.length === 0) {
    return;
  }

  const spots = payoffData.points.map((p) => p.spot);
  const pnlExpiry = payoffData.points.map((p) => p.pnl_expiry);
  const pnlToday = payoffData.points.map((p) => p.pnl_today);

  // Trace 1: At-Expiry P&L curve (Solid line)
  const expiryTrace = {
    x: spots,
    y: pnlExpiry,
    type: 'scatter',
    mode: 'lines',
    name: 'At Expiry',
    line: { color: '#60a5fa', width: 2.5 },
    hovertemplate: 'Spot: ₹%{x:,.0f}<br>Expiry P&L: ₹%{y:,.0f}<extra></extra>',
  };

  // Trace 2: Today (T+0) P&L curve (Dashed line)
  const todayTrace = {
    x: spots,
    y: pnlToday,
    type: 'scatter',
    mode: 'lines',
    name: 'Today (T+0)',
    line: { color: '#fbbf24', width: 2, dash: 'dash' },
    hovertemplate: 'Spot: ₹%{x:,.0f}<br>Today P&L: ₹%{y:,.0f}<extra></extra>',
  };

  // Vertical lines for Breakevens and Current Spot
  const shapes = [
    // Zero P&L horizontal reference line
    {
      type: 'line',
      x0: spots[0],
      x1: spots[spots.length - 1],
      y0: 0,
      y1: 0,
      line: { color: '#4b5563', width: 1.5, dash: 'dot' },
    },
    // Current Spot vertical reference line
    {
      type: 'line',
      x0: currentSpot,
      x1: currentSpot,
      y0: Math.min(...pnlExpiry, ...pnlToday, -1000),
      y1: Math.max(...pnlExpiry, ...pnlToday, 1000),
      line: { color: '#e5e7eb', width: 1.5 },
    },
  ];

  const annotations = [
    {
      x: currentSpot,
      y: 0,
      text: `Spot: ${Math.round(currentSpot).toLocaleString('en-IN')}`,
      showarrow: true,
      arrowhead: 2,
      ax: 0,
      ay: -30,
      font: { color: '#e5e7eb', size: 11 },
      bgcolor: '#1f2937',
      bordercolor: '#4b5563',
    },
  ];

  // Add Breakeven markers
  if (payoffData.breakevens && payoffData.breakevens.length > 0) {
    payoffData.breakevens.forEach((be) => {
      shapes.push({
        type: 'line',
        x0: be,
        x1: be,
        y0: Math.min(...pnlExpiry, -1000),
        y1: Math.max(...pnlExpiry, 1000),
        line: { color: '#a78bfa', width: 1.5, dash: 'dash' },
      });
      annotations.push({
        x: be,
        y: 0,
        text: `BE: ${Math.round(be).toLocaleString('en-IN')}`,
        showarrow: true,
        arrowhead: 1,
        ax: 0,
        ay: 30,
        font: { color: '#c4b5fd', size: 10 },
        bgcolor: '#2e1065',
        bordercolor: '#7c3aed',
      });
    });
  }

  const layout = {
    paper_bgcolor: 'transparent',
    plot_bgcolor: '#1a1f2e',
    margin: { l: 60, r: 30, t: 20, b: 50 },
    xaxis: {
      title: { text: 'NIFTY Spot Price (₹)', font: { color: '#9ca3af', size: 12 } },
      gridcolor: '#2a3040',
      zerolinecolor: '#4b5563',
      tickfont: { color: '#9ca3af', family: 'monospace' },
    },
    yaxis: {
      title: { text: 'Profit / Loss (₹)', font: { color: '#9ca3af', size: 12 } },
      gridcolor: '#2a3040',
      zerolinecolor: '#4b5563',
      tickfont: { color: '#9ca3af', family: 'monospace' },
    },
    shapes: shapes,
    annotations: annotations,
    legend: {
      font: { color: '#e5e7eb' },
      orientation: 'h',
      y: 1.12,
      x: 0.5,
      xanchor: 'center',
    },
    autosize: true,
  };

  const config = {
    responsive: true,
    displayModeBar: false,
  };

  Plotly.react(container, [expiryTrace, todayTrace], layout, config);
}
