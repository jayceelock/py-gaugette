#----------------------------------------------------------------------
# ssd1306.py from https://github.com/guyc/py-gaugette
# ported by Guy Carpenter, Clearwater Software
#
# This library works with 
#   Adafruit's 128x32 SPI monochrome OLED   http://www.adafruit.com/products/661
#   Adafruit's 128x64 SPI monochrome OLED   http://www.adafruit.com/products/326
# it should work with other SSD1306-based displays.
# The datasheet for the SSD1306 is available
#   http://www.adafruit.com/datasheets/SSD1306.pdf
#
# The code is based heavily on Adafruit's Arduino library
#   https://github.com/adafruit/Adafruit_SSD1306
# written by Limor Fried/Ladyada for Adafruit Industries.
#
# Some important things to know about this device and SPI:
#
# - The SPI interface has no MISO connection.  It is write-only.
#
# - The spidev xfer and xfer2 calls overwrite the output buffer
#   with the bytes read back in during the SPI transfer.
#   Use writebytes instead of xfer to avoid having your buffer overwritten.
#
# - The D/C (Data/Command) line is used to distinguish data writes
#   and command writes - HIGH for data, LOW for commands.  To be clear,
#   the attribute bytes following a command opcode are NOT considered data,
#   data in this case refers only to the display memory buffer.
#   keep D/C LOW for the command byte including any following argument bytes.
#   Pull D/C HIGH only when writting to the display memory buffer.
#   
# SPI and GPIO calls are made through an abstraction library that calls
# the appropriate library for the platform.
# For the RaspberryPi:
#     wiring2
#     spidev
# For the BeagleBone Black:
#     Adafruit_BBIO.SPI 
#     Adafruit_BBIO.GPIO
#
# - The pin connections between the BeagleBone Black SPI0 and OLED module are:
#
#      BBB    SSD1306
#      P9_17  -> CS
#      P9_15  -> RST   (arbirary GPIO, change at will)
#      P9_13  -> D/C   (arbirary GPIO, change at will)
#      P9_22  -> CLK
#      P9_18  -> DATA
#      P9_3   -> VIN
#      N/C    -> 3.3Vo
#      P9_1   -> GND
#----------------------------------------------------------------------

import gaugette.gpio
import gaugette.spi
import gaugette.font5x8
import time
import sys

class SSD1351:

    # Class constants are externally accessible as gaugette.ssd1351.SSD1351.CONST
    # or my_instance.CONST

    DELAYS_HWFILL = 3
    DELAYS_HWLINE = 1

    # SSD1351 Commands
    CMD_SETCOLUMN          = 0x15
    CMD_SETROW             = 0x75
    CMD_WRITERAM           = 0x5C
    CMD_READRAM            = 0x5D
    CMD_SETREMAP           = 0xA0
    CMD_STARTLINE          = 0xA1
    CMD_DISPLAYOFFSET      = 0xA2
    CMD_DISPLAYALLOFF      = 0xA4
    CMD_DISPLAYALLON       = 0xA5
    CMD_NORMALDISPLAY      = 0xA6
    CMD_INVERTDISPLAY      = 0xA7
    CMD_FUNCTIONSELECT     = 0xAB
    CMD_DISPLAYOFF         = 0xAE
    CMD_DISPLAYON          = 0xAF
    CMD_PRECHARGE          = 0xB1
    CMD_DISPLAYENHANCE     = 0xB2
    CMD_CLOCKDIV           = 0xB3
    CMD_SETVSL             = 0xB4
    CMD_SETGPIO            = 0xB5
    CMD_PRECHARGE2         = 0xB6
    CMD_SETGRAY            = 0xB8
    CMD_USELUT             = 0xB9
    CMD_PRECHARGELEVEL     = 0xBB
    CMD_VCOMH              = 0xBE
    CMD_CONTRASTABC        = 0xC1
    CMD_CONTRASTMASTER     = 0xC7
    CMD_MUXRATIO           = 0xCA
    CMD_COMMANDLOCK        = 0xFD
    CMD_HORIZSCROLL        = 0x96
    CMD_STOPSCROLL         = 0x9E
    CMD_STARTSCROLL        = 0x9F

    SSD1351WIDTH           = 128
    SSD1351HEIGHT           = 128

    # Device name will be /dev/spidev-{bus}.{device}
    # dc_pin is the data/commmand pin.  This line is HIGH for data, LOW for command.
    # We will keep d/c low and bump it high only for commands with data
    # reset is normally HIGH, and pulled LOW to reset the display

    def __init__(self, bus=0, device=0, dc_pin="P9_15", reset_pin="P9_13", buffer_rows=128, buffer_cols=128, rows=32, cols=128):
        self.cols = cols
        self.rows = rows
        self.buffer_rows = buffer_rows
        self.mem_bytes = self.buffer_rows * self.cols / 8 # total bytes in SSD1306 display ram
        self.dc_pin = dc_pin
        self.reset_pin = reset_pin
        self.spi = gaugette.spi.SPI(bus, device)
        self.spi.mode = 3 # necessary!
        self.gpio = gaugette.gpio.GPIO()
        self.gpio.setup(self.reset_pin, self.gpio.OUT)
        self.gpio.output(self.reset_pin, self.gpio.HIGH)
        self.gpio.setup(self.dc_pin, self.gpio.OUT)
        self.gpio.output(self.dc_pin, self.gpio.LOW)
        self.font = gaugette.font5x8.Font5x8
        self.col_offset = 0
        self.bitmap = self.SimpleBitmap(buffer_cols, buffer_rows)
        self.flipped = False

    def reset(self):
        self.gpio.output(self.reset_pin, self.gpio.LOW)
        time.sleep(0.010) # 10ms
        self.gpio.output(self.reset_pin, self.gpio.HIGH)

    def command(self, cmd, cmddata=None):
        # already low
        #self.gpio.output(self.dc_pin, self.gpio.LOW)

        if type(cmd) == list:
            self.spi.writebytes(cmd)
        else:
            self.spi.writebytes([cmd])

        if cmddata != None:
            if type(cmddata) == list:
                self.data(cmddata)
            else:
                self.data([cmddata])

    def data(self, bytes):
        self.gpio.output(self.dc_pin, self.gpio.HIGH)
        #  chunk data to work around 255 byte limitation in adafruit implementation of writebytes
        # revisit - change to 1024 when Adafruit_BBIO is fixed.
        max_xfer = 255 if gaugette.platform == 'beaglebone' else 1024
        start = 0
        remaining = len(bytes)
        while remaining>0:
            count = remaining if remaining <= max_xfer else max_xfer
            remaining -= count
            self.spi.writebytes(bytes[start:start+count])
            start += count
        self.gpio.output(self.dc_pin, self.gpio.LOW)
        
    def begin(self):
        time.sleep(0.001) # 1ms
        self.reset()

        self.command(self.CMD_COMMANDLOCK, 0x12) # Unlock OLED driver IC MCU interface from entering command
        self.command(self.CMD_COMMANDLOCK, 0xB1) # Command A2,B1,B3,BB,BE,C1 accessible if in unlock state 
        self.command(self.CMD_DISPLAYOFF)
        self.command([self.CMD_CLOCKDIV, 0xF1]) # 7:4 = Oscillator Frequency, 3:0 = CLK Div Ratio (A[3:0]+1 = 1..16)
        self.command(self.CMD_MUXRATIO, 127)
        self.command(self.CMD_SETREMAP, 0x74)
        self.command(self.CMD_SETCOLUMN, [0x00, 0x7F])
        self.command(self.CMD_SETROW, [0x00, 0x7F])
        self.command(self.CMD_STARTLINE, 0x00)
        self.command(self.CMD_DISPLAYOFFSET, 0x00)
        self.command(self.CMD_SETGPIO, 0x00)
        self.command(self.CMD_FUNCTIONSELECT, 0x01)
        self.command([self.CMD_PRECHARGE, 0x32])
        self.command([self.CMD_VCOMH, 0x05])
        self.command(self.CMD_NORMALDISPLAY)
        self.command(self.CMD_CONTRASTABC, [0xC8, 0x80, 0xC8])
        self.command(self.CMD_CONTRASTMASTER, 0x0F)
        self.command(self.CMD_SETVSL, [0xA0, 0xB5, 0x55])
        self.command(self.CMD_PRECHARGE2, 0x01)
        self.command(self.CMD_DISPLAYON)
        
    def clear_display(self):
        self.bitmap.clear()

    def invert_display(self):
        self.command(self.CMD_INVERTDISPLAY)

    def flip_display(self, flipped=True):
        self.flipped = flipped
        if flipped:
            self.command(self.COM_SCAN_INC)
            self.command(self.SEG_REMAP | 0x00)
        else:
            self.command(self.COM_SCAN_DEC)
            self.command(self.SET_COM_PINS, 0x02)

    def normal_display(self):
        self.command(self.CMD_NORMALDISPLAY)

    def set_contrast(self, contrast=0x7f):
        self.command(self.SET_CONTRAST, contrast)

    def goTo(self, x, y):
        if x >= self.SSD1351WIDTH or y >= self.SSD1351HEIGHT:
            return
  
        # set x and y coordinate
        self.command(self.CMD_SETCOLUMN, [x, self.SSD1351WIDTH-1])
        self.command(self.CMD_SETROW, [y, self.SSD1351HEIGHT-1])
        self.command(self.CMD_WRITERAM)

    def scale(self, x, inLow, inHigh, outLow, outHigh):
        return ((x - inLow) / float(inHigh) * outHigh) + outLow;

    def encode_color(self, color):
        red = (color >> 16) & 0xFF
        green = (color >> 8) & 0xFF
        blue = color & 0xFF

        redScaled = int(self.scale(red, 0, 0xFF, 0, 0x1F))
        greenScaled = int(self.scale(green, 0, 0xFF, 0, 0x3F))
        blueScaled = int(self.scale(blue, 0, 0xFF, 0, 0x1F))

        # print color, redScaled, greenScaled, blueScaled
        
        return (((redScaled << 6) | greenScaled) << 5) | blueScaled
            
    def color565(self, r, g, b): # ints
        c = r >> 3
        c <<= 6
        c |= g >> 2
        c <<= 5
        c |= b >> 3
        return c

    def fillScreen(self, fillcolor): # int
        self.fillRect(0, 0, self.SSD1351WIDTH, self.SSD1351HEIGHT, self.encode_color(fillcolor))

    def fillRect(self, x, y, w, h, fillcolor):
        # Bounds check
        if x >= self.SSD1351WIDTH or y >= self.SSD1351HEIGHT:
            return

        if y+h > self.SSD1351HEIGHT:
            h = self.SSD1351HEIGHT - y - 1

        if x+w > self.SSD1351WIDTH:
            w = self.SSD1351WIDTH - x - 1

        # set location
        self.command(self.CMD_SETCOLUMN, [x, x+w-1])
        self.command(self.CMD_SETROW, [y, y-h-1])
        # fill!
        self.command(self.CMD_WRITERAM)

        fillcolor = self.encode_color(fillcolor)

        self.data([fillcolor >> 8, fillcolor] * (w*h))

    def drawPixel(self, x, y, color):
        if x >= self.SSD1351WIDTH or y >= self.SSD1351HEIGHT:
            return

        if x < 0 or y < 0:
            return

        color = self.encode_color(color)

        # set location
        self.goTo(x, y)
        self.data([color >> 8, color])

    def drawBitmap(self, x, y, bitmap):
        h = len(bitmap)
        w = len(bitmap[0])

        self.command(self.CMD_SETCOLUMN, [x, w])
        self.command(self.CMD_SETROW, [y, h])
        self.command(self.CMD_WRITERAM)

        pixels = []

        for r in range(y, y+h):
            if len(pixels) + 4*w >= 1024:
                print "pixels!", pixels
                self.data(pixels)
                pixels = []

            for x in bitmap[r]:
                pixels = pixels + [(x >> 8) & 0xFF, x & 0xFF]

        print "pixels!", pixels
        self.data(pixels)

    # Diagnostic print of the memory buffer to stdout 
    def dump_buffer(self):
        self.bitmap.dump()

    def draw_text(self, x, y, string, color=0xFFFFFF):
        font_bytes = self.font.bytes
        font_rows = self.font.rows
        font_cols = self.font.cols

        for c in string:
            p = ord(c) * font_cols
            for col in range(font_cols):
                mask = font_bytes[p]
                p += 1
                for row in range(8):
                    if (mask & 1) != 0:
                        # self.drawPixel(x, y+row, self.encode_color(color))
                        self.bitmap.draw_pixel(x, y+row, self.encode_color(color))
                    else:
                        # self.drawPixel(x, y+row, 0)
                        self.bitmap.draw_pixel(x, y+row, 0)
                    mask >>= 1
                x += 1

    def draw_text2(self, x, y, string, color=0xFFFFFF, size=2, space=1):
        font_bytes = self.font.bytes
        font_rows = self.font.rows
        font_cols = self.font.cols
        for c in string:
            p = ord(c) * font_cols
            for col in range(0,font_cols):
                mask = font_bytes[p]
                p+=1
                py = y
                for row in range(0,8):
                    for sy in range(0,size):
                        px = x
                        for sx in range(0,size):
                            if mask & 1:
                                self.bitmap.draw_pixel(px, py, self.encode_color(color))
                            else:
                                self.bitmap.draw_pixel(px, py, 0)
                            px += 1
                        py += 1
                    mask >>= 1
                x += size
            x += space

    def clear_block(self, x0,y0,dx,dy):
        self.bitmap.clear_block(x0,y0,dx,dy)
        
    def draw_text3(self, x, y, string, font):
        return self.bitmap.draw_text(x,y,string,font)

    def text_width(self, string, font):
        return self.bitmap.text_width(string, font)

    class SimpleBitmap:
        def __init__(self, cols, rows):
            self.rows = rows
            self.cols = cols
            print rows, cols
            self.data = [([0] * self.cols) for i in range(self.rows)]
    
        def clear(self):
            for r in range(len(self.data)):
                for c in range(len(self.data[r])):
                    self.data[r][c] = 0

        # Diagnostic print of the memory buffer to stdout 
        def dump(self):
            for row in self.data:
                for col in row:
                    sys.stdout.write('X' if col else '.')
                sys.stdout.write('\n')

        def draw_pixel(self, x, y, color):
            if (x<0 or x>=self.cols or y<0 or y>=self.rows):
                return

            self.data[y][x] = color
    
        def clear_block(self, x0,y0,dx,dy):
            for x in range(x0,x0+dx):
                for y in range(y0,y0+dy):
                    self.draw_pixel(x,y,0)

        def display(self, ssd1351):
            ssd1351.command(ssd1351.CMD_SETCOLUMN, [0, ssd1351.SSD1351WIDTH])
            ssd1351.command(ssd1351.CMD_SETROW, [0, ssd1351.SSD1351HEIGHT])
            ssd1351.command(ssd1351.CMD_WRITERAM)

            pixels = []

            ## something is wrong in here... not sure what!

            for r in range(ssd1351.SSD1351WIDTH):
                if len(pixels) + ssd1351.SSD1351HEIGHT >= 513: # dump it out!
                    print "pixels!", pixels
                    ssd1351.data(pixels)
                    pixels = []

                pixels = pixels + self.data[r]

            print "pixels!", pixels
            ssd1351.data(pixels)

    # class Bitmap:
    
    #     # Pixels are stored in column-major order!
    #     # This makes it easy to reference a vertical slice of the display buffer
    #     # and we use the to achieve reasonable performance vertical scrolling 
    #     # without hardware support.
    #     def __init__(self, cols, rows):
    #         self.rows = rows
    #         self.cols = cols
    #         self.bytes_per_col = rows / 8
    #         self.data = [0] * (self.cols * self.bytes_per_col)
    
    #     def clear(self):
    #         for i in range(0,len(self.data)):
    #             self.data[i] = 0

    #     # Diagnostic print of the memory buffer to stdout 
    #     def dump(self):
    #         for y in range(0, self.rows):
    #             mem_row = y/8
    #             bit_mask = 1 << (y % 8)
    #             line = ""
    #             for x in range(0, self.cols):
    #                 mem_col = x
    #                 offset = mem_row + self.rows/8 * mem_col
    #                 if self.data[offset] & bit_mask:
    #                     line += '*'
    #                 else:
    #                     line += ' '
    #             print('|'+line+'|')
                
    #     def draw_pixel(self, x, y, on=True):
    #         if (x<0 or x>=self.cols or y<0 or y>=self.rows):
    #             return
    #         mem_col = x
    #         mem_row = y / 8
    #         bit_mask = 1 << (y % 8)
    #         offset = mem_row + self.rows/8 * mem_col
    
    #         if on:
    #             self.data[offset] |= bit_mask
    #         else:
    #             self.data[offset] &= (0xFF - bit_mask)
    
    #     def clear_block(self, x0,y0,dx,dy):
    #         for x in range(x0,x0+dx):
    #             for y in range(y0,y0+dy):
    #                 self.draw_pixel(x,y,0)

    #     # returns the width in pixels of the string allowing for kerning & interchar-spaces
    #     def text_width(self, string, font):
    #         x = 0
    #         prev_char = None
    #         for c in string:
    #             if (c<font.start_char or c>font.end_char):
    #                 if prev_char != None:
    #                     x += font.space_width + prev_width + font.gap_width
    #                 prev_char = None
    #             else:
    #                 pos = ord(c) - ord(font.start_char)
    #                 (width,offset) = font.descriptors[pos]
    #                 if prev_char != None:
    #                     x += font.kerning[prev_char][pos] + font.gap_width
    #                 prev_char = pos
    #                 prev_width = width
                    
    #         if prev_char != None:
    #             x += prev_width
                
    #         return x
              
    #     def draw_text(self, x, y, string, font):
    #         height = font.char_height
    #         prev_char = None
    
    #         for c in string:
    #             if (c<font.start_char or c>font.end_char):
    #                 if prev_char != None:
    #                     x += font.space_width + prev_width + font.gap_width
    #                 prev_char = None
    #             else:
    #                 pos = ord(c) - ord(font.start_char)
    #                 (width,offset) = font.descriptors[pos]
    #                 if prev_char != None:
    #                     x += font.kerning[prev_char][pos] + font.gap_width
    #                 prev_char = pos
    #                 prev_width = width
                    
    #                 bytes_per_row = (width + 7) / 8
    #                 for row in range(0,height):
    #                     py = y + row
    #                     mask = 0x80
    #                     p = offset
    #                     for col in range(0,width):
    #                         px = x + col
    #                         if (font.bitmaps[p] & mask):
    #                             self.draw_pixel(px,py,1)  # for kerning, never draw black
    #                         mask >>= 1
    #                         if mask == 0:
    #                             mask = 0x80
    #                             p+=1
    #                     offset += bytes_per_row
              
    #         if prev_char != None:
    #             x += prev_width
    
    #         return x

    # # This is a helper class to display a scrollable list of text lines.
    # # The list must have at least 1 item.
    # class ScrollingList:
    #     def __init__(self, ssd1306, list, font):
    #         self.ssd1306 = ssd1306
    #         self.list = list
    #         self.font = font
    #         self.position = 0 # row index into list, 0 to len(list) * self.rows - 1
    #         self.offset = 0   # led hardware scroll offset
    #         self.pan_row = -1
    #         self.pan_offset = 0
    #         self.pan_direction = 1
    #         self.bitmaps = []
    #         self.rows = ssd1306.rows
    #         self.cols = ssd1306.cols
    #         self.bufrows = self.rows * 2
    #         downset = (self.rows - font.char_height)/2
    #         for text in list:
    #             width = ssd1306.cols
    #             text_bitmap = ssd1306.Bitmap(width, self.rows)
    #             width = text_bitmap.draw_text(0,downset,text,font)
    #             if width > 128:
    #                 text_bitmap = ssd1306.Bitmap(width+15, self.rows)
    #                 text_bitmap.draw_text(0,downset,text,font)
    #             self.bitmaps.append(text_bitmap)
                
    #         # display the first word in the first position
    #         self.ssd1306.display_block(self.bitmaps[0], 0, 0, self.cols)
    
    #     # how many steps to the nearest home position
    #     def align_offset(self):
    #         pos = self.position % self.rows
    #         midway = (self.rows/2)
    #         delta = (pos + midway) % self.rows - midway
    #         return -delta

    #     def align(self, delay=0.005):
    #         delta = self.align_offset()
    #         if delta!=0:
    #             steps = abs(delta)
    #             sign = delta/steps
    #             for i in range(0,steps):
    #                 if i>0 and delay>0:
    #                     time.sleep(delay)
    #                 self.scroll(sign)
    #         return self.position / self.rows
    
    #     # scroll up or down.  Does multiple one-pixel scrolls if delta is not >1 or <-1
    #     def scroll(self, delta):
    #         if delta == 0:
    #             return
    
    #         count = len(self.list)
    #         step = cmp(delta, 0)
    #         for i in range(0,delta, step):
    #             if (self.position % self.rows) == 0:
    #                 n = self.position / self.rows
    #                 # at even boundary, need to update hidden row
    #                 m = (n + step + count) % count
    #                 row = (self.offset + self.rows) % self.bufrows
    #                 self.ssd1306.display_block(self.bitmaps[m], row, 0, self.cols)
    #                 if m == self.pan_row:
    #                     self.pan_offset = 0
    #             self.offset = (self.offset + self.bufrows + step) % self.bufrows
    #             self.ssd1306.command(self.ssd1306.SET_START_LINE | self.offset)
    #             max_position = count * self.rows
    #             self.position = (self.position + max_position + step) % max_position
    
    #     # pans the current row back and forth repeatedly.
    #     # Note that this currently only works if we are at a home position.
    #     def auto_pan(self):
    #         n = self.position / self.rows
    #         if n != self.pan_row:
    #             self.pan_row = n
    #             self.pan_offset = 0
                
    #         text_bitmap = self.bitmaps[n]
    #         if text_bitmap.cols > self.cols:
    #             row = self.offset # this only works if we are at a home position
    #             if self.pan_direction > 0:
    #                 if self.pan_offset <= (text_bitmap.cols - self.cols):
    #                     self.pan_offset += 1
    #                 else:
    #                     self.pan_direction = -1
    #             else:
    #                 if self.pan_offset > 0:
    #                     self.pan_offset -= 1
    #                 else:
    #                     self.pan_direction = 1
    #             self.ssd1306.display_block(text_bitmap, row, 0, self.cols, self.pan_offset)
    
