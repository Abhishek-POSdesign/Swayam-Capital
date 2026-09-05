/**
 * Lightweight in-memory DOM simulation for fast headless Vitest execution in Node.js.
 */

export function setupTestDOM() {
  const elementsById = new Map();

  function applyStyleString(styleObj, styleStr) {
    if (!styleStr) return;
    styleStr.split(';').forEach(rule => {
      const idx = rule.indexOf(':');
      if (idx !== -1) {
        const prop = rule.slice(0, idx).trim();
        const val = rule.slice(idx + 1).trim();
        if (prop && val) {
          const camel = prop.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
          styleObj[camel] = val;
        }
      }
    });
  }

  function createStyleObject() {
    const styles = {};
    return new Proxy(styles, {
      set(target, prop, val) {
        if (prop === 'cssText') {
          applyStyleString(target, String(val));
          target.cssText = String(val);
          return true;
        }
        target[prop] = val;
        return true;
      },
      get(target, prop) {
        return target[prop];
      }
    });
  }

  function createMockElement(tagName = 'div', id = null) {
    let _val = '';
    const el = {
      tagName: tagName.toUpperCase(),
      attributes: id ? { id } : {},
      get id() {
        return this.attributes.id;
      },
      set id(val) {
        this.attributes.id = val;
        if (val) elementsById.set(val, this);
      },
      children: [],
      parentNode: null,
      eventListeners: {},
      _innerHTML: '',
      _textContent: null,
      style: createStyleObject(),
      classList: {
        _classes: new Set(),
        add(c) { this._classes.add(c); },
        remove(c) { this._classes.delete(c); },
        contains(c) { return this._classes.has(c); },
      },
      appendChild(child) {
        this.children.push(child);
        child.parentNode = this;
        return child;
      },
      removeChild(child) {
        const idx = this.children.indexOf(child);
        if (idx !== -1) this.children.splice(idx, 1);
        child.parentNode = null;
        return child;
      },
      remove() {
        if (this.parentNode && typeof this.parentNode.removeChild === 'function') {
          this.parentNode.removeChild(this);
        }
        if (this.attributes?.id) {
          elementsById.delete(this.attributes.id);
        }
      },
      getAttribute(name) {
        return this.attributes[name] ?? null;
      },
      setAttribute(name, val) {
        this.attributes[name] = String(val);
        if (name === 'id') elementsById.set(val, this);
        if (name === 'style') applyStyleString(this.style, String(val));
        if (name === 'value') _val = String(val);
      },
      removeAttribute(name) {
        delete this.attributes[name];
      },
      get value() {
        return _val !== '' ? _val : (this.attributes['value'] ?? '');
      },
      set value(v) {
        _val = String(v);
        this.attributes['value'] = String(v);
      },

      addEventListener(evt, handler) {
        if (!this.eventListeners[evt]) this.eventListeners[evt] = [];
        this.eventListeners[evt].push(handler);
      },
      click() {
        const handlers = [...(this.eventListeners['click'] || [])];
        for (const h of handlers) {
          h({ target: this });
        }
      },
      dispatchEvent(evt) {
        const type = typeof evt === 'string' ? evt : evt.type;
        const handlers = [...(this.eventListeners[type] || [])];
        for (const h of handlers) {
          h({ target: this });
        }
      },
      get innerHTML() {
        return this._innerHTML;
      },
      set innerHTML(html) {
        this._innerHTML = html;
        this._textContent = null;
        this._queryCache = new Map();
      },
      get textContent() {
        if (this._textContent !== null) return this._textContent;
        return this._innerHTML.replace(/<[a-zA-Z\/][^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
      },
      set textContent(val) {
        this._textContent = String(val);
        this._innerHTML = String(val);
        this._queryCache = new Map();
      },
      querySelector(selector) {
        if (!this._queryCache) this._queryCache = new Map();
        if (this._queryCache.has(selector)) return this._queryCache.get(selector);

        const recordResult = (found) => {
          if (found && this._queryCache) this._queryCache.set(selector, found);
          return found;
        };

        if (selector.startsWith('#')) {
          const targetId = selector.slice(1);
          if (this.attributes['id'] === targetId) return recordResult(this);
          if (elementsById.has(targetId)) return recordResult(elementsById.get(targetId));

          const openTagRegex = new RegExp(`<([a-zA-Z0-9_-]+)\\s+([^>]*\\bid=["']${targetId}["'][^>]*)>`, 'i');
          const openMatch = this._innerHTML.match(openTagRegex);
          if (openMatch) {
            const tagName = openMatch[1];
            const attrs = openMatch[2];
            const found = createMockElement(tagName, targetId);
            const afterOpen = this._innerHTML.slice(openMatch.index + openMatch[0].length);
            const closeIdx = afterOpen.indexOf(`</${tagName}>`);
            if (closeIdx !== -1) {
              found.innerHTML = afterOpen.slice(0, closeIdx);
            }
            const attrRegex = /([a-zA-Z0-9_-]+)=["']([^"']*)["']/g;
            let m;
            while ((m = attrRegex.exec(attrs)) !== null) {
              found.setAttribute(m[1], m[2]);
              if (m[1] === 'class') {
                m[2].split(/\s+/).filter(Boolean).forEach(c => found.classList.add(c));
              }
            }
            return recordResult(found);
          }

          if (this._innerHTML.includes(`id="${targetId}"`) || this._innerHTML.includes(`id='${targetId}'`)) {
            return recordResult(createMockElement('div', targetId));
          }
        }

        if (selector.startsWith('.')) {
          const cls = selector.slice(1);
          const openTagRegex = new RegExp(`<([a-zA-Z0-9_-]+)\\s+([^>]*\\bclass=["'][^"']*\\b${cls}\\b[^"']*["'][^>]*)>`, 'i');
          const openMatch = this._innerHTML.match(openTagRegex);
          if (openMatch) {
            const tagName = openMatch[1];
            const attrs = openMatch[2];
            const found = createMockElement(tagName);
            found.classList.add(cls);
            const afterOpen = this._innerHTML.slice(openMatch.index + openMatch[0].length);
            const closeIdx = afterOpen.indexOf(`</${tagName}>`);
            if (closeIdx !== -1) {
              found.innerHTML = afterOpen.slice(0, closeIdx);
            }
            const attrRegex = /([a-zA-Z0-9_-]+)=["']([^"']*)["']/g;
            let m;
            while ((m = attrRegex.exec(attrs)) !== null) {
              found.setAttribute(m[1], m[2]);
            }
            return recordResult(found);
          }
          if (this._innerHTML.includes(cls)) {
            const found = createMockElement();
            found.classList.add(cls);
            return recordResult(found);
          }
        }

        // Handle attribute selectors e.g. input[value="..."], button[title*="..."]
        const attrSelectorMatch = selector.match(/^([a-zA-Z0-9_-]+)?\[([a-zA-Z0-9_-]+)([*^$])?=["']?([^"']*)["']?\]/);
        if (attrSelectorMatch) {
          const [, tag = '[a-zA-Z0-9_-]+', attrName, op, attrVal] = attrSelectorMatch;
          const openTagRegex = new RegExp(`<(${tag})\\s+([^>]*\\b${attrName}=["'][^"']*${attrVal}[^"']*["'][^>]*)>`, 'i');
          const openMatch = this._innerHTML.match(openTagRegex);
          if (openMatch) {
            const matchedTag = openMatch[1] || 'div';
            const matchedAttrs = openMatch[2] || '';
            const found = createMockElement(matchedTag);
            const afterOpen = this._innerHTML.slice(openMatch.index + openMatch[0].length);
            const closeIdx = afterOpen.indexOf(`</${matchedTag}>`);
            if (closeIdx !== -1) {
              found.innerHTML = afterOpen.slice(0, closeIdx);
            }
            const attrRegex = /([a-zA-Z0-9_-]+)=["']([^"']*)["']/g;
            let m;
            while ((m = attrRegex.exec(matchedAttrs)) !== null) {
              found.setAttribute(m[1], m[2]);
            }
            return recordResult(found);
          }
        }

        // Match tag selectors e.g. strong, code, em, li
        const tagRegex = new RegExp(`<(${selector})\\b([^>]*)>`, 'i');
        const openMatch = this._innerHTML.match(tagRegex);
        if (openMatch) {
          const matchedTag = openMatch[1];
          const matchedAttrs = openMatch[2] || '';
          const found = createMockElement(matchedTag);
          const afterOpen = this._innerHTML.slice(openMatch.index + openMatch[0].length);
          const closeIdx = afterOpen.indexOf(`</${matchedTag}>`);
          if (closeIdx !== -1) {
            found.innerHTML = afterOpen.slice(0, closeIdx);
          }
          const attrRegex = /([a-zA-Z0-9_-]+)=["']([^"']*)["']/g;
          let m;
          while ((m = attrRegex.exec(matchedAttrs)) !== null) {
            found.setAttribute(m[1], m[2]);
          }
          return recordResult(found);
        }
        return null;
      },
      querySelectorAll(selector) {
        const results = [];
        if (selector.startsWith('.')) {
          const cls = selector.slice(1);
          const regex = new RegExp(`class="[^"]*${cls}[^"]*"`, 'g');
          const matches = this._innerHTML.match(regex) || [];
          for (let i = 0; i < matches.length; i++) {
            const item = createMockElement();
            item.classList.add(cls);
            results.push(item);
          }
        } else {
          // Tag selectors
          const tagRegex = new RegExp(`<(${selector})\\b[^>]*>([\\s\\S]*?)<\\/\\1>`, 'gi');
          let m;
          while ((m = tagRegex.exec(this._innerHTML)) !== null) {
            const item = createMockElement(m[1]);
            item.innerHTML = m[2];
            results.push(item);
          }
        }
        return results;
      },
    };

    if (id) {
      elementsById.set(id, el);
    }
    return el;
  }

  const storage = new Map();
  global.localStorage = {
    getItem: (key) => (storage.has(key) ? storage.get(key) : null),
    setItem: (key, val) => storage.set(key, String(val)),
    removeItem: (key) => storage.delete(key),
    clear: () => storage.clear(),
  };

  const sessionStore = new Map();
  global.sessionStorage = {
    getItem: (key) => (sessionStore.has(key) ? sessionStore.get(key) : null),
    setItem: (key, val) => sessionStore.set(key, String(val)),
    removeItem: (key) => sessionStore.delete(key),
    clear: () => sessionStore.clear(),
  };

  const htmlEl = createMockElement('html');
  global.document = {
    documentElement: htmlEl,
    body: createMockElement('body'),
    createElement: (tag) => createMockElement(tag),
    getElementById: (id) => elementsById.get(id) || createMockElement('div', id),
    querySelector: (sel) => null,
    querySelectorAll: (sel) => [],
  };

  const windowListeners = new Map();
  global.window = {
    document: global.document,
    localStorage: global.localStorage,
    sessionStorage: global.sessionStorage,
    location: { pathname: '/', href: 'http://localhost:5173/' },
    history: { pushState: () => {}, replaceState: () => {} },
    addEventListener: (evt, handler) => {
      if (!windowListeners.has(evt)) windowListeners.set(evt, []);
      windowListeners.get(evt).push(handler);
    },
    removeEventListener: (evt, handler) => {
      if (windowListeners.has(evt)) {
        const arr = windowListeners.get(evt);
        const idx = arr.indexOf(handler);
        if (idx !== -1) arr.splice(idx, 1);
      }
    },
    dispatchEvent: (evt) => {
      const type = typeof evt === 'string' ? evt : evt.type;
      if (windowListeners.has(type)) {
        for (const h of windowListeners.get(type)) {
          h(evt);
        }
      }
    },

    AudioContext: class {
      createOscillator() { return { type: '', frequency: { setValueAtTime: () => {} }, connect: () => {}, start: () => {}, stop: () => {} }; }
      createGain() { return { gain: { setValueAtTime: () => {}, exponentialRampToValueAtTime: () => {} }, connect: () => {} }; }
      get destination() { return {}; }
      get currentTime() { return 0; }
    },
  };

  global.window.Plotly = {
    react: () => Promise.resolve(),
    newPlot: () => Promise.resolve(),
    relayout: () => Promise.resolve(),
    Plots: { resize: () => {} },
  };

  global.self = global.window;
  global.Event = class { constructor(type) { this.type = type; } };

  global.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({ session_id: 'test-mock-session', id: 'test-mock-session', status: 'ok', spot: 24850.0 }),
    text: async () => JSON.stringify({ session_id: 'test-mock-session', id: 'test-mock-session', status: 'ok' }),
  });
}
