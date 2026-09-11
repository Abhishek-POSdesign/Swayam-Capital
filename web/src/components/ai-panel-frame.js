/**
 * THE FLOATING AI PANEL'S FRAME. BUILD_07.
 *
 * HIS WORDS, 11 September 2026: "I don't want to squeeze the window, or I
 * don't want to shift the window to the left or right. I want the AI panel to
 * open above the window without squeezing or shifting it."
 *
 * Narrowing the page was measured, offered to him, and REJECTED. Nothing in
 * this file may ever add a margin, a width or a class to the page behind it.
 * The panel is `position: fixed` and the page below it does not know it exists.
 *
 * WHAT THIS FILE OWNS: where the panel sits, how big it is, dragging it,
 * resizing it from any of eight handles, detaching and re-attaching it,
 * shrinking it to its bar, and closing it. It owns nothing about the
 * conversation; `ai-chat.js` owns that.
 *
 * SMALL EVERY TIME, IN THE SAME PLACE. His correction of 11 September: it
 * opens at about four or five lines. WHERE it opens is remembered; HOW BIG it
 * was is not. Position is muscle memory, size depends on the minute. So the
 * stored record holds x, y and attached-or-not, and never a width or a height.
 *
 * ⚠️ THE EXIT TICKET AND THE EXECUTION TICKET ARE ALWAYS ABOVE THIS PANEL.
 * His instruction of 11 September: "my exit ticket will always be on top.
 * Orders are a priority, so nothing on top of that." Both tickets draw on
 * `.xt-backdrop` at z-index 950, the targets modal at 960 and the option chain
 * at 900. This panel is pinned at 800 in CSS and must stay below all of them.
 * That is a money rule: his window is sixty to ninety minutes, and the one
 * moment a covered control costs him is the moment he is getting out.
 */

/** Where the panel was last put. Position and attachment only, never size. */
export const PANEL_PLACE_KEY = 'swayam-ai-panel-place';

/** Four or five lines. The size it opens at, every time, however big it was. */
export const DEFAULT_W = 360;
// 280 rather than the mockup's 250, because the header became two rows
// once it was measured at this width. Four or five lines of conversation
// is the thing he asked for; the number was never the point.
export const DEFAULT_H = 280;

/** Below this it stops being usable as a chat. */
export const MIN_W = 260;
export const MIN_H = 150;

/** Where it sits when attached: clear of the launcher in the bottom-right. */
const DOCK_RIGHT = 22;
const DOCK_BOTTOM = 86;

/** How close to the window edge it may be dragged before it is held. */
const EDGE_GAP = 8;

/** The height of the bar when it is shrunk, used only to keep it on screen. */
const TINY_H = 44;

export const HANDLE_EDGES = ['n', 's', 'w', 'e', 'nw', 'ne', 'sw', 'se'];

/**
 * The ceiling he asked for: half the window across and half the window down.
 * "I want to be able to resize the window half vertically, like I'm chatting
 * with you like this, or half horizontally if I want to."
 */
export function clampSize(w, h, winW, winH) {
  const maxW = Math.max(MIN_W, Math.floor(winW / 2));
  const maxH = Math.max(MIN_H, Math.floor(winH / 2));
  return {
    w: Math.max(MIN_W, Math.min(Math.round(w), maxW)),
    h: Math.max(MIN_H, Math.min(Math.round(h), maxH)),
  };
}

/** Keeps the panel's top-left on screen whatever the window has just done. */
export function clampPosition(x, y, w, h, winW, winH) {
  return {
    x: Math.max(EDGE_GAP, Math.min(Math.round(x), Math.max(EDGE_GAP, winW - w - EDGE_GAP))),
    y: Math.max(EDGE_GAP, Math.min(Math.round(y), Math.max(EDGE_GAP, winH - h - EDGE_GAP))),
  };
}

/** What a drag of `dx, dy` on one handle does to a box. Pure, so it is testable. */
export function applyResize(edges, box, dx, dy, winW, winH) {
  let w = box.w;
  let h = box.h;
  if (edges.indexOf('e') > -1) w = box.w + dx;
  if (edges.indexOf('w') > -1) w = box.w - dx;
  if (edges.indexOf('s') > -1) h = box.h + dy;
  if (edges.indexOf('n') > -1) h = box.h - dy;

  const size = clampSize(w, h, winW, winH);
  // Pulling the west or north edge moves the opposite corner's anchor, so the
  // edge under his pointer is the one that moves and the far edge stays put.
  const x = edges.indexOf('w') > -1 ? box.x + box.w - size.w : box.x;
  const y = edges.indexOf('n') > -1 ? box.y + box.h - size.h : box.y;
  return { w: size.w, h: size.h, x, y };
}

function readPlace(storage) {
  try {
    const raw = storage.getItem(PANEL_PLACE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return {
      x: typeof parsed.x === 'number' ? parsed.x : null,
      y: typeof parsed.y === 'number' ? parsed.y : null,
      attached: parsed.attached !== false,
    };
  } catch (_) {
    return null;
  }
}

function writePlace(storage, place) {
  try {
    storage.setItem(
      PANEL_PLACE_KEY,
      JSON.stringify({ x: place.x, y: place.y, attached: place.attached })
    );
  } catch (_) {
    // A private window or blocked site data. It opens bottom-right instead.
  }
}

/** True when a ticket, the targets modal or the option chain is on screen. */
function aModalIsOpen(doc) {
  return Boolean(doc.querySelector('.xt-backdrop, .tg-backdrop, .ocm-backdrop'));
}

export class AIPanelFrame {
  /**
   * @param {HTMLElement} el the panel element itself, which is `position: fixed`
   * @param {object} options { onClose, storage, window, document }
   */
  constructor(el, options = {}) {
    this.el = el;
    this.options = options;
    this.win = options.window || (typeof window !== 'undefined' ? window : null);
    this.doc = options.document || (typeof document !== 'undefined' ? document : null);
    this.storage = options.storage || (this.win && this.win.localStorage) || null;

    const saved = this.storage ? readPlace(this.storage) : null;
    this.place = {
      x: saved ? saved.x : null,
      y: saved ? saved.y : null,
      attached: saved ? saved.attached : true,
    };
    this.size = { w: DEFAULT_W, h: DEFAULT_H };
    this.tiny = false;
    this.isOpen = false;

    this._drag = null;
    this._resize = null;
    this._bound = false;
  }

  // ------------------------------------------------------------- mounting

  /** Adds the eight handles and binds every pointer and key listener. */
  mount() {
    if (!this.el || !this.doc) return;
    this._addHandles();
    this._bindHeader();
    this._bindControls();
    if (!this._bound && this.win) {
      this.win.addEventListener('resize', () => {
        if (this.isOpen) this._place();
      });
      this.doc.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape' || !this.isOpen) return;
        // A ticket on screen owns Escape. Orders come first here too.
        if (aModalIsOpen(this.doc)) return;
        this.close();
      });
      this._bound = true;
    }
  }

  _addHandles() {
    // The handles are removed and re-added because ai-chat.js rewrites the
    // panel's innerHTML when it renders, which would otherwise strip them.
    this.el.querySelectorAll('.aip-rz').forEach((h) => h.remove());
    HANDLE_EDGES.forEach((edge) => {
      const h = this.doc.createElement('div');
      h.className = `aip-rz aip-rz--${edge}`;
      h.dataset.edge = edge;
      h.setAttribute('aria-hidden', 'true');
      this._bindHandle(h);
      this.el.appendChild(h);
    });
  }

  _bindHandle(handle) {
    handle.addEventListener('pointerdown', (e) => {
      this._detachInPlace();
      const box = { x: this.place.x, y: this.place.y, w: this.size.w, h: this.size.h };
      this._resize = { edges: handle.dataset.edge, x: e.clientX, y: e.clientY, box };
      try { handle.setPointerCapture(e.pointerId); } catch (_) {}
      if (e.preventDefault) e.preventDefault();
    });
    handle.addEventListener('pointermove', (e) => {
      if (!this._resize) return;
      const next = applyResize(
        this._resize.edges,
        this._resize.box,
        e.clientX - this._resize.x,
        e.clientY - this._resize.y,
        this._winW(),
        this._winH()
      );
      this.size = { w: next.w, h: next.h };
      this.place.x = next.x;
      this.place.y = next.y;
      this._place();
    });
    const stop = () => { this._resize = null; };
    handle.addEventListener('pointerup', stop);
    handle.addEventListener('pointercancel', stop);
  }

  _bindHeader() {
    // The title bar is the handle, not the whole header: the toolbar row
    // under it is all buttons and must not drag the window.
    const head = this.el.querySelector('.ai-panel__titlebar') || this.el.querySelector('.ai-panel__header');
    if (!head || head.dataset.aipDrag === '1') return;
    head.dataset.aipDrag = '1';
    head.addEventListener('pointerdown', (e) => {
      if (e.target && e.target.closest && e.target.closest('button, input, select, textarea, a')) return;
      this._detachInPlace();
      const r = this.el.getBoundingClientRect();
      this._drag = { dx: e.clientX - r.left, dy: e.clientY - r.top };
      try { head.setPointerCapture(e.pointerId); } catch (_) {}
    });
    head.addEventListener('pointermove', (e) => {
      if (!this._drag) return;
      this.place.x = e.clientX - this._drag.dx;
      this.place.y = e.clientY - this._drag.dy;
      this._place();
    });
    const stop = () => { this._drag = null; };
    head.addEventListener('pointerup', stop);
    head.addEventListener('pointercancel', stop);
  }

  /** The four chrome controls the mockup draws, wired if they are present. */
  _bindControls() {
    const dock = this.el.querySelector('#ai-btn-dock');
    if (dock && dock.dataset.aip !== '1') {
      dock.dataset.aip = '1';
      dock.addEventListener('click', () => this.toggleAttached());
    }
    const tiny = this.el.querySelector('#ai-btn-tiny');
    if (tiny && tiny.dataset.aip !== '1') {
      tiny.dataset.aip = '1';
      tiny.addEventListener('click', () => this.toggleTiny());
    }
    const close = this.el.querySelector('#ai-btn-close-panel');
    if (close && close.dataset.aip !== '1') {
      close.dataset.aip = '1';
      close.addEventListener('click', () => this.close());
    }
  }

  /** Called after ai-chat.js re-renders, to put the handles and bindings back. */
  refresh() {
    this._addHandles();
    this._bindHeader();
    this._bindControls();
    if (this.isOpen) this._place();
  }

  // -------------------------------------------------------------- geometry

  _winW() { return this.win ? this.win.innerWidth : 1280; }
  _winH() { return this.win ? this.win.innerHeight : 800; }

  /** Leaves the dock, keeping the panel exactly where it looks like it is. */
  _detachInPlace() {
    if (!this.place.attached) return;
    const r = this.el.getBoundingClientRect();
    this.place.attached = false;
    this.place.x = r.left;
    this.place.y = r.top;
  }

  _place() {
    const winW = this._winW();
    const winH = this._winH();
    const size = clampSize(this.size.w, this.size.h, winW, winH);
    this.size = size;

    this.el.style.width = `${size.w}px`;
    this.el.style.height = this.tiny ? 'auto' : `${size.h}px`;
    this.el.classList.toggle('aip-tiny', this.tiny);

    if (this.place.attached) {
      this.el.style.right = `${DOCK_RIGHT}px`;
      this.el.style.bottom = `${DOCK_BOTTOM}px`;
      this.el.style.left = 'auto';
      this.el.style.top = 'auto';
    } else {
      const h = this.tiny ? TINY_H : size.h;
      const x = this.place.x == null ? Math.max(EDGE_GAP, winW - size.w - 40) : this.place.x;
      const y = this.place.y == null ? Math.max(EDGE_GAP, winH - h - 110) : this.place.y;
      const at = clampPosition(x, y, size.w, h, winW, winH);
      this.place.x = at.x;
      this.place.y = at.y;
      this.el.style.left = `${at.x}px`;
      this.el.style.top = `${at.y}px`;
      this.el.style.right = 'auto';
      this.el.style.bottom = 'auto';
    }

    if (this.storage) writePlace(this.storage, this.place);
  }

  // --------------------------------------------------------------- actions

  /**
   * Opens at four or five lines, wherever he last left it. The size reset is
   * deliberate and is his instruction, not an oversight.
   */
  open() {
    this.size = { w: DEFAULT_W, h: DEFAULT_H };
    this.tiny = false;
    this.isOpen = true;
    this.el.hidden = false;
    this.el.style.display = '';
    this.el.setAttribute('aria-hidden', 'false');
    this._syncTinyLabel();
    this._place();
    const ta = this.el.querySelector('#ai-textarea');
    if (ta && typeof ta.focus === 'function') {
      try { ta.focus(); } catch (_) {}
    }
  }

  close() {
    this.isOpen = false;
    this.el.hidden = true;
    this.el.setAttribute('aria-hidden', 'true');
    if (this.options.onClose) this.options.onClose();
  }

  toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  toggleAttached() {
    if (this.place.attached) this._detachInPlace();
    else this.place.attached = true;
    this._place();
    const dock = this.el.querySelector('#ai-btn-dock');
    if (dock) {
      dock.title = this.place.attached ? 'Detach it from the corner' : 'Put it back in the corner';
      dock.setAttribute('aria-pressed', String(!this.place.attached));
    }
  }

  toggleTiny() {
    this.tiny = !this.tiny;
    this._syncTinyLabel();
    this._place();
  }

  _syncTinyLabel() {
    const tiny = this.el.querySelector('#ai-btn-tiny');
    if (!tiny) return;
    tiny.textContent = this.tiny ? '▢' : '–';
    tiny.title = this.tiny ? 'Open it back up' : 'Shrink it to the bar';
    tiny.setAttribute('aria-pressed', String(this.tiny));
  }
}
