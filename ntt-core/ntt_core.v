// ============================================================================
// ntt_core — a NEW, minimal, self-contained single-BFU NTT/INTT accelerator
// for Falcon (N=1024, q=12289), built around our own verified building blocks:
//   * compact_bf_v2      — the 1-multiplier K-RED butterfly (latency 6)
//   * tf_rom_fold        — the psi-fold twiddle ROM (stores half the words)
//   * an inlined dual-port BRAM array holding the N coefficients
//   * OUR OWN control FSM — no reverse-engineering of an unreleased FSM, so
//     the whole core round-trips by construction.
//
// This is deliberately SIMPLE: butterflies run one at a time (sequential),
// so a single dual-port BRAM (2 reads then 2 writes, never simultaneously)
// suffices and correctness is easy to see and to verify.  Throughput is
// ~ (BF_LAT+4) cycles/butterfly; a pipelined 2-bank variant is future work.
//
// Schedule (simulation-validated on every CI run against the streaming
// harness tb_stream.v AND an independent Python golden — ntt-core/run_check.py):
//   NTT  (sel=0): r=1;    for p=9..0: J=2^p; per group w=W[r++];
//                          per bfly lo=k*2J+j, hi=lo+J
//   INTT (sel=1): r=1023; for p=0..9: same pairing, w=W[r--]
// where W[r] = tf_rom_fold(A=r-1).  INTT(NTT(x)) == x EXACTLY — the
// per-stage halving is fused into compact_bf_v2's INTT mode (no 2^10 residue).
//
// Control:  start=1 with mode (0=NTT,1=INTT) begins a transform on the RAM
// contents; done pulses when finished.  Load/read the RAM through the
// host port (h_*) while idle.  Host input words are reduced mod q on load
// (one conditional subtract — 14-bit input < 2q), so the core never feeds
// an unreduced value into the verified datapath.
// ============================================================================
`timescale 1ns / 1ps
module ntt_core #(
    parameter DW    = 14,
    parameter N     = 1024,
    parameter LOGN  = 10,
    parameter AW    = 10,          // log2(N)
    parameter BF_LAT = 6           // compact_bf_v2 input->output latency
)(
    input               clk,
    input               rst,
    // control
    input               start,     // pulse to begin a transform
    input               mode,      // 0 = NTT (DIT-NR), 1 = INTT (DIF-RN)
    output reg          busy,
    output reg          done,
    // host access to the coefficient RAM (valid only while !busy)
    input               h_we,
    input      [AW-1:0] h_addr,
    input      [DW-1:0] h_din,
    output     [DW-1:0] h_dout
);
    // ------------------------------------------------------------------
    // Coefficient RAM: dual-port, registered read.  Port A also serves the
    // host while idle.  1024x14 infers one RAMB18 on Artix-7.
    // ------------------------------------------------------------------
    reg  [DW-1:0] mem [0:N-1];
    reg  [AW-1:0] a_addr, b_addr;
    reg           a_we,   b_we;
    reg  [DW-1:0] a_din,  b_din;
    reg  [DW-1:0] a_q,    b_q;

    // Port A (engine read/write + host); Port B (engine only).  Single always
    // block so the two write ports never form a multi-driver race; the engine
    // always drives lo on A and hi on B (distinct), and reads and writes of an
    // address never occur in the same cycle.
    // Host words are fully reduced on load: h_din is 14 bits (max 16383
    // < 2q), so ONE conditional subtract enforces the < q operating envelope
    // that the verified datapath (K-RED butterfly, add/sub/half leaf proofs)
    // is justified for — even when the host writes a raw value in [q, 2^14).
    wire [DW-1:0] h_din_red = (h_din >= 14'd12289) ? h_din - 14'd12289 : h_din;
    wire [AW-1:0] pa_addr = busy ? a_addr : h_addr;
    wire          pa_we   = busy ? a_we   : h_we;
    wire [DW-1:0] pa_din  = busy ? a_din  : h_din_red;
    always @(posedge clk) begin
        if (pa_we) mem[pa_addr] <= pa_din;
        if (b_we)  mem[b_addr]  <= b_din;
        a_q <= mem[pa_addr];
        b_q <= mem[b_addr];
    end
    assign h_dout = a_q;

    // ------------------------------------------------------------------
    // psi-fold twiddle ROM.  A=r-1 -> Q=W[r].
    // ------------------------------------------------------------------
    reg  [AW-1:0] rom_a;
    reg           rom_ren;
    wire [DW-1:0] rom_q;
    tf_rom_fold rom (.clk(clk), .A(rom_a[9:0]), .REN(rom_ren), .Q(rom_q));

    // ------------------------------------------------------------------
    // The butterfly.  We hold its inputs steady across the compute window.
    // ------------------------------------------------------------------
    reg          bf_sel;
    reg  [DW-1:0] bf_u, bf_v, bf_w;
    wire [DW-1:0] bf_lower, bf_upper;
    compact_bf_v2 bf (.clk(clk), .rst(rst), .sel(bf_sel),
                      .u(bf_u), .v(bf_v), .w(bf_w),
                      .bf_upper(bf_upper), .bf_lower(bf_lower));

    // ------------------------------------------------------------------
    // Control FSM — nested loops p / k / j, sequential per butterfly.
    // ------------------------------------------------------------------
    localparam S_IDLE    = 0,
               S_GRP     = 1,   // start of a group: kick the twiddle read
               S_GRP1    = 2,   // twiddle read latency
               S_RDADDR  = 3,   // present read addresses lo/hi
               S_RDADDR2 = 9,   // addr registered; RAM latches q this edge
               S_RDDAT   = 4,   // read data valid -> latch into the butterfly
               S_BF      = 5,   // wait out the butterfly latency
               S_WR      = 6,   // write results back
               S_NEXT    = 7,   // advance j / k / p
               S_DONE    = 8;

    reg  [3:0]  st;
    reg         cur_mode;                 // 0 NTT, 1 INTT
    reg  signed [4:0] p;                   // stage index (NTT 9..0, INTT 0..9)
    reg  [AW:0] k, j;                      // group, butterfly-in-group
    reg  [AW:0] rr;                        // twiddle running index
    reg  [DW-1:0] w_lat;                   // latched twiddle for the group
    reg  [$clog2(BF_LAT+2):0] wait_cnt;

    // J = 2^p ; lo = k*2J + j = (k << (p+1)) + j ; hi = lo + J
    wire [AW:0] Jv  = (11'd1 << p[3:0]);
    wire [AW:0] lo  = (k << (p[3:0] + 1)) + j;
    wire [AW:0] hi  = lo + Jv;
    wire [AW:0] ngrp = (N >> (p[3:0] + 1));   // N/(2J) groups this stage

    always @(posedge clk) begin
        if (rst) begin
            st <= S_IDLE; busy <= 1'b0; done <= 1'b0;
            a_we <= 1'b0; b_we <= 1'b0; rom_ren <= 1'b0;
        end else begin
            done <= 1'b0;
            a_we <= 1'b0; b_we <= 1'b0;
            case (st)
            // --------------------------------------------------------
            S_IDLE: begin
                busy <= 1'b0;
                if (start) begin
                    busy     <= 1'b1;
                    cur_mode <= mode;
                    p        <= mode ? 5'd0 : 5'd9;      // NTT 9..0, INTT 0..9
                    k        <= 0; j <= 0;
                    rr       <= mode ? 11'd1023 : 11'd1; // INTT 1023--, NTT 1++
                    st       <= S_GRP;
                end
            end
            // ---- group start: read the twiddle W[rr] (addr rr-1) --------
            S_GRP: begin
                rom_a   <= rr - 1;
                rom_ren <= 1'b1;
                st      <= S_GRP1;
            end
            S_GRP1: begin              // rom_q valid next cycle
                st <= S_RDADDR;
            end
            // ---- per butterfly: present read addresses ------------------
            S_RDADDR: begin
                if (j == 0) w_lat <= rom_q;      // latch group twiddle once
                a_addr <= lo[AW-1:0];
                b_addr <= hi[AW-1:0];
                a_we   <= 1'b0; b_we <= 1'b0;
                st     <= S_RDADDR2;
            end
            S_RDADDR2: begin           // a_addr/b_addr registered; q latched now
                st <= S_RDDAT;
            end
            S_RDDAT: begin             // a_q/b_q now hold u,v
                bf_u   <= a_q;
                bf_v   <= b_q;
                bf_w   <= w_lat;
                bf_sel <= cur_mode;
                wait_cnt <= 0;
                st     <= S_BF;
            end
            // ---- wait out the butterfly pipeline ------------------------
            S_BF: begin
                if (wait_cnt == BF_LAT[$clog2(BF_LAT+2):0]) st <= S_WR;
                else wait_cnt <= wait_cnt + 1'b1;
            end
            // ---- write the two results back -----------------------------
            S_WR: begin
                a_addr <= lo[AW-1:0]; a_din <= bf_lower; a_we <= 1'b1;
                b_addr <= hi[AW-1:0]; b_din <= bf_upper; b_we <= 1'b1;
                st     <= S_NEXT;
            end
            // ---- advance j / k / p --------------------------------------
            S_NEXT: begin
                if (j + 1 < Jv) begin
                    j  <= j + 1'b1;
                    st <= S_RDADDR;                 // same group, same twiddle
                end else begin
                    j <= 0;
                    if (k + 1 < ngrp) begin
                        k  <= k + 1'b1;
                        rr <= cur_mode ? rr - 1'b1 : rr + 1'b1;
                        st <= S_GRP;                // new group, new twiddle
                    end else begin
                        k <= 0;
                        rr <= cur_mode ? rr - 1'b1 : rr + 1'b1;
                        if (( cur_mode && p == 5'd9) ||
                            (!cur_mode && p == 5'd0)) begin
                            st <= S_DONE;           // last stage finished
                        end else begin
                            p  <= cur_mode ? p + 1'b1 : p - 1'b1;
                            st <= S_GRP;
                        end
                    end
                end
            end
            S_DONE: begin
                rom_ren <= 1'b0;
                busy <= 1'b0; done <= 1'b1;
                st   <= S_IDLE;
            end
            default: st <= S_IDLE;
            endcase
        end
    end
endmodule
