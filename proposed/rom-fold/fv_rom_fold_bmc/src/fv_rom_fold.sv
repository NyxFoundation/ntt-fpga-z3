// RTL equivalence: the psi-fold ROM (tf_rom_fold.v, 512 stored words +
// fold7) against the SHIPPED tf_ROM.v (1023 words), for every address —
// with the KRED scaling relation 9 * Q_new == Q_ref (mod q), since the
// fold ROM stores 9^-1-scaled words for the CFNTT-KRED butterfly.
// Both are 1-cycle-registered, so compare with a $past(valid) guard.
module fv_rom_fold (
    input clk,
    input [9:0] A
);
  localparam [13:0] GQ = 14'd12289;

  wire [13:0] q_new, q_ref;
  tf_rom_fold dut (.clk(clk), .A(A), .REN(1'b1), .Q(q_new));
  tf_ROM gold (.clk(clk), .A(A), .REN(1'b1), .Q(q_ref));

  always @* assume (A < 10'd1023);

  reg [1:0] cnt = 0;
  always @(posedge clk) if (cnt < 3) cnt <= cnt + 1;

  reg [17:0] nine_new;
  always @(posedge clk) begin
    if (cnt >= 2) begin
      nine_new = {4'd0, q_new} * 18'd9;
      assert (nine_new % {4'd0, GQ} == {4'd0, q_ref});  // q_new == 9^-1 * q_ref
      assert (q_new < GQ);
    end
  end
endmodule
