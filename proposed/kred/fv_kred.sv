// RTL proof of the proposed modular_mul_kred: with reduced inputs streaming
// every cycle, P_out at time t == (9 * A * B) mod q sampled 4 cycles
// earlier, and the output stays < q.  Also: rst forces P_out to 0.
//
// (Same complete-BMC structure as ../yosys/fv_modular_mul.sv: time-local
// assertions + unconstrained initial state => depth guard+4+1 covers every
// window of every execution.)
module fv_kred (
    input clk,
    input [13:0] A,
    input [13:0] B
);
  localparam [13:0] GQ = 14'd12289;

  wire [13:0] P;
  modular_mul_kred dut (.clk(clk), .rst(1'b0), .A_in(A), .B_in(B), .P_out(P));

  always @* begin
    assume (A < GQ);
    assume (B < GQ);
  end

  reg [3:0] cnt = 0;
  always @(posedge clk) if (cnt < 15) cnt <= cnt + 1;

  // Golden: the K-RED fold spec, written width-exactly in the SAME shape as
  // verify_kred.py's z3 model.  That z3 proof establishes fold(z) == 9z mod q
  // for EVERY 28-bit z, so this task only has to prove the RTL pipeline
  // computes the fold at latency 4 — the compositional chain
  //   sby: RTL == fold      z3: fold == 9z mod q
  // gives RTL == (9*A*B) mod q without re-bit-blasting a divider here.
  function [13:0] gkred(input [27:0] z);
    reg [16:0] d;
    reg [14:0] e;
    begin
      d = ({4'd0, z[11:0], 1'b0} + {5'd0, z[11:0]}) + 17'd73734
          - {1'b0, z[27:12]};
      e = ({2'd0, d[11:0], 1'b0} + {3'd0, d[11:0]}) + 15'd12289
          - {10'd0, d[16:12]};
      gkred = (e >= 15'd12289) ? e - 15'd12289 : e[13:0];
    end
  endfunction

  reg [27:0] z6;
  always @(posedge clk) begin
    if (cnt >= 5) begin
      z6 = $past(A, 4) * $past(B, 4);
      assert (P == gkred(z6));    // latency-4 == the z3-proven fold
      assert (P < GQ);            // output stays reduced
    end
  end
endmodule

// rst behaviour, from ANY state (own top, tiny)
module fv_kred_rst (
    input clk,
    input rst,
    input [13:0] A,
    input [13:0] B
);
  wire [13:0] P;
  modular_mul_kred dut (.clk(clk), .rst(rst), .A_in(A), .B_in(B), .P_out(P));
  always @* if (rst) assert (P == 14'd0);
endmodule
