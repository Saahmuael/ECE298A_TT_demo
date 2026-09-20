module confinfo (
    input wire clk,
    input wire rst_n,

    input wire valid,
    input wire [2:0] addr,
    input wire [7:0] data,
    output wire ready,

    output wire [40:0] config_out,
    output wire setval_indc,
    output wire reset_indc
);

// BIG ENDIAN, MSB FIRST
// a start value (width 8)
// a set_val (width 8)
// a counter type (up, down, grey, countby x)
// a count by x value (width 5, i.e. up to 16 with sign bit)  
// an enable pins (8 for the pin enable) 

reg [7:0] startval;
reg [7:0] setval;
reg [7:0] endval;
reg [1:0] countertype; //00 up, 01 down, 10 grey, 11 countby
reg [4:0] countby; //<sign><value>
reg [7:0] enable_out;
reg [1:0] operating_vals; //[1] = reset (set to startval) [0] 1 = enable, 0 = disable (pause)

reg rst_chain0, rst_chain1;
wire sync_rstn;
reg setval_detected;
reg reset_detected;

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
        startval            <= 8'h00;
        setval              <= 8'h00;
        endval              <= 8'h00;
        countertype         <= 2'b00;
        countby             <= 5'b00000;
        enable_out          <= 8'h00;
        setval_detected     <= 1'b0;
        reset_detected      <= 1'b0;
        operating_vals      <= 2'b00;
    end else if (!sync_rstn) begin 
        startval            <= 8'h00;
        setval              <= 8'h00;
        endval              <= 8'h00;
        countertype         <= 2'b00;
        countby             <= 5'b00000;
        enable_out          <= 8'h00;
        setval_detected     <= 1'b0;
        reset_detected      <= 1'b0;
        operating_vals      <= 2'b00;
    end
    else begin 
        setval_detected <= 1'b0;
        reset_detected  <= 1'b0;
        
        if (valid) begin 
            
            case (addr)
                3'b000: begin 
                    startval <= data;
                end
                3'b001: begin 
                    setval          <= data;
                    setval_detected <= 1'b1;
                end
                3'b010: begin 
                    endval <= data;
                end
                3'b011: begin 
                    countertype <= data[7:6];
                end
                3'b100: begin 
                    countby <= data[7:3];
                end
                3'b101: begin 
                    enable_out <= data;
                end
                3'b110: begin 
                    operating_vals <= data[7:6];
                    reset_detected <= (data[7] == 1'b1) ? 1'b1 : 1'b0;
                end
                default: begin 
                end
            endcase
        end
    end 
end

assign ready = 1'b1;
assign config_out = {
    startval,        //[40:33]
    setval,          //[32:25]
    endval,          //[24:17]
    countertype,     //[16:15]
    countby,         //[14:10]
    enable_out,      //[9:2]
    operating_vals   //[1:0]
};
assign setval_indc = setval_detected;
assign reset_indc = reset_detected;
endmodule