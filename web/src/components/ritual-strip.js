/**
 * The morning ritual, as one thin strip filled from a modal.
 *
 * It is a journal and nothing more. It cannot block a trade, cannot shrink a
 * position and shows no verdict, because a badge that stops nothing teaches you
 * to ignore badges.
 *
 * Saving is bound to the SAVE BUTTON'S CLICK, never to the dialog's `close`
 * event. Some browsers do not dispatch `close` on a programmatic .close(), and
 * a check-in that silently fails to save is worse than no check-in. This was
 * found the hard way; do not rewire it.
 */

import { api } from '../api.js';
import { escapeHtml } from '../utils/display.js';

const SLEEP_BUCKETS = ['<3', '3-4', '4-5', '5-6', '6-7', '7+'];

const MOODS = [
  ['focused', 'Focused'],
  ['neutral', 'Neutral'],
  ['tired', 'Tired'],
  ['off', 'Off'],
  ['angry_grief', 'Angry or grieving'],
];

const STRESSORS = [
  ['none', 'None'],
  ['family', 'Family'],
  ['work', 'Work'],
  ['health', 'Health'],
  ['financial', 'Financial'],
  ['other', 'Other'],
];

export class RitualStripComponent {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.entry = null; // null until today's check-in is read or written
    this.saveError = null;
  }

  async init() {
    this.render();
    await this.load();
  }

  async load() {
    try {
      const res = await api.getTodayReadiness();
      if (res && res.logged && res.factors && res.factors.input) {
        this.entry = this._fromInput(res.factors.input);
      }
    } catch (_) {
      // Not filled in is the honest default; a failed read never invents an entry.
    }
    this.render();
  }

  _fromInput(inp) {
    return {
      sleep: inp.sleep_hours_bucket || null,
      workout: typeof inp.workout_in_last_48h === 'boolean' ? inp.workout_in_last_48h : null,
      alcohol: typeof inp.alcohol_yesterday === 'boolean' ? inp.alcohol_yesterday : null,
      meditated: Boolean(inp.meditation_completed_at),
      mood: inp.journal_mood || null,
      stressor: inp.life_stressor || 'none',
      note: inp.stressor_note || '',
    };
  }

  render() {
    if (!this.container) return;
    const e = this.entry;
    const label = (list, key) => (list.find(([k]) => k === key) || [null, null])[1];

    const cell = (k, v, colour) =>
      `<div class="rr"><i>${escapeHtml(k)}</i><b${colour ? ` style="color:${colour}"` : ''}>${escapeHtml(v)}</b></div>`;

    const strip = !e
      ? `<div class="rr" style="border-right:none;color:var(--fg-2)">
           <i>This morning</i><span style="font-size:12.5px">not filled in yet</span></div>
         <div class="edit"><button class="lnk" id="btn-open-ritual" type="button">Add today's check-in</button></div>`
      : cell('Sleep', e.sleep ? `${e.sleep} h` : '—', e.sleep === '7+' || e.sleep === '6-7' ? 'var(--up)' : 'var(--warn)') +
        cell('Workout', e.workout === null ? '—' : e.workout ? 'Yes' : 'No', e.workout ? 'var(--up)' : 'var(--fg-2)') +
        cell('Alcohol', e.alcohol === null ? '—' : e.alcohol ? 'Yes' : 'No', e.alcohol === false ? 'var(--up)' : 'var(--warn)') +
        cell('Meditation', e.meditated ? 'Done' : 'Not done') +
        cell('Mood', label(MOODS, e.mood) || '—') +
        `<div class="rr" style="max-width:340px;overflow:hidden;text-overflow:ellipsis">
           <i>Note</i><b style="font-weight:500;color:var(--fg-2)">${escapeHtml(e.note || '—')}</b></div>` +
        `<div class="edit"><button class="lnk" id="btn-open-ritual" type="button">Edit</button></div>`;

    this.container.innerHTML =
      `<div class="ritual">${strip}</div>` +
      (this.saveError
        ? `<div class="why" style="border-top:none;color:var(--down);padding-left:0">Check-in not saved: ${escapeHtml(this.saveError)}</div>`
        : '') +
      this._dialogHtml();

    const open = this.container.querySelector('#btn-open-ritual');
    if (open) open.addEventListener('click', () => this._open());

    const save = this.container.querySelector('#btn-save-ritual');
    if (save) save.addEventListener('click', (ev) => {
      if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
      this._save();
    });

    const cancel = this.container.querySelector('#btn-cancel-ritual');
    if (cancel) cancel.addEventListener('click', (ev) => {
      if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
      this._close();
    });
  }

  _dialogHtml() {
    const e = this.entry || {};
    const opt = (list, sel) =>
      list.map(([k, v]) => `<option value="${k}"${k === sel ? ' selected' : ''}>${escapeHtml(v)}</option>`).join('');
    const sleepOpts = SLEEP_BUCKETS.map(
      (b) => `<option value="${b}"${b === e.sleep ? ' selected' : ''}>${b} hours</option>`,
    ).join('');
    const yesNo = (val) =>
      `<option value="no"${val ? '' : ' selected'}>No</option><option value="yes"${val ? ' selected' : ''}>Yes</option>`;

    return `
      <dialog id="ritual-dialog" class="sw-dialog">
        <div class="dh">This morning</div>
        <div class="db">
          <div class="two">
            <div class="fld"><label for="f_sleep">Sleep</label>
              <select id="f_sleep">${sleepOpts}</select></div>
            <div class="fld"><label for="f_work">Workout in the last 48 hours</label>
              <select id="f_work">${yesNo(e.workout)}</select></div>
          </div>
          <div class="two">
            <div class="fld"><label for="f_alc">Alcohol last night</label>
              <select id="f_alc">${yesNo(e.alcohol)}</select></div>
            <div class="fld"><label for="f_med">Meditation</label>
              <select id="f_med">${yesNo(e.meditated)}</select></div>
          </div>
          <div class="two">
            <div class="fld"><label for="f_mood">Mood</label>
              <select id="f_mood">${opt(MOODS, e.mood || 'neutral')}</select></div>
            <div class="fld"><label for="f_stress">Anything on your mind</label>
              <select id="f_stress">${opt(STRESSORS, e.stressor || 'none')}</select></div>
          </div>
          <div class="fld"><label for="f_note">One line for the day</label>
            <input id="f_note" value="${escapeHtml(e.note || '')}"></div>
        </div>
        <div class="df">
          <button class="btn" id="btn-cancel-ritual" type="button">Cancel</button>
          <button class="btn pri" id="btn-save-ritual" type="button">Save</button>
        </div>
      </dialog>`;
  }

  _dialog() {
    return this.container ? this.container.querySelector('#ritual-dialog') : null;
  }

  _open() {
    const d = this._dialog();
    if (d && typeof d.showModal === 'function') d.showModal();
    else if (d) d.setAttribute('open', 'true');
  }

  _close() {
    const d = this._dialog();
    if (d && typeof d.close === 'function') d.close();
    else if (d) d.removeAttribute('open');
  }

  _read(id, fallback = '') {
    const el = this.container.querySelector(`#${id}`);
    return el && el.value !== undefined && el.value !== '' ? el.value : fallback;
  }

  /** Bound to the Save button's click. See the note at the top of this file. */
  async _save() {
    const entry = {
      sleep: this._read('f_sleep', '7+'),
      workout: this._read('f_work', 'no') === 'yes',
      alcohol: this._read('f_alc', 'no') === 'yes',
      meditated: this._read('f_med', 'no') === 'yes',
      mood: this._read('f_mood', 'neutral'),
      stressor: this._read('f_stress', 'none'),
      note: (this._read('f_note', '') || '').trim(),
    };

    const payload = {
      sleep_hours_bucket: entry.sleep,
      alcohol_yesterday: entry.alcohol,
      workout_in_last_48h: entry.workout,
      journal_mood: entry.mood,
      life_stressor: entry.stressor,
      stressor_note: entry.note || null,
      meditation_completed_at: entry.meditated ? new Date().toISOString() : null,
    };

    try {
      await api.logReadiness(payload);
      this.entry = entry;
      this.saveError = null;
      this._close();
      this.render();
      if (this.options.onSaved) this.options.onSaved(entry);
    } catch (err) {
      // The strip keeps saying "not filled in yet" and names the reason, rather
      // than showing an entry the server never accepted.
      this.saveError = (err && err.message) || String(err);
      this._close();
      this.render();
    }
  }
}
