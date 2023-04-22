import os
import time
import keyboard
import pyautogui
from PIL import Image, ImageDraw, ImageFont

import requests

def get_current_block():
    url = "https://blockchain.info/q/getblockcount"
    try:
        response = requests.get(url)
        return response.text
    except Exception as e:
        print(e)
        return "unknown"

def get_current_block_hash():
    url = f"https://blockchain.info/block/{get_current_block()}?format=json"
    try:
        response = requests.get(url)
        block_data = response.json()
        return block_data['hash']
    except Exception as e:
        print(e)
        return "unknown"

def get_swatch_internet_time():
    now = time.time() % 86400
    beats = int(now / 86.4)
    return f"@{beats:03}"


def add_watermark(image, text, angle=33, opacity=64):
    width, height = image.size
    watermark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    font = ImageFont.truetype("arial.ttf", 34)

    # ..:::::pierwsza linia tekstu:::::..
    text1 = f"adepthus@Current Time: {time.strftime('%H:%M:%S')} | BeatTime: {get_swatch_internet_time()} | Timechain Block: {get_current_block()}"
    text1_width, text1_height = draw.textsize(text1, font)
    draw.text(((width - text1_width) / 2, (height - text1_height) / 2 - 20), text1, font=font, fill=(128, 128, 128, opacity)) # gray font color

    # druga linia tekstu
    text2 = f"Block Hash: {get_current_block_hash()}"
    text2_width, text2_height = draw.textsize(text2, font)
    draw.text(((width - text2_width) / 2, (height - text2_height) / 2 + 20), text2, font=font, fill=(128, 128, 128, opacity)) # gray font color

    watermark = watermark.rotate(angle, resample=Image.BICUBIC, expand=True)
    watermark_width, watermark_height = watermark.size
    x, y = (width - watermark_width) // 2, (height - watermark_height) // 2
    image.paste(watermark, (x, y), watermark)

    return image

def screenshot_with_watermark():
    screenshot = pyautogui.screenshot()
    timestamp = time.strftime("%Y-%m-%d %H-%M-%S")

    screenshot = add_watermark(screenshot, "", angle=33)

    file_name = f"screenshot_{timestamp}.png"
    screenshot.save(file_name, "PNG")
    print(f"Screenshot saved as {file_name}")

if __name__ == "__main__":
    print("Press 'Prt Scr' to take a screenshot with watermark...")
    while True:
        if keyboard.is_pressed("print screen"):
            screenshot_with_watermark()
            time.sleep(1)
