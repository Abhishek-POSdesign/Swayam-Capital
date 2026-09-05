/**
 * PWA Install Prompt Component (BUILD-11.11).
 *
 * Provides a subtle, dismissible banner encouraging installation as a PWA
 * and requesting notification permissions strictly on user gesture.
 */

import { api } from '../api.js';

export class PwaInstallPromptComponent {
  constructor(container) {
    this.container = container;
    this.deferredPrompt = null;
    this.dismissedKey = 'swayam-pwa-dismissed-until';
    this.initListeners();
  }

  isDismissed() {
    try {
      const until = localStorage.getItem(this.dismissedKey);
      if (until && Date.now() < parseInt(until, 10)) {
        return true;
      }
    } catch (_) {}
    return false;
  }

  dismiss(days = 30) {
    try {
      const expiry = Date.now() + days * 24 * 60 * 60 * 1000;
      localStorage.setItem(this.dismissedKey, expiry.toString());
    } catch (_) {}
    this.hide();
  }

  initListeners() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredPrompt = e;
      if (!this.isDismissed()) {
        this.render();
      }
    });

    window.addEventListener('appinstalled', () => {
      this.deferredPrompt = null;
      this.hide();
      console.log('[PWA] Swayam Capital installed successfully');
    });
  }

  async handleInstallClick() {
    // 1. REINFORCEMENT 1: Request notification permission strictly on user gesture
    if (typeof window !== 'undefined' && 'Notification' in window && window.Notification && window.Notification.permission === 'default') {
      try {
        const perm = await window.Notification.requestPermission();
        if (perm === 'granted' && 'serviceWorker' in navigator) {
          const reg = await navigator.serviceWorker.ready;
          if (reg && reg.pushManager) {
            try {
              const sub = await reg.pushManager.getSubscription();
              if (sub) {
                const token = JSON.stringify(sub);
                await api.registerDevice(token, navigator.userAgent, 'pwa');
              }
            } catch (subErr) {
              console.warn('[PWA] Push subscription skipped or pending VAPID:', subErr);
            }
          }
        }
      } catch (permErr) {
        console.warn('[PWA] Notification permission prompt failed:', permErr);
      }
    }

    // 2. Trigger native install prompt if available
    if (this.deferredPrompt) {
      this.deferredPrompt.prompt();
      try {
        const choice = await this.deferredPrompt.userChoice;
        if (choice && choice.outcome === 'accepted') {
          console.log('[PWA] User accepted install prompt');
        }
      } catch (_) {}
      this.deferredPrompt = null;
    }

    this.hide();
  }

  render() {
    if (!this.container) return;
    if (this.isDismissed()) {
      this.hide();
      return;
    }

    this.container.innerHTML = `
      <div class="pwa-install-banner" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; background: var(--dl-card); border: 1px solid var(--accent-sage); border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; gap: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: fadeIn 0.3s ease;">
        <div style="display: flex; align-items: center; gap: 12px; font-size: 0.88rem; color: var(--dl-fg); min-width: 220px; flex: 1;">
          <span style="font-size: 1.35rem; flex-shrink: 0; line-height: 1; display: inline-block;">📱</span>
          <span><strong>Install Swayam</strong> · Get instant push notifications and a home-screen app icon.</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
          <button id="pwa-install-btn" style="background: var(--accent-sage); color: #101116; border: none; padding: 7px 16px; border-radius: 6px; font-weight: 700; font-size: 0.82rem; cursor: pointer; transition: opacity 0.15s ease;">
            Install
          </button>
          <button id="pwa-dismiss-btn" style="background: transparent; color: var(--dl-fg-3); border: 1px solid var(--dl-line); padding: 7px 14px; border-radius: 6px; font-size: 0.82rem; cursor: pointer;">
            Not now
          </button>
        </div>
      </div>
    `;

    const installBtn = this.container.querySelector('#pwa-install-btn');
    if (installBtn) {
      installBtn.addEventListener('click', () => this.handleInstallClick());
    }

    const dismissBtn = this.container.querySelector('#pwa-dismiss-btn');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => this.dismiss(30));
    }
  }

  hide() {
    if (this.container) {
      this.container.innerHTML = '';
    }
  }
}
