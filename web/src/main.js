/**
 * Main application orchestrator for Swayam Capital (BUILD-9).
 * Multi-page architecture: Home (Readiness + Market Prep) & Strategy Builder.
 */

import { api } from './api.js';
import { ActiveTradesComponent } from './components/active-trades.js';
import { AIChatPanel } from './components/ai-chat.js';
import { AIFloatingLauncher } from './components/ai-launcher.js';
import { initHeader, updateHeaderSpot } from './components/header.js';
import { renderRulePanel } from './components/rule-panel.js';
import { StrategyBuilder } from './components/strategy-builder.js';
import { SpotWebSocketClient } from './modules/ws-client.js';
import { HomePage } from './pages/home.js';
import { AISettingsDrawer } from './components/ai-settings-drawer.js';

class SwayamApp {
  constructor() {
    this.rules = null;
    this.activePositions = [];
    this.builder = null;
    this.wsClient = null;
    this.homePage = null;
    this.aiChat = null;
    this.aiLauncher = null;
    this.settingsDrawer = null;
    this.activeTradesComponent = null;
    this.currentPage = 'home';
    this.isAIDrawerOpen = false;
  }

  async init() {
    console.log('Initializing Swayam Capital trading platform (BUILD-9)...');

    // 1. Initialize Navigation Header
    const headerContainer = document.getElementById('header-container');
    if (headerContainer) {
      initHeader(headerContainer, {
        activePage: this.currentPage,
        onNavigate: (page) => this.navigateTo(page),
        onReloadRules: () => this.handleReloadRules(),
      });
    }

    // 1b. Initialize AI Voice & Memory Settings Drawer
    const settingsContainer = document.getElementById('ai-settings-drawer-container');
    if (settingsContainer) {
      this.settingsDrawer = new AISettingsDrawer(settingsContainer);
      this.settingsDrawer.init();
    }

    // 2. Initialize Home Page (Default landing view)
    const homeViewContainer = document.getElementById('home-view');
    if (homeViewContainer) {
      this.homePage = new HomePage(homeViewContainer, {
        onOpenAIDrawer: () => this.openAIDrawer(),
        onOpenSettings: () => {
          if (this.settingsDrawer) {
            const sid = this.homePage?.aiBriefComponent?.sessionId;
            this.settingsDrawer.open(sid);
          }
        },
        onNavigateStrategy: () => {
          this.navigateTo('strategy');
        },
      });
      await this.homePage.init();
    }

    // 3. Initialize Strategy Builder View
    await this.initStrategyView();

    // 4. Connect WebSocket for live NIFTY Spot ticks
    this.wsClient = new SpotWebSocketClient((spot) => {
      updateHeaderSpot(spot);
      if (this.builder) this.builder.setSpot(spot);
    });
    this.wsClient.connect();
    this.pollSpot();

    // 5. Initialize AI Trading Partner Drawer & Persistent Launcher Orb
    await this.initAIDrawer();
  }

  async initStrategyView() {
    await this.loadRules();

    const builderContainer = document.getElementById('builder-container');
    if (builderContainer) {
      this.builder = new StrategyBuilder(builderContainer, {
        onTradeExecuted: () => this.loadPositions(),
      });
      if (this.rules) {
        this.builder.setMarginBase(this.rules.margin_base_inr);
      }
      await this.builder.init();
    }

    const activeContainer = document.getElementById('active-trades-container');
    if (activeContainer) {
      this.activeTradesComponent = new ActiveTradesComponent(activeContainer, {
        onTradeClosed: () => {
          if (this.builder) this.builder.recomputeAndValidate();
        },
      });
      await this.activeTradesComponent.init();
    }

    this.setupModal();
  }

  async initAIDrawer() {
    const aiContainer = document.getElementById('ai-sidebar-container');
    if (aiContainer) {
      this.aiChat = new AIChatPanel(aiContainer);
      await this.aiChat.init();

      // Add a close drawer button in the header of the drawer if not present
      const drawerHeader = aiContainer.querySelector('.ai-panel__header');
      if (drawerHeader && !aiContainer.querySelector('#btn-close-ai-drawer')) {
        const btnClose = document.createElement('button');
        btnClose.id = 'btn-close-ai-drawer';
        btnClose.innerHTML = '✕';
        btnClose.style.cssText = 'background: transparent; border: none; color: var(--dl-fg-2); font-size: 1rem; cursor: pointer; padding: 4px 8px;';
        btnClose.addEventListener('click', () => this.closeAIDrawer());
        drawerHeader.appendChild(btnClose);
      }
    }

    this.aiLauncher = new AIFloatingLauncher({
      onToggle: () => this.toggleAIDrawer(),
    });
    this.aiLauncher.init();
  }

  openAIDrawer() {
    const drawer = document.getElementById('ai-sidebar-container');
    if (drawer) {
      drawer.style.right = '0px';
      try { document.body.classList.add('ai-panel-open'); } catch (_) {}
      this.isAIDrawerOpen = true;
    }
  }

  closeAIDrawer() {
    const drawer = document.getElementById('ai-sidebar-container');
    if (drawer) {
      drawer.style.right = '-420px';
      try { document.body.classList.remove('ai-panel-open'); } catch (_) {}
      this.isAIDrawerOpen = false;
    }
  }

  toggleAIDrawer() {
    if (this.isAIDrawerOpen) {
      this.closeAIDrawer();
    } else {
      this.openAIDrawer();
    }
  }

  navigateTo(page) {
    this.currentPage = page;
    const homeView = document.getElementById('home-view');
    const strategyView = document.getElementById('strategy-view');

    if (page === 'home') {
      if (homeView) homeView.style.display = 'block';
      if (strategyView) strategyView.style.display = 'none';
    } else if (page === 'strategy') {
      if (homeView) homeView.style.display = 'none';
      if (strategyView) strategyView.style.display = 'block';
      if (this.builder) {
        this.builder.recomputeAndValidate();
      }
    }
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
  }

  async loadPositions() {
    if (this.activeTradesComponent) {
      await this.activeTradesComponent.refresh();
    }
  }

  setupModal() {
    const modal = document.getElementById('confirmation-modal');
    const cancelBtn = document.getElementById('modal-btn-cancel');
    const confirmBtn = document.getElementById('modal-btn-confirm');

    if (cancelBtn) {
      cancelBtn.onclick = () => {
        modal.classList.remove('active');
      };
    }

    if (confirmBtn) {
      confirmBtn.onclick = async () => {
        modal.classList.remove('active');
        if (this.builder) {
          await this.builder.confirmAndExecuteTrade();
        }
      };
    }
  }

  pollSpot() {
    setInterval(async () => {
      try {
        const spotData = await api.getNiftySpot();
        if (spotData && spotData.spot) {
          updateHeaderSpot(spotData.spot);
          if (this.builder) this.builder.setSpot(spotData.spot);
        }
      } catch {
        // quiet fallback polling
      }
    }, 10000);
  }
}

// Bootstrap application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new SwayamApp();
  app.init().catch(console.error);
});
