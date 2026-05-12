/*****************************************************************************
* | File      	:   LCD_1in44.c
* | Author      :   Waveshare team
* | Function    :   Hardware underlying interface
* | Info        :
*                Used to shield the underlying layers of each master
*                and enhance portability
*----------------
* |	This version:   V1.1
* | Date        :   2023-06-05
* | Info        :   Basic version
*
******************************************************************************/
#include "LCD_1in44.h"
#include "DEV_Config.h"

#include <stdlib.h>		//itoa()
#include <stdio.h>

LCD_DIS sLCD_DIS;


/******************************************************************************
function :	Hardware reset
parameter:
******************************************************************************/
static void LCD_Reset(void)
{
    LCD_RST_1;
    DEV_Delay_ms(100);
    LCD_RST_0;
    DEV_Delay_ms(100);
    LCD_RST_1;
    DEV_Delay_ms(100);
}

/******************************************************************************
function :	send command
parameter:
     Reg : Command register
******************************************************************************/
static void LCD_SendCommand(UBYTE Reg)
{
    LCD_DC_0;
    // LCD_CS_0;
    DEV_SPI_WriteByte(Reg);
    // LCD_CS_1;
}

/******************************************************************************
function :	send data
parameter:
    Data : Write data
******************************************************************************/
static void LCD_SendData_8Bit(UBYTE Data)
{
    LCD_DC_1;
    // LCD_CS_0;
    DEV_SPI_WriteByte(Data);
    // LCD_CS_1;
}

/******************************************************************************
function :	send data
parameter:
    Data : Write data
******************************************************************************/
static void LCD_SendData_16Bit(UWORD Data)
{
    LCD_DC_1;
    // LCD_CS_0;
    DEV_SPI_WriteByte((Data >> 8) & 0xFF);
    DEV_SPI_WriteByte(Data & 0xFF);
    // LCD_CS_1;
}

/********************************************************************************
function:	Set the display scan and color transfer modes
parameter:
		Scan_dir   :   Scan direction
		Colorchose :   RGB or GBR color format
********************************************************************************/
void LCD_SetGramScanWay(LCD_SCAN_DIR Scan_dir)
{
    //Get the screen scan direction
    sLCD_DIS.LCD_Scan_Dir = Scan_dir;

    //Get GRAM and LCD width and height
    if(Scan_dir == L2R_U2D || Scan_dir == L2R_D2U || Scan_dir == R2L_U2D || Scan_dir == R2L_D2U) {
        sLCD_DIS.LCD_Dis_Column	= LCD_HEIGHT ;
        sLCD_DIS.LCD_Dis_Page = LCD_WIDTH ;
    } else {
        sLCD_DIS.LCD_Dis_Column	= LCD_WIDTH ;
        sLCD_DIS.LCD_Dis_Page = LCD_HEIGHT ;
    }

    // Gets the scan direction of GRAM
    uint16_t MemoryAccessReg_Data=0;  //0x36
    switch (Scan_dir) {
    case L2R_U2D:
        MemoryAccessReg_Data = 0X00 | 0x00;//x Scan direction | y Scan direction
        break;
    case L2R_D2U:
        MemoryAccessReg_Data = 0x00 | 0x80;//0xC8 | 0X10
        break;
    case R2L_U2D://	0X4
        MemoryAccessReg_Data = 0x40 | 0x00;
        break;
    case R2L_D2U://	0XC
        MemoryAccessReg_Data = 0x40 | 0x80;
        break;
    case U2D_L2R://0X2
        MemoryAccessReg_Data = 0X00 | 0X00 | 0x20;
        break;
    case U2D_R2L://0X6
        MemoryAccessReg_Data = 0x00 | 0X40 | 0x20;
        break;
    case D2U_L2R://0XA
        MemoryAccessReg_Data = 0x80 | 0x00 | 0x20;
        break;
    case D2U_R2L://0XE
        MemoryAccessReg_Data = 0x40 | 0x80 | 0x20;
        break;
    }

    //please set (MemoryAccessReg_Data & 0x10) != 1
    if((MemoryAccessReg_Data && 0x20) != 1) {
        sLCD_DIS.LCD_X_Adjust = LCD_X;
        sLCD_DIS.LCD_Y_Adjust = LCD_Y;
    } else {
        sLCD_DIS.LCD_X_Adjust = LCD_Y;
        sLCD_DIS.LCD_Y_Adjust = LCD_X;
    }

    // Set the read / write scan direction of the frame memory
    LCD_SendCommand(0x36); //MX, MY, RGB mode
    LCD_SendData_8Bit( MemoryAccessReg_Data | 0x08);	//0x08 set RGB


}

/******************************************************************************
function :	Initialize the lcd register
parameter:
******************************************************************************/
static void LCD_InitReg(void)
{                   
    //ST7735R Frame Rate
    LCD_SendCommand(0xB1);
    LCD_SendData_8Bit(0x01);
    LCD_SendData_8Bit(0x2C);
    LCD_SendData_8Bit(0x2D);

    LCD_SendCommand(0xB2);
    LCD_SendData_8Bit(0x01);
    LCD_SendData_8Bit(0x2C);
    LCD_SendData_8Bit(0x2D);

    LCD_SendCommand(0xB3);
    LCD_SendData_8Bit(0x01);
    LCD_SendData_8Bit(0x2C);
    LCD_SendData_8Bit(0x2D);
    LCD_SendData_8Bit(0x01);
    LCD_SendData_8Bit(0x2C);
    LCD_SendData_8Bit(0x2D);

    LCD_SendCommand(0xB4); //Column inversion
    LCD_SendData_8Bit(0x07);

    //ST7735R Power Sequence
    LCD_SendCommand(0xC0);
    LCD_SendData_8Bit(0xA2);
    LCD_SendData_8Bit(0x02);
    LCD_SendData_8Bit(0x84);
    LCD_SendCommand(0xC1);
    LCD_SendData_8Bit(0xC5);

    LCD_SendCommand(0xC2);
    LCD_SendData_8Bit(0x0A);
    LCD_SendData_8Bit(0x00);

    LCD_SendCommand(0xC3);
    LCD_SendData_8Bit(0x8A);
    LCD_SendData_8Bit(0x2A);
    LCD_SendCommand(0xC4);
    LCD_SendData_8Bit(0x8A);
    LCD_SendData_8Bit(0xEE);

    LCD_SendCommand(0xC5); //VCOM
    LCD_SendData_8Bit(0x0E);

    //ST7735R Gamma Sequence
    LCD_SendCommand(0xe0);
    LCD_SendData_8Bit(0x0f);
    LCD_SendData_8Bit(0x1a);
    LCD_SendData_8Bit(0x0f);
    LCD_SendData_8Bit(0x18);
    LCD_SendData_8Bit(0x2f);
    LCD_SendData_8Bit(0x28);
    LCD_SendData_8Bit(0x20);
    LCD_SendData_8Bit(0x22);
    LCD_SendData_8Bit(0x1f);
    LCD_SendData_8Bit(0x1b);
    LCD_SendData_8Bit(0x23);
    LCD_SendData_8Bit(0x37);
    LCD_SendData_8Bit(0x00);
    LCD_SendData_8Bit(0x07);
    LCD_SendData_8Bit(0x02);
    LCD_SendData_8Bit(0x10);

    LCD_SendCommand(0xe1);
    LCD_SendData_8Bit(0x0f);
    LCD_SendData_8Bit(0x1b);
    LCD_SendData_8Bit(0x0f);
    LCD_SendData_8Bit(0x17);
    LCD_SendData_8Bit(0x33);
    LCD_SendData_8Bit(0x2c);
    LCD_SendData_8Bit(0x29);
    LCD_SendData_8Bit(0x2e);
    LCD_SendData_8Bit(0x30);
    LCD_SendData_8Bit(0x30);
    LCD_SendData_8Bit(0x39);
    LCD_SendData_8Bit(0x3f);
    LCD_SendData_8Bit(0x00);
    LCD_SendData_8Bit(0x07);
    LCD_SendData_8Bit(0x03);
    LCD_SendData_8Bit(0x10);

    LCD_SendCommand(0xF0); //Enable test command
    LCD_SendData_8Bit(0x01);

    LCD_SendCommand(0xF6); //Disable ram power save mode
    LCD_SendData_8Bit(0x00);

    LCD_SendCommand(0x3A); //65k mode
    LCD_SendData_8Bit(0x05);  
     
}

/********************************************************************************
function :	Initialize the lcd
parameter:
********************************************************************************/
void LCD_1in44_Init(LCD_SCAN_DIR Scan_dir)
{
    //Turn on the backlight
    LCD_BL_1;

    //Hardware reset
    LCD_Reset();

    //Set the initialization register
    LCD_InitReg();

    //Set the resolution and scanning method of the screen
    LCD_SetGramScanWay(Scan_dir);
    DEV_Delay_ms(100);

    //sleep out
    LCD_SendCommand(0x11);
    DEV_Delay_ms(120);

    //Turn on the LCD display
    LCD_SendCommand(0x29);

}

/********************************************************************************
function:	Sets the start position and size of the display area
parameter:
		Xstart 	:   X direction Start coordinates
		Ystart  :   Y direction Start coordinates
		Xend    :   X direction end coordinates
		Yend    :   Y direction end coordinates
********************************************************************************/
void LCD_1in44_SetWindows(UWORD Xstart, UWORD Ystart, UWORD Xend, UWORD Yend)
{
    //set the X coordinates
    LCD_SendCommand ( 0x2A );
    LCD_SendData_8Bit ( 0x00 );						//Set the horizontal starting point to the high octet
    LCD_SendData_8Bit ( (Xstart & 0xff) + sLCD_DIS.LCD_X_Adjust);			//Set the horizontal starting point to the low octet
    LCD_SendData_8Bit ( 0x00 );				//Set the horizontal end to the high octet
    LCD_SendData_8Bit ( (( Xend - 1 ) & 0xff) + sLCD_DIS.LCD_X_Adjust);	//Set the horizontal end to the low octet

    //set the Y coordinates
    LCD_SendCommand ( 0x2B );
    LCD_SendData_8Bit ( 0x00 );
    LCD_SendData_8Bit ( (Ystart & 0xff) + sLCD_DIS.LCD_Y_Adjust);
    LCD_SendData_8Bit ( 0x00 );
    LCD_SendData_8Bit ( ( (Yend - 1) & 0xff )+ sLCD_DIS.LCD_Y_Adjust);

    LCD_SendCommand(0x2C);
}

/******************************************************************************
function :	Clear screen
parameter:
******************************************************************************/
void LCD_1in44_Clear(UWORD Color)
{
    UWORD j;
    UWORD Image[LCD_WIDTH*LCD_HEIGHT];
    
    Color = ((Color<<8)&0xff00)|(Color>>8);
   
    for (j = 0; j < LCD_HEIGHT*LCD_WIDTH; j++) {
        Image[j] = Color;
    }
    
    LCD_1in44_SetWindows(0, 0, LCD_WIDTH, LCD_HEIGHT);
    LCD_DC_1;
    for(j = 0; j < LCD_HEIGHT; j++){
        DEV_SPI_Write_nByte((uint8_t *)&Image[j*LCD_WIDTH], LCD_WIDTH*2);
    }
}

/******************************************************************************
function :	Sends the image buffer in RAM to displays
parameter:
******************************************************************************/
void LCD_1in44_Display(UWORD *Image)
{
    UWORD j;
    LCD_1in44_SetWindows(0, 0, LCD_WIDTH, LCD_HEIGHT);
    LCD_DC_1;
    for (j = 0; j < LCD_HEIGHT; j++) {
        DEV_SPI_Write_nByte((uint8_t *)&Image[j*LCD_WIDTH], LCD_WIDTH*2);
    }
}

void LCD_1in44_DisplayWindows(UWORD Xstart, UWORD Ystart, UWORD Xend, UWORD Yend, UWORD *Image)
{
    // display
    UDOUBLE Addr = 0;

    UWORD j;
    LCD_1in44_SetWindows(Xstart, Ystart, Xend-1 , Yend-1);
    LCD_DC_1;
    for (j = Ystart; j < Yend - 1; j++) {
        Addr = Xstart + j * LCD_WIDTH ;
        DEV_SPI_Write_nByte((uint8_t *)&Image[Addr], (Xend-Xstart-1)*2);
    }
}

void LCD_1in44_DisplayPoint(UWORD X, UWORD Y, UWORD Color)
{
    LCD_1in44_SetWindows(X,Y,X,Y);
    LCD_SendData_16Bit(Color);
}

void  Handler_1in44_LCD(int signo)
{
    //System Exit
    printf("\r\nHandler:Program stop\r\n");     
    DEV_ModuleExit();
    exit(0);
}
