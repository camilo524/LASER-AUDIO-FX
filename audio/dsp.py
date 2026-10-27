"""Procesamiento de senal de audio.

Todo el analisis vive aqui y solo depende de numpy, asi que se puede probar
fuera de Blender. La unidad de tiempo del analisis es ``ANALYSIS_FPS`` frames
por segundo.
"""

import math

import numpy as np

ANALYSIS_FPS = 100.0
NFFT = 1024
BANDS = {
    "BASS": (35.0, 150.0),
    "MID": (150.0, 2000.0),
    "HIGH": (2000.0, 9000.0),
    "FULL": (35.0, 9000.0),
}


def _norm(v, lo=5.0, hi=98.0):
    a, b = np.percentile(v, [lo, hi])
    if b - a < 1e-9:
        return np.zeros_like(v, dtype=np.float32)
    return np.clip((v - a) / (b - a), 0.0, 1.0).astype(np.float32)


def _smooth(x, n):
    n = max(1, int(n))
    if n == 1:
        return x
    return np.convolve(x, np.ones(n) / n, mode="same")


def _stft_mag(x, sr, hop):
    win = np.hanning(NFFT).astype(np.float32)
    n = int(len(x) / hop) + 1
    pad = NFFT // 2
    xp = np.concatenate([np.zeros(pad, np.float32), x.astype(np.float32),
                         np.zeros(NFFT + pad, np.float32)])
    S = np.empty((n, NFFT // 2 + 1), np.float32)
    ar = np.arange(NFFT)
    for s0 in range(0, n, 256):
        s1 = min(n, s0 + 256)
        starts = (np.arange(s0, s1) * hop).astype(np.int64)
        seg = xp[starts[:, None] + ar[None, :]] * win
        S[s0:s1] = np.abs(np.fft.rfft(seg, axis=1))
    return S, np.fft.rfftfreq(NFFT, 1.0 / sr)


def _suppress(cands, strengths, min_gap):
    order = np.argsort(-strengths)
    taken = []
    for j in order:
        c = int(cands[j])
        if all(abs(c - t) >= min_gap for t in taken):
            taken.append(c)
    return np.array(sorted(taken), dtype=np.int64)


def _peaks(env, fps, sens=1.0, min_gap_s=0.12, win_s=0.8):
    e = env / (env.max() + 1e-9)
    w = max(3, int(win_s * fps))
    k = np.ones(w) / w
    mean = np.convolve(e, k, mode="same")
    var = np.convolve(e * e, k, mode="same") - mean ** 2
    std = np.sqrt(np.maximum(var, 0.0))
    s = max(sens, 0.05)
    thr = mean + (0.9 / s) * std + 0.05 / s
    i = np.arange(1, len(e) - 1)
    ok = (e[i] > e[i - 1]) & (e[i] >= e[i + 1]) & (e[i] > thr[i])
    cands = i[ok]
    if len(cands) == 0:
        return np.array([], dtype=np.float64)
    keep = _suppress(cands, e[cands], max(1, int(min_gap_s * fps)))
    return keep / fps


def _estimate_bpm(env, fps, lo=70.0, hi=180.0, center=105.0):
    e = env - env.mean()
    n = len(e)
    if n < fps * 4 or not np.any(e):
        return 100.0
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    ac = ac / (ac[0] + 1e-12)
    lag_lo = max(2, int(fps * 60.0 / hi))
    lag_hi = min(int(fps * 60.0 / lo), n - 2)
    lags = np.arange(lag_lo, lag_hi)
    if len(lags) < 3:
        return 100.0
    bpm = 60.0 * fps / lags
    prior = np.exp(-0.5 * (np.log2(bpm / center) / 0.7) ** 2)
    score = ac[lags] * (0.5 + prior)
    k = int(np.argmax(score))
    lag = float(lags[k])
    y0, y1, y2 = ac[lags[k] - 1], ac[lags[k]], ac[lags[k] + 1]
    den = y0 - 2 * y1 + y2
    if abs(den) > 1e-12:
        lag += 0.5 * (y0 - y2) / den
    return 60.0 * fps / lag


def _fit_grid(env, fps, bpm0, span=2.5, step=0.05):
    n = len(env)
    dur = n / fps
    best = (-1.0, bpm0, 0.0)
    for bpm in np.arange(bpm0 - span, bpm0 + span + 1e-6, step):
        T = 60.0 / bpm
        offs = np.arange(0.0, T, 1.0 / fps)
        nb = int(dur / T) + 1
        times = offs[:, None] + np.arange(nb)[None, :] * T
        idx = np.round(times * fps).astype(np.int64)
        valid = idx < n
        idx = np.minimum(idx, n - 1)
        vals = (env[idx] * valid).sum(axis=1) / np.maximum(valid.sum(axis=1), 1)
        k = int(np.argmax(vals))
        if vals[k] > best[0]:
            best = (float(vals[k]), float(bpm), float(offs[k]))
    return best[1], best[2]


def _pick_downbeat(beats, bass, fps, bpb):
    if len(beats) < bpb * 2:
        return 0
    idx = np.minimum(np.round(beats * fps).astype(int), len(bass) - 1)
    vals = bass[idx]
    scores = [vals[p::bpb].mean() if len(vals[p::bpb]) else 0.0 for p in range(bpb)]
    return int(np.argmax(scores))


def _sections(energy, fps, win_s=4.0, thr=0.15, min_gap_s=8.0):
    w = int(win_s * fps)
    n = len(energy)
    if n < 3 * w:
        return np.array([], dtype=np.float64)
    c = np.concatenate([[0.0], np.cumsum(energy)])
    i = np.arange(w, n - w)
    score = np.abs((c[i + w] - c[i]) / w - (c[i] - c[i - w]) / w)
    loc = (score[1:-1] >= score[:-2]) & (score[1:-1] >= score[2:]) & (score[1:-1] > thr)
    cands = i[1:-1][loc]
    if len(cands) == 0:
        return np.array([], dtype=np.float64)
    st = score[1:-1][loc]
    keep = _suppress(cands, st, int(min_gap_s * fps))
    return keep / fps


def analyze_signal(x, sr, sensitivity=1.0, bpm_manual=0.0, bpm_mult=1.0, bpb=4):
    """Analiza una senal mono y devuelve bandas, BPM, beats, bombos y secciones."""
    fps = ANALYSIS_FPS
    hop = sr / fps
    S, freqs = _stft_mag(x, sr, hop)
    n = S.shape[0]
    bands = {}
    for k, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        bands[k] = _norm(np.log1p(S[:, m].mean(axis=1) * 4.0))

    def flux(lo, hi):
        m = (freqs >= lo) & (freqs <= hi)
        L = np.log1p(S[:, m] * 4.0)
        d = np.maximum(np.diff(L, axis=0, prepend=L[:1]), 0.0).sum(axis=1)
        return _smooth(d, 3)

    f_all, f_kick = flux(30, 5000), flux(30, 160)
    onsets = _peaks(f_all, fps, sensitivity)
    kicks = _peaks(f_kick, fps, sensitivity, 0.18)
    # El bombo manda al ubicar la rejilla: asi los beats caen en el golpe grave
    # y no en el contratiempo (hi-hat, snare).
    env = 0.3 * f_all / (f_all.max() + 1e-9) + 1.0 * f_kick / (f_kick.max() + 1e-9)
    env = _smooth(env, 3)
    if bpm_manual > 0:
        bpm, off = _fit_grid(env, fps, bpm_manual, span=0.0)
    else:
        bpm, off = _fit_grid(env, fps, _estimate_bpm(env, fps) * bpm_mult)
    T = 60.0 / bpm
    dur = n / fps
    beats = off + np.arange(int(max(dur - off, 0) / T) + 1) * T
    phase = _pick_downbeat(beats, bands["BASS"], fps, bpb)
    secs = _sections(_smooth(bands["FULL"], 50), fps)
    return {"duration": dur, "bands": bands, "bpm": float(bpm), "offset": float(off),
            "beats": beats, "kicks": kicks, "onsets": onsets, "sections": secs,
            "downbeat_phase": phase}


def pulse_curve(positions, n, decay_frames):
    """Curva de destellos: cada posicion es un pico con caida exponencial."""
    out = np.zeros(n, np.float32)
    d = max(float(decay_frames), 1e-3)
    span = int(d * 6) + 2
    for p in positions:
        i0 = int(round(p))
        if i0 >= n or i0 + span < 0:
            continue
        a, b = max(i0, 0), min(n, i0 + span)
        if b <= a:
            continue
        v = np.exp(-(np.arange(a, b) - i0) / d)
        out[a:b] = np.maximum(out[a:b], v)
    return out


def smooth_env(x, fps, attack_s, release_s):
    """Envolvente con ataque y caida independientes."""
    out = np.empty(len(x), np.float32)
    ka = 1.0 - math.exp(-1.0 / (max(attack_s, 1e-3) * fps))
    kr = 1.0 - math.exp(-1.0 / (max(release_s, 1e-3) * fps))
    y = 0.0
    for i, v in enumerate(x):
        y += (float(v) - y) * (ka if v > y else kr)
        out[i] = y
    return out


def synthetic_analysis(bpm, dur, bpb=4):
    """Analisis sintetico por BPM: sin audio, ideal para renderizar loops."""
    fps = ANALYSIS_FPS
    n = int(dur * fps) + 1
    T = 60.0 / bpm
    beats = np.arange(0.0, dur + T, T)
    half = beats + T / 2.0
    both = np.sort(np.concatenate([beats, half]))
    bands = {"BASS": pulse_curve(beats * fps, n, T * fps * 0.45),
             "MID": pulse_curve(half * fps, n, T * fps * 0.35),
             "HIGH": pulse_curve(both * fps, n, T * fps * 0.18)}
    bands["FULL"] = np.maximum(bands["BASS"], 0.6 * bands["MID"])
    return {"duration": dur, "bands": bands, "bpm": float(bpm), "offset": 0.0,
            "beats": beats, "kicks": beats, "onsets": both,
            "sections": np.array([], dtype=np.float64), "downbeat_phase": 0}
