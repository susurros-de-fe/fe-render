import numpy as np, wave

SR = 44100

def _note(freq, dur, amp, detune=0.18, attack=2.5, release=3.0):
    t = np.arange(int(dur * SR)) / SR
    s = (np.sin(2*np.pi*(freq-detune)*t) + np.sin(2*np.pi*(freq+detune)*t)) * 0.5
    s += 0.30 * np.sin(2*np.pi*freq*2*t) + 0.10 * np.sin(2*np.pi*freq*3*t)
    env = np.minimum(1.0, t/attack) * np.minimum(1.0, (dur - t)/release)
    env = np.clip(env, 0, 1)
    env = env * env * (3 - 2*env)
    lfo = 1.0 + 0.12*np.sin(2*np.pi*0.11*t + freq)
    return amp * s * env * lfo

def _chime(freq, amp, dur=4.0):
    t = np.arange(int(dur * SR)) / SR
    s = np.sin(2*np.pi*freq*t) + 0.25*np.sin(2*np.pi*freq*2.76*t)*np.exp(-t*3.0)
    env = np.minimum(1.0, t/0.01) * np.exp(-t*1.1)
    return amp * s * env

def _reverb(x, wet=0.35, rt=2.2, seed=3):
    rng = np.random.default_rng(seed)
    n = int(rt * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n)/SR * (6.9/rt))
    ir[:int(0.02*SR)] *= np.linspace(0, 1, int(0.02*SR))
    ir /= np.sqrt(np.sum(ir**2))
    L = len(x) + n
    nfft = 1 << (L-1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(x)]
    return (1-wet)*x + wet*y

def synth_relax(path, secs, seed=5):
    rng = np.random.default_rng(seed)
    n = int(secs * SR)
    buf = np.zeros(n)
    # progresion lenta y calida (Do mayor): Cmaj9 - Am9 - Fmaj7 - Gsus
    acordes = [
        [130.81, 164.81, 196.00, 246.94, 293.66],
        [110.00, 130.81, 164.81, 196.00, 246.94],
        [87.31, 110.00, 130.81, 164.81, 220.00],
        [98.00, 146.83, 164.81, 220.00, 293.66],
    ]
    paso = 9.0
    k, t0 = 0, 0.0
    while t0 < secs + 3:
        for f in acordes[k % 4]:
            nota = _note(f, paso + 4.0, 0.16)
            i0 = int(t0 * SR)
            fin = min(n, i0 + len(nota))
            if i0 < n:
                buf[i0:fin] += nota[:fin-i0]
        k += 1
        t0 += paso
    # campanitas suaves (pentatonica)
    penta = [523.25, 587.33, 659.25, 783.99, 880.00, 1046.5]
    t = 2.5
    while t < secs:
        f = penta[rng.integers(0, len(penta))]
        c = _chime(f, rng.uniform(0.05, 0.10))
        i0 = int(t * SR)
        fin = min(n, i0 + len(c))
        buf[i0:fin] += c[:fin-i0]
        t += rng.uniform(5.0, 9.0)
    # viento muy suave (ruido marron filtrado)
    r = rng.standard_normal(n)
    br = np.cumsum(r); br -= np.convolve(br, np.ones(4410)/4410, mode='same')
    br /= np.max(np.abs(br)) + 1e-9
    tt = np.arange(n)/SR
    buf += 0.05 * br * (0.6 + 0.4*np.sin(2*np.pi*0.07*tt))
    buf = _reverb(buf, wet=0.38)
    # fundido de entrada y salida
    f_in = int(1.5*SR); f_out = int(2.5*SR)
    buf[:f_in] *= np.linspace(0, 1, f_in)
    buf[-f_out:] *= np.linspace(1, 0, f_out)
    buf = buf / (np.max(np.abs(buf)) + 1e-9) * 0.85
    pcm = (buf * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())

if __name__ == '__main__':
    import sys
    synth_relax(sys.argv[1], float(sys.argv[2]))
