// Compositional proof of the proposed butterfly compact_bf_v2 (leaf units
// abstracted per abstract_units_v2.v; justifications: fv_kred.sby and
// ../yosys/fv_units.sby).  Inputs stream every cycle through the real
// DFF/shift_4 fabric; latency 6, both modes.  With the ROM storing
// W = 9^-1 * w these RTL-level identities are exactly the true butterflies:
//
//   NTT  (sel=0): lower = u + 9vW,        upper = u - 9vW      (9vW == vw)
//   INTT (sel=1): lower = op21(u + v),
//                 upper = 9*(v-u)*op21(W)                (== ((v-u)*w)/2)
module fv_bf_v2_ntt (
    input clk,
    input [13:0] u,
    input [13:0] v,
    input [13:0] w
);
  `include "golden_v2.vh"

  wire [13:0] bf_upper, bf_lower;
  compact_bf_v2 dut (
      .clk(clk), .rst(1'b0), .sel(1'b0),
      .u(u), .v(v), .w(w),
      .bf_upper(bf_upper), .bf_lower(bf_lower)
  );

  always @* begin
    assume (u < GQ);
    assume (v < GQ);
    assume (w < GQ);
  end

  reg [3:0] cnt = 0;
  always @(posedge clk) if (cnt < 15) cnt <= cnt + 1;

  reg [13:0] m6;
  always @(posedge clk) begin
    m6 = g9mul($past(v, 6), $past(w, 6));
    if (cnt >= 7) begin
      assert (bf_lower == gadd($past(u, 6), m6));
      assert (bf_upper == gsub($past(u, 6), m6));
      assert (bf_lower < GQ);
      assert (bf_upper < GQ);
    end
  end
endmodule

module fv_bf_v2_intt (
    input clk,
    input [13:0] u,
    input [13:0] v,
    input [13:0] w
);
  `include "golden_v2.vh"

  wire [13:0] bf_upper, bf_lower;
  compact_bf_v2 dut (
      .clk(clk), .rst(1'b0), .sel(1'b1),
      .u(u), .v(v), .w(w),
      .bf_upper(bf_upper), .bf_lower(bf_lower)
  );

  always @* begin
    assume (u < GQ);
    assume (v < GQ);
    assume (w < GQ);
  end

  reg [3:0] cnt = 0;
  always @(posedge clk) if (cnt < 15) cnt <= cnt + 1;

  always @(posedge clk) begin
    if (cnt >= 7) begin
      assert (bf_lower == ghalf(gadd($past(u, 6), $past(v, 6))));
      assert (bf_upper == g9mul(gsub($past(v, 6), $past(u, 6)),
                                ghalf($past(w, 6))));
      assert (bf_lower < GQ);
      assert (bf_upper < GQ);
    end
  end
endmodule
