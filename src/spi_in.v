module spi_in (
    input wire clk,
    input wire rst_n,
    input wire copi,
    input wire sclk,
    input wire cs,
    
    output reg [2:0] addr,
    output reg [7:0] dout,
    output reg dout_v,
    input wire conf_r
);
//Note, clk >> SCLK
//we assume all SPI input frames hold the following data
//<ADDR, 3 BIT><DATA, 8 bits>
//we assume the SPI input is fed in big endian order, that is MSB first, LSB last
//SPI output is big endian
//for configs targeting regs that arent 8 bits wide, LSB are discarded
//data is output after 11 bits have been received

reg posedge0, posedge1, posedge2; //posedge0 is used to CDC. posedge1 out is assumed to be stable
reg dat0, dat1; //dat0, 1 is used to CDC. dat2 is for posedge synchronization
reg cs0, cs1;

reg dvalid_internal;
reg rst_chain0, rst_chain1;
reg [10:0] shiftin;
wire sync_rstn;
reg [3:0] counter;
reg word_complete;

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

always @(posedge clk or negedge sync_rstn) begin
    if (!sync_rstn) begin 
        shiftin <= {11{1'b0}};
        counter <= 4'b0000;

        dvalid_internal <= 1'b0;

        posedge0 <= 1'b1;
        posedge1 <= 1'b1;
        posedge2 <= 1'b1;

        dat0 <= 1'b1;
        dat1 <= 1'b1;

        cs0 <= 1'b1;
        cs1 <= 1'b1;


    end else begin 

        //track POSEDGE transition of SCLK
        posedge0 <= sclk;
        posedge1 <= posedge0;
        posedge2 <= posedge1;

        dat0 <= copi;
        dat1 <= dat0;

        cs0 <= cs;
        cs1 <= cs0;

        if (cs1 == 0) begin
            if (posedge1 && !posedge2) begin 
                shiftin[0] <= dat1;
                for (integer i = 1; i <= 10; i = i + 1) begin 
                    shiftin[i] <= shiftin[i-1];
                end

                if (counter != 4'd10) begin 
                    counter <= counter + 1;
                end else begin 
                    counter <= 4'd0;
                end
            end
        end else begin 
            counter <= 4'd0;
        end

        if (counter == 4'd10 && (posedge1 && !posedge2)) begin 
            dvalid_internal <= 1'b1;
        end else begin 
            if (dvalid_internal && conf_r) begin 
                dvalid_internal <= 1'b0;
            end
        end
    end
end

always@(*) begin 
    word_complete = (counter == 4'd10) && (posedge1 && !posedge2);
    dout_v = word_complete | dvalid_internal;
    addr = shiftin[10:8];
    dout = shiftin[7:0];
end

endmodule