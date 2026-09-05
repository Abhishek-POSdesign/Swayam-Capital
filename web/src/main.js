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
import { StrategyBuilderPage } from './pages/strategy-builder.js';
import { JournalPage } from './pages/journal.js';

class SwayamApp {
  constructor() {
    this.rules = null;
    this.activePositions = [];
    this.strategyPage = null;
    this.journalPage = null;
    this.wsClient = null;
    this.homePage = null;
    this.aiChat = null;
    this.aiLauncher = null;
    this.settingsDrawer = null;
    const isStrategy = typeof window !== 'undefined' && window.location.pathname.includes('strategy');
    const isJournal = typeof window !== 'undefined' && window.location.pathname.includes('journal');
    this.currentPage = isStrategy ? 'strategy' : isJournal ? 'journal' : 'home';
    this.isAIDrawerOpen = false;
  }

  async init() {
    console.log('Initializing Swayam Capital trading platform (BUILD-11)...');

    const isStrategy = typeof window !== 'undefined' && window.location.pathname.includes('strategy');
    const isJournal = typeof window !== 'undefined' && window.location.pathname.includes('journal');
    this.currentPage = isStrategy ? 'strategy' : isJournal ? 'journal' : 'home';

    // Synchronously enforce view visibility to prevent flash of wrong page on refresh
    const homeViewContainer = document.getElementById('home-view');
    const strategyContainer = document.getElementById('strategy-view');
    const journalContainer = document.getElementById('journal-view');
    if (this.currentPage === 'strategy') {
      if (homeViewContainer) homeViewContainer.style.display = 'none';
      if (strategyContainer) strategyContainer.style.display = 'block';
      if (journalContainer) journalContainer.style.display = 'none';
    } else if (this.currentPage === 'journal') {
      if (homeViewContainer) homeViewContainer.style.display = 'none';
      if (strategyContainer) strategyContainer.style.display = 'none';
      if (journalContainer) journalContainer.style.display = 'block';
    } else {
      if (homeViewContainer) homeViewContainer.style.display = 'block';
      if (strategyContainer) strategyContainer.style.display = 'none';
      if (journalContainer) journalContainer.style.display = 'none';
    }

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

    // 2. Initialize current active view first
    if (isStrategy) {
      await this.initStrategyView();
      if (homeViewContainer) {
        this.homePage = new HomePage(homeViewContainer, {
          onOpenAIDrawer: () => this.openAIDrawer(),
          onOpenSettings: () => {
            if (this.settingsDrawer) {
              const sid = this.strategyPage?.sessionId;
              this.settingsDrawer.open(sid);
            }
          },
          onNavigateStrategy: () => this.navigateTo('strategy'),
        });
        this.homePage.init();
      }
    } else if (isJournal) {
      await this.initJournalView();
      if (homeViewContainer) {
        this.homePage = new HomePage(homeViewContainer, {
          onOpenAIDrawer: () => this.openAIDrawer(),
          onOpenSettings: () => {
            if (this.settingsDrawer) {
              this.settingsDrawer.open();
            }
          },
          onNavigateStrategy: () => this.navigateTo('strategy'),
        });
        this.homePage.init();
      }
    } else {
      if (homeViewContainer) {
        this.homePage = new HomePage(homeViewContainer, {
          onOpenAIDrawer: () => this.openAIDrawer(),
          onOpenSettings: () => {
            if (this.settingsDrawer) {
              const sid = this.homePage?.aiBriefComponent?.sessionId;
              this.settingsDrawer.open(sid);
            }
          },
          onNavigateStrategy: () => this.navigateTo('strategy'),
        });
        await this.homePage.init();
      }
      this.initStrategyView();
    }

    // 3. Connect WebSocket for live NIFTY Spot ticks
    this.wsClient = new SpotWebSocketClient((spot) => {
      updateHeaderSpot(spot);
      if (this.builder) this.builder.setSpot(spot);
    });
    this.wsClient.connect();
    this.pollSpot();

    // 4. Initialize AI Trading Partner Drawer & Persistent Launcher Orb
    await this.initAIDrawer();

    // 5. Setup popstate listener for back/forward browser history
    if (typeof window !== 'undefined') {
      window.addEventListener('popstate', () => {
        const p = window.location.pathname;
        const page = p.includes('strategy') ? 'strategy' : p.includes('journal') ? 'journal' : 'home';
        this.navigateTo(page, false);
      });
    }

    // 6. Ensure correct view is displayed based on current route
    this.navigateTo(this.currentPage, false);
  }

  async initStrategyView() {
    await this.loadRules();

    const strategyContainer = document.getElementById('strategy-view');
    if (strategyContainer && !this.strategyPage) {
      this.strategyPage = new StrategyBuilderPage(strategyContainer, {
        onNavigateHome: () => this.navigateTo('home'),
        onOpenSettings: () => {
          if (this.settingsDrawer) {
            const sid = this.strategyPage?.sessionId;
            this.settingsDrawer.open(sid);
          }
        },
      });
      await this.strategyPage.init();
    }
  }

  async initJournalView() {
    const journalContainer = document.getElementById('journal-view');
    if (journalContainer && !this.journalPage) {
      this.journalPage = new JournalPage(journalContainer, {
        onOpenAIDrawer: () => this.openAIDrawer(),
      });
      await this.journalPage.init();
    }
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
      setTimeout(() => {
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('resize'));
        if (this.strategyPage?.payoffChart) this.strategyPage.payoffChart.retheme();
      }, 250);
    }
  }

  closeAIDrawer() {
    const drawer = document.getElementById('ai-sidebar-container');
    if (drawer) {
      drawer.style.right = '-450px';
      try { document.body.classList.remove('ai-panel-open'); } catch (_) {}
      this.isAIDrawerOpen = false;
      setTimeout(() => {
        if (typeof window !== 'undefined') window.dispatchEvent(new Event('resize'));
        if (this.strategyPage?.payoffChart) this.strategyPage.payoffChart.retheme();
      }, 250);
    }
  }

  toggleAIDrawer() {
    if (this.isAIDrawerOpen) {
      this.closeAIDrawer();
    } else {
      this.openAIDrawer();
    }
  }

  navigateTo(page, updateHistory = true) {
    this.currentPage = page;
    // Clear anti-flash initial-page attribute — its !important CSS rules
    // block navigation to sibling views. See styles.css.
    if (typeof document !== 'undefined' && document.documentElement) {
      document.documentElement.removeAttribute('data-initial-page');
    }
    const homeView = document.getElementById('home-view');
    const strategyView = document.getElementById('strategy-view');
    const journalView = document.getElementById('journal-view');

    // Update active state on nav pills
    const navPills = document.querySelectorAll('.nav-pill');
    navPills.forEach((btn) => {
      const p = btn.getAttribute('data-page');
      if (p === page) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    if (page === 'home') {
      if (homeView) homeView.style.display = 'block';
      if (strategyView) strategyView.style.display = 'none';
      if (journalView) journalView.style.display = 'none';
      if (updateHistory && typeof window !== 'undefined') {
        try {
          const url = new URL(window.location.href);
          url.pathname = '/';
          window.history.pushState({}, '', url.toString());
        } catch (_) {}
      }
    } else if (page === 'strategy') {
      if (homeView) homeView.style.display = 'none';
      if (strategyView) strategyView.style.display = 'block';
      if (journalView) journalView.style.display = 'none';
      if (updateHistory && typeof window !== 'undefined') {
        try {
          const url = new URL(window.location.href);
          url.pathname = '/strategy';
          window.history.pushState({}, '', url.toString());
        } catch (_) {}
      }
      if (this.strategyPage) {
        this.strategyPage.refreshPositions();
      }
    } else if (page === 'journal') {
      if (homeView) homeView.style.display = 'none';
      if (strategyView) strategyView.style.display = 'none';
      if (journalView) journalView.style.display = 'block';
      if (updateHistory && typeof window !== 'undefined') {
        try {
          const url = new URL(window.location.href);
          url.pathname = '/journal';
          window.history.pushState({}, '', url.toString());
        } catch (_) {}
      }
      if (!this.journalPage) {
        this.initJournalView();
      } else {
        this.journalPage.loadData();
      }
    }

    // Force layout refresh and redraw for charts on route transition to prevent zero width/height blankness
    const triggerChartRedraw = () => {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new Event('resize'));
      }
      if (page === 'journal' && this.journalPage) {
        this.journalPage.resizeCharts?.();
      } else if (page === 'strategy' && this.strategyPage?.payoffChart) {
        this.strategyPage.payoffChart.retheme?.();
      } else if (page === 'home' && this.homePage?.niftyChart) {
        this.homePage.niftyChart.retheme?.();
      }
    };

    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(triggerChartRedraw);
    }
    setTimeout(triggerChartRedraw, 100);
    setTimeout(triggerChartRedraw, 300);
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
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    const app = new SwayamApp();
    app.init().catch(console.error);
  });
}

export { SwayamApp };
