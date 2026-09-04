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
          if (this._innerHTML.includes(`id="${targetId}"`) || this._innerHTML.includes(`id='${targetId}'`)) {
            return createMockElement('div', targetId);
          }
        }
        if (selector.startsWith('.')) {
          const cls = selector.slice(1);
          if (this._innerHTML.includes(cls)) {
            const found = createMockElement();
            found.classList.add(cls);
            return found;
          }
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
        }
        return results;
      },
    };

    if (id) {
      elementsById.set(id, el);
    }
    return el;
  }

  global.document = {
    body: createMockElement('body'),
    createElement: (tag) => createMockElement(tag),
    getElementById: (id) => createMockElement('div', id),
  };

  global.window = {
    document: global.document,
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
