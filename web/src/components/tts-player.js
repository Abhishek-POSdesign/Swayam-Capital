/**
 * TTS Audio Player for Swayam Capital.
 * Provides text-to-speech playback using Google Cloud TTS Indian English voices.
 * Features:
 * - Single active audio stream (playing a new message stops any previous one)
 * - In-memory object URL cache per message/text so replay is instant
 * - Subtle resting speaker icon -> loading waveform -> playing/pause toggle
 * - Settings integration with localStorage for voice profile and speech rate
 */

let _activeAudio = null;
let _activeButton = null;
const _audioCache = new Map(); // key -> objectUrl

export function getTTSPreferences() {
  const voice = localStorage.getItem('swayam_tts_voice') || 'swayam_calm';
  const rate = parseFloat(localStorage.getItem('swayam_tts_rate') || '0.90');
  const autoPlay = localStorage.getItem('swayam_tts_autoplay') === 'true';
  return { voice, rate, autoPlay };
}

export function setTTSPreferences({ voice, rate, autoPlay }) {
  if (voice) localStorage.setItem('swayam_tts_voice', voice);
  if (rate !== undefined) localStorage.setItem('swayam_tts_rate', String(rate));
  if (autoPlay !== undefined) localStorage.setItem('swayam_tts_autoplay', String(autoPlay));
}

export function stopCurrentPlayback() {
  if (_activeAudio) {
    try {
      _activeAudio.pause();
      _activeAudio.currentTime = 0;
    } catch (_) {}
    _activeAudio = null;
  }
  if (_activeButton) {
    updateButtonUI(_activeButton, 'idle');
    _activeButton = null;
  }
}

function updateButtonUI(btn, state) {
  if (!btn) return;
  btn.setAttribute('data-state', state);
  if (btn.dataset) btn.dataset.state = state;

  if (state === 'loading') {
    btn.innerHTML = `
      <svg class="tts-waveform-anim" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-lilac); animation: tts-pulse 1s infinite alternate;">
        <line x1="6" y1="9" x2="6" y2="15"></line>
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="18" y1="8" x2="18" y2="16"></line>
      </svg>
    `;
    btn.title = 'Generating audio...';
  } else if (state === 'playing') {
    btn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-lilac);">
        <rect x="6" y="4" width="4" height="16" fill="currentColor"></rect>
        <rect x="14" y="4" width="4" height="16" fill="currentColor"></rect>
      </svg>
    `;
    btn.title = 'Pause audio';
  } else if (state === 'error') {
    btn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--accent-coral);">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
    `;
    btn.title = 'Failed to generate audio (click to retry)';
  } else {
    // idle state
    btn.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--dl-fg-3);">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor"></polygon>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
      </svg>
    `;
    btn.title = 'Read aloud';
  }
}

export async function playText(text, btnElement = null) {
  if (!text || !text.trim()) return;

  // If clicking on already playing button, toggle pause
  if (_activeButton === btnElement && _activeAudio) {
    if (!_activeAudio.paused) {
      _activeAudio.pause();
      updateButtonUI(btnElement, 'idle');
      return;
    } else {
      _activeAudio.play();
      updateButtonUI(btnElement, 'playing');
      return;
    }
  }

  // Stop previous
  stopCurrentPlayback();

  const { voice, rate } = getTTSPreferences();
  const cacheKey = `${voice}_${rate}_${text.trim()}`;

  if (btnElement) {
    _activeButton = btnElement;
    updateButtonUI(btnElement, 'loading');
  }

  try {
    let audioUrl = _audioCache.get(cacheKey);
    if (!audioUrl) {
      const response = await fetch('/api/tts/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text.trim(),
          voice_profile: voice,
          speaking_rate: rate,
        }),
      });

      if (!response.ok) {
        let errDetail = 'Failed to synthesize speech';
        try {
          const errJson = await response.json();
          if (errJson.detail) errDetail = errJson.detail;
        } catch (_) {
          errDetail = `${response.status} ${response.statusText}`;
        }
        throw new Error(errDetail);
      }

      const blob = await response.blob();
      audioUrl = URL.createObjectURL(blob);
      _audioCache.set(cacheKey, audioUrl);
    }

    const audio = new Audio(audioUrl);
    _activeAudio = audio;

    audio.onended = () => {
      if (_activeButton === btnElement) {
        updateButtonUI(btnElement, 'idle');
        _activeButton = null;
      }
      _activeAudio = null;
    };

    audio.onerror = (e) => {
      console.error('Audio playback error:', e);
      if (btnElement) updateButtonUI(btnElement, 'error');
      _activeAudio = null;
      _activeButton = null;
    };

    await audio.play();
    if (btnElement) updateButtonUI(btnElement, 'playing');
  } catch (err) {
    console.error('TTS synthesis error:', err);
    if (btnElement) {
      updateButtonUI(btnElement, 'error');
      btnElement.title = `TTS Error: ${err.message}`;
    }
    _activeAudio = null;
    _activeButton = null;
    alert(`Voice Readout Notice: ${err.message}`);
  }
}

export function createTTSButton(textProvider) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'btn-tts-action';
  btn.style.cssText = `
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: background var(--dur-fast, 120ms) ease, transform var(--dur-fast, 120ms) ease;
  `;
  btn.setAttribute('aria-label', 'Read aloud');

  updateButtonUI(btn, 'idle');

  btn.addEventListener('mouseenter', () => {
    btn.style.background = 'var(--accent-lilac-tint, rgba(172, 159, 210, 0.14))';
  });
  btn.addEventListener('mouseleave', () => {
    btn.style.background = 'transparent';
  });

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const text = typeof textProvider === 'function' ? textProvider() : textProvider;
    playText(text, btn);
  });

  return btn;
}
