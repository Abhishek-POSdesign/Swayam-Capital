/**
 * Main application orchestrator for Swayam Capital web dashboard.
 */

import { api } from './api.js';
import { renderActiveTrades } from './components/active-trades.js';
import { initHeader, updateHeaderSpot } from './components/header.js';
import { renderRulePanel } from './components/rule-panel.js';
import { StrategyBuilder } from './components/strategy-builder.js';
import { SpotWebSocketClient } from './modules/ws-client.js';

class SwayamApp {
  constructor() {
    this.rules = null;
    this.activePositions = [];
    this.builder = null;
    this.wsClient = null;
  }

  async init() {
    console.log('Initializing Swayam Capital dashboard...');

    // 1. Initialize Header
    const headerContainer = document.getElementById('header-container');
    initHeader(headerContainer, () => this.handleReloadRules());

    // 2. Fetch Initial Rules & Margin Base
    await this.loadRules();

    // 3. Initialize Strategy Builder
    const builderContainer = document.getElementById('builder-container');
    this.builder = new StrategyBuilder(builderContainer, {
      onTradeExecuted: () => this.loadPositions(),
    });
    if (this.rules) {
      this.builder.setMarginBase(this.rules.margin_base_inr);
    }
    await this.builder.init();

    // 4. Initialize Active Trades Panel
    await this.loadPositions();

    // 5. Connect WebSocket for Spot ticks
    this.wsClient = new SpotWebSocketClient((spot) => {
      updateHeaderSpot(spot);
      if (this.builder) this.builder.setSpot(spot);
    });
    this.wsClient.connect();

    // 6. Polling fallback for NIFTY spot if WebSocket inactive
    this.pollSpot();

    // 7. Wire Modal Action Listeners
    this.setupModal();
  }

  async loadRules(forceReload = false) {
    try {
      this.rules = await api.getRules(forceReload);
      const ruleContainer = document.getElementById('rule-panel-container');
      if (ruleContainer) renderRulePanel(ruleContainer, this.rules);
      if (this.builder && this.rules.margin_base_inr) {
        this.builder.setMarginBase(this.rules.margin_base_inr);
      }
    } catch (err) {
      console.error('Failed to load rules:', err);
    }
  }

  async handleReloadRules() {
    await this.loadRules(true);
    if (this.builder) {
      await this.builder.recomputeAndValidate();
    }
    if (this.builder) {
      this.builder.showToast('Method Rules reloaded directly from Obsidian vault.');
    }
  }

  async loadPositions() {
    try {
      this.activePositions = await api.getPositions('open');
      const container = document.getElementById('active-trades-container');
      if (container) renderActiveTrades(container, this.activePositions);
    } catch (err) {
      console.error('Failed to load positions:', err);
    }
  }

  async pollSpot() {
    try {
      const res = await api.getNiftySpot();
      if (res && res.spot) {
        updateHeaderSpot(res.spot);
        if (this.builder) this.builder.setSpot(res.spot);
      }
    } catch (e) {
      // Offline / market closed
      updateHeaderSpot(24867.5);
    }
    // Poll every 10s
    setTimeout(() => this.pollSpot(), 10000);
  }

  setupModal() {
    const modal = document.getElementById('confirmation-modal');
    const btnCancel = document.getElementById('modal-btn-cancel');
    const btnConfirm = document.getElementById('modal-btn-confirm');

    if (btnCancel) {
      btnCancel.addEventListener('click', () => {
        if (modal) modal.style.display = 'none';
      });
    }

    if (btnConfirm) {
      btnConfirm.addEventListener('click', async () => {
        btnConfirm.disabled = true;
        btnConfirm.textContent = 'Executing...';
        try {
          if (this.builder) await this.builder.executePaperTrade();
        } finally {
          btnConfirm.disabled = false;
          btnConfirm.textContent = 'Confirm & Execute';
        }
      });
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const app = new SwayamApp();
  app.init();
});
