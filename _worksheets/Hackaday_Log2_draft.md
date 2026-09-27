# Hackaday.io — PTSG-WPMS-Formation — Build Log #2 (draft)

*Non-normative worksheet. English-primary; a Japanese gloss for the architect follows. ~1,200 words. Edit freely — especially where it boasts.*

---

## Log #2 — The Back Buffer Is Two Frames Old
### (or: how we stopped swapping pages and learned to race the beam)

Open Prompt promised that this ecosystem would correct itself in both directions. This week it did — twice, in two repositories, with receipts.

First the customer. FPGA Spectrum Engine finished its Layer 1 specification: five chapters, and an oracle of eighteen checks that passes in about three seconds. On the way, its amanuensis withdrew a format it had itself proposed and seen ratified. Linear fixed-point amplitude, it turned out, silences an ordinary Gaussian packet: at σ = 71 bins the first coefficient underflows 32-bit fixed point to exactly zero, and the whole packet plays nothing. The cure was four hundred years old. In 1614 John Napier published his logarithms so that astronomers could turn multiplications into additions; WPMS now keeps amplitude in log₂, where a Gaussian is a parabola, underflow does not exist, and every loop in the pipeline carries additions only. The same σ = 71 packet now sounds 927 audible bins.

Then the profile — this project — withdrew its own headline design. That is the story of this log, because it contains a bug that every games programmer of the 1990s already knew.

**What we had.** Log #1 described eight packet blocks kept in a *page pair*: the pipeline reads the active page, the program writes the shadow, and the two swap on the trailing edge of each packet. A slot named CUR told the pipeline which block to play next; while packet *b* played, the program prepared packet *b+1* and committed. It was cheap — about 25 clocks a packet — the customer agreed, and built on it.

It leaned on one sentence of the master ISA: after a commit, the new shadow holds the former active page's contents, so *everything a program does not touch is the value the consumer was just using*. Every word of that is true. "Just" is the trouble.

**The bug with a spectral signature.** A pointer flip hands you back the page you wrote *two* commits ago. Anyone who ever drew sprites with page flipping learned this the hard way: the back buffer is two frames old, so your dirty rectangles must cover the last two frames, not one. Our rule — "rewrite only what changed" — never said *changed since when*.

We built a small model before believing anything. With one packet per sweep, all fine. With two, a phase advanced once, then froze at the same value forever. With one commit per sample instead of per packet, a new frequency landed on one sample and vanished on the next, and the partial settled **halfway** between the old pitch and the new one, wobbling at 24 kHz — exactly Fs/2. A bug you could have found with a spectrum analyser.

**Racing the beam.** The Atari 2600 had no frame buffer at all. Its programmers — see Montfort and Bogost, *Racing the Beam* — rewrote the video chip's registers after the electron beam had passed, and before it came round again. That is the whole fix.

Our beam is the L1 pipeline: one bin per clock at 100 MHz, and it reads each packet exactly once per sample — a **bundle** of eight numbers (three phase terms, a level, three shape terms, a routing word) latched at the clock the packet starts. So we deleted the second page. There is one block store. A block may be written anywhere between two of the beam's visits — its **write window** — and the hardware enforces it: an illegal write halts the machine with an error code instead of producing a click. With one copy, nothing is ever stale, and "rewrite only what changed" is finally, exactly, true.

The customer's amanuensis had actually sketched this shape a week earlier, as one candidate among two. This profile already had the one-word version: the two-stage Stay-value register from Log #1, staged ahead of time and presented at Stay Set. We widened it from one word to eight. Good ideas in this ecosystem tend to be found twice.

**Two instructions in, five out.** The customer wanted level glides: every packet walks its loudness toward a target at a set rate, reaches it exactly, and parks — so a missed control update leaves a note resting instead of running away. Analog people know this circuit as the slew limiter, the lag processor, the portamento knob. An RC envelope decays exponentially and never quite arrives; in log₂ an exponential is a straight line, so a walker can arrive exactly. The new instruction **STP** (step-toward) does it in one clock. Without it, the same law took 35 instructions, and overflowed on precisely the most common gesture in music: fade to silence.

The second, **BCP**, is a masked block copy: a controller stages new values, marks which slots to replace, and the whole update lands between two samples in every module at once — in at most ten clocks.

The master ISA has eighteen formation instructions. This profile removed five (the page commit, the routing write, stack push and pop, the program's Stay-value write) and added three (a shift register write, STP, BCP): sixteen. A *subtraction profile* that got smaller by getting better.

**A gift to the Core.** Because nothing is committed at a packet boundary any more, the Formation asks the timing core for nothing between packets. The Core's single reservation slot stays free for the jump into the next packet, and the architect has pledged — on PTSG's pride — zero idle clocks between consecutive Stays. The Core itself grew a `stay_value` pin this week: the Formation hands it each packet's length, and a zero on the pin means *read the score*. The Core will repeat packets by re-entering one packet body; an unrolled score stays available for bring-up and quick checks.

**Receipts.** A sweep oracle ran the real packet program on a model of the new sequencer, under random traffic — retunes, re-seeds, level glides, sweeps growing and shrinking, full-load sweeps of exactly 2,048 bins. Every bundle the pipeline latched was compared with a reference written from the customer's specification, with the glide law imported straight from the customer's own oracle. Over 60,000 samples, 215,627 packets and 4,174 updates (1,175 of them at full load): **zero mismatches**. Worst sweep: 2,064 clocks of the 2,083 available. A deliberately broken program — one that advances a phase twice — was caught 2,798 times in 3,000 samples, and thirteen out of thirteen negative tests reject what they should.

Now the honest footnote, in the house style. Sixty thousand samples is 1.25 seconds of audio. And an oracle is not silicon. *Measured, not promised* — the measuring on DE10-nano comes next: the gap between packets, the wake-up latency, the shortest packet (32 bins, by count), and how long an update takes to land.

**Allow us a little pride.** Nearly five months ago Hackaday called FPGA Spectrum Engine "an SDR for the world of acoustics." A software-defined radio lives or dies by a control plane that is exact to the sample. This week that control plane learned to hand 2,048 oscillators per module their orders without ever tearing a packet — and two AI amanuenses, in two repositories, each retracted a design they had proposed themselves, with evidence, in the same week. The architect ruled on both — the second on the same day.

The full reasoning, the model that sank the page swap, and the oracle are in the repository: a new Layer 2 trace, Decision Register W v0.7, the register map v0.3, and two new deliverables — the pipeline's side of the interface and the choreography of a sample period.

---

*(JA 要旨: 今週、エコシステムは二度、根拠を添えて自らを訂正した。顧客側は線形振幅を撤回して log₂ へ——1614 年のネイピアの「積を和に」。本プロファイルはページ交代(Mode T)を撤回した。ポインタ反転の裏ページは「二コマ前」——90 年代のゲームプログラマなら誰でも知っていた罠で、二パケットで位相が止まり、再調律は新旧の中間で 24 kHz に揺れた。解は Atari 2600 の「ビームと競走」: L1 がパケット開始時に一度だけ読むバンドルを守り、各ブロックへの書込みは二回の読み出しの間(書込み窓)に限る。命令は五つ減らして三つ足し、十八から十六へ。STP はアナログのスルーリミッタを log₂ で正確に着地させる一命令、BCP は更新を全モジュール同一サンプルに十クロック以内で着地させる。パケット境界で何も要求しないので、Core の予約スロットは次パケットへの跳躍に空き、無停止の連続 Stay は PTSG の誇りにかけて守られる。60,000 サンプル・215,627 パケット・4,174 更新で不一致ゼロ——ただし 1.25 秒分の音で、オラクルでありシリコンではない。次は DE10-nano で実測。Hackaday 本誌が「音響の SDR」と呼んだ装置の制御面が、一度も波束を裂かずに 2,048 本へ命令を渡せるようになった。)*
