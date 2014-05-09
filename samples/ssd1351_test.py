import gaugette.ssd1351
import time
import sys
from random import randint

import Image

ROWS = 128
COLS = 128

if gaugette.platform == 'raspberrypi':
  RESET_PIN = 15
  DC_PIN    = 16
else:  # beagebone (have not implemented at all)
    pass
#  RESET_PIN = "P9_15"
#  DC_PIN    = "P9_13"

print("init")
led = gaugette.ssd1351.SSD1351(reset_pin=RESET_PIN, dc_pin=DC_PIN, rows=ROWS, cols=COLS)
print("begin")
led.begin()

#led.fillScreen(led.encode_color(int(randint(0, 0xFFFFFF))))
led.fillScreen(0)
# led.drawPixel(0, 0, led.encode_color(0xFF0000))
# led.drawPixel(50, 50, led.encode_color(0x00FFFF))

R = led.encode_color(0xFF0000)
G = led.encode_color(0x00FF00)
B = led.encode_color(0x0000FF)
# R = G
# G = R
# B = R

# led.drawBitmap(0, 0, [[R for i in range(64)]])

def drawImage(imageName="test.png"):
    image = Image.open(imageName)
    rgb_image = image.convert("RGB")

    imageWidth, imageHeight = image.size

    imagePixels = []
    for y in range(imageHeight):
        row = []
        imagePixels.append(row)
        for x in range(imageWidth):
            red, green, blue = image.getpixel((x, y))
            row.append(led.encode_color((red << 16) | (green << 8) | blue))

    led.drawBitmap(0, 0, imagePixels)

def drawCircle(x, y, r):
    pixels = []

    for yy in range(20):
        row = []
        pixels.append(row)
        for xx in range(20):
            if ((x - xx) ** 2 + (y - yy) ** 2) - (r ** 2) < 2:
                row.append(led.encode_color(0xFFFFFF))
            else:
                row.append(led.encode_color(0x0))

    led.drawBitmap(0, 0, pixels)

drawCircle(10, 10, 10)


offset = 0 # flips between 0 and 32 for double buffering
