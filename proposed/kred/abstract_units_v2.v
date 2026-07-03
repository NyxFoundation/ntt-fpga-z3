// Behavioural abstractions for compositional verification of compact_bf_v2
// (assume-guarantee; each justified by a dedicated RTL proof):
//   modular_mul_kred     == (9*A*B) mod q, latency 4   <- fv_kred.sby
//   modular_add          == (x+y) mod q                <- ../yosys/fv_units.sby
//   modular_substraction == (x-y) mod q                <- ../yosys/fv_units.sby
//   modular_half         == x*2^-1 mod q (op21 shape)  <- ../yosys/fv_units.sby

module modular_mul_kred #(parameter data_width = 14)(
    input clk, rst,
    input [data_width-1:0] A_in, B_in,
    output wire [data_width-1:0] P_out
    );
    parameter q = 14'd12289;
    reg [data_width-1:0] s1, s2, s3, s4;
    wire [31:0] p9 = {18'd0, A_in} * {18'd0, B_in} * 32'd9;
    always @(posedge clk or posedge rst) begin
      if (rst) begin s1 <= 0; s2 <= 0; s3 <= 0; s4 <= 0; end
      else begin s1 <= p9 % q; s2 <= s1; s3 <= s2; s4 <= s3; end
    end
    assign P_out = s4;
endmodule

module modular_add #(parameter data_width = 14)(
    input [data_width-1:0] x_add, y_add,
    output [data_width-1:0] z_add
    );
    parameter M = 12289;
    wire [data_width:0] s = x_add + y_add;
    assign z_add = (s >= M) ? s - M : s[data_width-1:0];
endmodule

module modular_substraction #(parameter data_width = 14)(
    input [data_width-1:0] x_sub, y_sub,
    output [data_width-1:0] z_sub
    );
    parameter M = 12289;
    assign z_sub = (x_sub >= y_sub) ? x_sub - y_sub : (x_sub + M) - y_sub;
endmodule

module modular_half #(parameter data_width = 14)(
    input [data_width-1:0] x_half,
    output [data_width-1:0] y_half
    );
    assign y_half = x_half[0] ? (x_half >> 1) + 14'd6145 : (x_half >> 1);
endmodule
