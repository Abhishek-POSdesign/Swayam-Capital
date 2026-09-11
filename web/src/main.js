/**
 * Main application orchestrator for Swayam Capital (BUILD-9).
 * Multi-page architecture: Home (Readiness + Market Prep) & Strategy Builder.
 */

import { api } from './api.js';
import { ActiveTradesComponent } from './components/active-trades.js';
import { AIChatPanel } from './components/ai-chat.js';
import { AIFloatingLauncher } from './components/ai-launcher.js';
import { AIPanelFrame } from './components/ai-panel-frame.js';
import { initHeader, updateHeaderSpot } from './components/header.js';
import { renderRulePanel } from './components/rule-panel.js';
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
    this.aiFrame = null;
    this.settingsDrawer = null;
    const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
    if (urlParams && urlParams.get('notrans') === '1') {
      try {
        document.documentElement.setAttribute('data-no-transitions', 'true');
        document.body.classList.add('no-transitions');
      } catch (_) {}
    }
    const qpTheme = urlParams ? urlParams.get('theme') : null;
    if (qpTheme && ['light', 'dark', 'auto'].includes(qpTheme)) {
      try {
        localStorage.setItem('swayam-theme', qpTheme);
        document.documentElement.setAttribute('data-theme', qpTheme);
      } catch (_) {}
    }
    const qpPage = urlParams ? urlParams.get('page') : null;
    const isStrategy = qpPage === 'strategy' || (typeof window !== 'undefined' && window.location.pathname.includes('strategy'));
    const isJournal = qpPage === 'journal' || (typeof window !== 'undefined' && window.location.pathname.includes('journal'));
    this.currentPage = isStrategy ? 'strategy' : isJournal ? 'journal' : 'home';
    this.isAIDrawerOpen = false;
    this._strategyInitInProgress = false;
    this._skeletonCheckTimer = null;
  }

  async init() {
    console.log('Initializing Swayam Capital trading platform (BUILD-11)...');

    const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
    if (urlParams && urlParams.get('notrans') === '1') {
      try {
        document.documentElement.setAttribute('data-no-transitions', 'true');
        document.body.classList.add('no-transitions');
      } catch (_) {}
    }
    const qpTheme = urlParams ? urlParams.get('theme') : null;
    if (qpTheme && ['light', 'dark', 'auto'].includes(qpTheme)) {
      try {
        localStorage.setItem('swayam-theme', qpTheme);
        document.documentElement.setAttribute('data-theme', qpTheme);
      } catch (_) {}
    }
    const qpPage = urlParams ? urlParams.get('page') : null;
    const isStrategy = qpPage === 'strategy' || (typeof window !== 'undefined' && window.location.pathname.includes('strategy'));
    const isJournal = qpPage === 'journal' || (typeof window !== 'undefined' && window.location.pathname.includes('journal'));
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

    // 3. Connect WebSocket for live NIFTY Spot ticks. The client publishes
    // every tick to `spotFeed`, which Home and the Strategy Desk subscribe to,
    // and falls back to a REST poll on its own if the socket goes silent. The
    // separate 10-second poll that used to live here updated only the header
    // pill; it is gone, so there is one stream and every panel follows it.
    this.wsClient = new SpotWebSocketClient((spot) => {
      updateHeaderSpot(spot);
    });
    this.wsClient.connect();

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

    // 6. Register PWA Service Worker (BUILD-11.11)
    this.registerServiceWorker();

    // 6. Ensure correct view is displayed based on current route
    this.navigateTo(this.currentPage, false);

    // 7. Auto-open the AI panel if he arrived with ?ai=open
    const wantsAI =
      (urlParams && urlParams.get('ai') === 'open') ||
      (typeof window !== 'undefined' && window.__swayamOpenAIPanel === true);
    if (wantsAI) {
      this.openAIDrawer();
    }
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

  /**
   * THE FLOATING AI PANEL. BUILD_07.
   *
   * `ai-chat.js` renders the conversation into the shell, then `AIPanelFrame`
   * takes over the shell's geometry: drag, eight resize handles, detach and
   * attach, shrink to the bar, and close. The order matters, because the chat
   * rewrites the shell's innerHTML and would otherwise strip the handles.
   *
   * The panel starts CLOSED and opens small, wherever he last left it.
   */
  async initAIDrawer() {
    const aiContainer = document.getElementById('ai-sidebar-container');
    if (aiContainer) {
      this.aiChat = new AIChatPanel(aiContainer);
      await this.aiChat.init();

      this.aiFrame = new AIPanelFrame(aiContainer);
      this.aiFrame.mount();
    }

    this.aiLauncher = new AIFloatingLauncher({
      onToggle: () => this.toggleAIDrawer(),
    });
    this.aiLauncher.init();
  }

  /**
   * Opening the panel does NOTHING to the page. No class, no margin, no
   * reflow, and no resize event to make the payoff graph redraw, because
   * nothing behind the panel has moved. That whole apparatus was deleted in
   * BUILD_07 on his instruction and must not come back.
   */
  openAIDrawer() {
    if (this.aiFrame) this.aiFrame.open();
    this.isAIDrawerOpen = true;
  }

  closeAIDrawer() {
    if (this.aiFrame) this.aiFrame.close();
    this.isAIDrawerOpen = false;
  }

  toggleAIDrawer() {
    if (this.aiFrame) {
      this.aiFrame.toggle();
      this.isAIDrawerOpen = this.aiFrame.isOpen;
      return;
    }
    this.isAIDrawerOpen = false;
  }

  navigateTo(page, updateHistory = true) {
    // A NEW PAGE OPENS AT ITS TOP. His report, 2026-09-11: "Switching pages
    // opens the new page at its top; today the scroll position carries over."
    // The three views are siblings that are shown and hidden, so the WINDOW
    // never scrolls -- it simply keeps whatever offset the page he left was
    // sitting at, and the new one appears already scrolled into its middle.
    // Done before the swap so he never sees the old page jump.
    const changed = this.currentPage !== page;
    if (changed && typeof window !== 'undefined' && window.scrollTo) {
      // 'instant' rather than a smooth glide: he is switching pages, not
      // scrolling, and a half-second animation on every tab press reads as lag.
      try { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }); }
      catch (_) { window.scrollTo(0, 0); }
    }
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
      // Lazy-initialize strategy page if not yet done (e.g. first navigation to strategy)
      if (!this.strategyPage && !this._strategyInitInProgress) {
        this._strategyInitInProgress = true;
        this.initStrategyView().finally(() => { this._strategyInitInProgress = false; });
      } else if (this.strategyPage) {
        this.strategyPage.refreshPositions();
      }
      // Stuck-skeleton fallback: if the strategy container still shows a skeleton
      // after 1.5s (content never mounted), force a re-init.
      if (strategyView) {
        const skeletonCheck = setTimeout(() => {
          const stillHasSkeleton = strategyView.querySelector('.skeleton-shimmer, .skeleton-row, [data-skeleton]');
          const hasRealContent = strategyView.querySelector('#strategy-builder-layout');
          if (stillHasSkeleton && !hasRealContent && !this._strategyInitInProgress) {
            console.warn('[SwayamApp] Strategy skeleton stuck — forcing re-init.');
            this.strategyPage = null;
            this._strategyInitInProgress = true;
            this.initStrategyView().finally(() => { this._strategyInitInProgress = false; });
          }
        }, 1500);
        // Store so we can cancel it if needed
        if (this._skeletonCheckTimer) clearTimeout(this._skeletonCheckTimer);
        this._skeletonCheckTimer = skeletonCheck;
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

  registerServiceWorker() {
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js')
          .then((reg) => {
            console.log('[SW] Service worker registered successfully:', reg.scope);
          })
          .catch((err) => {
            console.warn('[SW] Service worker registration failed:', err);
          });
      });
    }
  }
}

// Bootstrap application on DOM ready
if (typeof document !== 'undefined') {
  const bootstrap = () => {
    const app = new SwayamApp();
    window.__swayamApp = app;
    app.init().catch(console.error);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }
}

export { SwayamApp };
