`timescale 1ns/1ps
module tb_kyber;
  reg clk=0,rst; always #5 clk=~clk;
  reg [11:0] A,B; wire [11:0] P;
  modular_mul_kred_kyber dut(.clk(clk),.rst(rst),.A_in(A),.B_in(B),.P_out(P));
  integer i,errs; reg [11:0] Aq[0:3],Bq[0:3];
  reg [11:0] ta[0:99999], tb[0:99999]; integer NT;
  initial begin
    rst=1; A=0; B=0; errs=0;
    // load test vectors from file (python-generated: edges + random)
    $readmemh("ky_a.hex", ta); $readmemh("ky_b.hex", tb);
    NT=0; while (NT<100000 && ta[NT]!==12'hxxx) NT=NT+1;
    repeat(4) @(posedge clk); rst=0;
    for (i=0;i<NT+4;i=i+1) begin
      A = (i<NT)? ta[i] : 12'd0;
      B = (i<NT)? tb[i] : 12'd0;
      Aq[0]=A; Bq[0]=B;
      @(posedge clk); #1;
      if (i>=3 && (i-3)<NT) begin
        if ((169*Aq[3]*Bq[3]) % 3329 != P) begin
          if (errs<3) $display("MISMATCH a=%0d b=%0d got=%0d want=%0d",Aq[3],Bq[3],P,(169*Aq[3]*Bq[3])%3329);
          errs=errs+1;
        end
      end
      Aq[3]=Aq[2];Aq[2]=Aq[1];Aq[1]=Aq[0];
      Bq[3]=Bq[2];Bq[2]=Bq[1];Bq[1]=Bq[0];
    end
    if (errs==0) $display("KYBER_RTL_PASS n=%0d",NT); else $display("FAILS=%0d",errs);
    $finish;
  end
endmodule
