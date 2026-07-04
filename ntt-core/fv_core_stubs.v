// Datapath stubs for the ntt_core FSM safety proof (fv_core.sby).
// The control-plane properties (ROM address bound, RAM write-port
// disjointness, handshake, counter invariants) are independent of the
// data values, so the verified butterfly and ROM are replaced by
// unconstrained ($anyseq) sources — this keeps the k-induction small
// and makes the proof about the FSM alone.  The real units carry their
// own proofs (fv_bf_v2_*, fv_kred, fv_rom_fold).
module compact_bf_v2 #(parameter data_width = 14)(
    input clk, rst,
    input sel,
    input [data_width-1:0] u, v, w,
    output [data_width-1:0] bf_upper, bf_lower
    );
    (* anyseq *) wire [data_width-1:0] any_u, any_l;
    assign bf_upper = any_u;
    assign bf_lower = any_l;
endmodule

module tf_rom_fold (
    input clk,
    input [9:0] A,
    input REN,
    output [13:0] Q
    );
    (* anyseq *) wire [13:0] any_q;
    assign Q = any_q;
endmodule
