#!/usr/bin/env python3
# negative_tests.py — each profile rule rejects what it should (Register W v0.6 §4).
# License: MIT (Layer 3). Evidence class ORACLE.
import json, os, subprocess, sys, tempfile
import pfasm_tools_w as T
isa = json.load(open("isa_table_w.json"))
PKT = open("../instruction_lists/wpms_packet.pfasm").read()

def prog_of(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".pfasm", delete=False); f.write(text); f.close()
    p = T.parse(f.name); os.unlink(f.name); return p

def machine_with_block(b=0, N=64, LE0=100):
    mc = T.Machine(); mc.store[b * 16] = N; mc.store[b * 16 + 5] = LE0; return mc

results = []
def case(name, expect, got):
    ok = any(expect in g for g in got); results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name:52s} -> {'; '.join(sorted(set(got)))[:110] or 'nothing'}")

# N1 Mode-T style: advance by direct store address inside a packet window
p = prog_of(".bg\n SAD 0x006\n LDM\n SAD 0x00A\n ADD @PPM\n SAD 0x006\n STM\n")
mc = machine_with_block(); mc.run(p, 'PKT', cur=0); case("N1 direct store write in a packet window", "EW4", mc.errors)
# N2 BCP inside a packet window
p = prog_of(".bg\n BCP\n"); mc = machine_with_block(); mc.run(p, 'PKT', cur=0); case("N2 BCP in a packet window", "EW4", mc.errors)
# N3 CUR write outside a packet window
p = prog_of(".bg\n SAD 0x106\n STM\n"); mc = machine_with_block(); mc.run(p, 'HK'); case("N3 CUR write in HK", "EW4", mc.errors)
# N4 STM into the inbox
p = prog_of(".bg\n SAD 0x082\n STM\n"); mc = machine_with_block(); mc.run(p, 'HK'); case("N4 STM into the inbox", "EW3", mc.errors)
# N5 negative glide rate
mc = machine_with_block(LE0=-1); mc.run(prog_of(PKT), 'PKT', cur=0); case("N5 STP with LE0 < 0", "EW6", mc.errors)
# N6 repeated block in the sweep word
mc = T.Machine(); mc.store[0] = mc.store[16] = 64
mc.sweep_staged, mc.sweep_armed = T.make_sweep([0, 1, 0]), True; mc.take_sweep = True
mc.run(prog_of(".bg\n BCP\n"), 'HK'); case("N6 sweep word repeats a block", "EW5", mc.errors)
# N7 sum N > NMAX
mc = T.Machine(); mc.store[0] = mc.store[16] = 1100
mc.sweep_staged, mc.sweep_armed = T.make_sweep([0, 1]), True; mc.take_sweep = True
mc.run(prog_of(".bg\n BCP\n"), 'HK'); case("N7 sweep sum N > NMAX", "EW5", mc.errors)
# N8-N10 contract-level rejections
for name, text, code in (("N8 CMT (no page pair)", ".q\n CMT\n", "E4"), ("N9 WSV (sequencer owns stay_value)", ".bg\n WSV\n", "E4"),
                         ("N10 PSH (no data stack)", ".bg\n PSH\n", "E4"), ("N11 STA ADRS (W-F1)", ".bg\n STA ADRS\n", "E4")):
    case(name, code, T.validate(prog_of(text), isa))
# N12 sensitivity: a window that advances PH0 twice must be caught by the sweep oracle
mut = PKT.replace("        LDM                     ; A = PHD1", "        SAD     0x106\n        LDM\n        SAD     0x10A\n        ADD     @PPM\n        SAD     0x106\n        STM\n        SAD     0x107\n        LDM                     ; A = PHD1")
d = tempfile.mkdtemp(); open(os.path.join(d, "wpms_packet.pfasm"), "w").write(mut)
env_prog = open("sweep_sim.py").read().replace('"../instruction_lists/wpms_packet.pfasm"', repr(os.path.join(d, "wpms_packet.pfasm")))
open(os.path.join(d, "sim_mut.py"), "w").write(env_prog)
r = subprocess.run([sys.executable, os.path.join(d, "sim_mut.py"), "-", "3000", "5"], capture_output=True, text=True, cwd=".",
                   env=dict(os.environ, PYTHONPATH="."))
line = [l for l in r.stdout.splitlines() if "mismatches" in l]
case("N12 mutant window (PH0 advanced twice) caught", "mismatches vs reference: ", [l.strip() for l in line if not l.strip().startswith("L1 bundle mismatches vs reference: 0 ")] )
# N13 packet shorter than N_MIN, caught by the sequencer at prefetch
import sweep_sim as SS
mc = T.Machine(); mc.store[0] = 16; sq = SS.Sequencer(mc, prog_of(PKT), prog_of(".bg\n BCP\n")); sq.prefetch(0)
case("N13 block N = 16 < N_MIN at prefetch", "EW2", sq.errors)
print(f"{sum(results)}/{len(results)} negative tests behave as specified")
sys.exit(0 if all(results) else 1)
