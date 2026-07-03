// Golden operators for the v2 (K-RED) harnesses.  g9mul/ghalf are written
// in the SAME expression shape as the behavioural abstractions so the DUT
// and golden terms hash structurally equal in the SMT encoding.
localparam [13:0] GQ = 14'd12289;

function [13:0] gadd(input [13:0] a, input [13:0] b);
  reg [14:0] s;
  begin
    s = a + b;
    gadd = (s >= GQ) ? s - GQ : s[13:0];
  end
endfunction

function [13:0] gsub(input [13:0] a, input [13:0] b);
  gsub = (a >= b) ? a - b : (a + GQ) - b;
endfunction

function [13:0] g9mul(input [13:0] a, input [13:0] b);
  reg [31:0] p9;
  begin
    p9 = {18'd0, a} * {18'd0, b} * 32'd9;
    g9mul = p9 % GQ;
  end
endfunction

function [13:0] ghalf(input [13:0] a);
  ghalf = a[0] ? (a >> 1) + 14'd6145 : (a >> 1);
endfunction
