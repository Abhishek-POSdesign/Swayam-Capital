import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import { setupTestDOM } from './setup_test_dom.js';
import { PwaInstallPromptComponent } from '../src/components/pwa-install-prompt.js';
import { api } from '../src/api.js';

describe('BUILD-11.11 PWA & Install Prompt Components', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders install prompt banner and dismisses for 30 days on Not Now click', () => {
    const prompt = new PwaInstallPromptComponent(container);
    // Initially not dismissed
    expect(prompt.isDismissed()).toBe(false);

    prompt.render();
    expect(container.textContent).toContain('Install Swayam');
    expect(container.textContent).toContain('Get instant push notifications');
    expect(container.querySelector('#pwa-install-btn')).not.toBeNull();
    expect(container.querySelector('#pwa-dismiss-btn')).not.toBeNull();

    // Click Not Now
    const dismissBtn = container.querySelector('#pwa-dismiss-btn');
    dismissBtn.click();

    // Now dismissed and hidden
    expect(prompt.isDismissed()).toBe(true);
    expect(container.innerHTML).toBe('');

    // Re-rendering while dismissed leaves container empty
    prompt.render();
    expect(container.innerHTML).toBe('');
  });

  it('suppresses install prompt banner when already running in standalone display mode', () => {
    window.matchMedia = vi.fn().mockImplementation(query => ({
      matches: query === '(display-mode: standalone)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const prompt = new PwaInstallPromptComponent(container);
    expect(prompt.isDismissed()).toBe(true);
  });

  it('requests notification permission on Install click (user gesture - REINFORCEMENT 1)', async () => {
    const prompt = new PwaInstallPromptComponent(container);
    prompt.render();

    // Mock Notification API
    const requestPermissionSpy = vi.fn().mockResolvedValue('granted');
    global.window.Notification = {
      permission: 'default',
      requestPermission: requestPermissionSpy,
    };

    const mockPromptEvent = {
      prompt: vi.fn(),
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    };
    prompt.deferredPrompt = mockPromptEvent;

    const installBtn = container.querySelector('#pwa-install-btn');
    expect(installBtn).not.toBeNull();

    await prompt.handleInstallClick();

    // REINFORCEMENT 1: Notification permission must be triggered by user gesture
    expect(requestPermissionSpy).toHaveBeenCalledTimes(1);
    expect(mockPromptEvent.prompt).toHaveBeenCalledTimes(1);
  });

  it('validates web/public/manifest.webmanifest configuration', () => {
    const manifestPath = path.resolve(__dirname, '../public/manifest.webmanifest');
    expect(fs.existsSync(manifestPath)).toBe(true);

    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    expect(manifest.name).toBe('Swayam Capital');
    expect(manifest.short_name).toBe('Swayam');
    expect(manifest.start_url).toBe('/');
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBe('#86ab92');
    expect(manifest.icons).toHaveLength(2);
    expect(manifest.icons[0].sizes).toBe('192x192');
    expect(manifest.icons[1].sizes).toBe('512x512');
  });

  it('validates web/public/service-worker.js push and notificationclick navigation (REINFORCEMENT 2)', () => {
    const swPath = path.resolve(__dirname, '../public/service-worker.js');
    expect(fs.existsSync(swPath)).toBe(true);

    const swCode = fs.readFileSync(swPath, 'utf8');

    // 1. Cache shell
    expect(swCode).toContain('swayam-shell-v1');
    expect(swCode).toContain('install');
    expect(swCode).toContain('activate');
    expect(swCode).toContain('fetch');

    // 2. Push event listener
    expect(swCode).toContain("self.addEventListener('push'");
    expect(swCode).toContain('showNotification');

    // 3. REINFORCEMENT 2: notificationclick handler focuses window AND navigates to payload url
    expect(swCode).toContain("self.addEventListener('notificationclick'");
    expect(swCode).toContain('client.focus');
    expect(swCode).toContain('client.navigate');
    expect(swCode).toContain('self.clients.openWindow');
    expect(swCode).toContain('targetUrl');
  });
});
