/**
 * Active Trades component: Renders table of open paper positions.
 */

import { formatINR } from '../utils/format.js';

export function renderActiveTrades(container, positions) {
  if (!positions || positions.length === 0) {
    container.innerHTML = `
      <div class="panel active-trades-container">
        <div class="panel-title">ACTIVE PAPER TRADES</div>
        <p style="color: var(--text-secondary); font-size: 0.85rem; padding: 1rem 0;">
          No active paper trades open. Build and execute a spread above to start paper tracking.
        </p>
      </div>
    `;
    return;
  }

  const rows = positions.map((p, idx) => {
    const openedTime = new Date(p.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const openedDate = new Date(p.opened_at).toLocaleDateString([], { month: '2-digit', day: '2-digit' });
    const pnlClass = p.unrealized_pnl_inr >= 0 ? 'text-green' : 'text-red';
    const journalFilename = p.journal_path ? p.journal_path.split('/').pop() : 'journal.md';
    const obsidianLink = p.journal_path
      ? `obsidian://open?vault=Second%20Brain&file=${encodeURIComponent(p.journal_path)}`
      : '#';

    return `
      <tr>
        <td class="mono">${idx + 1}</td>
        <td><strong>${p.strategy_name}</strong> <span style="font-size: 0.75rem; color: var(--text-secondary);">(${p.underlying})</span></td>
        <td class="mono">${openedDate} ${openedTime}</td>
        <td class="mono text-red">-${formatINR(p.max_loss_inr)}</td>
        <td class="mono ${pnlClass}"><strong>${formatINR(p.unrealized_pnl_inr)}</strong></td>
        <td>
          <a href="${obsidianLink}" style="color: var(--accent); text-decoration: none; font-size: 0.8rem;" title="Open in Obsidian">
            ${journalFilename} ↗
          </a>
        </td>
      </tr>
    `;
  }).join('');

  container.innerHTML = `
    <div class="panel active-trades-container">
      <div class="panel-title">
        <span>ACTIVE PAPER TRADES</span>
        <span style="font-size: 0.8rem; color: var(--text-secondary);">${positions.length} Open</span>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Strategy</th>
              <th>Opened</th>
              <th>Max Loss</th>
              <th>Live P&L</th>
              <th>Journal</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
