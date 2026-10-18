# recording_analysis.py — the architect's recording of 2026-10-18 (media/wpms_test001_2026-10-18.flac,
# lossless from the WAV sent, 48 kHz, 24 bit, stereo): level, the notes, the bursts and their period.
# Needs ffmpeg and numpy.  python3 recording_analysis.py > recording_analysis.txt
import os, subprocess, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, "..", "media", "wpms_test001_2026-10-18.flac")
fs = 48000
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", F, "-f", "s32le", "-"], capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype="<i4").reshape(-1, 2) / float(1 << 31)
m = x.mean(1)
db = lambda a: 20 * np.log10(a + 1e-12)
print(f"duration {len(m) / fs:.2f} s, 48 kHz, 24 bit, stereo")
for c in range(2):
    print(f"ch{c}: peak {db(np.abs(x[:, c]).max()):.1f} dBFS, rms {db(np.sqrt(np.mean(x[:, c] ** 2))):.1f} dBFS, "
          f"samples at full scale {int(np.sum(np.abs(x[:, c]) >= 0.999))}")
N = 1 << 20
S = np.abs(np.fft.rfft(np.pad(m, (0, max(0, N - len(m))))[:N] * np.hanning(N))); f = np.fft.rfftfreq(N, 1 / fs)
peaks = []
for i in np.argsort(S)[::-1]:
    if f[i] >= 20 and all(abs(f[i] - p) > 10 for p in peaks): peaks.append(f[i])
    if len(peaks) >= 16: break
print("16 strongest spectral peaks (Hz):", ", ".join(f"{p:.1f}" for p in sorted(peaks)))
hop = fs // 50
env = db(np.array([np.sqrt(np.mean(m[i:i + hop] ** 2)) for i in range(0, len(m) - hop, hop)]))
cand = [i for i in range(1, len(env) - 1) if env[i] > -40 and env[i] >= env[i - 1] and env[i] >= env[i + 1]]
bursts = []
for i in cand:
    if bursts and i - bursts[-1] < 25:
        if env[i] > env[bursts[-1]]: bursts[-1] = i
    else: bursts.append(i)
print("bursts (20 ms rms above -40 dBFS):")
for i in bursts:
    t = i * hop / fs; s = m[int((t - 0.15) * fs):int((t + 0.15) * fs)]
    Sp = np.abs(np.fft.rfft(s * np.hanning(len(s)), 1 << 16)); fr = np.fft.rfftfreq(1 << 16, 1 / fs); Sp[fr < 60] = 0
    w6 = np.sum(env[max(0, i - 40):i + 40] > env[i] - 6) * hop / fs * 1000
    print(f"  {t:6.2f} s  {env[i]:6.1f} dBFS  {fr[np.argmax(Sp)]:7.1f} Hz  -6 dB width {w6:.0f} ms")
q = m[int(0.2 * fs):int(2.0 * fs)]
Sq = np.abs(np.fft.rfft(q * np.hanning(len(q)))); fq = np.fft.rfftfreq(len(q), 1 / fs)
print("between bursts (0.2-2.0 s), components:")
for f0 in (131, 262, 523, 750, 1500, 2250, 3000):
    k = np.argmin(abs(fq - f0)); a = Sq[max(0, k - 5):k + 6].max() * 2 / np.sum(np.hanning(len(q)))
    print(f"  {f0:5d} Hz  {db(a):6.1f} dBFS")
