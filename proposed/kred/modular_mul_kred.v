// PROPOSED replacement for cfntt_ref's modular_mul.v (Barrett, 3 hardware
// multipliers) — a K-RED reduction unit for q = 12289 = 3*2^12 + 1 that
// needs ONE multiplier (the unavoidable A*B product); the reduction itself
// is shifts and adds only, because 3*2^12 == -1 (mod q):
//
//   z  = A*B                                   28 bits
//   d  = 3*z[11:0] + 6q - z[27:12]             ≡ 3z (mod q),  0 < d < 2^17
//   e  = 3*d[11:0] +  q - d[16:12]             ≡ 9z (mod q),  0 < e < 2q
//   r  = e >= q ? e - q : e                    == 9*A*B mod q
//
// (Bounds and r == 9z mod q are z3-PROVEN over the full 28-bit domain in
// verify_kred.py; the RTL pipeline is proven against the same golden in
// fv_kred.sby.)  The output carries a factor 9: the twiddle ROM stores
// 9^-1-scaled twiddles so every butterfly multiply is EXACT — see
// kred_math.py / proposed README.
//
// Latency 4 and the port list match modular_mul.v, so it is a DROP-IN for
// compact_bf's delay fabric.  K-RED per Longa & Naehrig 2016 (known art in
// software for this q); the hardware fusion here is the proposal.
module modular_mul_kred #(parameter data_width = 14)(
    input clk, rst,
    input [data_width-1:0] A_in, B_in,
    output wire [data_width-1:0] P_out
    );

    parameter q = 14'd12289;

    reg [27:0] z_q;
    reg [16:0] d_q;
    reg [14:0] e_q;
    reg [13:0] r_q;

    // fold 1: d = 3*c0 + 6q - c1   (17-bit, never wraps: z3-proven)
    wire [11:0] c0 = z_q[11:0];
    wire [15:0] c1 = z_q[27:12];
    wire [16:0] d = ({4'd0, c0, 1'b0} + {5'd0, c0}) + 17'd73734 - {1'b0, c1};

    // fold 2: e = 3*d0 + q - d1    (15-bit, 0 < e < 2q: z3-proven)
    wire [11:0] d0 = d_q[11:0];
    wire [4:0]  d1 = d_q[16:12];
    wire [14:0] e = ({2'd0, d0, 1'b0} + {3'd0, d0}) + 15'd12289 - {10'd0, d1};

    // one conditional subtraction fully reduces
    wire [14:0] e_m = e_q - 15'd12289;
    wire [13:0] r = (e_q >= 15'd12289) ? e_m[13:0] : e_q[13:0];

    always @(posedge clk or posedge rst) begin
      if (rst) begin
        z_q <= 0; d_q <= 0; e_q <= 0; r_q <= 0;
      end else begin
        z_q <= A_in * B_in;
        d_q <= d;
        e_q <= e;
        r_q <= r;
      end
    end

    assign P_out = r_q;
endmodule
