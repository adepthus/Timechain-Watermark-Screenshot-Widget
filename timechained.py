import os
import time
import keyboard
import pyautogui
from PIL import Image, ImageDraw, ImageFont

import requests

def get_current_block():
    url = "https://blockstream.info/api/blocks/tip/height"
    try:
        response = requests.get(url)
        return response.text
    except Exception as e:
        print(e)
        return "unknown"


def get_current_block_hash():
    url = "https://blockchain.info/q/latesthash"
    try:
        response = requests.get(url)
        return response.text
    except Exception as e:
        print(e)
        return "unknown"


def get_swatch_internet_time():
    now = time.time() % 86400
    beats = int(now / 86.4)
    return f"@{beats:03}"

def add_watermark(image, text, angle=35, opacity=64):
    width, height = image.size
    watermark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    font = ImageFont.truetype("arial.ttf", 36)

    # ..:::::pierwsza linia tekstu:::::..
    text1 = f"{text}@Current Time: {time.strftime('%H:%M:%S')} | ₿eatTime: {get_swatch_internet_time()} | Timechain Block: {get_current_block()}"
    text1_bbox = draw.textbbox((0, 0), text1, font=font)
    draw.text(((width - text1_bbox[2]) / 2, (height - text1_bbox[3]) / 2 - 20), text1, font=font, fill=(128, 128, 128, opacity))

    # ..:::::druga linia tekstu:::::..
    text2 = f"Block Hash: {get_current_block_hash()}"
    text2_bbox = draw.textbbox((0, 0), text2, font=font)
    draw.text(((width - text2_bbox[2]) / 2, (height - text2_bbox[3]) / 2 + 20), text2, font=font, fill=(128, 128, 128, opacity))

    watermark = watermark.rotate(angle, resample=Image.BICUBIC, expand=True)
    watermark_width, watermark_height = watermark.size
    x, y = (width - watermark_width) // 2, (height - watermark_height) // 2
    image.paste(watermark, (x, y), watermark)

    return image

def screenshot_with_watermark(prompt):
    screenshot = pyautogui.screenshot()
    timestamp = time.strftime("%Y-%m-%d %H-%M-%S")

    screenshot = add_watermark(screenshot, prompt, angle=33)

    file_name = f"screenshot_{timestamp}.{prompt}@{get_current_block_hash()}.png"
    screenshot.save(file_name, "PNG")
    print(f"Screenshot saved as {file_name}")

if __name__ == "__main__":
    prompt = input("Enter watermark text prompt on timechain : ")
    print("Press 'Prt Scr' to take a screenshot with a watermark,...")
    while True:
        if keyboard.is_pressed("print screen"):
            screenshot_with_watermark(prompt)
            time.sleep(1)
