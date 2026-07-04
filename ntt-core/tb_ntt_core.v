// Functional test for ntt_core: multiple vectors (deterministic ramp + seeded
// LCG random), each loaded, NTT'd, dumped, INTT'd and checked for the exact
// round-trip INTT(NTT(x)) == x (compact_bf_v2 fuses the per-stage halving, so
// there is NO 2^10 residue).  Also runs INTT-only vectors and dumps their
// outputs so run_check.py can validate the INTT against an independent Python
// golden (ntt_golden(INTT_rtl(y)) == y).  Every dump goes to ntt-core/ and a
// failed $fopen is fatal — a silent dump failure must never let stale files
// pass cross-validation again.
`timescale 1ns / 1ps
module tb_ntt_core;
    localparam DW = 14, N = 1024, AW = 10, Q = 12289;
    localparam NRT = 4;   // round-trip vectors (0 = ramp, 1.. = LCG random)
    localparam NIV = 2;   // INTT-only vectors (golden-checked in run_check.py)

    reg clk = 0, rst;
    always #5 clk = ~clk;

    reg          start, mode, h_we;
    reg  [AW-1:0] h_addr;
    reg  [DW-1:0] h_din;
    wire [DW-1:0] h_dout;
    wire         busy, done;

    ntt_core #(.BF_LAT(8)) dut (
        .clk(clk), .rst(rst), .start(start), .mode(mode),
        .busy(busy), .done(done),
        .h_we(h_we), .h_addr(h_addr), .h_din(h_din), .h_dout(h_dout));

    reg [DW-1:0] x [0:N-1];      // reference input
    integer i, errors;
    reg [31:0] lcg;              // deterministic PRNG (seed fixed below)

    task automatic fill_vector(input integer t);
        integer m;
        begin
            for (m = 0; m < N; m = m + 1)
                if (t == 0) x[m] = (m*7 + 1) % Q;
                else begin
                    lcg  = lcg * 32'd1664525 + 32'd1013904223;
                    // last round-trip vector: RAW 14-bit words (may be >= q)
                    // — exercises the host-port mod-q reduction on load
                    x[m] = (t == NRT-1) ? lcg[13:0] : (lcg % Q);
                end
        end
    endtask

    // open a dump file; a failed open is fatal (never silently drop dumps)
    function automatic integer fopen_checked(input string name);
        integer f;
        begin
            f = $fopen(name, "w");
            if (f == 0) begin
                $display("FATAL: cannot open dump file %0s", name);
                $fatal(1);
            end
            fopen_checked = f;
        end
    endfunction

    task automatic dump_x(input string name);
        integer f, m;
        begin
            f = fopen_checked(name);
            for (m = 0; m < N; m = m + 1) $fdisplay(f, "%h", x[m]);
            $fclose(f);
        end
    endtask

    task automatic load_mem;
        integer m;
        begin
            for (m = 0; m < N; m = m + 1) begin
                @(posedge clk); #1;
                h_we = 1'b1; h_addr = m[AW-1:0]; h_din = x[m];
            end
            @(posedge clk); #1; h_we = 1'b0;
        end
    endtask

    task automatic run(input md);
        begin
            @(posedge clk); #1; mode = md; start = 1'b1;
            @(posedge clk); #1; start = 1'b0;
            wait (done == 1'b1);
            @(posedge clk); #1;
        end
    endtask

    // read mem[idx] through the host port (registered, 1-cycle latency)
    task automatic rd(input [AW-1:0] idx, output [DW-1:0] val);
        begin
            @(posedge clk); #1; h_addr = idx; h_we = 1'b0;
            @(posedge clk); #1;                 // a_q <= mem[idx]
            val = h_dout;
        end
    endtask

    // dump the current RAM contents through the host port
    task automatic dump_mem(input string name);
        integer f; reg [DW-1:0] vv;
        begin
            f = fopen_checked(name);
            for (i = 0; i < N; i = i + 1) begin
                rd(i[AW-1:0], vv); $fdisplay(f, "%h", vv);
            end
            $fclose(f);
        end
    endtask

    reg [DW-1:0] got;
    integer t, vec_errors;
    initial begin : main
        rst = 1; start = 0; mode = 0; h_we = 0; h_addr = 0; h_din = 0;
        errors = 0; lcg = 32'hF01D_517E;

        repeat (5) @(posedge clk); #1; rst = 0;

        // ---- round-trip vectors: NTT then INTT, back-to-back restarts ----
        for (t = 0; t < NRT; t = t + 1) begin
            fill_vector(t);
            dump_x($sformatf("ntt-core/nc_in_%0d.hex", t));
            load_mem;
            run(1'b0);      // NTT
            dump_mem($sformatf("ntt-core/nc_ntt_%0d.hex", t));
            run(1'b1);      // INTT
            vec_errors = 0;
            for (i = 0; i < N; i = i + 1) begin
                rd(i[AW-1:0], got);
                // raw inputs are reduced on load, so round-trip lands on x mod q
                if (got !== (x[i] % Q)) begin
                    if (vec_errors < 4)
                        $display("  MISMATCH t=%0d i=%0d got=%0d want=%0d",
                                 t, i, got, x[i] % Q);
                    vec_errors = vec_errors + 1;
                end
            end
            errors = errors + vec_errors;
            $display("round-trip vector %0d: %0s", t,
                     vec_errors == 0 ? "ok" : "FAIL");
        end

        // ---- INTT-only vectors: dumped for the independent golden check ----
        for (t = 0; t < NIV; t = t + 1) begin
            fill_vector(1);  // random (lcg advances each call)
            dump_x($sformatf("ntt-core/nc_iin_%0d.hex", t));
            load_mem;
            run(1'b1);      // INTT only
            dump_mem($sformatf("ntt-core/nc_intt_%0d.hex", t));
        end

        if (errors == 0)
            $display("NTT_CORE ALL PASS (%0d round-trip + %0d INTT-only vectors, N=%0d)",
                     NRT, NIV, N);
        else begin
            $display("NTT_CORE FAIL: %0d mismatches", errors);
            $fatal(1);
        end
        $finish;
    end

    // safety timeout (10 transforms ~ 7.3 ms simulated; allow ample margin)
    initial begin #50000000; $display("TIMEOUT"); $fatal(1); end
endmodule
