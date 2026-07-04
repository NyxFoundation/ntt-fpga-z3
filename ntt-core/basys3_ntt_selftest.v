// ============================================================================
// basys3_ntt_selftest — self-checking on-board demo of ntt_core for the
// Digilent Basys 3 (Artix-7 xc7a35tcpg236).  No host PC needed: on power-up
// it generates a deterministic input, runs NTT then INTT on our own-FSM core,
// reads the result back, and checks INTT(NTT(x)) == x on-chip.  The verdict
// lights the LEDs:
//
//   led[0]  = done       (self-test finished)
//   led[1]  = PASS       (all 1024 coefficients matched)
//   led[2]  = FAIL       (at least one mismatch)
//   led[15:6] = mismatch count (saturating) — 0 when PASS
//   led[5:3] = running phase (load / ntt / intt / check) for a visible sweep
//
// Input model: x[i] = (i*7 + 1) mod q, computed by a running +7 (mod q) so
// load and check use the same golden without a ROM.
// ============================================================================
`timescale 1ns / 1ps
module basys3_ntt_selftest #(
    parameter DW = 14,
    parameter N  = 1024,
    parameter AW = 10,
    parameter Q  = 14'd12289
)(
    input             clk,          // 100 MHz (Basys 3 pin W5)
    input             btn_start,    // optional: re-run on a button (btnC)
    output reg [15:0] led
);
    // ---- /2 clock: the core's Fmax (open flow) is ~95 MHz, so run the whole
    // design on a 50 MHz BUFG-buffered clock to meet timing with margin.  The
    // self-test is not throughput-critical (it finishes in ~3 ms), so the
    // divided clock is invisible; only the verdict LEDs matter.
    reg clk_div = 1'b0;
    always @(posedge clk) clk_div <= ~clk_div;
    wire clk_core;
    BUFG bufg_core (.I(clk_div), .O(clk_core));

    // ---- reset synchronizer + initial auto-start ---------------------------
    reg [3:0] rstcnt = 0;
    reg       rst = 1'b1;
    always @(posedge clk_core) begin
        if (rstcnt != 4'hF) begin rstcnt <= rstcnt + 1'b1; rst <= 1'b1; end
        else rst <= 1'b0;
    end

    // ---- 2-FF synchronizer for the asynchronous button ---------------------
    // btn_start comes straight off a pin; feeding it into FSM next-state
    // logic unsynchronized risks metastability on the T_DONE->T_IDLE edge.
    reg btn_m = 1'b0, btn_s = 1'b0;
    always @(posedge clk_core) begin btn_m <= btn_start; btn_s <= btn_m; end

    // ---- the core ----------------------------------------------------------
    reg           start, mode, h_we;
    reg  [AW-1:0] h_addr;
    reg  [DW-1:0] h_din;
    wire [DW-1:0] h_dout;
    wire          busy, done;
    ntt_core #(.BF_LAT(8)) core (
        .clk(clk_core), .rst(rst), .start(start), .mode(mode),
        .busy(busy), .done(done),
        .h_we(h_we), .h_addr(h_addr), .h_din(h_din), .h_dout(h_dout));

    // ---- self-test controller ---------------------------------------------
    localparam T_IDLE=0, T_LOAD=1, T_NTT0=2, T_NTT1=3, T_INTT0=4, T_INTT1=5,
               T_CADDR=6, T_CWAIT=7, T_CCMP=8, T_DONE=9;
    reg [3:0]  ts;
    reg [AW:0] idx;
    reg [DW-1:0] xg;               // running golden x[i]
    reg [9:0]  miss;               // saturating mismatch count
    reg        btn_q;

    // next golden: xg + 7 mod q
    wire [DW:0] xg_p7 = xg + 14'd7;
    wire [DW-1:0] xg_next = (xg_p7 >= Q) ? (xg_p7 - Q) : xg_p7[DW-1:0];

    always @(posedge clk_core) begin
        if (rst) begin
            ts <= T_IDLE; led <= 16'h0000;
            start <= 0; mode <= 0; h_we <= 0; h_addr <= 0; h_din <= 0;
            idx <= 0; xg <= 14'd1; miss <= 0; btn_q <= 0;
        end else begin
            start <= 1'b0; h_we <= 1'b0;
            btn_q <= btn_s;
            case (ts)
            // idle briefly, then auto-start; btnC re-runs
            T_IDLE: begin
                idx <= 0; xg <= 14'd1; miss <= 0;
                led <= 16'h0000;       // clear the previous verdict on re-run
                ts <= T_LOAD;
            end
            // ---- load x[i] via the host port ----
            T_LOAD: begin
                led[5:3] <= 3'd1;
                h_we   <= 1'b1;
                h_addr <= idx[AW-1:0];
                h_din  <= xg;
                xg     <= xg_next;
                if (idx == N-1) begin idx <= 0; ts <= T_NTT0; end
                else idx <= idx + 1'b1;
            end
            // ---- NTT ----
            T_NTT0: begin led[5:3]<=3'd2; mode<=1'b0; start<=1'b1; ts<=T_NTT1; end
            T_NTT1: if (done) ts <= T_INTT0;
            // ---- INTT ----
            T_INTT0: begin led[5:3]<=3'd3; mode<=1'b1; start<=1'b1; ts<=T_INTT1; end
            T_INTT1: if (done) begin idx<=0; xg<=14'd1; ts<=T_CADDR; end
            // ---- check INTT(NTT(x)) == x ----
            T_CADDR: begin
                led[5:3] <= 3'd4;
                h_addr <= idx[AW-1:0]; h_we <= 1'b0;
                ts <= T_CWAIT;
            end
            T_CWAIT: ts <= T_CCMP;             // registered read latency
            T_CCMP: begin
                if (h_dout != xg && miss != 10'h3FF) miss <= miss + 1'b1;
                xg <= xg_next;
                if (idx == N-1) ts <= T_DONE;
                else begin idx <= idx + 1'b1; ts <= T_CADDR; end
            end
            // ---- verdict ----
            T_DONE: begin
                led[0]     <= 1'b1;            // done
                led[1]     <= (miss == 0);     // PASS
                led[2]     <= (miss != 0);     // FAIL
                led[15:6]  <= miss;            // mismatch count
                led[5:3]   <= 3'd7;
                if (btn_s & ~btn_q) ts <= T_IDLE;   // re-run on button edge (synced)
            end
            default: ts <= T_IDLE;
            endcase
        end
    end
endmodule
