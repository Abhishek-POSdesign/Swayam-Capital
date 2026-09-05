/**
 * Strategy Payoff Chart Component for Swayam Capital (BUILD-10).
 *
 * Plotly-based payoff chart displaying dual curves (Expiry & T+0),
 * current spot marker, breakeven markers, and risk threshold lines (2σ and Blast Radius).
 */

export class PayoffChartComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options; // { onSliderChange }
    this._Plotly = null;
    this.chartData = null;
    this.currentSpot = 24850;
    this.maxLoss = 0;
    this.maxProfit = 0;
    this.breakevens = [];
    this.realisticRisk = 0;
    this.greeks = null;
    this.pop = null;
    this.timeSliderVal = 0;
    this.ivSliderVal = 0;
    this.daysToExpiry = 7;
    this.expiryDate = null;
    this._themeListenerAttached = false;
  }

  _renderGreeksContent() {
    const hasG = this.greeks !== null && this.greeks !== undefined;
    const hasPop = this.pop !== null && this.pop !== undefined;

    const deltaVal = hasG ? (this.greeks.net_delta ?? this.greeks.delta) : undefined;
    const thetaVal = hasG ? (this.greeks.net_theta_per_day ?? this.greeks.theta) : undefined;
    const gammaVal = hasG ? (this.greeks.net_gamma ?? this.greeks.gamma) : undefined;
    const vegaVal = hasG ? (this.greeks.net_vega ?? this.greeks.vega) : undefined;

    const deltaHtml = deltaVal !== undefined
      ? `Net Δ <span style="color: var(--dl-fg);">${(deltaVal > 0 ? '+' : '') + Number(deltaVal).toFixed(2)}</span>`
      : `Net Δ <span title="Greek computation unavailable — see server logs" style="color: var(--accent-amber); cursor: help;">⚠</span>`;

    let thetaHtml;
    if (thetaVal !== undefined) {
      const th = Math.round(thetaVal);
      const thColor = th >= 0 ? 'var(--accent-sage)' : 'var(--accent-coral)';
      const thSign = th >= 0 ? `+₹${th}/day` : `−₹${Math.abs(th)}/day`;
      thetaHtml = `Θ <span style="color: ${thColor}; font-weight: 600;">${thSign}</span>`;
    } else {
      thetaHtml = `Θ <span title="Greek computation unavailable — see server logs" style="color: var(--accent-amber); cursor: help;">⚠</span>`;
    }

    const gammaHtml = gammaVal !== undefined
      ? `Γ <span style="color: var(--dl-fg);">${(gammaVal > 0 ? '+' : '') + Number(gammaVal).toFixed(4)}</span>`
      : `Γ <span title="Greek computation unavailable — see server logs" style="color: var(--accent-amber); cursor: help;">⚠</span>`;

    const vegaHtml = vegaVal !== undefined
      ? `ν <span style="color: var(--dl-fg);">₹${Math.round(vegaVal)}/vol</span>`
      : `ν <span title="Greek computation unavailable — see server logs" style="color: var(--accent-amber); cursor: help;">⚠</span>`;

    const popHtml = hasPop
      ? `POP <span style="color: var(--accent-sage); font-weight: 700;">${Math.round(this.pop)}%</span>`
      : `POP <span title="Greek computation unavailable — see server logs" style="color: var(--accent-amber); cursor: help;">⚠</span>`;

    return `
      <div style="display: flex; align-items: center; gap: 4px;">${deltaHtml}</div>
      <div style="color: var(--dl-line);">·</div>
      <div style="display: flex; align-items: center; gap: 4px;">${thetaHtml}</div>
      <div style="color: var(--dl-line);">·</div>
      <div style="display: flex; align-items: center; gap: 4px;">${gammaHtml}</div>
      <div style="color: var(--dl-line);">·</div>
      <div style="display: flex; align-items: center; gap: 4px;">${vegaHtml}</div>
      <div style="color: var(--dl-line);">·</div>
      <div style="display: flex; align-items: center; gap: 4px;">${popHtml}</div>
    `;
  }

  _computeTargetDateText(days) {
    const today = new Date();
    if (days === 0) {
      const dStr = today.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      return `T+0 (Today, ${dStr})`;
    }
    const target = new Date();
    target.setDate(today.getDate() + days);
    const fromStr = today.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const toStr = target.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return `T+${days} (${fromStr} → ${toStr})`;
  }

  async init() {
    const timeLabelText = this._computeTargetDateText(this.timeSliderVal);

    this.container.innerHTML = `
      <div class="payoff-chart-tile" style="display: flex; flex-direction: column; gap: 8px; background: var(--dl-card); padding: 16px 18px; border-radius: var(--radius-card); border: 1px solid var(--dl-line); height: 100%; min-height: 520px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="eyebrow" style="color: var(--dl-fg-3);">STRATEGY PAYOFF PROFILE</span>
          </div>
          <div style="display: flex; align-items: center; gap: 10px; font-size: 0.72rem;">
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-sage); font-weight: 600;">
              <span style="display: inline-block; width: 14px; height: 3px; background: var(--accent-sage); border-radius: 2px;"></span> At Expiry
            </span>
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-lilac); font-weight: 600;">
              <span style="display: inline-block; width: 14px; height: 2px; border-top: 2px dashed var(--accent-lilac);"></span> Today (T+0)
            </span>
            <span style="display: flex; align-items: center; gap: 4px; color: var(--accent-amber); font-weight: 600;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--accent-amber);"></span> Breakeven
            </span>
          </div>
        </div>

        <!-- Hero Metrics Strip immediately above chart -->
        <div id="payoff-metrics-strip" style="display: flex; gap: 20px; flex-wrap: wrap; align-items: baseline; padding: 4px 0;">
          <div style="display: flex; flex-direction: column;">
            <span style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;">Max Profit</span>
            <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: var(--accent-sage); line-height: 1.2;">
              +₹${Math.round(this.maxProfit).toLocaleString('en-IN')}
            </span>
          </div>
          <div style="display: flex; flex-direction: column;">
            <span style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;">Max Loss</span>
            <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: var(--accent-coral); line-height: 1.2;">
              -₹${Math.round(this.maxLoss).toLocaleString('en-IN')}
            </span>
          </div>
          ${this.breakevens.length > 0 ? `
            <div style="display: flex; flex-direction: column;">
              <span style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;">Breakeven</span>
              <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: var(--accent-amber); line-height: 1.2;">
                ${this.breakevens.map(b => Math.round(b).toLocaleString('en-IN')).join(' | ')}
              </span>
            </div>
          ` : ''}
        </div>

        <!-- Portfolio Greeks Strip (Sensibull pattern) -->
        <div id="payoff-greeks-strip" style="
          display: flex;
          gap: 12px;
          align-items: center;
          flex-wrap: wrap;
          font-family: var(--font-mono);
          font-size: 0.72rem;
          color: var(--text-secondary);
          padding: 6px 12px;
          background: var(--dl-card-2);
          border: 1px solid var(--dl-line);
          border-radius: 6px;
        ">
          ${this._renderGreeksContent()}
        </div>

        <div id="payoff-plotly-canvas" style="width: 100%; flex: 1; min-height: 320px;"></div>

        <!-- Sensibull-style Interactive Time & IV Sliders -->
        <div id="payoff-sliders-section" style="
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
          align-items: start;
          padding: 10px 4px 4px 4px;
          border-top: 1px solid var(--dl-line);
        ">
          <!-- Time Decay Slider Row -->
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.74rem;">
              <span style="font-weight: 600; color: var(--text-primary); font-family: var(--font-mono);">
                <span id="payoff-time-label">${timeLabelText}</span>
              </span>
              <span style="font-size: 0.68rem; color: var(--text-muted);">Time Horizon</span>
            </div>
            <input
              type="range"
              min="0"
              max="${this.daysToExpiry}"
              step="1"
              value="${this.timeSliderVal}"
              id="payoff-time-slider"
              class="swayam-slider-lilac"
              style="width: 100%; cursor: pointer;"
            />
            <div id="payoff-time-ticks" style="display: flex; justify-content: space-between; font-size: 0.65rem; color: var(--text-muted); font-family: var(--font-mono); padding: 0 2px;">
              <span>Today</span>
              <span>Expiry</span>
            </div>
          </div>

          <!-- IV Shift Slider Row -->
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.74rem;">
              <span style="font-weight: 600; color: var(--text-primary); font-family: var(--font-mono);">
                <span id="payoff-iv-label">IV Change: ${this.ivSliderVal > 0 ? '+' : ''}${this.ivSliderVal}%</span>
              </span>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 0.68rem; color: var(--dl-fg-3);">Volatility Stress</span>
                <button
                  type="button"
                  id="btn-reset-payoff-sliders"
                  style="
                    background: transparent;
                    border: 1px solid var(--dl-line);
                    color: var(--dl-fg-2);
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 0.68rem;
                    cursor: pointer;
                    transition: all var(--dur-fast) ease;
                  "
                  onmouseover="this.style.color='var(--dl-fg)'; this.style.borderColor='var(--dl-fg-3)';"
                  onmouseout="this.style.color='var(--dl-fg-2)'; this.style.borderColor='var(--dl-line)';"
                >
                  Reset
                </button>
              </div>
            </div>
            <input
              type="range"
              min="-30"
              max="30"
              step="5"
              value="${this.ivSliderVal}"
              id="payoff-iv-slider"
              class="swayam-slider-amber"
              style="width: 100%; cursor: pointer;"
            />
            <div style="display: flex; justify-content: space-between; font-size: 0.65rem; color: var(--dl-fg-3); font-family: var(--font-mono); padding: 0 2px;">
              <span>−30%</span>
              <span>−15%</span>
              <span>0%</span>
              <span>+15%</span>
              <span>+30%</span>
            </div>
          </div>
        </div>

        <!-- Legend / Risk Key -->
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; padding-top: 6px; border-top: 1px solid var(--dl-line); font-family: var(--font-mono);">
          <span style="color: var(--accent-amber); font-weight: 600;">● Spot: ${this.currentSpot.toFixed(2)}</span>
          <span style="color: var(--dl-fg-3);">Green = Profit Zone · Red = Loss Zone</span>
        </div>
      </div>
    `;

    this._attachSliderEvents();

    if (typeof window !== 'undefined' && !this._themeListenerAttached) {
      window.addEventListener('swayam-theme-change', () => this.retheme());
      this._themeListenerAttached = true;
    }

    // Immediately render initial plot
    await this.renderPlot();
  }

  _attachSliderEvents() {
    const timeSlider = this.container.querySelector('#payoff-time-slider');
    const timeLabel = this.container.querySelector('#payoff-time-label');
    const ivSlider = this.container.querySelector('#payoff-iv-slider');
    const ivLabel = this.container.querySelector('#payoff-iv-label');
    const btnReset = this.container.querySelector('#btn-reset-payoff-sliders');

    if (timeSlider) {
      timeSlider.addEventListener('input', (e) => {
        this.timeSliderVal = parseInt(e.target.value, 10);
        if (timeLabel) timeLabel.textContent = this._computeTargetDateText(this.timeSliderVal);
        this._notifySliderChange();
      });
    }

    if (ivSlider) {
      ivSlider.addEventListener('input', (e) => {
        this.ivSliderVal = parseFloat(e.target.value);
        if (ivLabel) ivLabel.textContent = `IV Change: ${this.ivSliderVal > 0 ? '+' : ''}${this.ivSliderVal}%`;
        this._notifySliderChange();
      });
    }

    if (btnReset) {
      btnReset.addEventListener('click', () => {
        this.timeSliderVal = 0;
        this.ivSliderVal = 0;
        if (timeSlider) timeSlider.value = 0;
        if (ivSlider) ivSlider.value = 0;
        if (timeLabel) timeLabel.textContent = this._computeTargetDateText(0);
        if (ivLabel) ivLabel.textContent = 'IV Change: 0%';
        this._notifySliderChange();
      });
    }
  }

  _notifySliderChange() {
    const today = new Date();
    const target = new Date();
    target.setDate(today.getDate() + this.timeSliderVal);
    const targetDateStr = target.toISOString().slice(0, 10);

    if (this.options.onSliderChange) {
      this.options.onSliderChange({
        targetDays: this.timeSliderVal,
        targetDate: this.timeSliderVal > 0 ? targetDateStr : null,
        ivShiftPct: this.ivSliderVal,
      });
    }
  }

  async updateData({ curveData, curveExpiry, curveTarget, currentSpot, maxLoss, maxProfit, breakevens, realisticRisk, greeks, pop, expiryDate }) {
    this.chartData = curveData || this.chartData;
    this.curveExpiry = curveExpiry || curveData || this.curveExpiry;
    this.curveTarget = curveTarget || curveData || this.curveTarget;
    this.currentSpot = currentSpot || this.currentSpot;
    this.maxLoss = Math.abs(maxLoss || 0);
    this.maxProfit = maxProfit || 0;
    this.breakevens = breakevens || [];
    this.realisticRisk = Math.abs(realisticRisk || 0);
    if (greeks !== undefined) this.greeks = greeks;
    if (pop !== undefined) this.pop = pop;

    if (expiryDate) {
      this.expiryDate = expiryDate;
      const exp = new Date(expiryDate);
      const now = new Date();
      now.setHours(0, 0, 0, 0);
      exp.setHours(0, 0, 0, 0);
      const diff = Math.max(0, Math.round((exp.getTime() - now.getTime()) / (1000 * 3600 * 24)));
      this.daysToExpiry = diff;
      const slider = this.container.querySelector('#payoff-time-slider');
      if (slider) slider.max = String(diff);
      const ticks = this.container.querySelector('#payoff-time-ticks');
      if (ticks) {
        if (diff <= 7) {
          const days = [];
          for (let i = 0; i <= diff; i++) {
            days.push(`<span>${i === 0 ? 'Today' : i === diff ? 'Exp' : '+' + i}</span>`);
          }
          ticks.innerHTML = days.join('');
        } else {
          ticks.innerHTML = `<span>Today</span><span>+${Math.round(diff / 2)}</span><span>Exp (+${diff}d)</span>`;
        }
      }
    }

    // Update metrics strip in DOM
    const strip = this.container.querySelector('#payoff-metrics-strip');
    if (strip) {
      strip.innerHTML = `
        <div style="display: flex; flex-direction: column;">
          <span style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;">Max Profit</span>
          <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: var(--accent-sage); line-height: 1.2;">
            +₹${Math.round(this.maxProfit).toLocaleString('en-IN')}
          </span>
        </div>
        <div style="display: flex; flex-direction: column;">
          <span style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;">Max Loss</span>
          <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: var(--accent-coral); line-height: 1.2;">
            -₹${Math.round(this.maxLoss).toLocaleString('en-IN')}
          </span>
        </div>
        ${this.breakevens.length > 0 ? `
          <div style="display: flex; flex-direction: column;">
            <span style="font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); font-weight: 600;">Breakeven</span>
            <span style="font-family: var(--font-serif); font-size: 1.35rem; font-weight: 700; color: var(--accent-amber); line-height: 1.2;">
              ${this.breakevens.map(b => Math.round(b).toLocaleString('en-IN')).join(' | ')}
            </span>
          </div>
        ` : ''}
      `;
    }

    // Update Greeks strip in DOM
    const greeksStrip = this.container.querySelector('#payoff-greeks-strip');
    if (greeksStrip) {
      greeksStrip.innerHTML = this._renderGreeksContent();
    }

    await this.renderPlot();
  }

  async renderPlot() {
    if (typeof window === 'undefined') return;
    if (typeof process !== 'undefined' && process.env?.VITEST) return;

    try {
      if (!this._Plotly) {
        if (typeof window !== 'undefined' && window.Plotly) {
          this._Plotly = window.Plotly;
        } else {
          const m = await import('plotly.js-dist-min');
          this._Plotly = m.default || m;
        }
      }
      const Plotly = this._Plotly;
      const chartDiv = this.container.querySelector('#payoff-plotly-canvas');
      if (!chartDiv) return;

      const style = typeof window !== 'undefined' && window.getComputedStyle ? window.getComputedStyle(document.documentElement) : null;
      const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
      const bgColor = style?.getPropertyValue('--plotly-bg')?.trim() || (isDark ? '#191b21' : '#f8f6f2');
      const textColor = style?.getPropertyValue('--text-secondary')?.trim() || (isDark ? '#8b8e9b' : '#6b6e7b');
      const gridColor = style?.getPropertyValue('--plotly-grid')?.trim() || (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)');

      let xVals = [];
      let yExpiry = [];
      let yToday = [];

      if (this.curveExpiry && this.curveExpiry.points && this.curveExpiry.points.length > 0) {
        xVals = this.curveExpiry.points.map((p) => p.spot);
        yExpiry = this.curveExpiry.points.map((p) => (p.pnl_expiry !== undefined ? p.pnl_expiry : p.pnl || 0));
      }
      if (this.curveTarget && this.curveTarget.points && this.curveTarget.points.length > 0) {
        if (xVals.length === 0) xVals = this.curveTarget.points.map((p) => p.spot);
        yToday = this.curveTarget.points.map((p) => (p.pnl_today !== undefined ? p.pnl_today : p.pnl || 0));
      } else if (this.chartData && this.chartData.points && this.chartData.points.length > 0) {
        xVals = this.chartData.points.map((p) => p.spot);
        yExpiry = this.chartData.points.map((p) => p.pnl_expiry);
        yToday = this.chartData.points.map((p) => p.pnl_today);
      } else {
        // Fallback default Bear Put curve around current spot
        const s = this.currentSpot || 24850;
        for (let pt = s - 600; pt <= s + 600; pt += 25) {
          xVals.push(pt);
          // Bear put spread (Long 24900 PE @ 116, Short 24700 PE @ 59 -> Net Debit 57 pts = ₹4275)
          const longPut = Math.max(0, 24900 - pt) - 116.62;
          const shortPut = Math.max(0, 24700 - pt) - 59.13;
          const pnlExpiry = (longPut - shortPut) * 75;
          yExpiry.push(Math.round(pnlExpiry));
          // T+0 smooth transition
          const diff = (24850 - pt) / 600;
          yToday.push(Math.round(pnlExpiry * 0.45 + diff * 1500));
        }
      }

      console.log('[PayoffChart.renderPlot]', {
        curve_expiry_0: yExpiry[0],
        curve_target_0: yToday[0],
        targetDays: this.timeSliderVal,
        ivShiftPct: this.ivSliderVal,
      });

      // Shaded green area for positive profit zone
      const profitShadeTrace = {
        x: xVals,
        y: yExpiry.map((y) => (y > 0 ? y : 0)),
        type: 'scatter',
        mode: 'lines',
        line: { width: 0, color: 'transparent' },
        fill: 'tozeroy',
        fillcolor: isDark ? 'rgba(134, 171, 146, 0.16)' : 'rgba(134, 171, 146, 0.22)',
        hoverinfo: 'none',
        showlegend: false,
      };

      // Shaded red area for negative loss zone
      const lossShadeTrace = {
        x: xVals,
        y: yExpiry.map((y) => (y < 0 ? y : 0)),
        type: 'scatter',
        mode: 'lines',
        line: { width: 0, color: 'transparent' },
        fill: 'tozeroy',
        fillcolor: isDark ? 'rgba(221, 129, 112, 0.16)' : 'rgba(221, 129, 112, 0.22)',
        hoverinfo: 'none',
        showlegend: false,
      };

      const expiryTrace = {
        x: xVals,
        y: yExpiry,
        type: 'scatter',
        mode: 'lines',
        name: 'Expiry P&L',
        line: { color: '#86ab92', width: 2.6 },
        hovertemplate: 'Spot: %{x:,.0f}<br>Expiry P&L: ₹%{y:,.0f}<extra></extra>',
      };

      const targetLabel = this.timeSliderVal > 0 ? `Target (T+${this.timeSliderVal})` : 'Today (T+0)';
      const todayTrace = {
        x: xVals,
        y: yToday,
        type: 'scatter',
        mode: 'lines',
        name: targetLabel,
        line: { color: isDark ? '#ac9fd2' : '#7b6ea8', width: 2.5, dash: 'dash' },
        opacity: 1.0,
        hovertemplate: `Spot: %{x:,.0f}<br>${targetLabel} P&L: ₹%{y:,.0f}<extra></extra>`,
      };

      // Breakeven markers
      const bePoints = this.breakevens.map((be) => ({
        x: [be],
        y: [0],
        type: 'scatter',
        mode: 'markers+text',
        name: 'Breakeven',
        text: [`BE ${Math.round(be).toLocaleString('en-IN')}`],
        textposition: 'top center',
        textfont: { size: 9, color: '#c9a04a', family: 'JetBrains Mono, monospace' },
        marker: { color: '#c9a04a', size: 9, symbol: 'diamond' },
        hovertemplate: 'Breakeven: %{x:,.0f}<extra></extra>',
      }));

      // Shapes: Zero baseline + Spot vertical line + 2σ / Max Loss
      const shapes = [
        // Solid Zero line
        {
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: 0, y1: 0,
          line: { color: isDark ? 'rgba(255,255,255,0.28)' : 'rgba(0,0,0,0.28)', width: 1.2 },
        },
        // Spot vertical line
        {
          type: 'line',
          x0: this.currentSpot, x1: this.currentSpot,
          yref: 'paper', y0: 0, y1: 1,
          line: { color: '#c9a04a', width: 1.6, dash: 'dash' },
        },
      ];

      // 2σ Realistic worst-case line
      if (this.realisticRisk > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: -this.realisticRisk, y1: -this.realisticRisk,
          line: { color: '#c9a04a', width: 1.2, dash: 'dot' },
        });
      }

      // Max profit horizontal line
      if (this.maxProfit > 0) {
        shapes.push({
          type: 'line', xref: 'paper', x0: 0, x1: 1,
          y0: this.maxProfit, y1: this.maxProfit,
          line: { color: '#86ab92', width: 1.0, dash: 'dot' },
        });
      }

      const annotations = [
        {
          x: this.currentSpot,
          yref: 'paper',
          y: 0.98,
          text: `● Spot: ${this.currentSpot.toFixed(1)}`,
          showarrow: false,
          font: { color: '#c9a04a', size: 9, family: 'JetBrains Mono, monospace', weight: 700 },
          bgcolor: isDark ? 'rgba(25, 27, 33, 0.92)' : 'rgba(255, 255, 255, 0.92)',
          bordercolor: '#c9a04a',
          borderwidth: 1,
          borderpad: 3,
        },
      ];

      const layout = {
        margin: { l: 55, r: 20, t: 15, b: 30 },
        paper_bgcolor: bgColor,
        plot_bgcolor: bgColor,
        showlegend: false,
        dragmode: false,
        xaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 9, family: 'JetBrains Mono, monospace' },
          tickformat: ',.0f',
        },
        yaxis: {
          showgrid: true,
          gridcolor: gridColor,
          zeroline: false,
          tickfont: { color: textColor, size: 9, family: 'JetBrains Mono, monospace' },
          tickformat: '+,.0f',
        },
        shapes,
        annotations,
      };

      chartDiv.innerHTML = '';
      await Plotly.newPlot(
        chartDiv,
        [profitShadeTrace, lossShadeTrace, expiryTrace, todayTrace, ...bePoints],
        layout,
        {
          responsive: true,
          displayModeBar: false,
        }
      );
    } catch (e) {
      // Quiet fail if Plotly fails to render
    }
  }

  retheme() {
    this.renderPlot();
  }
}
