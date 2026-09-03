/**
 * TradingView deep-link button generator.
 */

export function renderTvButton(container, symbol = 'NSE:NIFTY50') {
  container.innerHTML = `
    <button id="btn-open-tv" style="width: 100%; margin-top: 0.5rem;" title="Open second-screen chart on TradingView">
      📺 Open in TradingView
    </button>
  `;

  document.getElementById('btn-open-tv').addEventListener('click', () => {
    const tvUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}`;
    window.open(tvUrl, '_blank');
  });
}
