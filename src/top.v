module top (
    input wire clk,
    input wire rst_n,
    input wire copi,
    input wire sclk,
    input wire cs,

    output wire [7:0] counter_vals
);
wire [2:0]  addr;
wire [7:0]  dout;
wire        dout_v;
wire        conf_r;
wire [40:0] cfg;
wire        setval_indc;
wire        reset_indc;

(* keep_hierarchy *)
spi_in u_spi_in (
    .clk    (clk),
    .rst_n  (rst_n),
    .copi   (copi),
    .sclk   (sclk),
    .cs     (cs),

    .addr   (addr),
    .dout   (dout),
    .dout_v (dout_v),
    .conf_r (conf_r)
);

(* keep_hierarchy *)
confinfo u_confinfo (
    .clk        (clk),
    .rst_n      (rst_n),

    .valid      (dout_v),
    .addr       (addr),
    .data       (dout),
    .ready      (conf_r),

    .config_out (cfg),
    .setval_indc(setval_indc),
    .reset_indc (reset_indc)
);

(* keep_hierarchy *)
counter u_counter (
    .clk           (clk),
    .rst_n         (rst_n),
    .cfg           (cfg),
    .setval_indc   (setval_indc),
    .reset_indc    (reset_indc),
    .counter_out   (counter_vals)
);
    
endmodule

