/**
 * BUILD_07. THE FLOATING AI PANEL.
 *
 * What these tests are for, and what they are NOT for.
 *
 * They hold the RULES: it opens small every time, it remembers only where it
 * was, it stops at half the window, it carries no starter prompt in any state,
 * Clear touches nothing, Delete asks first, and the microphone is either real
 * or absent with words in its place.
 *
 * They are NOT proof that the panel sits under the exit ticket. A stacking
 * context made by a transform or a filter anywhere up the tree can defeat a
 * z-index that reads perfectly, so the last test here is a REGRESSION GUARD on
 * the numbers, and the proof is dragging the panel over the ticket in a real
 * browser and opening the ticket. That is in the handoff.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { setupTestDOM } from './setup_test_dom.js';
import {
  AIPanelFrame,
  clampSize,
  clampPosition,
  applyResize,
  leadingAxis,
  DEFAULT_W,
  DEFAULT_H,
  MIN_W,
  MIN_H,
  HANDLE_EDGES,
  PANEL_PLACE_KEY,
} from '../src/components/ai-panel-frame.js';
import { AIChatPanel } from '../src/components/ai-chat.js';

// Some rules live in CSS the test DOM cannot hold, so they are read from
// the source itself. A guard against them being deleted, not a render test.
const chatSource = readFileSync(new URL('../src/components/ai-chat.js', import.meta.url), 'utf8');

// ---------------------------------------------------------------- fake DOM
//
// Hand-made rather than borrowed, because this is geometry: the numbers have
// to come from the code under test, not from a shim's idea of a rectangle.

function fakeEl(rect = { left: 100, top: 100, width: DEFAULT_W, height: DEFAULT_H }) {
  const el = {
    style: {},
    hidden: true,
    dataset: {},
    children: [],
    attrs: {},
    classes: new Set(),
    _rect: rect,
    classList: {
      toggle(name, on) { if (on) el.classes.add(name); else el.classes.delete(name); },
      add(name) { el.classes.add(name); },
      remove(name) { el.classes.delete(name); },
      contains(name) { return el.classes.has(name); },
    },
    listeners: {},
    addEventListener(type, fn) { el.listeners[type] = fn; },
    removeEventListener() {},
    setAttribute(k, v) { el.attrs[k] = v; },
    getAttribute(k) { return el.attrs[k]; },
    appendChild(child) { el.children.push(child); return child; },
    removeChild(child) { el.children = el.children.filter((c) => c !== child); },
    querySelectorAll(sel) {
      if (sel === '.aip-rz') return el.children.filter((c) => String(c.className || '').includes('aip-rz'));
      return [];
    },
    querySelector() { return null; },
    getBoundingClientRect() { return { ...el._rect }; },
  };
  return el;
}

function fakeDoc() {
  return {
    createElement() {
      const node = fakeEl();
      node.className = '';
      node.listeners = {};
      node.addEventListener = (type, fn) => { node.listeners[type] = fn; };
      node.remove = () => {};
      return node;
    },
    addEventListener: vi.fn(),
    querySelector: () => null,
  };
}

function fakeStorage() {
  const map = new Map();
  return {
    map,
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
  };
}

function fakeWindow(innerWidth = 1600, innerHeight = 1000) {
  return { innerWidth, innerHeight, addEventListener: vi.fn() };
}

// =========================================================== the geometry

describe('A half of his screen is a HALF, and never smaller than a chat', () => {
  // HIS CORRECTION, 12 September 2026: "half horizontally means the full
  // horizontal area's height is half, and the full length width is half."
  // The first build capped both at half, which is a QUARTER of his screen.
  it('lets the axis he is pulling reach the whole window', () => {
    const wide = clampSize(5000, 5000, 1600, 1000, 'w');
    expect(wide.w).toBe(1600 - 16);   // the full width, less the edge gap
    expect(wide.h).toBe(500);         // and the other axis held at half

    const tall = clampSize(5000, 5000, 1600, 1000, 'h');
    expect(tall.h).toBe(1000 - 16);
    expect(tall.w).toBe(800);
  });

  it('never lets both axes past half at once, whatever the lead says', () => {
    const both = clampSize(5000, 5000, 1600, 1000, null);
    expect(both.w).toBe(800);
    expect(both.h).toBe(500);
  });

  it('leaves a window that fits well inside the rule alone', () => {
    const small = clampSize(460, 460, 1600, 1000, 'w');
    expect(small.w).toBe(460);
    expect(small.h).toBe(460);
  });

  it('refuses to shrink below a usable chat', () => {
    const tiny = clampSize(10, 10, 1600, 1000, 'w');
    expect(tiny.w).toBe(MIN_W);
    expect(tiny.h).toBe(MIN_H);
  });

  it('keeps the minimum even on a window too small to halve', () => {
    const squeezed = clampSize(400, 400, 300, 200, 'w');
    expect(squeezed.w).toBe(MIN_W);
    expect(squeezed.h).toBe(MIN_H);
  });

  it('holds the panel on screen when the window shrinks under it', () => {
    const at = clampPosition(1500, 900, 360, 250, 800, 600);
    expect(at.x).toBeLessThanOrEqual(800 - 360);
    expect(at.y).toBeLessThanOrEqual(600 - 250);
    expect(at.x).toBeGreaterThan(0);
    expect(at.y).toBeGreaterThan(0);
  });
});

describe('All eight handles, and the far edge stays put', () => {
  const box = { x: 400, y: 300, w: 360, h: 250 };

  it('offers exactly eight, four edges and four corners', () => {
    expect(HANDLE_EDGES.sort()).toEqual(['e', 'n', 'ne', 'nw', 's', 'se', 'sw', 'w'].sort());
  });

  it('grows east and south without moving the top-left corner', () => {
    const out = applyResize('se', box, 120, 90, 1600, 1000);
    expect(out.w).toBe(480);
    expect(out.h).toBe(340);
    expect(out.x).toBe(400);
    expect(out.y).toBe(300);
  });

  it('grows west by moving the left edge, keeping the right edge where it was', () => {
    const out = applyResize('w', box, -100, 0, 1600, 1000);
    expect(out.w).toBe(460);
    expect(out.x).toBe(300);
    // The right edge has not moved: 400 + 360 === 300 + 460.
    expect(out.x + out.w).toBe(box.x + box.w);
  });

  it('grows north by moving the top edge, keeping the bottom edge where it was', () => {
    const out = applyResize('n', box, 0, -80, 1600, 1000);
    expect(out.h).toBe(330);
    expect(out.y).toBe(220);
    expect(out.y + out.h).toBe(box.y + box.h);
  });

  it('names the axis he is actually pulling, even on a corner', () => {
    expect(leadingAxis('e', 50, 0)).toBe('w');
    expect(leadingAxis('n', 0, 50)).toBe('h');
    expect(leadingAxis('se', 200, 30)).toBe('w');   // mostly sideways
    expect(leadingAxis('se', 30, 200)).toBe('h');   // mostly downwards
  });

  it('pulls the east edge all the way to the far side of the screen', () => {
    const out = applyResize('e', box, 9000, 0, 1600, 1000);
    expect(out.w).toBe(1600 - 16);
    expect(out.h).toBe(box.h);
  });

  it('pulls the bottom edge all the way down the screen', () => {
    const out = applyResize('s', box, 0, 9000, 1600, 1000);
    expect(out.h).toBe(1000 - 16);
    expect(out.w).toBe(box.w);
  });

  it('holds the other axis at half once one of them is past half', () => {
    const wide = applyResize('se', box, 9000, 9000, 1600, 1000);
    expect(wide.w).toBe(1600 - 16);
    expect(wide.h).toBe(500);
  });
});

// ================================================= small every time, same place

describe('It opens small every time, and remembers only where it was', () => {
  let el;
  let frame;
  let storage;

  beforeEach(() => {
    el = fakeEl();
    storage = fakeStorage();
    frame = new AIPanelFrame(el, {
      window: fakeWindow(),
      document: fakeDoc(),
      storage,
    });
  });

  it('opens at four or five lines however large it was last time', () => {
    frame.open();
    expect(el.style.width).toBe(`${DEFAULT_W}px`);
    expect(el.style.height).toBe(`${DEFAULT_H}px`);

    // He drags it out to half the screen.
    frame.size = { w: 800, h: 500 };
    frame._place();
    expect(el.style.width).toBe('800px');
    expect(el.style.height).toBe('500px');

    frame.close();
    frame.open();
    // Small again. HIS CORRECTION of 11 September: size is forgotten on purpose.
    expect(el.style.width).toBe(`${DEFAULT_W}px`);
    expect(el.style.height).toBe(`${DEFAULT_H}px`);
  });

  it('stores where it was and NEVER how big it was', () => {
    frame.open();
    frame.toggleAttached();       // detaches, which is what gives it an x and y
    frame.place.x = 240;
    frame.place.y = 160;
    frame._place();

    const stored = JSON.parse(storage.getItem(PANEL_PLACE_KEY));
    expect(stored.x).toBe(240);
    expect(stored.y).toBe(160);
    expect(stored.attached).toBe(false);
    expect(stored.w).toBeUndefined();
    expect(stored.h).toBeUndefined();
  });

  it('comes back to where he left it on the next session', () => {
    storage.setItem(PANEL_PLACE_KEY, JSON.stringify({ x: 512, y: 64, attached: false }));
    const next = new AIPanelFrame(fakeEl(), {
      window: fakeWindow(),
      document: fakeDoc(),
      storage,
    });
    next.open();
    expect(next.el.style.left).toBe('512px');
    expect(next.el.style.top).toBe('64px');
  });

  it('sits in the corner when it has never been moved', () => {
    frame.open();
    expect(el.style.right).toBe('22px');
    expect(el.style.left).toBe('auto');
  });

  it('shrinks to the bar and opens back up', () => {
    frame.open();
    frame.toggleTiny();
    expect(el.classes.has('aip-tiny')).toBe(true);
    expect(el.style.height).toBe('auto');
    frame.toggleTiny();
    expect(el.classes.has('aip-tiny')).toBe(false);
    expect(el.style.height).toBe(`${DEFAULT_H}px`);
  });

  it('survives a browser that refuses to store anything', () => {
    const blocked = {
      getItem() { throw new Error('blocked'); },
      setItem() { throw new Error('blocked'); },
    };
    const f = new AIPanelFrame(fakeEl(), { window: fakeWindow(), document: fakeDoc(), storage: blocked });
    expect(() => f.open()).not.toThrow();
    expect(f.el.style.right).toBe('22px');
  });
});

describe('Escape, and who owns it', () => {
  function frameWithDoc(hasTicket) {
    const doc = fakeDoc();
    doc.querySelector = (sel) =>
      hasTicket && sel.includes('.xt-backdrop') ? {} : null;
    const f = new AIPanelFrame(fakeEl(), {
      window: fakeWindow(),
      document: doc,
      storage: fakeStorage(),
    });
    return { f, doc };
  }

  it('closes the panel when nothing else is on screen', () => {
    const { f, doc } = frameWithDoc(false);
    f.mount();
    f.open();
    const handler = doc.addEventListener.mock.calls.find((c) => c[0] === 'keydown')[1];
    handler({ key: 'Escape' });
    expect(f.isOpen).toBe(false);
  });

  it('LEAVES ESCAPE TO THE EXIT TICKET when a ticket is open. Orders come first.', () => {
    const { f, doc } = frameWithDoc(true);
    f.mount();
    f.open();
    const handler = doc.addEventListener.mock.calls.find((c) => c[0] === 'keydown')[1];
    handler({ key: 'Escape' });
    expect(f.isOpen).toBe(true);
  });
});

// ======================================================== the panel's insides

describe('The conversation panel itself', () => {
  let container;

  beforeEach(() => {
    setupTestDOM();
    container = document.createElement('div');
    document.body.appendChild(container);
    vi.restoreAllMocks();
  });

  it('carries NO starter prompt, in any state', () => {
    const panel = new AIChatPanel(container);
    panel._render();
    const html = container.innerHTML;
    expect(html).not.toContain('ai-starter');
    expect(html).not.toContain('Ask me something to start');
    expect(html).not.toContain('VIX is at the 8th percentile');
  });

  it('offers New, History, Clear and Delete, and the three window controls', () => {
    const panel = new AIChatPanel(container);
    panel._render();
    const html = container.innerHTML;
    ['ai-btn-new', 'ai-btn-history', 'ai-btn-clear', 'ai-btn-delete',
     'ai-btn-dock', 'ai-btn-tiny', 'ai-btn-close-panel'].forEach((id) => {
      expect(html).toContain(id);
    });
  });

  it('CLEAR EMPTIES THE PANE AND TOUCHES NO ROW', () => {
    const panel = new AIChatPanel(container);
    panel._render();
    const fetchSpy = vi.fn();
    global.fetch = fetchSpy;

    document.getElementById('ai-messages').innerHTML = '<div>an old answer</div>';
    panel._clearPane();

    const pane = document.getElementById('ai-messages');
    expect(pane.innerHTML).not.toContain('an old answer');
    expect(pane.innerHTML).toContain('still in History');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('DELETE ASKS FIRST, and sends nothing until he confirms', async () => {
    const panel = new AIChatPanel(container);
    panel._render();
    panel.conversationId = 'abc-123';
    const fetchSpy = vi.fn();
    global.fetch = fetchSpy;

    panel._askToDelete();
    expect(document.getElementById('ai-delete-scrim').hidden).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalled();

    // "Keep it" sends nothing at all.
    panel._closeDeleteSheet();
    expect(document.getElementById('ai-delete-scrim').hidden).toBe(true);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('deletes exactly one conversation, by its own id, and never a list', async () => {
    const panel = new AIChatPanel(container);
    panel._render();
    panel.conversationId = 'abc-123';

    const calls = [];
    global.fetch = vi.fn((url, opts) => {
      calls.push({ url, method: opts && opts.method });
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'deleted', conversation_id: 'abc-123', images_removed: 2 }),
      });
    });

    await panel._deleteConversation();

    const del = calls.filter((c) => c.method === 'DELETE');
    expect(del).toHaveLength(1);
    expect(del[0].url).toContain('/api/ai/conversations/abc-123');
  });

  it('has no coloured edge down one side of it', () => {
    // HIS REVIEW, 12 September: "why is there a left-side color edge? It is
    // not required." A 2px blue border left over from when this was a drawer
    // glued to the right of the screen.
    const shell = chatSource.slice(
      chatSource.indexOf('      .ai-panel {'),
      chatSource.indexOf('      .ai-panel__header {')
    );
    expect(shell.length).toBeGreaterThan(50);
    expect(shell).not.toContain('border-left');
  });

  it('dresses its own scrollbars instead of leaving the browser to do it', () => {
    // Read from the source, because the test DOM does not keep what is put
    // into a <style> tag.
    expect(chatSource).toContain('::-webkit-scrollbar-thumb');
    expect(chatSource).toContain('scrollbar-width: thin');
    // And the desk behind it must not scroll when the conversation runs out.
    expect(chatSource).toContain('overscroll-behavior: contain');
  });

  it('says who said each message, the way the mockup does', () => {
    const panel = new AIChatPanel(container);
    panel._render();
    const pane = document.getElementById('ai-messages');
    const before = pane.children.length;
    panel._appendMessage('user', 'what is it worth');
    panel._appendMessage('assistant', 'about this much');
    expect(pane.children.length).toBe(before + 2);

    const labels = pane.children.flatMap((m) => (m.children || []))
      .filter((c) => String(c.className || '').includes('ai-message__who'))
      .map((c) => c.textContent);
    expect(labels).toContain('You');
    expect(labels).toContain('Partner');
  });

  it('shows no microphone where the browser cannot dictate, and says what to do instead', () => {
    const panel = new AIChatPanel(container);
    // This environment has no speech engine, which is the case under test.
    panel._render();
    const note = document.getElementById('ai-dictation-note');
    expect(note.hidden).toBe(false);
    expect(note.textContent).toContain('Chrome or Edge');
    expect(note.textContent).toContain('type');
  });
});

// ============================================================ the money rule

describe('REGRESSION GUARD: the panel is layered below both order tickets', () => {
  // Read from the stylesheets. This is a guard against someone raising the
  // number by accident, NOT proof that the ticket draws on top. The proof is
  // in a browser, with the panel dragged over the ticket.
  const tokens = readFileSync(new URL('../src/styles/swayam-tokens.css', import.meta.url), 'utf8');
  const desk = readFileSync(new URL('../src/styles/swayam-desk.css', import.meta.url), 'utf8');

  function layerOf(css, selector) {
    const block = css.slice(css.indexOf(selector));
    const match = block.match(/z-index:\s*(\d+)/);
    return match ? Number(match[1]) : null;
  }

  it('puts the ticket above the panel, and the panel above the launcher', () => {
    const ticket = layerOf(desk, '.xt-backdrop');
    const panel = layerOf(tokens, '.ai-float-panel {');
    const launcher = layerOf(tokens, '.ai-floating-launcher {');

    expect(ticket).toBe(950);
    expect(panel).toBe(800);
    expect(launcher).toBe(790);
    expect(panel).toBeLessThan(ticket);
    expect(launcher).toBeLessThan(ticket);
  });

  it('has no page-shift rule left anywhere', () => {
    const app = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
    // The comment that records the deletion is allowed; a rule is not.
    expect(app).not.toMatch(/body[^\n]*\.ai-panel-open[^\n]*\{/);
    expect(app).not.toContain('margin-right: 400px');
  });
});
