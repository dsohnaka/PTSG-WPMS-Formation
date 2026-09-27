// ============================================================================
//  PTSG-Core — Reference Top-Level Verilog Implementation
//  PTSG (Programmable Timing Sequence Generator) Core
//  PTSGコア — リファレンス・トップ層 Verilog 実装
// ----------------------------------------------------------------------------
//  License : MIT (Layer 3 sample implementation; see 03_Sample_Implementations/README.md)
//
//  This module is the *top layer* of the PTSG-Core: a single synthesizable
//  module that ties together the instruction memory, the instruction decoder,
//  the four opcodes (Global / Stay / Branch / Jump), the eight internal-control
//  sub-opcodes, the Stay-window / background-execution machinery, the prescaler,
//  the stay / loop / prescaler counters with their match flags, the internal
//  information-holding register with implicit external-stack nesting, and the
//  external interface buses (operation, stack, insertion, indirect-read).
//
//  このモジュールは PTSG コアの*トップ層*である: 命令メモリ、命令デコーダ、
//  4 オペコード(Global/Stay/Branch/Jump)、8 個の内部制御サブオペコード、
//  Stay ウィンドウ／裏実行機構、プリスケーラ、ステイ／ループ／プリスケーラ
//  カウンタと一致フラグ、暗黙的外部スタック入れ子を伴う内部情報保持レジスタ、
//  そして外部インターフェースバス(演算／スタック／挿入／間接読み)を結びつける
//  単一の合成可能モジュールである。
//
//  Specification basis (Layer 1):
//    Chapter 1 — Scope and Design Philosophy
//    Chapter 2 — Memory Layout and Opcode Set (v1.1)
//    Chapter 3 — Sub-Opcode Architecture and Background Execution (v1.1)
//    Chapter 4 — Indirect Addressing and Prescaler (v1.0)
//    Chapter 5 — External Logic Interface (v1.0)
//
//  This is ONE possible implementation, not THE implementation. It resolves the
//  open Ties of Layer 1 according to the contributor's documented leans:
//
//    C5-V1 reset polarity ......... active-high
//    C5-V2 clock edge ............. rising edge
//    C5-V3 reset .................. synchronous
//    C5-V5 state_number ........... registered
//    C3-T1 timing-signal hold ..... Stay state's D16-D31 during the wait (lean A);
//                                   Stay-Set state's D16-D31 during the background band
//    C3-T2 queued op order ........ FIFO (only one queued op slot is implemented)
//    C3-T4 min-stay violation ..... Core proceeds (no stall on ext_op_ready)
//    C3-T6 stack push/pop ......... implicit (Core auto-pushes/pops, with stall)
//    C3-T7 insertion flag bit ..... Core carries the "saved-by-insertion" flag
//    C3-F20 insertion timing ...... deferred to Stay-timeup inside a Stay window
//    C4-T1 indirect handshake ..... Core stalls until indirect_ready (covers B and C)
//    C4-T2 prescaler config ....... pin-level prescaler_value with PRESCALE parameter
//                                   fallback (reference form "B'", RH029, PROVISIONAL)
//    C4-T5 stay_value sampling .... read in the execute clock (form B; RH031, PROVISIONAL)
//    C5-T2 stay_value width ....... CNT_W (12 bits; both zero = 4096 stays the maximum)
//    C4-T4 Stay Set role .......... clear/sync only — the stay counter ticks only
//                                   during the wait, so background-band length adds
//                                   no jitter to the wait duration (lean B)
//
//  Deliberate simplifications (documented; faithful to the canonical patterns):
//    * The queued band (after Prog End) implements a single queued operation slot
//      and supports the canonical queued Loop. Other internal-mode commands placed
//      after Prog End execute immediately (the dominant pattern queues one Loop).
//    * The indirect-read for a *queued* (post-Prog-End) Loop is not performed; a
//      queued Loop uses its literal D16-D31 target (0 => zero iterations, C4-V1).
//    * Base Set keeps a single-level base (it sets the base and advances). The
//      Loop body re-enters the Base Set state every iteration, so Base Set is
//      idempotent and does not spill the previous base to the external stack;
//      nested-loop base-stacking is therefore not provided here. (Branch / Call /
//      Insertion auto-save and the external stack nesting ARE implemented.)
//    * Instruction memory is modelled with single-cycle (asynchronous) read for
//      clarity. On Cyclone V this would map to a registered M10K block; the FSM
//      can be pipelined accordingly without changing the externally-visible
//      contract (the 1-clock-per-opcode Convention C2-T4).
// ============================================================================
// REVISION HISTORY(RH)
// 001 2026-06-14 22:06 Arch. Ohnaka  Add : This defines the execution of NOP as a Que command, background command, and foreground command.
// 002 2026-06-14 22:06 Arch. Ohnaka  Add : Since the stay counter may have already started counting due to StaySet,
//                                          in that case, if it's a prescaler tick, the stay counter needs to be incremented.
// 003 2026-06-14 22:06 Arch. Ohnaka  Del : The stay counter may have already started counting in StaySet, so it should not be cleared here.
// 004 2026-06-14 22:06 Arch. Ohnaka  Add : Since the stay counter may have already started counting due to StaySet, in that case,
//                                          if it's a prescaler tick, the stay counter needs to be incremented.
// 005 2026-06-15 21:07 Arch. Ohnaka  Add : When the Stay window is open, even if a global command is running,
//                                          the Stay counter needs to be incremented when the prescaler expires.
// 006 2026-06-15 21:07 Arch. Ohnaka  Add : This defines the execution of JUMP as a Que command, background command, and foreground command.
// 007 2026-06-15 21:07 Arch. Ohnaka  Add : Opcode for Foreground commands can also be queued.
// 008 2026-06-15 21:07 Arch. Ohnaka  Add : When queuing the JUMP command
// 009 2026-07-07       Claude Code   Mod : Loop operand/counter width is 16 bits (full D16-D31 extended
//                                          operand, architect ruling 2026-07-07). loop_cnt / hr_loop /
//                                          queued_target / loop_counter output / STACK_W widened via LOOP_W.
// 010 2026-07-07       Claude Code   Mod : Que/BG NOP (and reserved 8-255) advance with state_num+1; band is
//                                          judged by in_queued_band (architect ruling 2026-07-07). The former
//                                          prog_end_seen -> S_WAIT transition is removed. Band-template kept.
// 011 2026-07-07       Claude Code   Mod : A4 conformance — the in-window stay-counter tick increment is
//                                          hoisted to a single rule outside the opcode case (covers BG
//                                          Branch/Jump and S_IND/S_PUSH/S_POP, which RH004/005 missed).
// 012 2026-07-07       Claude Code   Mod : Branch band-templated (§3.4b): FG decides on the prescaler tick
//                                          (C4-F8) and drives tsig; BG/Q hold tsig and decide at full clock.
//                                          Q reservation (evaluate-at-timeup) deferred to Phase 3.
// 013 2026-07-07       Claude Code   Mod : Insertion — the C3-F20 deferral is enforced (no acceptance inside
//                                          an open window; the S_WAIT timeup path honours the held request),
//                                          and an occupied holding register spills to the external stack
//                                          (implicit push, C3-T6 lean A) via save_or_set(is_insert), making
//                                          the pend_is_insert path live.
// 014 2026-07-08       Claude Code   Mod : Reset (SUB_RESET) is band-templated per C3-F22 (PROVISIONAL):
//                                          FG/BG fire immediately (no tick-gate) and now drive their own
//                                          tsig field instead of clearing to 0 (C7); Q defers to the
//                                          existing single-slot queue, firing at Stay-timeup with its own
//                                          captured tsig. This surfaced (and fixes) a latent queue-field
//                                          aliasing gap: queued_subop's reset/default value (0) equals
//                                          SUB_RESET's own encoding, and queued_opcode was never reset
//                                          (X in simulation) and was left untouched by the Loop Q-branch —
//                                          so a queued Jump could misfire as a queued Reset, and (pre-
//                                          existing, now also fixed) a queued Loop that exits could alias
//                                          a stale queued_opcode==OP_JUMP from an earlier window. Every
//                                          Q-branch (Loop/Jump/Reset) now sets both queued_subop AND
//                                          queued_opcode explicitly, and all three consumers (resume_addr,
//                                          the S_WAIT Loop-update, the S_WAIT Reset-firing) check both.
// 015 2026-07-08       Claude Code   Mod : Architect ruling — a queued Reset must not share the Loop/Jump
//                                          slot: it is now an independent parallel reservation
//                                          (pending_reset/pending_reset_tsig), checked with ABSOLUTE
//                                          PRIORITY at Stay-timeup (discards any queued Loop/Jump and any
//                                          deferred insertion). Firing is fully destructive — mirrors the
//                                          hardware rst block for every execution-context register, except
//                                          presc_cnt (C3-F21, never touched) and timing_signals (drives the
//                                          captured own-tsig, C7, not zero). Replaces RH014's queued_tsig.
// 016 2026-07-08       Claude Code   Fix : Indirect Jump (operand 0) band bug, found while investigating an
//                                          architect concern. need_ind_jump lacked need_ind_loop's existing
//                                          !in_queued_band exclusion: a Q-band Jump(0) hijacked the FSM into
//                                          S_IND the instant it was scanned, resolving and jumping mid-scan
//                                          instead of queuing and firing at Stay-timeup. Fixed by excluding
//                                          the Q band (queued Jump(0) now falls through to the ordinary
//                                          in_queued_band branch and is queued as literal 0, matching the
//                                          existing queued-Loop-indirect simplification, C4-V1). Also found:
//                                          a foreground indirect Jump completed on an arbitrary system clock
//                                          instead of a presc_tick boundary, unlike every other FG command
//                                          (C4-F8) — breaking the structural phase-lock invariant (C4-F9)
//                                          for any program using an FG indirect Jump; and it never drove its
//                                          own tsig field, unlike literal FG Jump. Fixed via ind_in_window
//                                          (captured at request time) splitting S_IND's completion: BG
//                                          remains immediate; FG latches the result (ind_resolved/ind_target)
//                                          and commits state_num on the next presc_tick, with tsig driven at
//                                          the S_RUN->S_IND transition (holds through the stall unchanged,
//                                          since state_num — and so the tsig wire — does not move until
//                                          resolution).
// 017 2026-07-08       Claude Code   Mod : Phase 3a — the Q-band shared reservation slot is generalized to
//                                          Branch (§3.4b Branch Q row), replacing the "behaves like BG"
//                                          placeholder. Scan time captures queued_save_state (Branch's own
//                                          address) and queued_target (taken-target); Condition is evaluated
//                                          live at Stay-timeup. Not-taken and the operand-0 self-loop idiom
//                                          (no auto-save, C2-F5) fold into resume_addr; the real taken case
//                                          needs an explicit save_or_set (possibly an S_PUSH stall).
// 018 2026-07-08       Claude Code   Mod : Phase 3b — Call is added to the same Q-band reservation slot.
//                                          Unconditional (no Condition to evaluate, unlike Branch): fires as
//                                          a plain save_or_set from the captured own-address/target the
//                                          moment the reservation is checked at Stay-timeup.
// 019 2026-07-08       Claude Code   Mod : Phase 3c — Return is added to the same Q-band reservation slot.
//                                          Needs no extra scan-time capture (hr_state/hr_loop/hr_base/hr_ins/
//                                          stack_depth are live registers, read at firing); fires by restoring
//                                          them at Stay-timeup, including the S_POP fallback for a deeper
//                                          stacked context.
// 020 2026-07-08       Claude Code   Add : Phase 4a/4b — new S_HALT FSM state, error_flag output port, and
//                                          the halt task (C3-F24 runaway-error trap; state_num holds at the
//                                          violating instruction, escape via hardware reset or an insertion
//                                          that auto-saves the halted address). First traps wired in: Base
//                                          Set/Return/Call/Loop's foreground case now HALTs instead of
//                                          silently running (C3-F23 FG-Global exclusion principle) — closes
//                                          the "documented deviation" gaps Phase 3 left open. need_ind_loop
//                                          gained a window_open term so an FG indirect-target Loop reaches
//                                          the same HALT trap instead of resolving via S_IND first.
// 021 2026-07-08       Claude Code   Add : Phase 4c — Prog End gains two HALT traps (C3-F24): a stray/
//                                          duplicate Prog End scanned while already in the Q band
//                                          (in_queued_band) HALTs, and FG Prog End (previously a silent
//                                          "blank shot" no-op) now HALTs too (C3-F23, window-only). BG
//                                          (first shot, opens the Q band) keeps its existing behavior.
// 022 2026-07-08       Claude Code   Fix : S_HALT's insertion-rescue path never returned the FSM to
//                                          S_RUN (save_or_set only sets fsm on its S_PUSH branch; its
//                                          other call sites are already S_RUN, so the "leave fsm alone"
//                                          default silently meant "stay" there but meant "stay stuck in
//                                          S_HALT forever" here) — found while adding the first test that
//                                          actually exercises an S_HALT rescue (T22/T23 below had none
//                                          before). Now sets fsm <= S_RUN explicitly (overridden by
//                                          save_or_set's own S_PUSH assignment when hr_occupied).
// 023 2026-07-08       Claude Code   Mod : Phase 4d — closes the C3-F26/C8 TODO Phase 3c/3d left open:
//                                          each of the five Q-band SN-reservation sites (Loop, Jump,
//                                          Branch, Call, Return) now HALTs (C3-F24) instead of silently
//                                          overwriting when queued_valid is already 1, i.e. a second SN
//                                          reservation is scanned in the same Q band before the first
//                                          ever fires. "Last-write-wins" is what the FIRST (0->1)
//                                          reservation in a fresh window's Q band describes, not a
//                                          license to clobber a pending one. Reset is unaffected (it
//                                          never touches queued_valid at scan time; its own independent
//                                          track always wins at Stay-timeup). T21's old last-write-wins
//                                          scenario is superseded by this HALT (it was Phase 3d's own
//                                          documented placeholder for exactly this gap).
// 024 2026-07-08       Claude Code   Add : Phase 4e (BG side only, C3-F24) — a new base_pending tracker
//                                          is set by a BG Base Set and cleared by a BG Loop's successful
//                                          exit; if a BG Prog End (the first-shot band-crossing point) is
//                                          reached while base_pending is still 1, the Base Set was never
//                                          paired with an exiting Loop -> HALT. Cleared by Stay Set (fresh
//                                          window) and by Reset (panic-clears the whole loop scaffold, all
//                                          three bands). The Q-band half of C3-F24's pairing rule (a queued
//                                          Base Set whose Loop lies in the BG window) is deferred to Phase
//                                          5, since Base Set's Q semantics (C3-F25, Stay Start State) are
//                                          not yet implemented.
// 025 2026-07-08       Claude Code   Add : Phase 5 (C3-F25, PROVISIONAL) — new stay_start_state register:
//                                          a FOREGROUND Stay Set (window_open reads 0) writes its own
//                                          address here; BG/Q Stay Set (re-arming an already-open window)
//                                          do not. Base Set is genuinely band-split for the first time: Q
//                                          now loads Base := Stay Start State (the time-axis origin)
//                                          instead of the old "behaves like BG" placeholder, so a
//                                          non-exiting queued Loop's jump-back restarts the WHOLE window
//                                          (the self-loop pattern the spec's worked illustration
//                                          describes) rather than resuming a scan position. Closes the
//                                          Q-band half of C3-F24's Base Set<->Loop pairing rule Phase 4e
//                                          deferred: a new q_base_pending tracker (set by a Q Base Set,
//                                          cleared the moment a Q Loop is reserved — paired either way,
//                                          whether that Loop exits this lap or loops back for another)
//                                          HALTs at Stay-timeup if still 1 (checked after pending_reset,
//                                          which still wins unconditionally).
// 026 2026-07-08       Claude Code   Mod : Phase 6 (C4-F10/§3.4b, PROVISIONAL) — Stay Set is genuinely
//                                          band-split for the first time (previously one unconditional
//                                          body for every band). FG unchanged (drives tsig, resets the
//                                          stay counter, immediate). BG now holds timing_signals (was
//                                          incorrectly driving tsig) and is tick-gated (was advancing
//                                          immediately) while still resetting the stay counter. Q now
//                                          holds timing_signals and does NOT reset the stay counter (was
//                                          incorrectly resetting it) while still advancing immediately.
//                                          window_open/prog_end_seen/queued_valid/base_pending/
//                                          q_base_pending re-arm identically in all three bands, matching
//                                          pre-Phase-6 behavior (the table is silent on this point).
// 027 2026-07-08       Claude Code   Fix : Retrospective audit of the whole 7-phase pass. RH026's Q/BG
//                                          Stay Set branches over-implemented the §3.4b table: a Q Stay
//                                          Set cleared prog_end_seen (flipping the rest of the Q scan
//                                          back into BG mid-band) and queued_valid (silently DISCARDING a
//                                          pending SN reservation — contradicting the very C8 discipline
//                                          Phase 4d added) and q_base_pending (erasing the unpaired-Base-
//                                          Set evidence T29 exists to catch). The table's Q/BG Notes
//                                          cells are empty and the CHANGES handoff (C4) marks Q Stay Set
//                                          firing semantics as still-to-be-defined, so: Q is now a pure
//                                          pass-through (advance only), BG re-kick touches only what its
//                                          cells state (stay counter reset + tick-gated advance), and the
//                                          full fresh-window re-arm belongs to FG alone. New conformance
//                                          items: T32 (scaled 2^28 self-loop timing, the CHANGES C6
//                                          recommendation — 4 laps x Stay-8, jitter-free 40-clock spacing)
//                                          and T33 (S_HALT insertion rescue with an occupied holding
//                                          register — exercises the rescue's S_PUSH spill path, which
//                                          T23 did not cover).
// 028 2026-07-08       Claude Code   Fix : PRESCALE=1 coincident-tick discipline (architect findings
//                                          2026-07-08). At PRESCALE=1 every clock is a tick, so Stay Set
//                                          and Stay always land ON a tick; three coordinated fixes keep
//                                          the written Stay count exact there (and de-risk any prescale):
//                                          (1) FG Stay Set: a coincident tick COUNTS — increment takes
//                                          priority over the arm-clear (architect's proposed form
//                                          verbatim); FG Stay Set consumes no tick, so the coincident
//                                          tick is the new count's tick #1. BG re-kick unchanged: its
//                                          gating tick is consumed by the Stay Set itself. (2) OP_STAY:
//                                          the execute-clock coincident tick counts in the bare
//                                          (windowless) case too (in-window was already covered by the
//                                          RH011 hoisted rule), and a bare Stay whose deadline IS that
//                                          coincident tick times up same-clock — bare Stay-1 @PRESCALE=1
//                                          = exactly one clock, like FG NOP. (3) S_WAIT deadline test
//                                          == -> >=: a deadline that passed during the arm/scan pipeline
//                                          fires on the first S_WAIT tick (earliest realizable) instead
//                                          of silently running away through a 2^13-count wrap. Measured
//                                          before/after: windowed Stay-1@P=1 runaway -> 3-clock resume;
//                                          bare Stay-2/Stay-1 loops 5/4 -> exact 4/3 clocks; idiom-D
//                                          duty @P=1 6:6 -> written 5:5; over-constrained window @P=5
//                                          runaway -> earliest-tick resume. T1-T33 unaffected.
// 029 2026-07-16       Arch. Ohnaka  Add : Externally settable prescaler (C4-T2, reference form "B'": pin-level
//                                          value with parameter fallback, PROVISIONAL). New ports prescaler_value
//                                          (tri0 input; 0/unconnected => PRESCALE parameter, i.e. option-A
//                                          behaviour at zero cost) and prescaler_output (reserved, see note).
//                                          presc_valueM registers (prescaler_value - 1) so the "-1" is off the
//                                          compare path; presc_tickP compares presc_cnt against presc_valueM
//                                          (or PRESCALE-1 at zero). Premise (architect, 2026-08-27): the
//                                          prescaler counter value is not for external use; the prescaler is a
//                                          base-frequency generator only. Trace: 2026-08-27_ptsg-free-running-
//                                          fruits (closes 2026-06-23 reset-command-bands Hook E).
// 030 2026-07-16       Arch. Ohnaka  Mod : One-clock registered tick (Fmax) + raw-tick export (sync).
//                                          presc_tick <= presc_tickP: the internal tick is now a registered
//                                          one-clock pulse; every in-core consumer uses it, so the whole tick
//                                          grid shifts by exactly one clock and all intervals / C4-F9 phase-lock
//                                          / RH028 collision rules are unchanged (silicon re-confirmation:
//                                          Hook A). presc_cnt rolls over on the raw presc_tickP. prescaler_match
//                                          now exports the RAW (pre-register) tick, one clock ahead of the
//                                          internal tick; consumers must register it — a slave that does so
//                                          lands coincident with this core's internal tick. Sync delivered =
//                                          period-sharing (same prescaler_value + common rst + C3-F21);
//                                          tick-following slave NOT provided (Chapter 6).
//                                          RULING (architect, 2026-08-27): presc_tickP deliberately uses ==,
//                                          NOT >=. A prescaler that runs past its terminal is a fatal fault;
//                                          a loud 2^16-wrap is preferred to a quiet small error (fail-loud).
//                                          This is the intended asymmetry with RH028's >= on the stay counter.
//                                          OPEN (architect): prescaler_value==0 test is combinational while presc_valueM is
//                                          registered (1-clk mismatch at 0<->non-0); prescaler_output is
//                                          declared but undriven; presc_tick/presc_valueM have no rst.
// 031 2026-09-27       Arch. Ohnaka  Add : Formation-supplied Stay duration (PROVISIONAL; C4-F15..F17, C5-F4).
//                                          New optional port stay_value (tri0 [CNT_W-1:0]). IND-reverse, the
//                                          RH029 pattern applied to Stay: stay_value != 0 => that value;
//                                          0/unconnected => the operand (0 => 4096, C2-F3). stay_dur is the
//                                          single substitution point, so the duration is read ONCE, at the
//                                          Stay's execute clock, and held in stay_target for the whole Stay
//                                          (a pin change mid-Stay affects later Stays only). RH028 >= applies
//                                          unchanged. Zero test and value are one sample (never a raw-pin zero
//                                          test beside a registered value: 0->N would latch 0 => 8192-tick
//                                          runaway). Requirement: WPMS packet length = Stay length.
//                                          Trace: 2026-09-26_ptsg-stay-value-from-formation.
//                                          Header Tie list: C4-T5 = form B (execute clock), C5-T2 = CNT_W.
//                                          NUMBER PROVISIONAL: applied by Claude Code on a working copy
//                                          (PTSG-WPMS-Formation 03_Sample_Implementations/hw/core/
//                                          ptsg_core_rh031p.v, SILICON_BRIEF_2026-09-27 Phase 1); the Core's
//                                          office assigns the RH number and date at its checkpoint. The
//                                          frozen RH030 source is untouched.
//
// ============================================================================

module ptsg_core #(
    // ---- Geometry -----------------------------------------------------------
    parameter integer ADDR_W      = 12,           // State-number / address width (Fixed by Core)
    parameter integer DATA_W      = 32,           // Instruction word width        (Fixed by Core)
    parameter integer TSIG_W      = 16,           // Timing-signal bus width        (Fixed by Core)
    parameter integer CNT_W       = 12,           // Stay counter width (12-bit operand D4-D15)
    parameter integer LOOP_W      = 16,           // Loop counter/target width — full D16-D31
                                                  // extended operand (architect ruling 2026-07-07;
                                                  // supersedes the 12-bit C3-V2 reading)
    parameter integer IMEM_DEPTH  = 256,          // Instruction-memory depth (<= 4096)
    // ---- Prescaler (C4-T2 form B': pin-level value, PRESCALE = fallback) -----
    parameter integer PRESCALE    = 6250,         // System-clock divider for the time axis (>=1)
    parameter integer PRESC_W     = 16,           // Prescaler counter width
    // ---- External stack data layout ----------------------------------------
    //   {ins_flag, base[11:0], loop[15:0], state[11:0]} = 1 + 12 + 16 + 12 = 41
    parameter integer STACK_W     = 1 + ADDR_W + LOOP_W + ADDR_W,
    // ---- Instruction-memory initialisation (simulation: hex; Quartus: .mif) -
    parameter         INIT_FILE     = "blinky_with_prescaler.hex",  // $readmemh file (SIM branch), or "" for none
    parameter         INIT_FILE_MIF = "",           // .mif file (M10K branch), or "" for none
    // ---- Instruction-memory vendor branch (ptsg_imem wrapper) ---------------
    //   "M10K" : Cyclone V altsyncram + ISMCE (INSTANCE_NAME=PTSG) — synthesis
    //   "SIM"  : behavioural array — simulation (iverilog etc.)
    parameter         IMEM_VENDOR   = "M10K",
    parameter         IMEM_EDGE     = "NEG"         // "NEG" = half-cycle read, FSM needs no fetch stage
) (
    // ---- Mandatory pins (Chapter 5 §5.2) ------------------------------------
    input  wire                 clk,              // System clock           (§5.3)
    input  wire                 rst,              // Synchronous, active-high (§5.3, C5-V1/V3)
    input  wire                 condition,        // 1-bit Condition input  (§5.4)
    output wire [ADDR_W-1:0]    state_number,     // Current State Number   (§5.6, registered C5-V5)
    output reg  [TSIG_W-1:0]    timing_signals,   // 16 timing signals      (§5.5)

    // ---- External-operation bus (§5.7) --------------------------------------
    output wire                 ext_op_valid,
    output wire [3:0]           ext_op_subopcode,
    output wire [7:0]           ext_op_sub_operand,
    output wire [TSIG_W-1:0]    ext_op_data,
    input  wire                 ext_op_ready,     // Captured but not stalled on (C3-T4 lean A)

    // ---- External-stack bus (§5.8) — split bidirectional bus for synthesis --
    output reg                  stack_push_req,
    output reg                  stack_pop_req,
    output wire [STACK_W-1:0]   stack_wdata,      // Core -> External (push)
    input  wire [STACK_W-1:0]   stack_rdata,      // External -> Core (pop)
    input  wire                 stack_ack,

    // ---- Insertion bus (§5.9) -----------------------------------------------
    input  wire                 insert_req,
    input  wire [ADDR_W-1:0]    insert_target,
    output reg                  insert_ack,

    // ---- Loop-counter and match flags (§5.10) -------------------------------
    output wire [LOOP_W-1:0]    loop_counter,
    output reg                  loop_cnt_match,
    output wire [CNT_W-1:0]     stay_counter,
    output reg                  stay_cnt_match,
    output wire [PRESC_W-1:0]   prescaler_counter,
    output wire                 prescaler_match,
    input  tri0 [PRESC_W-1:0]   prescaler_value             , // RH029
    output wire [PRESC_W-1:0]   prescaler_output            , // RH029

    // ---- Formation-supplied Stay duration (§5.12a, RH031 PROVISIONAL) --------
    input  tri0 [CNT_W-1:0]     stay_value                  , // RH031: 0/unconnected => Stays as written

    // ---- Indirect-read bus (§5.11) ------------------------------------------
    output wire                 indirect_req,
    output wire [1:0]           indirect_purpose, // 00 = Jump, 01 = Loop target
    input  wire [ADDR_W-1:0]    indirect_data,
    input  wire                 indirect_ready,

    // ---- Error-HALT flag (Phase 4, C3-F24) -----------------------------------
    // Registered; raised on entering S_HALT, held until hardware reset (or an
    // insertion rescues the core, see the S_HALT state below). Doubles as a
    // SignalTap trigger (the capture shows the violating scene, since
    // state_number holds at the violating instruction) and an insertion
    // trigger for automated recovery/diagnosis (C3-F24).
    output reg                  error_flag
);

    // ========================================================================
    //  Opcode / sub-opcode constants (Chapter 2)
    // ========================================================================
    localparam [3:0] OP_GLOBAL = 4'd0;
    localparam [3:0] OP_STAY   = 4'd1;
    localparam [3:0] OP_BRANCH = 4'd2;
    localparam [3:0] OP_JUMP   = 4'd3;

    localparam [7:0] SUB_RESET    = 8'd0;   // Reset
    localparam [7:0] SUB_BASESET  = 8'd1;   // Base Set
    localparam [7:0] SUB_STAYSET  = 8'd2;   // Stay Set
    localparam [7:0] SUB_RETURN   = 8'd3;   // Return
    localparam [7:0] SUB_CALL     = 8'd4;   // Sub-sequence Call
    localparam [7:0] SUB_LOOP     = 8'd5;   // Loop
    localparam [7:0] SUB_PROGEND  = 8'd6;   // Prog End (v1.1, tentative)
    localparam [7:0] SUB_NOP      = 8'd7;   // NOP

    // ========================================================================
    //  Instruction memory — vendor-abstracted wrapper (ptsg_imem, EDGE="NEG").
    //  From this posedge FSM's viewpoint the NEG half-cycle read behaves like a
    //  combinational read (effective latency 0): at every rising edge,
    //  instr == mem[state_num]. See ptsg_imem.v for the timing contract.
    //  The wrapper instance is declared below, after the fetch wires.
    // ========================================================================

    // ========================================================================
    //  Core control registers
    // ========================================================================
    reg [ADDR_W-1:0]  state_num;        // Program counter (the live State Number)
    reg [LOOP_W-1:0]  loop_cnt;         // Single primary loop counter (C3-F16), up-count
    reg [ADDR_W-1:0]  base_addr;        // Loop base address (Base Set)

    // Internal information-holding register (depth-1, C3-F10) ----------------
    reg [ADDR_W-1:0]  hr_state;
    reg [LOOP_W-1:0]  hr_loop;
    reg [ADDR_W-1:0]  hr_base;
    reg               hr_ins;           // "saved by insertion" flag (C3-T7 lean A)
    reg               hr_occupied;
    reg [15:0]        stack_depth;      // # of contexts spilled to external stack

    // Stay window / background-execution state -------------------------------
    reg               window_open;      // Set by Stay Set, cleared at Stay-timeup
    reg               prog_end_seen;    // Set by Prog End inside an open window

    // Base Set<->Loop band-pairing tracker (Phase 4e, C3-F24, BG side) -------
    // Set by a BG Base Set; cleared by a BG Loop's successful exit. If a BG
    // Prog End is reached while this is still 1, the Base Set was never
    // paired with an exiting Loop -- a runaway error, HALT. Cleared by Stay
    // Set (fresh window) and Reset.
    reg               base_pending;

    // Stay Start State register (Phase 5, C3-F25, PROVISIONAL) ---------------
    // Gives the time axis its own notion of "here": a FOREGROUND Stay Set
    // writes its own State Number here; BG/Q Stay Set (re-arming an
    // already-open window) do not touch it. Valid only within the same Stay
    // cycle -- a Q-band Base Set hands it to base_addr (Base := Stay Start
    // State, the time-axis origin, vs. BG Base Set's Base := current State
    // Number); if no Q Base Set occurs, the next Stay Set simply overwrites
    // it. Reset 0; no Core-level external visibility (a Formation may copy
    // it out via a general register).
    reg [ADDR_W-1:0]  stay_start_state;

    // Q-band Base Set<->Loop band-pairing tracker (Phase 5, C3-F24 Q half) ---
    // Set by a Q Base Set; cleared the moment a Q Loop is RESERVED (scan
    // time, not fire time) -- once a Loop reservation exists, the Base Set
    // is paired, whether that Loop exits this lap or jumps back to
    // Base (= Stay Start State) for another one (the self-loop pattern,
    // C3-F25 -- not a violation either way). If Stay-timeup arrives with
    // this still 1, no Q Loop was ever reserved to consume it -- HALT (the
    // Q-side mirror of base_pending above; this is the "queued Base Set
    // whose Loop lies in the BG window" cell Phase 4e deferred, read here
    // as "the Q Base Set has nothing queued to pair with it").
    reg               q_base_pending;

    // Single queued-operation slot (queued band, C3-T2 FIFO depth-1) ---------
    // RH015: Reset does NOT use this slot. Per architect ruling (2026-07-08),
    // a queued Reset must not be "just another" queued op competing with
    // Loop/Jump for the one shared slot — it is reserved on a wholly separate
    // track (pending_reset below) and takes unconditional priority over
    // whatever this slot holds at Stay-timeup.
    //
    // C3-F26 / C8: every internal sub-opcode with Q-band semantics (Loop,
    // Jump, Branch, Call, Return) shares this one slot. Because queued_valid
    // is set to 1 by exactly these five reservation sites and by nothing
    // else while a window is open, "queued_valid already 1" IS "an SN-class
    // reservation is already pending" — so each of the five now guards its
    // own write: if queued_valid is already 1, a second SN reservation in
    // the same Q band is a runaway error, HALT + error flag (C3-F24), not a
    // silent replace (Phase 4d, RH023, closes the TODO Phase 3c/3d left
    // here). The FIRST reservation in a fresh window's Q band always
    // succeeds (queued_valid starts at 0, cleared by Stay Set) — that
    // initial 0->1 write is what "last-write-wins" actually describes now:
    // there is nothing earlier to overwrite yet. Reset does NOT participate
    // in any of this — it never touches queued_valid at scan time; its own
    // track always wins at Stay-timeup regardless of what this slot holds.
    // Related open question the spec itself leaves Tied: Tie C3-T15 (nested
    // multi-booking — two Base Sets and two Loops in one window).
    reg               queued_valid;
    reg [7:0]         queued_subop;
    reg [3:0]         queued_opcode;    // Add: Opcode for Foreground commands can also be queued. - RH 007 Arch. Ohnaka (2026-06-15 21:07)
    reg [LOOP_W-1:0]  queued_target;
    reg [ADDR_W-1:0]  queued_save_state; // RH017: Branch/Call's own address at Q-scan time,
                                         // for the return-to-after auto-save (C3-F12) at firing

    // Queued (Q-band) Reset — independent, parallel reservation (RH015).
    // Set by SUB_RESET's Q-branch; consumed with absolute priority at
    // Stay-timeup, discarding whatever the shared slot above holds.
    reg               pending_reset;
    reg [TSIG_W-1:0]  pending_reset_tsig;   // own D16-D31, captured at Q-scan time,
                                            // driven at Stay-timeup firing (C7)

    // Stay-counter (13-bit internal: 0..4096) --------------------------------
    reg [CNT_W:0]     stay_cnt;
    reg [CNT_W:0]     stay_target;

    // Prescaler (free-running) -----------------------------------------------
    reg [PRESC_W-1:0] presc_cnt;
    reg [PRESC_W-1:0] presc_valueM;
    wire              presc_tickP = (presc_cnt == ((prescaler_value == 0) ? (PRESCALE-1) : presc_valueM));  //RH029: prescaler_value override (C4-T2 form B', PROVISIONAL); raw tick
    reg               presc_tick;  // RH030: registered one-clock pulse, one clk after presc_tickP; the only tick the FSM uses

    // Indirect-read latch ----------------------------------------------------
    reg               ind_is_loop;      // 0 = indirect Jump, 1 = indirect Loop target
    // RH016: which band requested an indirect Jump, captured at request time
    // (need_ind_jump excludes the Q band entirely, so this can only be FG or
    // BG). BG completes immediately on indirect_ready (matches literal BG
    // Jump); FG must additionally wait for a presc_tick before committing the
    // state transition (C4-F8 parity with literal FG Jump — otherwise an FG
    // indirect Jump could complete off the tick grid and break the
    // structural phase-lock invariant, C4-F9). ind_resolved/ind_target latch
    // the read result while FG waits out that extra tick.
    reg               ind_in_window;
    reg               ind_resolved;
    reg [ADDR_W-1:0]  ind_target;

    // FSM --------------------------------------------------------------------
    localparam [2:0] S_RUN  = 3'd0,
                     S_WAIT = 3'd1,
                     S_IND  = 3'd2,
                     S_PUSH = 3'd3,
                     S_POP  = 3'd4,
                     S_HALT = 3'd5;   // Phase 4, C3-F24: runaway-error trap
    reg [2:0] fsm;

    // Pending context for a stalled (PUSH) auto-save -------------------------
    reg [ADDR_W-1:0]  pend_state;       // return address to store
    reg [LOOP_W-1:0]  pend_loop;
    reg [ADDR_W-1:0]  pend_base;
    reg               pend_ins;
    reg [ADDR_W-1:0]  pend_target;      // where to jump once the save completes
    reg               pend_is_insert;   // pulse insert_ack on completion

    // ========================================================================
    //  Instruction fetch and field decode (Chapter 2 §2.2)
    //  ptsg_imem EDGE="NEG": effectively combinational for this posedge FSM.
    // ========================================================================
    wire [DATA_W-1:0]	instr;
    ptsg_imem #(
    	.ADDR_W        (ADDR_W),
    	.DATA_W        (DATA_W),
    	.DEPTH         (IMEM_DEPTH),
    	.RD_LAT        (1),
    	.EDGE          (IMEM_EDGE),
    	.VENDOR        (IMEM_VENDOR),
    	.INIT_FILE_HEX (INIT_FILE),
    	.INIT_FILE_MIF (INIT_FILE_MIF)
    ) ptsg_imem (
    	.clk	(clk),
    	.addr	(state_num),
    	.rdata	(instr)
    );

    wire [3:0]        opcode  = instr[3:0];        // D0-D3
    wire [11:0]       operand = instr[15:4];       // D4-D15
    wire [15:0]       tsig    = instr[31:16];      // D16-D31 (timing signals)
    wire [3:0]        g_mode  = instr[7:4];        // D4-D7  (Global mode / ext sub-op)
    wire [7:0]        g_subop = instr[15:8];       // D8-D15 (internal sub-op selector)
    wire [15:0]       g_ext   = instr[31:16];      // D16-D31 (extended operand / data)

    wire is_global          = (opcode == OP_GLOBAL);
    wire is_internal_global = is_global && (g_mode == 4'd0);
    wire is_external_global = is_global && (g_mode != 4'd0);

    // True while a Loop encountered here belongs to the queued band ----------
    wire in_queued_band = window_open && prog_end_seen;

    // An indirect read is required this RUN clock when:
    //   * a foreground or background Jump with operand 0, or
    //   * a foreground or background Loop whose D16-D31 target field is 0.
    // RH016: need_ind_jump now excludes the queued band (matching
    // need_ind_loop's existing pattern, which already excluded it). Before
    // this fix, a Q-band Jump(0) would hijack the FSM into S_IND the instant
    // it was scanned — bypassing the Q-band's queue-and-fire-at-Stay-timeup
    // model entirely, resolving and jumping immediately mid-scan, and never
    // going through the normal Stay-timeup window-close path at all. A
    // queued Jump's operand 0 now falls through to OP_JUMP's ordinary
    // in_queued_band branch and is queued as its literal value (jump to
    // address 0) — the same documented simplification already applied to a
    // queued Loop's indirect target (C4-V1: "queued Loop uses its literal
    // D16-D31 target").
    wire need_ind_jump = (opcode == OP_JUMP) && (operand == 12'd0) && !in_queued_band;
    // Phase 4b: gains a window_open term. Loop is FG-illegal (C3-F23) — an
    // FG indirect-target Loop (g_ext==0) must reach SUB_LOOP's case and HALT
    // there like any other FG Loop, not be intercepted here and silently
    // resolved via S_IND. (Jump has no such restriction — Jump is a
    // top-level structural opcode, not a Global sub-opcode, so it is not
    // subject to C3-F23 and need_ind_jump is unaffected.)
    wire need_ind_loop = is_internal_global && (g_subop == SUB_LOOP) &&
                         (g_ext == 16'd0) && !in_queued_band && window_open;
    wire need_indirect = (fsm == S_RUN) && !insert_pending &&
                         (need_ind_jump || need_ind_loop);

    // Honour an insertion request at the next safe moment in RUN (between
    // instructions). Inside a Stay window it is deferred to timeup (C3-F20):
    // the S_WAIT timeup path honours the (still-held) request instead.
    // RH013: the !window_open term makes the C3-F20 deferral real (the old
    // expression accepted an insertion mid-window, during the BG scan), and
    // an occupied holding register now spills to the external stack
    // (C3-T6 lean A) instead of blocking the request.
    wire insert_pending = (fsm == S_RUN) && insert_req && !window_open;

    // ========================================================================
    //  Combinational external-bus outputs
    // ========================================================================
    // state_num is itself the State Number register; presenting it directly keeps
    // the output in step with the executing state (C5-V5) with no extra latency.
    assign state_number       = state_num;
    assign ext_op_valid       = (fsm == S_RUN) && is_external_global && !insert_pending;
    assign ext_op_subopcode   = g_mode;
    assign ext_op_sub_operand  = g_subop;
    assign ext_op_data        = g_ext;

    assign indirect_req       = need_indirect;
    assign indirect_purpose   = need_ind_jump ? 2'b00 : 2'b01;

    assign stack_wdata        = {hr_ins, hr_base, hr_loop, hr_state};

    assign loop_counter       = loop_cnt;
    assign stay_counter       = stay_cnt[CNT_W-1:0];
    assign prescaler_counter  = presc_cnt;
    assign prescaler_match    = presc_tickP;    // RH030: RAW tick export (1 clk ahead of presc_tick; consumer registers)

    // ========================================================================
    //  Resolved Stay duration: literal-zero-as-escape => 4096 (C2-F3)
    //  RH031 (PROVISIONAL): IND-reverse, the RH029 pattern applied to Stay (C4-F15):
    //    stay_value != 0 => stay_value ; else operand ; operand 0 => 4096 (C2-F3).
    //    Read in the execute clock (C4-T5 form B) and latched by OP_STAY into
    //    stay_target (C4-F16). The zero test and the value are ONE sample (C5-F4).
    // ========================================================================
    wire [CNT_W:0] stay_dur_lit = (operand == 12'd0) ? (1'b1 << CNT_W) : {1'b0, operand};
    wire [CNT_W:0] stay_dur     = (stay_value != {CNT_W{1'b0}}) ? {1'b0, stay_value} : stay_dur_lit;

    // Loop "increment-then-compare" helper (combinational) -------------------
    //   target == 0           -> exit immediately, 0 iterations (C4-V1)
    //   loop_cnt+1 >= target  -> exit, auto-clear, emit match (C3-F17/F18)
    //   else                  -> continue, jump to base_addr
    function automatic [0:0] loop_exits;
        input [LOOP_W-1:0] cur;
        input [LOOP_W-1:0] target;
        begin
            loop_exits = (target == 0) || ((cur + 1'b1) >= target);
        end
    endfunction

    // ========================================================================
    //  Main synchronous process
    // ========================================================================
    integer i;
    // Post-Stay resume address at timeup. Combinational (driven from the live
    // registers) so it has no extra clock of latency: a queued Loop that has not
    // yet reached its target redirects the resume to the base address, otherwise
    // execution advances past the Stay state.
    // RH014: both branches now also check the companion field (queued_opcode
    // for Loop, queued_subop for Jump) — every Q-branch sets both fields
    // explicitly (Loop/Reset: queued_opcode<=OP_GLOBAL; Jump: queued_subop<=
    // SUB_NOP), so a queued Loop that exits can no longer alias a stale
    // queued_opcode==OP_JUMP left over from an earlier window, and vice versa.
    // RH017: two Branch cases are folded in here (not-taken; taken-but-
    // operand-was-0 self-loop, C2-F5, no auto-save) since both are plain
    // address resolutions. The real taken-with-auto-save case is NOT here —
    // it needs a register write (hr_state etc., possibly an S_PUSH stall) and
    // is handled by an explicit save_or_set call in the sequential block
    // below, which never reads this wire in that case.
    wire [ADDR_W-1:0] resume_addr =
        (queued_valid && (queued_subop == SUB_LOOP) && (queued_opcode == OP_GLOBAL) &&
         !loop_exits(loop_cnt, queued_target)) ? base_addr :
        // =============================================================================//
        // REVISION HISTORY  008                                                        //
        // 2026-06-15 21:07 Arch. Ohnaka  Add : When queuing the JUMP command           //
        // =============================================================================//
        (queued_valid && (queued_opcode == OP_JUMP)) ? queued_target :                  //
        // =============================================================================//
        (queued_valid && (queued_opcode == OP_BRANCH) && condition) ?
            (queued_save_state + 1'b1) :
        (queued_valid && (queued_opcode == OP_BRANCH) &&
         (queued_target[ADDR_W-1:0] == queued_save_state)) ? queued_save_state :
        (state_num + 1'b1);

    always @(posedge clk) begin
        // RH030: registered one-clock tick, one clk after presc_tickP
        presc_tick   <= presc_tickP;
        // RH029: pre-decremented compare value, registered off the compare path
        presc_valueM <= prescaler_value - 1;
    end

    always @(posedge clk) begin
        if (rst) begin
            // -------- Synchronous reset (C5-V3); also the Reset sub-op target -
            state_num       <= {ADDR_W{1'b0}};
            timing_signals  <= {TSIG_W{1'b0}};
            loop_cnt        <= {LOOP_W{1'b0}};
            base_addr       <= {ADDR_W{1'b0}};
            hr_state        <= {ADDR_W{1'b0}};
            hr_loop         <= {LOOP_W{1'b0}};
            hr_base         <= {ADDR_W{1'b0}};
            hr_ins          <= 1'b0;
            hr_occupied     <= 1'b0;
            stack_depth     <= 16'd0;
            window_open     <= 1'b0;
            prog_end_seen   <= 1'b0;
            base_pending    <= 1'b0;
            stay_start_state <= {ADDR_W{1'b0}};
            q_base_pending  <= 1'b0;
            queued_valid    <= 1'b0;
            queued_subop    <= 8'd0;
            queued_opcode   <= OP_GLOBAL;  // RH014 hygiene: was never reset (X in sim);
                                            // harmless in silicon (FFs power up 0 = OP_GLOBAL,
                                            // never matching OP_JUMP) but a genuine simulation
                                            // gap — see resume_addr's queued_opcode==OP_JUMP arm.
            queued_target   <= {LOOP_W{1'b0}};
            queued_save_state <= {ADDR_W{1'b0}};
            pending_reset   <= 1'b0;
            pending_reset_tsig <= {TSIG_W{1'b0}};
            stay_cnt        <= {(CNT_W+1){1'b0}};
            stay_target     <= {(CNT_W+1){1'b0}};
            presc_cnt       <= {PRESC_W{1'b0}};
            ind_is_loop     <= 1'b0;
            ind_in_window   <= 1'b0;
            ind_resolved    <= 1'b0;
            ind_target      <= {ADDR_W{1'b0}};
            fsm             <= S_RUN;
            stack_push_req  <= 1'b0;
            stack_pop_req   <= 1'b0;
            insert_ack      <= 1'b0;
            loop_cnt_match  <= 1'b0;
            stay_cnt_match  <= 1'b0;
            pend_is_insert  <= 1'b0;
            error_flag      <= 1'b0;
        end else begin
            // -------- Default (one-clock) pulse de-assertions ----------------
            stack_push_req <= 1'b0;
            stack_pop_req  <= 1'b0;
            insert_ack     <= 1'b0;
            loop_cnt_match <= 1'b0;
            stay_cnt_match <= 1'b0;

            // Free-running prescaler ----------------------------------------
            presc_cnt <= presc_tickP ? {PRESC_W{1'b0}} : (presc_cnt + 1'b1);        // RH030 

            // =============================================================================//
            // REVISION HISTORY 011 (A4 hoist)                                              //
            // 2026-07-07 Claude Code  Mod : While the Stay window is open, the stay        //
            //      counter counts EVERY prescaler tick regardless of which in-window       //
            //      path is executing (C4-F10 On-Tick; Ch3 §3.2 / §3.4b "Continue counting  //
            //      ... when On-Tick") — including BG Branch/Jump and the S_IND/S_PUSH/     //
            //      S_POP stalls, which the per-path RH004/RH005 increments missed. This    //
            //      single rule replaces them. S_WAIT keeps its own count/timeup handling   //
            //      (it must also serve the windowless bare-Stay case), and later explicit  //
            //      assignments in the case below (Stay Set arm, timeup clear) override     //
            //      this default increment, which also removes the RH005-overwrites-arm    //
            //      ordering hazard.                                                        //
            // =============================================================================//
            if (window_open && presc_tick && (fsm != S_WAIT))                               //
                stay_cnt <= stay_cnt + 1'b1;                                                //
            // =============================================================================//

            case (fsm)
            // ================================================================
            //  S_RUN — fetch and execute one state per clock
            // ================================================================
            S_RUN: begin
                if (insert_pending) begin
                    // ---- Honour insertion (between instructions) -----------
                    //  Save the instruction we were about to execute (no +1 on
                    //  return, C3-F12) and jump to the inserted address. An
                    //  occupied holding register spills to the external stack
                    //  first (implicit push, C3-T6 lean A) — RH013.
                    save_or_set(state_num, 1'b1, insert_target, 1'b1);
                end
                else if (need_indirect) begin
                    // ---- Begin an indirect read; stall in S_IND ------------
                    // RH016: capture which band requested this (need_ind_jump/
                    // need_ind_loop already exclude the Q band, so this is FG
                    // or BG). An FG indirect Jump drives its own tsig field
                    // immediately here, matching literal FG Jump — the value
                    // then holds through the S_IND stall since state_num (and
                    // so the combinational tsig wire) does not move until
                    // resolution.
                    ind_is_loop   <= need_ind_loop;
                    ind_in_window <= window_open;
                    ind_resolved  <= 1'b0;
                    fsm           <= S_IND;
                    if (need_ind_jump && !window_open) timing_signals <= tsig;
                    // state_num held; indirect_req pulsed combinationally now.
                end
                else begin
                    case (opcode)
                    // --------------------------------------------------------
                    //  Global (opcode 0)
                    // --------------------------------------------------------
                    OP_GLOBAL: begin
                        if (is_internal_global) begin
                            case (g_subop)
                            SUB_RESET: begin
                                // =============================================================================//
                                // REVISION HISTORY 014 / 015                                                   //
                                // 2026-07-08 Claude Code  Mod : Reset is band-templated per C3-F22             //
                                //      (PROVISIONAL). FG and BG both fire IMMEDIATELY (no tick-gate — the      //
                                //      §3.4b table marks Prescaler Tick "Ignored" in both rows; FG carries     //
                                //      the doctrine's Leading-edge exception, Ch1 §1.4a). Reset never touches  //
                                //      presc_cnt in any band (C3-F21 — audited: no branch below writes it).    //
                                //      BG interpretation choice (open, flagged for architect review): the     //
                                //      table only arms the stay counter for BG ("reset to 0, don't start");   //
                                //      it does not say the window closes, so window_open/prog_end_seen/       //
                                //      queued_valid are left untouched here — a BG Reset is read as a         //
                                //      panic-to-state-0 that stays inside the still-open "staff meal" window, //
                                //      not as an implicit window-close. FG needs no such statement (it is     //
                                //      already outside any window by construction).                           //
                                //      RH015 (architect ruling 2026-07-08): Q is NOT queued through the       //
                                //      shared Loop/Jump slot — it sets the independent pending_reset flag,    //
                                //      leaving queued_valid/subop/opcode/target completely untouched. At      //
                                //      Stay-timeup pending_reset is checked with absolute priority, discarding//
                                //      whatever the shared slot holds and performing a fully destructive      //
                                //      clear (Reset is initialization; C3-F21 exempts only the prescaler).    //
                                // =============================================================================//
                                if (in_queued_band) begin                    // as Que command (after Prog End) //
                                    pending_reset      <= 1'b1;   // independent reservation — RH015            //
                                    pending_reset_tsig  <= tsig;  // captured now; driven at firing (C7)        //
                                    state_num     <= state_num + 1'b1;               // scan on                //
                                end                                                                             //
                                else if (window_open) begin       // as background command (inside Stay window) //
                                    state_num      <= {ADDR_W{1'b0}};                                          //
                                    loop_cnt       <= {LOOP_W{1'b0}};                                          //
                                    base_addr      <= {ADDR_W{1'b0}};                                          //
                                    base_pending   <= 1'b0;         // panic clears the loop scaffold too       //
                                    stay_start_state <= {ADDR_W{1'b0}};                                        //
                                    q_base_pending <= 1'b0;                                                    //
                                    hr_occupied    <= 1'b0;                                                    //
                                    stack_depth    <= 16'd0;                                                   //
                                    stay_cnt       <= {(CNT_W+1){1'b0}};       // arm to 0, don't start (§3.4b) //
                                    timing_signals <= tsig;               // own field, not cleared (C7)       //
                                end                                                                             //
                                else begin                       // as foreground command (outside Stay window) //
                                    state_num      <= {ADDR_W{1'b0}};                                          //
                                    loop_cnt       <= {LOOP_W{1'b0}};                                          //
                                    base_addr      <= {ADDR_W{1'b0}};                                          //
                                    base_pending   <= 1'b0;                                                    //
                                    stay_start_state <= {ADDR_W{1'b0}};                                        //
                                    q_base_pending <= 1'b0;                                                    //
                                    hr_occupied    <= 1'b0;                                                    //
                                    stack_depth    <= 16'd0;                                                   //
                                    timing_signals <= tsig;               // own field, not cleared (C7)       //
                                end                                                                             //
                                // =============================================================================//
                            end
                            SUB_BASESET: begin
                                // =============================================================================//
                                // REVISION HISTORY 025 (Phase 5)                                               //
                                // 2026-07-08 Claude Code  Mod : Base Set is now genuinely band-split per        //
                                //      §3.4b/C3-F25 (PROVISIONAL): BG keeps Base := current State Number       //
                                //      (space-axis; must be paired by a BG Loop exit before Prog End, or        //
                                //      HALT, C3-F24/Phase 4e). Q now loads Base := Stay Start State (the        //
                                //      time-axis origin captured by the window's own FG Stay Set) instead of    //
                                //      the old "behaves like BG" placeholder -- this is what makes a queued      //
                                //      Loop's non-exit jump restart the WHOLE window (the self-loop pattern,    //
                                //      C3-F25's worked illustration) rather than just a scan position. FG       //
                                //      remains §3.4b-illegal (C3-F23) -> HALT (C3-F24), unchanged.              //
                                // =============================================================================//
                                if (in_queued_band) begin                    // as Que command (after Prog End) //
                                    base_addr      <= stay_start_state;                                         //
                                    q_base_pending <= 1'b1;    // Phase 5: must be paired by a queued Loop      //
                                                                // reservation before Stay-timeup, or HALT.      //
                                    state_num      <= state_num + 1'b1;                                         //
                                end                                                                             //
                                else if (window_open) begin       // as background command (inside Stay window) //
                                    // Mark the current address as the Loop base and
                                    // advance. The base address is where Loop jumps
                                    // back to, so a loop re-enters this state every
                                    // iteration; Base Set is therefore idempotent and
                                    // must NOT auto-save (that would push a context per
                                    // iteration). This reference keeps a single-level
                                    // base — nested-loop base-stacking (spilling the
                                    // previous base to the external stack) is omitted.
                                    base_addr    <= state_num;
                                    base_pending <= 1'b1;   // Phase 4e: must be paired by a Loop exit
                                                             // before the next BG Prog End, or HALT.
                                    state_num    <= state_num + 1'b1;
                                end
                                else begin      // as foreground command -> FG-illegal (C3-F23), runaway error //
                                    halt;                                                                       //
                                end                                                                             //
                                // =============================================================================//
                            end
                            SUB_STAYSET: begin
                                // =============================================================================//
                                // REVISION HISTORY 026 (Phase 6, C4-F10/§3.4b, PROVISIONAL)                   //
                                // 2026-07-08 Claude Code  Mod : Stay Set is genuinely band-split for the       //
                                //      first time (previously one unconditional body for every band). Per the //
                                //      §3.4b table: FG "re-kicks" fresh -- drives its own tsig, resets the     //
                                //      stay counter, advances immediately (Leading-edge exception), and        //
                                //      writes Stay Start State (Phase 5, C3-F25). BG "re-kicks" an             //
                                //      already-open window -- HOLDS timing_signals (does not drive tsig),      //
                                //      resets the stay counter same as FG, but is now tick-gated (waits for    //
                                //      the next prescaler tick before advancing, like FG Branch/Jump/Reset).   //
                                //      Q -- HOLDS timing_signals, does NOT reset the stay counter (it simply   //
                                //      continues On-Tick, uninterrupted), and advances immediately (full       //
                                //      system clock, not tick-gated).                                          //
                                //      (RH026's original note claimed the window/queue/pairing registers        //
                                //      re-arm identically in all three bands; superseded by RH027 below.)      //
                                // =============================================================================//
                                // RH027 (retrospective audit): the Q and BG branches are pared back to        //
                                // exactly what the §3.4b table's cells state, no more. The first Phase-6      //
                                // cut re-armed window_open/prog_end_seen/queued_valid/base_pending/           //
                                // q_base_pending in all three bands; on review that over-implements the       //
                                // table (its Q/BG Notes cells are empty) and, worse, a Q Stay Set clearing    //
                                // queued_valid would silently DISCARD a pending SN reservation (contradicting //
                                // the C8 discipline where such a discard is a HALT-worthy event) and clearing //
                                // q_base_pending would erase the unpaired-Q-Base-Set evidence T29 exists to   //
                                // catch. The CHANGES handoff (item C4) says a Q Stay Set is "registered       //
                                // during the scan (semantics of its firing to be exercised in verification)"  //
                                // — i.e. its firing semantics are genuinely UNDECIDED at the spec level — so  //
                                // Q is now a minimal pass-through, awaiting the architect's definition.       //
                                // A BG re-kick likewise leaves window/queue/pairing state untouched: the      //
                                // window is already open, queued_valid is structurally 0 in BG, and a         //
                                // dangling BG Base Set's pairing obligation persists across a re-kick         //
                                // (base_addr is undisturbed, so a later BG Loop still pairs with it).         //
                                if (in_queued_band) begin        // Q: pass-through — counter NOT reset, tsig  //
                                    state_num      <= state_num + 1'b1;   // held, no window/queue side effects //
                                end                                                                             //
                                else if (window_open) begin       // BG: re-kick — counter reset, tick-gated    //
                                    if (presc_tick) begin                                                       //
                                        stay_cnt   <= {(CNT_W+1){1'b0}};                                        //
                                        state_num  <= state_num + 1'b1;                                         //
                                    end                                                                         //
                                    // timing_signals intentionally untouched (BG: Held); no advance until      //
                                    // the next prescaler tick (BG: "Consumes one tick, waits for next")        //
                                end                                                                             //
                                else begin                        // FG: fresh window, immediate, drives tsig  //
                                    stay_start_state <= state_num;   // C3-F25 (Phase 5): fresh window only     //
                                    window_open      <= 1'b1;                                                   //
                                    prog_end_seen    <= 1'b0;                                                   //
                                    queued_valid     <= 1'b0;                                                   //
                                    base_pending     <= 1'b0;                                                   //
                                    q_base_pending   <= 1'b0;                                                   //
                                    // RH028 (architect, 2026-07-08): a tick coincident with the FG Stay Set    //
                                    // (guaranteed at PRESCALE=1; possible off-grid after FG Reset) must COUNT  //
                                    // — the increment takes priority over the arm-clear, else that tick is    //
                                    // lost and the written Stay count is violated (measured: idiom-D duty at  //
                                    // PRESCALE=1 read 6:6 for a written 5:5). FG Stay Set does not consume a  //
                                    // tick (§3.4b Prescaler Tick "Ignored", Leading-edge exception), so a     //
                                    // coincident tick belongs to the NEW count, as tick #1. Contrast the BG   //
                                    // re-kick above: it "Consumes one tick", i.e. its gating tick is spent on //
                                    // the Stay Set itself and correctly does NOT count into the new count.    //
                                    if (presc_tick) stay_cnt <= stay_cnt + 1'b1;                                //
                                    else            stay_cnt <= {(CNT_W+1){1'b0}};                              //
                                    timing_signals   <= tsig;                                                   //
                                    state_num        <= state_num + 1'b1;                                       //
                                end                                                                             //
                                // =============================================================================//
                            end
                            SUB_RETURN: begin
                                // =============================================================================//
                                // REVISION HISTORY 019 (Phase 3c)                                              //
                                // 2026-07-08 Claude Code  Mod : Return is band-templated per §3.4b. Q now      //
                                //      genuinely reserves and fires at Stay-timeup; no extra capture is        //
                                //      needed (hr_state/hr_loop/hr_base/hr_ins/stack_depth are live registers, //
                                //      read at firing, not at scan time — nothing else in a Q band can touch   //
                                //      them between the Return's reservation and the window's own timeup).     //
                                //      FG is §3.4b-illegal (C3-F23) -> runaway error, HALT (C3-F24) — Phase 4b //
                                //      closes the gap Phase 3c left open. Phase 4d: overwriting an already-   //
                                //      pending SN reservation is itself a runaway error (C3-F26/C8) -> HALT.  //
                                // =============================================================================//
                                if (in_queued_band) begin                    // as Que command (after Prog End) //
                                    if (queued_valid) begin      // SN-overwrite (C3-F26/C8) -> HALT           //
                                        halt;                                                                   //
                                    end else begin                                                             //
                                        queued_valid  <= 1'b1;                                                  //
                                        queued_opcode <= OP_GLOBAL;                                              //
                                        queued_subop  <= SUB_RETURN;                                             //
                                        state_num     <= state_num + 1'b1;                // scan on            //
                                    end                                                                         //
                                end                                                                             //
                                else if (window_open) begin       // as background command (inside Stay window) //
                                    // Restore the held context.
                                    state_num <= hr_ins ? hr_state : (hr_state + 1'b1);
                                    loop_cnt  <= hr_loop;
                                    base_addr <= hr_base;
                                    if (stack_depth != 16'd0) begin
                                        // A deeper context is on the external stack.
                                        stack_pop_req <= 1'b1;
                                        fsm           <= S_POP;
                                    end else begin
                                        hr_occupied <= 1'b0;
                                    end
                                end                                                                             //
                                else begin      // as foreground command -> FG-illegal (C3-F23), runaway error //
                                    halt;                                                                       //
                                end                                                                             //
                                // =============================================================================//
                            end
                            SUB_CALL: begin
                                // =============================================================================//
                                // REVISION HISTORY 018 (Phase 3b)                                              //
                                // 2026-07-08 Claude Code  Mod : Call is band-templated per §3.4b. Q now        //
                                //      genuinely reserves (queued_save_state = this Call's own address,        //
                                //      queued_target = save_state + g_ext, the offset-16-D31 target) and       //
                                //      fires unconditionally at Stay-timeup — Call has no Condition to         //
                                //      evaluate, unlike Branch, so firing is a plain save_or_set the moment    //
                                //      the reservation is checked. FG is §3.4b-illegal (C3-F23) -> runaway     //
                                //      error, HALT (C3-F24) — Phase 4b closes the gap Phase 3b left open.      //
                                //      Phase 4d: overwriting an already-pending SN reservation is itself a     //
                                //      runaway error (C3-F26/C8) -> HALT.                                      //
                                // =============================================================================//
                                if (in_queued_band) begin                    // as Que command (after Prog End) //
                                    if (queued_valid) begin      // SN-overwrite (C3-F26/C8) -> HALT           //
                                        halt;                                                                   //
                                    end else begin                                                             //
                                        queued_valid      <= 1'b1;                                              //
                                        queued_opcode     <= OP_GLOBAL;                                          //
                                        queued_subop      <= SUB_CALL;                                           //
                                        queued_save_state <= state_num;     // this Call's own address           //
                                        queued_target      <= state_num + g_ext[ADDR_W-1:0]; // implicit zero-ext //
                                        state_num          <= state_num + 1'b1;           // scan on            //
                                    end                                                                         //
                                end                                                                             //
                                else if (window_open) begin       // as background command (inside Stay window) //
                                    // Unconditional call: auto-save the call address
                                    // (Return restores saved+1, the return-to-after
                                    // convention C3-F12) then jump by the 12-bit
                                    // offset in the extended operand (D16-D31).
                                    save_or_set(state_num,
                                                1'b0,
                                                state_num + g_ext[ADDR_W-1:0],
                                                1'b0);
                                end                                                                             //
                                else begin      // as foreground command -> FG-illegal (C3-F23), runaway error //
                                    halt;                                                                       //
                                end                                                                             //
                                // =============================================================================//
                            end
                            SUB_LOOP: begin
                                // =============================================================================//
                                // REVISION HISTORY 020 (Phase 4b)                                              //
                                // 2026-07-08 Claude Code  Mod : Loop's FG case now HALTs (C3-F23/C3-F24)       //
                                //      instead of silently running as an immediate loop. (need_ind_loop        //
                                //      also gained a window_open term above, so an FG indirect-target Loop     //
                                //      (g_ext==0) no longer escapes into S_IND before ever reaching this       //
                                //      case — it now HALTs here too, the same as a literal-target FG Loop.)    //
                                // =============================================================================//
                                if (in_queued_band) begin
                                    // Defer to Stay-timeup (queued band).
                                    // RH014: queued_opcode is set explicitly (not left
                                    // stale) so a queued Reset's queued_subop==SUB_RESET
                                    // check in S_WAIT can never alias a queued Loop, and
                                    // so a queued Loop that exits can never alias a stale
                                    // queued_opcode==OP_JUMP in resume_addr.
                                    // Phase 4d: overwriting an already-pending SN reservation
                                    // is itself a runaway error (C3-F26/C8) -> HALT.
                                    if (queued_valid) begin
                                        halt;
                                    end else begin
                                        queued_valid   <= 1'b1;
                                        queued_subop   <= SUB_LOOP;
                                        queued_opcode  <= OP_GLOBAL;
                                        queued_target  <= g_ext[LOOP_W-1:0];
                                        q_base_pending <= 1'b0;   // Phase 5: paired -- a Loop is now
                                                                   // reserved to consume this Q Base Set,
                                                                   // whether it exits this lap or not.
                                        state_num      <= state_num + 1'b1;
                                    end
                                end else if (window_open) begin
                                    // Immediate background Loop (literal target;
                                    // indirect target handled via S_IND above).
                                    if (loop_exits(loop_cnt, g_ext[LOOP_W-1:0])) begin
                                        loop_cnt       <= {LOOP_W{1'b0}};
                                        loop_cnt_match <= 1'b1;
                                        base_pending   <= 1'b0;   // Phase 4e: paired -- exited cleanly
                                        state_num      <= state_num + 1'b1;
                                    end else begin
                                        loop_cnt  <= loop_cnt + 1'b1;
                                        state_num <= base_addr;
                                    end
                                end else begin
                                    // Foreground -> FG-illegal (C3-F23), runaway error.
                                    halt;
                                end
                            end
                            SUB_PROGEND: begin
                                // =============================================================================//
                                // REVISION HISTORY 021 (Phase 4c)                                              //
                                // 2026-07-08 Claude Code  Mod : Prog End is band-templated per §3.4b and gains  //
                                //      two HALT traps (C3-F24): a second Prog End scanned while already in the //
                                //      Q band (in_queued_band, i.e. a stray/duplicate BG->Q boundary) HALTs,   //
                                //      and FG Prog End -- previously a silent "blank shot" advance with no     //
                                //      window to close -- now HALTs too (C3-F23, window-only). BG (first shot, //
                                //      opens the Q band) keeps its existing behavior, plus a third trap        //
                                //      (Phase 4e, RH024): a BG Base Set whose Loop was never exited (C3-F24    //
                                //      unpaired Base Set<->Loop) HALTs here too, at the band-crossing point.   //
                                // =============================================================================//
                                if (in_queued_band) begin                    // stray 2nd Prog End in Q band     //
                                    halt;                                                                       //
                                end                                                                             //
                                else if (window_open) begin       // as background command: opens the Q band    //
                                    if (base_pending) begin       // unpaired Base Set<->Loop -> HALT           //
                                        halt;                                                                   //
                                    end else begin                                                             //
                                        prog_end_seen <= 1'b1;                                                  //
                                        state_num     <= state_num + 1'b1;                                      //
                                    end                                                                         //
                                end                                                                             //
                                else begin      // as foreground command -> FG-illegal (C3-F23), runaway error //
                                    halt;                                                                       //
                                end                                                                             //
                                // =============================================================================//
                            end
                            default: begin
                                // NOP (sub-op 7) and reserved 8-255: present tsig.
                                // =============================================================================//
                                // REVISION HISTORY 001 / 010                                                   //
                                // 2026-06-14 22:06 Arch. Ohnaka  Add :This defines the execution of NOP        //
                                //      as a Que command, background command, and foreground command.           //
                                // 2026-07-07       Claude Code   Mod : Architect ruling — the band test is     //
                                //      in_queued_band (not prog_end_seen), and a Que/BG NOP simply advances    //
                                //      (the former transition to S_WAIT entered the wait with a stale          //
                                //      stay_target and skipped the rest of the Q-band scan). The three-band    //
                                //      if/else format is kept deliberately: it is the TEMPLATE for extending   //
                                //      internal sub-opcodes 8-255.                                             //
                                // =============================================================================//
                                if (in_queued_band) begin                    // as Que command (after Prog End) //
                                    state_num      <= state_num + 1'b1;      // scan on; nothing to reserve     //
                                end                                                                             //
                                else if (window_open) begin       // as background command (inside Stay window) //
                                    state_num      <= state_num + 1'b1;                                         //
                                end                                                                             //
                                else begin                       // as foreground command (outside Stay window) //
                                    timing_signals <= tsig;                                                     //
                                    if (presc_tick) begin      // Advance only on prescaler tick (C4-F8)        //
                                        state_num      <= state_num + 1'b1;      // Advance to next instruction //
                                    end                                                                         //
                                end                                                                             //
                                // =============================================================================//
                            end
                            endcase
                        end else begin
                            // External-mode Global: ext_op_valid pulsed this clock;
                            // D16-D31 is operand data, so timing_signals is held.
                            state_num <= state_num + 1'b1;
                        end
                        // RH005 (2026-06-15, Arch. Ohnaka): in-window tick increment — superseded
                        // by the hoisted single rule above the case (RH011 / A4).
                    end
                    // --------------------------------------------------------
                    //  Stay (opcode 1) — enter the wait
                    // --------------------------------------------------------
                    OP_STAY: begin
                        //stay_cnt       <= {(CNT_W+1){1'b0}};  // Del : The stay counter may have already started counting in StaySet, so it should not be cleared here. - RH 003 Arch. Ohnaka (2026-06-14 22:06)
                        // RH028: a tick coincident with the Stay's own execute clock counts —
                        // guaranteed at PRESCALE=1, where every Stay transition lands on a tick
                        // (whether reached from FG, BG, or the Q scan). In-window this duplicates
                        // the hoisted RH011 rule (same value assigned twice, harmless); the bare
                        // (windowless FG) case was previously uncovered, costing every bare Stay
                        // one extra clock at PRESCALE=1 (Stay-N took N+1 clocks).
                        // Additionally, a bare Stay whose deadline IS the coincident tick
                        // (Stay-1 at PRESCALE=1, or an off-grid coincidence after FG Reset)
                        // times up on this very clock — no S_WAIT entry — making the minimal
                        // Stay-1 consume exactly one clock, like FG NOP. This same-clock bare
                        // timeup needs none of the windowed dispatch machinery: with no window
                        // there is no queue, no pending Reset, and a pending insertion would
                        // have preempted this instruction via insert_pending.
                        if (!window_open && presc_tick && (stay_cnt >= stay_dur - 1'b1)) begin
                            stay_cnt_match <= 1'b1;
                            stay_cnt       <= {(CNT_W+1){1'b0}};
                            timing_signals <= tsig;
                            state_num      <= state_num + 1'b1;
                        end else begin
                            if (presc_tick) stay_cnt <= stay_cnt + 1'b1;
                            stay_target    <= stay_dur;
                            timing_signals <= tsig;        // held value during wait (C3-T1 A)
                            fsm            <= S_WAIT;
                        end
                        // RH004 (2026-06-14, Arch. Ohnaka): in-window tick increment — superseded
                        // by the hoisted single rule above the case (RH011 / A4).
                    end
                    // --------------------------------------------------------
                    //  Branch (opcode 2) — conditional state transition
                    // --------------------------------------------------------
                    OP_BRANCH: begin
                        // =============================================================================//
                        // REVISION HISTORY 012 / 017                                                   //
                        // 2026-07-07 Claude Code  Mod : Branch is band-templated per §3.4b:            //
                        //      FG drives tsig and decides on the next prescaler tick (C4-F8 —          //
                        //      previously it decided on the next clock, un-prescaled);                 //
                        //      BG holds the timing signals (previously it drove them) and decides      //
                        //      on the next clock at full system rate.                                  //
                        // 2026-07-08 Claude Code  Mod : Q now genuinely reserves and defers to          //
                        //      Stay-timeup (§3.4b Branch Q row), replacing the earlier "behaves like    //
                        //      BG" placeholder. Scan time captures this Branch's own address            //
                        //      (queued_save_state, for the return-to-after auto-save, C3-F12) and       //
                        //      the taken-target (queued_target = save_state + operand — operand 0       //
                        //      naturally falls out as target == save_state, the self-loop idiom).       //
                        //      Condition is evaluated live at firing (S_WAIT), not captured here.       //
                        // 2026-07-08 Claude Code  Mod : Phase 4d — overwriting an already-pending SN    //
                        //      reservation is itself a runaway error (C3-F26/C8) -> HALT.               //
                        // =============================================================================//
                        if (in_queued_band) begin                    // as Que command (after Prog End) //
                            if (queued_valid) begin      // SN-overwrite (C3-F26/C8) -> HALT             //
                                halt;                                                                    //
                            end else begin                                                              //
                                queued_valid      <= 1'b1;                                              //
                                queued_opcode     <= OP_BRANCH;                                          //
                                queued_subop      <= SUB_NOP;    // sentinel; disambiguated by opcode    //
                                queued_save_state <= state_num;  // this Branch's own address            //
                                queued_target     <= state_num + operand; // taken-target (implicit 0-ext)//
                                state_num         <= state_num + 1'b1; // scan on                        //
                            end                                                                          //
                        end                                                                             //
                        else if (window_open) begin       // as background command (inside Stay window) //
                            branch_decide;                     // tsig held; full-clock decision        //
                        end                                                                             //
                        else begin                       // as foreground command (outside Stay window) //
                            timing_signals <= tsig;                                                     //
                            if (presc_tick) begin      // Decide only on prescaler tick (C4-F8)         //
                                branch_decide;                                                          //
                            end                                                                         //
                        end                                                                             //
                        // =============================================================================//
                    end
                    // --------------------------------------------------------
                    //  Jump (opcode 3) — unconditional (operand 0 = indirect,
                    //  handled by need_indirect above)
                    // --------------------------------------------------------
                    OP_JUMP: begin
                        // =============================================================================//
                        // REVISION HISTORY  006                                                        //
                        // 2026-06-15  Arch. Ohnaka  Add :This defines the execution of JUMP            //
                        //      as a Que command, background command, and foreground command.           //
                        // 2026-07-08  Claude Code   Mod : Phase 4d — overwriting an already-pending SN  //
                        //      reservation is itself a runaway error (C3-F26/C8) -> HALT.               //
                        // =============================================================================//
                        if (in_queued_band) begin  // After Prog End inside Stay window: queue a Jump   // (immediate target).
                            if (queued_valid) begin      // SN-overwrite (C3-F26/C8) -> HALT             //
                                halt;                                                                    //
                            end else begin                                                              //
                                queued_valid  <= 1'b1;                                                  //
                                queued_opcode <= OP_JUMP;                                                //
                                queued_subop  <= SUB_NOP; // RH014: non-SUB_RESET sentinel — see Loop Q  //
                                queued_target <= operand;                                                //
                                state_num     <= state_num + 1'b1;                                       //
                            end                                                                          //
                        end                                                                             //
                        else if (window_open) begin  // Inside Stay window: treat as background command // (immediate target).
                            state_num      <= operand;  // Advance to the target immediately,           // but do NOT present tsig (C3-T1 B). 
                        end                                                                             //
                        else begin  // Outside Stay window: treat as foreground command                 // (immediate target).
                            timing_signals <= tsig;  // Present tsig immediately (C3-T1 A),             // but advance to the target only on the next prescaler tick (C4-T4 lean B).
                            if (presc_tick) begin  // Advance to the target on the next prescaler tick  // (C4-T4 lean B)
                                state_num      <= operand;     // absolute target                       //
                            end                                                                         //   
                        end                                                                             //
                        // =============================================================================//                           
                    end
                    // --------------------------------------------------------
                    //  Reserved opcodes 4-F: treated as NOP (advance)
                    // --------------------------------------------------------
                    default: begin
                        timing_signals <= tsig;
                        state_num      <= state_num + 1'b1;
                    end
                    endcase
                end
            end

            // ================================================================
            //  S_WAIT — sit at the Stay state, tick the (prescaled) counter
            // ================================================================
            S_WAIT: begin
                if (presc_tick) begin
                    // RH028: >= (was ==). If the deadline tick fell on a pre-S_WAIT
                    // clock (the arm/scan pipeline — guaranteed reachable at
                    // PRESCALE=1 for a windowed Stay-1/Stay-2, and at any PRESCALE
                    // when the BG scan runs longer than the written Stay), the
                    // counter has already passed target-1 and an equality test can
                    // never fire: the wait silently ran away for a full 2^13-count
                    // wrap. With >=, an already-passed deadline fires the timeup on
                    // the FIRST tick in S_WAIT — the earliest realizable moment
                    // (architect-approved choice over a HALT: minimal Stays must
                    // work, and an over-constrained window degrades gracefully).
                    // For exact programs, >= and == coincide — no verified timing
                    // changes (T1 25:25, T2 30:30, T32 self-loop all unaffected).
                    if (stay_cnt >= (stay_target - 1'b1)) begin
                        // ---- Stay-timeup -----------------------------------
                        stay_cnt_match <= 1'b1;
                        stay_cnt       <= {(CNT_W+1){1'b0}};  // Add : Clear stay counter and match flag; close the window. - RH 002 Arch. Ohnaka (2026-06-14 22:06)
                        window_open    <= 1'b0;
                        prog_end_seen  <= 1'b0;
                        queued_valid   <= 1'b0;
                        fsm            <= S_RUN;

                        // =============================================================================//
                        // REVISION HISTORY 015 (architect ruling 2026-07-08)                           //
                        // A queued Reset (pending_reset) is checked FIRST, with ABSOLUTE PRIORITY over //
                        // everything else that can happen at Stay-timeup: a queued Loop's counter      //
                        // update, a queued Jump's target, and even a deferred insertion are all         //
                        // DISCARDED if a Reset is pending — Reset overrides/wins unconditionally, never //
                        // competing for the shared Loop/Jump slot. Firing is fully destructive (Reset   //
                        // is initialization): every execution-context register this core owns is       //
                        // cleared, mirroring the hardware `rst` block, with exactly two exceptions —    //
                        // presc_cnt is never touched (C3-F21: the prescaler is a time-base a program    //
                        // must never perturb) and timing_signals is driven from the Reset's own         //
                        // captured D16-D31 field rather than cleared to 0 (C7).                         //
                        // =============================================================================//
                        if (pending_reset) begin
                            pending_reset   <= 1'b0;
                            state_num       <= {ADDR_W{1'b0}};
                            timing_signals  <= pending_reset_tsig;
                            loop_cnt        <= {LOOP_W{1'b0}};
                            base_addr       <= {ADDR_W{1'b0}};
                            base_pending    <= 1'b0;
                            stay_start_state <= {ADDR_W{1'b0}};
                            q_base_pending  <= 1'b0;
                            hr_state        <= {ADDR_W{1'b0}};
                            hr_loop         <= {LOOP_W{1'b0}};
                            hr_base         <= {ADDR_W{1'b0}};
                            hr_ins          <= 1'b0;
                            hr_occupied     <= 1'b0;
                            stack_depth     <= 16'd0;
                            // window_open/prog_end_seen/queued_valid are already forced to 0
                            // above (the unconditional Stay-timeup prologue); explicitly
                            // discard the shared queue's payload too, for full destructiveness.
                            queued_subop    <= 8'd0;
                            queued_opcode   <= OP_GLOBAL;
                            queued_target   <= {LOOP_W{1'b0}};
                            ind_is_loop     <= 1'b0;
                            stack_push_req  <= 1'b0;
                            stack_pop_req   <= 1'b0;
                            insert_ack      <= 1'b0;
                            pend_is_insert  <= 1'b0;
                            // insert_req (if still asserted) is simply caught on the next
                            // S_RUN clock, now that window_open reads 0 — no special handling.
                        end
                        // =============================================================================//
                        // REVISION HISTORY 025 (Phase 5, C3-F24 Q half, PROVISIONAL)                   //
                        // A Q Base Set with no queued Loop ever reserved to consume it by the time      //
                        // its window reaches Stay-timeup is an unpaired Base Set<->Loop across bands    //
                        // (the Q-side mirror of Phase 4e's BG check) -- a runaway error, HALT. Checked  //
                        // second, after pending_reset (which still wins unconditionally -- q_base_pending//
                        // is already cleared above if a Reset just fired) and before the ordinary       //
                        // queued dispatch below, which a HALT here preempts entirely (state_num is left //
                        // untouched, freezing at the Stay that exposed the gap).                        //
                        //                                                                               //
                        // ARCHITECT MEMO (2026-07-08, Arch. Ohnaka): the exact HALT trigger the spec     //
                        // text describes ("a queued Base Set whose Loop lies in the BG window") could   //
                        // not be pinned down with confidence -- BG is chronologically always earlier    //
                        // than Q within one window, so it is unclear how that literal condition can     //
                        // arise. The check above ("no Q Loop ever reserved before Stay-timeup") is this //
                        // implementer's best-effort substitute, not a confirmed reading. The architect  //
                        // has separately flagged that Q-execution Loop semantics in general -- nested Q //
                        // Loops in particular -- remain genuinely undecided (multiple open design       //
                        // questions, not yet resolved even at the spec level) and are explicitly        //
                        // deferred: this whole area is planned follow-up work AFTER the current "33     //
                        // items" conformance-alignment pass this PR belongs to is complete. Do not       //
                        // over-fit this HALT condition to the current guess in future work -- revisit   //
                        // it fresh once the architect's Loop-semantics decisions land.                  //
                        // =============================================================================//
                        else if (q_base_pending &&
                                 !(queued_valid && (queued_subop == SUB_LOOP) &&
                                   (queued_opcode == OP_GLOBAL))) begin
                            halt;
                        end
                        else begin
                            // Apply a queued Loop's counter update. The resume target
                            // itself is computed by the combinational resume_addr wire.
                            if (queued_valid && (queued_subop == SUB_LOOP) &&
                                (queued_opcode == OP_GLOBAL)) begin
                                if (loop_exits(loop_cnt, queued_target)) begin
                                    loop_cnt       <= {LOOP_W{1'b0}};
                                    loop_cnt_match <= 1'b1;
                                end else begin
                                    loop_cnt    <= loop_cnt + 1'b1;
                                end
                            end

                            // RH017: a queued Branch that is TAKEN (Condition
                            // false at firing) and not the operand-0 self-loop
                            // degenerate case (C2-F5, no auto-save there) needs
                            // an auto-save (C2-F6) — a register write, possibly
                            // an S_PUSH stall — so it cannot be folded into the
                            // resume_addr wire like the not-taken / self-loop
                            // cases already are. Mutually exclusive with the
                            // deferred-insertion save_or_set below (only one
                            // save_or_set per clock): a simultaneously-pending
                            // insertion is simply left pending, caught on the
                            // next S_RUN clock (window_open is already 0),
                            // the same deferral style as C3-F20/RH013.
                            if (queued_valid && (queued_opcode == OP_BRANCH) &&
                                !condition &&
                                (queued_target[ADDR_W-1:0] != queued_save_state)) begin
                                save_or_set(queued_save_state, 1'b0,
                                            queued_target[ADDR_W-1:0], 1'b0);
                            end
                            // RH018 (Phase 3b): a queued Call fires unconditionally
                            // (no Condition to evaluate, unlike Branch) — plain
                            // save_or_set from the captured own-address/target.
                            // Same save_or_set mutual-exclusivity with a
                            // simultaneously-pending insertion as Branch above.
                            else if (queued_valid && (queued_subop == SUB_CALL) &&
                                     (queued_opcode == OP_GLOBAL)) begin
                                save_or_set(queued_save_state, 1'b0,
                                            queued_target[ADDR_W-1:0], 1'b0);
                            end
                            // RH019 (Phase 3c): a queued Return fires by restoring
                            // the (live) holding-register context, same as the BG
                            // path — including the S_POP fallback when a deeper
                            // context is on the external stack, which overrides the
                            // fsm<=S_RUN set above (same override pattern save_or_set
                            // already uses for S_PUSH). Mutually exclusive with a
                            // simultaneously-pending insertion, same deferral style.
                            else if (queued_valid && (queued_subop == SUB_RETURN) &&
                                     (queued_opcode == OP_GLOBAL)) begin
                                state_num <= hr_ins ? hr_state : (hr_state + 1'b1);
                                loop_cnt  <= hr_loop;
                                base_addr <= hr_base;
                                if (stack_depth != 16'd0) begin
                                    stack_pop_req <= 1'b1;
                                    fsm           <= S_POP;
                                end else begin
                                    hr_occupied <= 1'b0;
                                end
                            end
                            // Deferred insertion (C3-F20). An occupied holding
                            // register spills to the external stack (implicit
                            // push, C3-T6 lean A; the later fsm <= S_PUSH inside
                            // save_or_set overrides the S_RUN assigned above) —
                            // RH013. The saved address is the post-Stay resume
                            // address (no +1 on return, C3-F12).
                            else if (insert_req) begin
                                save_or_set(resume_addr, 1'b1, insert_target, 1'b1);
                            end else begin
                                state_num   <= resume_addr;
                            end
                        end
                    end else begin
                        stay_cnt <= stay_cnt + 1'b1;
                    end
                end
            end

            // ================================================================
            //  S_IND — wait for the external indirect-read result
            // ================================================================
            S_IND: begin
                // RH016: indirect Jump completion is band-split. BG completes
                // immediately on indirect_ready (full system clock, matching
                // literal BG Jump — tsig stays held, never driven here). FG
                // must land the state transition on a presc_tick (C4-F8
                // parity with literal FG Jump), so the result is latched into
                // ind_target/ind_resolved and applied on the next tick — the
                // indirect_ready handshake itself is not held open waiting
                // for that tick (it may be a 1-clock pulse, Tie C4-T1 lean B,
                // so the data must be captured the moment it is presented).
                // Indirect Loop is unaffected: it is unreachable in the Q
                // band already (need_ind_loop), and its foreground case is
                // presently undefined pending the Phase-4 FG-Global HALT
                // machinery (C3-F23), so no new tick-gating is introduced
                // for it here.
                if (!ind_resolved) begin
                    if (indirect_ready) begin
                        if (ind_is_loop) begin
                            fsm <= S_RUN;
                            // indirect_data (ADDR_W bits) zero-extends implicitly to the
                            // LOOP_W-wide task input; no explicit replication (which would
                            // be illegal if LOOP_W == ADDR_W).
                            if (loop_exits(loop_cnt, indirect_data)) begin
                                loop_cnt       <= {LOOP_W{1'b0}};
                                loop_cnt_match <= 1'b1;
                                state_num      <= state_num + 1'b1;
                            end else begin
                                loop_cnt  <= loop_cnt + 1'b1;
                                state_num <= base_addr;
                            end
                        end else if (ind_in_window) begin
                            // BG indirect Jump: immediate (matches literal BG Jump).
                            fsm       <= S_RUN;
                            state_num <= indirect_data;
                        end else begin
                            // FG indirect Jump: latch the target; commit on the
                            // next presc_tick (may be this very clock).
                            ind_target   <= indirect_data;
                            ind_resolved <= 1'b1;
                        end
                    end
                end else begin
                    // FG indirect Jump, resolved: wait for the tick to commit.
                    if (presc_tick) begin
                        fsm          <= S_RUN;
                        state_num    <= ind_target;
                        ind_resolved <= 1'b0;
                    end
                end
            end

            // ================================================================
            //  S_PUSH — spill the occupied holding register to external stack,
            //           then store the pending new context (auto-save nesting)
            // ================================================================
            S_PUSH: begin
                stack_push_req <= 1'b1;             // hold request until ack
                if (stack_ack) begin
                    stack_push_req <= 1'b0;
                    hr_state    <= pend_state;
                    hr_loop     <= pend_loop;
                    hr_base     <= pend_base;
                    hr_ins      <= pend_ins;
                    hr_occupied <= 1'b1;
                    stack_depth <= stack_depth + 16'd1;
                    state_num   <= pend_target;
                    if (pend_is_insert) insert_ack <= 1'b1;
                    fsm         <= S_RUN;
                end
            end

            // ================================================================
            //  S_POP — refill the holding register from the external stack
            // ================================================================
            S_POP: begin
                stack_pop_req <= 1'b1;
                if (stack_ack) begin
                    stack_pop_req <= 1'b0;
                    {hr_ins, hr_base, hr_loop, hr_state} <= stack_rdata;
                    hr_occupied   <= 1'b1;
                    stack_depth   <= stack_depth - 16'd1;
                    fsm           <= S_RUN;
                end
            end

            // ================================================================
            //  S_HALT — runaway-error trap (C3-F24). State Number holds at
            //           the violating instruction (the scene is preserved,
            //           for SignalTap capture); error_flag stays asserted.
            //           Escape: hardware reset, or an insertion (auto-saves
            //           the halted address exactly like ordinary insertion,
            //           C3-T7/C3-F12, so a rescue handler's eventual Return
            //           resumes at halted_address+1 — no special-casing).
            //           ISMCE live-patch-over-JTAG is the third escape route
            //           C3-F24 lists; it is an external repair workflow, not
            //           an RTL behavior.
            // ================================================================
            S_HALT: begin
                if (insert_req) begin
                    error_flag <= 1'b0;
                    // RH022: save_or_set only ever sets fsm to S_PUSH (spill
                    // case) or leaves it unassigned (its S_RUN call sites are
                    // already S_RUN, so "unassigned" correctly means "stay").
                    // From S_HALT that default would leave the FSM stuck here
                    // forever, so the rescue must claim S_RUN itself; the
                    // task's own S_PUSH assignment (if hr_occupied) executes
                    // after this one and correctly overrides it.
                    fsm <= S_RUN;
                    save_or_set(state_num, 1'b1, insert_target, 1'b1);
                end
            end

            default: fsm <= S_RUN;
            endcase
        end
    end

    // ========================================================================
    //  Auto-save helper (task): save the current context (or spill to stack if
    //  the holding register is already occupied) and set the jump target.
    //
    //   save_state : the return address to record (return-to-after = addr+1;
    //                for insertion, the address itself — C3-F12)
    //   ins        : the "saved-by-insertion" flag (C3-T7)
    //   target     : where execution continues immediately after the save
    //   is_insert  : pulse insert_ack (now, or on S_PUSH completion) — RH013
    // ========================================================================
    // ========================================================================
    //  Runaway-error trap (task, Phase 4 / C3-F24): enter S_HALT and raise
    //  error_flag. state_num is deliberately left untouched by every caller —
    //  it holds at the violating instruction, preserving the scene.
    // ========================================================================
    task halt;
        begin
            fsm        <= S_HALT;
            error_flag <= 1'b1;
        end
    endtask

    // ========================================================================
    //  Branch decision (task): the Condition-directed next-state selection,
    //  shared by the FG (tick-gated) and BG/Q (full-clock) bands of OP_BRANCH.
    // ========================================================================
    task branch_decide;
        begin
            if (condition) begin
                // Condition true => no branch (C2-F5)
                state_num <= state_num + 1'b1;
            end else if (operand == 12'd0) begin
                // Self-loop / wait-for-Condition (no auto-save)
                state_num <= state_num;
            end else begin
                // Branch taken => auto-save the branch address
                // (Return restores saved+1), jump forward.
                save_or_set(state_num, 1'b0, state_num + operand, 1'b0);
            end
        end
    endtask

    task save_or_set;
        input [ADDR_W-1:0] save_state;
        input              ins;
        input [ADDR_W-1:0] target;
        input              is_insert;  // RH013: pulse insert_ack (now, or on S_PUSH completion)
        begin
            if (hr_occupied) begin
                // Spill the existing context first (implicit push, C3-T6 lean A).
                pend_state     <= save_state;
                pend_loop      <= loop_cnt;
                pend_base      <= base_addr;
                pend_ins       <= ins;
                pend_target    <= target;
                pend_is_insert <= is_insert;
                stack_push_req <= 1'b1;
                fsm            <= S_PUSH;
            end else begin
                hr_state    <= save_state;
                hr_loop     <= loop_cnt;
                hr_base     <= base_addr;
                hr_ins      <= ins;
                hr_occupied <= 1'b1;
                state_num   <= target;
                if (is_insert) insert_ack <= 1'b1;
            end
        end
    endtask

endmodule
