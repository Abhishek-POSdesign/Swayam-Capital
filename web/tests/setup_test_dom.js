/**
 * Lightweight in-memory DOM simulation for fast headless Vitest execution in Node.js.
 */

export function setupTestDOM() {
  const elementsById = new Map();

  function createMockElement(tagName = 'div', id = null) {
    if (id && elementsById.has(id)) {
      return elementsById.get(id);
    }

    const el = {
      tagName: tagName.toUpperCase(),
      attributes: id ? { id } : {},
      children: [],
      eventListeners: {},
      _innerHTML: '',
      _textContent: null,
      style: {},
      classList: {
        _classes: new Set(),
        add(c) { this._classes.add(c); },
        remove(c) { this._classes.delete(c); },
        contains(c) { return this._classes.has(c); },
      },
      appendChild(child) {
        this.children.push(child);
        return child;
      },
      removeChild(child) {
        const idx = this.children.indexOf(child);
        if (idx !== -1) this.children.splice(idx, 1);
        return child;
      },
      getAttribute(name) {
        return this.attributes[name] ?? null;
      },
      setAttribute(name, val) {
        this.attributes[name] = String(val);
        if (name === 'id') elementsById.set(val, this);
      },
      removeAttribute(name) {
        delete this.attributes[name];
      },

      addEventListener(evt, handler) {
        if (!this.eventListeners[evt]) this.eventListeners[evt] = [];
        this.eventListeners[evt].push(handler);
      },
      click() {
        if (this.eventListeners['click']) {
          for (const h of this.eventListeners['click']) {
            h({ target: this });
          }
        }
      },
      dispatchEvent(evt) {
        const type = typeof evt === 'string' ? evt : evt.type;
        if (this.eventListeners[type]) {
          for (const h of this.eventListeners[type]) {
            h({ target: this });
          }
        }
      },
      get innerHTML() {
        return this._innerHTML;
      },
      set innerHTML(html) {
        this._innerHTML = html;
        this._textContent = null;
      },
      get textContent() {
        if (this._textContent !== null) return this._textContent;
        // Strip only valid HTML tags like <div>, </span>, etc.
        return this._innerHTML.replace(/<[a-zA-Z\/][^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
      },
      set textContent(val) {
        this._textContent = String(val);
        this._innerHTML = String(val);
      },
      querySelector(selector) {
        if (selector.startsWith('#')) {
          const targetId = selector.slice(1);
          if (this.attributes['id'] === targetId) return this;
          if (elementsById.has(targetId)) return elementsById.get(targetId);

          const tagMatch = this._innerHTML.match(new RegExp(`<([a-zA-Z0-9_-]+)\\b([^>]*id=["']${targetId}["'][^>]*)>([\\s\\S]*?)<\\/\\1>`, 'i'));
          if (tagMatch) {
            const found = createMockElement(tagMatch[1], targetId);
            found.innerHTML = tagMatch[3];
            const attrRegex = /([a-zA-Z0-9_-]+)=["']([^"']*)["']/g;
            let m;
            while ((m = attrRegex.exec(tagMatch[2])) !== null) {
              found.setAttribute(m[1], m[2]);
              if (m[1] === 'class') {
                m[2].split(/\s+/).filter(Boolean).forEach(c => found.classList.add(c));
              }
            }
            return found;
          }

          if (this._innerHTML.includes(`id="${targetId}"`) || this._innerHTML.includes(`id='${targetId}'`)) {
            return createMockElement('div', targetId);
          }
        }

        if (selector.startsWith('.')) {
          const attrMatch = selector.match(/^\.([a-zA-Z0-9_-]+)\[([a-zA-Z0-9_-]+)=["']?([^"']*)["']?\]/);
          if (attrMatch) {
            const [, cls, attrName, attrVal] = attrMatch;
            if (this._innerHTML.includes(cls) && this._innerHTML.includes(`${attrName}="${attrVal}"`)) {
              const found = createMockElement();
              found.classList.add(cls);
              found.setAttribute(attrName, attrVal);
              return found;
            }
          }
          const cls = selector.slice(1);
          if (this._innerHTML.includes(cls)) {
            const found = createMockElement();
            found.classList.add(cls);
            return found;
          }
        }
        // Match tag selectors e.g. strong, code, em, li
        const tagRegex = new RegExp(`<(${selector})\\b[^>]*>([\\s\\S]*?)<\\/\\1>`, 'i');
        const match = this._innerHTML.match(tagRegex);
        if (match) {
          const found = createMockElement(match[1]);
          found.innerHTML = match[2];
          return found;
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

  const htmlEl = createMockElement('html');
  global.document = {
    documentElement: htmlEl,
    body: createMockElement('body'),
    createElement: (tag) => createMockElement(tag),
    getElementById: (id) => createMockElement('div', id),
  };

  global.window = {
    document: global.document,
    localStorage: global.localStorage,

    AudioContext: class {
      createOscillator() { return { type: '', frequency: { setValueAtTime: () => {} }, connect: () => {}, start: () => {}, stop: () => {} }; }
      createGain() { return { gain: { setValueAtTime: () => {}, exponentialRampToValueAtTime: () => {} }, connect: () => {} }; }
      get destination() { return {}; }
      get currentTime() { return 0; }
    },
  };

  global.self = global.window;
  global.Event = class { constructor(type) { this.type = type; } };
}
