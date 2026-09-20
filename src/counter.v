module counter (
    input wire clk,
    input wire rst_n,
    input wire [40:0] cfg,
    input wire setval_indc,
    input wire reset_indc,

    output reg [7:0] counter_out
    );

/*
    startval,        //[40:33]
    setval,          //[32:25]
    endval,          //[24:17]
    countertype,     //[16:15]
    countby,         //[14:10]
    enable_out,      //[9:2]
    operating_vals   //[1:0]
*/
wire [7:0] startval       = cfg[40:33];
wire [7:0] setval         = cfg[32:25];
wire [7:0] endval         = cfg[24:17];
wire [1:0] countertype    = cfg[16:15];
wire [4:0] countby        = cfg[14:10];
wire [7:0] enable_out     = cfg[9:2];
wire [1:0] operating_vals = cfg[1:0];

reg rst_chain0, rst_chain1;
wire sync_rstn;

reg [7:0] count_bin;
wire [7:0] count_gray;

assign count_gray = count_bin ^ (count_bin >> 1);

//reset async assert, sync deassert
always@(posedge clk or negedge rst_n) begin 
    if (!rst_n) begin 
        rst_chain0 <= 1'b0;
        rst_chain1 <= 1'b0;
    end else begin 
        rst_chain0 <= 1'b1;
        rst_chain1 <= rst_chain0;
    end 
end
assign sync_rstn = rst_chain1;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        count_bin <= 8'h00;
    end 
    else if (!sync_rstn) begin 
        count_bin <= 8'h00;
    end 
    else begin
        if (reset_indc) begin
            count_bin <= startval;
        end else if (setval_indc) begin
            count_bin <= setval;
        end else if (operating_vals[0]) begin
            case (countertype)
                //normal upcounter
                2'b00: begin
                    if (count_bin >= endval) begin
                        count_bin <= startval;
                    end
                    else begin
                        count_bin <= count_bin + 8'd1;
                    end
                end
                //normal down counter
                2'b01: begin
                    if (count_bin <= endval) begin
                        count_bin <= startval;
                    end
                    else begin
                        count_bin <= count_bin - 8'd1;
                    end
                end
                //gray counter
                2'b10: begin
                    if (count_bin >= endval) begin
                        count_bin <= startval;
                    end
                    else begin
                        count_bin <= count_bin + 8'd1;
                    end
                end
                //count by counter
                2'b11: begin
                    if (countby[4]) begin
                        if (count_bin >= endval) begin
                            count_bin <= startval;
                        end
                        else begin 
                            count_bin <= count_bin + {4'b0000, countby[3:0]};
                        end
                    end else begin
                        if (count_bin <= endval) begin
                            count_bin <= startval;
                        end
                        else begin
                            count_bin <= count_bin - {4'b0000, countby[3:0]};
                        end 
                    end
                end
                default: begin
                    count_bin <= count_bin;
                end
            endcase
        end
    end
end

//output
always@(*) begin    
    for (integer i = 0; i < 8; i = i + 1) begin
        if (enable_out[i]) begin 
            if (countertype == 2'b10) begin 
                counter_out[i] = count_gray[i];
            end else begin 
                counter_out[i] = count_bin[i];
            end
        end else begin 
            counter_out[i] = 1'bz;
        end
    end
end
endmodule
