import os
import time
import requests
import pyautogui
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from pynput import keyboard

def get_api_data(url, cache_time=60):
    """Pobiera dane z URL i przechowuje je w pamięci podręcznej przez określony czas."""
    cache_key = url.replace("/", "_").replace(":", "_")
    if cache_time > 0:
        try:
            with open(cache_key, 'r') as f:
                data = f.read()
                if time.time() - os.path.getmtime(cache_key) < cache_time:
                    return data
        except FileNotFoundError:
            pass
    response = requests.get(url)
    data = response.text
    with open(cache_key, 'w') as f:
        f.write(data)
    return data

def get_current_block():
    url = "https://blockstream.info/api/blocks/tip/height"
    return get_api_data(url)

def get_current_block_hash():
    url = "https://blockchain.info/q/latesthash"
    return get_api_data(url)

def get_swatch_internet_time():
    now = time.time() % 86400
    beats = int(now / 86.4)
    return f"@{beats:03}"

def create_watermark_text(prompt, additional_info=True, lang='pl'):
    """Tworzy tekst znaku wodnego na podstawie monitu użytkownika i opcjonalnych informacji."""
    text = f"{prompt}@"
    if additional_info:
        if lang == 'pl':
            text += f"Obecny czas: {time.strftime('%H:%M:%S')} | BeatTime: {get_swatch_internet_time()} | Blok Timechain: {get_current_block()}"
            text += f"\nHash bloku: {get_current_block_hash()}"
        else:
            text += f"Current time: {time.strftime('%H:%M:%S')} | BeatTime: {get_swatch_internet_time()} | Timechain Block: {get_current_block()}"
            text += f"\nBlock hash: {get_current_block_hash()}"
    return text

def get_bitcoin_font():
    """Zwraca ścieżkę do czcionki obsługującej znak bitcoina."""
    font_paths = [
        "C:\\Windows\\Fonts\\seguisym.ttf",  # Windows
        "/System/Library/Fonts/Apple Symbols.ttf",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    print("Ostrzeżenie: Nie znaleziono czcionki obsługującej znak bitcoina. Użycie znaku '₿' może nie być możliwe.")
    return None

def add_watermark(image, text, angle=35, opacity=111):
    width, height = image.size
    watermark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    font_path = get_bitcoin_font()
    try:
        font = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
    except IOError:
        print(f"Nie można otworzyć pliku czcionki: {font_path}")
        font = ImageFont.load_default()

    watermark_text = text.replace("₿", "B") if font == ImageFont.load_default() else text
    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    
    # Dodawanie cienia
    shadow_offset = 2
    shadow_color = (0, 0, 0, opacity)
    for x_offset in range(-shadow_offset, shadow_offset+1):
        for y_offset in range(-shadow_offset, shadow_offset+1):
            draw.text(
                ((width - text_bbox[2]) / 2 + x_offset, (height - text_bbox[3]) / 2 + y_offset),
                watermark_text,
                font=font,
                fill=shadow_color
            )
    
    # Dodawanie tekstu
    draw.text(
        ((width - text_bbox[2]) / 2, (height - text_bbox[3]) / 2),
        watermark_text,
        font=font,
        fill=(255, 255, 255, opacity)
    )

    rotated_watermark = watermark.rotate(angle, resample=Image.BICUBIC, expand=True)
    watermark_width, watermark_height = rotated_watermark.size
    x, y = (width - watermark_width) // 2, (height - watermark_height) // 2
    image.paste(rotated_watermark, (x, y), rotated_watermark)

    return image

def screenshot_with_watermark(prompt, lang='pl'):
    screenshot = pyautogui.screenshot()
    timestamp = time.strftime("%Y-%m-%d %H-%M-%S")

    watermark_text = create_watermark_text(prompt, lang=lang)
    screenshot = add_watermark(screenshot, watermark_text, angle=33)

    file_name = f"screenshot_{timestamp}_{prompt}@{get_current_block_hash()}.png"
    screenshot.save(file_name, "PNG")
    print(f"{'Zrzut ekranu zapisany jako' if lang == 'pl' else 'Screenshot saved as'} {file_name}")

def add_watermark_to_frame(frame, text, angle=35, opacity=111):
    height, width, _ = frame.shape
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    watermarked_image = add_watermark(image, text, angle, opacity)
    
    return cv2.cvtColor(np.array(watermarked_image), cv2.COLOR_RGB2BGR)

def record_video_with_watermark(prompt, duration=10, lang='pl'):
    timestamp = time.strftime("%Y-%m-%d %H-%M-%S")
    file_name = f"video_{timestamp}_{prompt}@{get_current_block_hash()}.mp4"

    screen_size = pyautogui.size()
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(file_name, fourcc, 20.0, (screen_size.width, screen_size.height))

    watermark_text = create_watermark_text(prompt, lang=lang)
    start_time = time.time()
    while (time.time() - start_time) < duration:
        img = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        frame = add_watermark_to_frame(frame, watermark_text, angle=33)
        out.write(frame)

    out.release()
    print(f"{'Film zapisany jako' if lang == 'pl' else 'Video saved as'} {file_name}")

def record_gif_with_watermark(prompt, duration=21, lang='pl'):
    timestamp = time.strftime("%Y-%m-%d %H-%M-%S")
    file_name = f"gif_{timestamp}_{prompt}@{get_current_block_hash()}.gif"

    frames = []
    watermark_text = create_watermark_text(prompt, lang=lang)

    start_time = time.time()
    while (time.time() - start_time) < duration:
        img = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        frame = add_watermark_to_frame(frame, watermark_text, angle=33)
        frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))

    frames[0].save(file_name, save_all=True, append_images=frames[1:], duration=100, loop=0)
    print(f"{'Gif zapisany jako' if lang == 'pl' else 'Gif saved as'} {file_name}")

def on_press(key, prompt, lang):
    try:
        if key == keyboard.Key.print_screen:
            screenshot_with_watermark(prompt, lang)
        elif key == keyboard.Key.f9:
            record_video_with_watermark(prompt, duration=10, lang=lang)
        elif key == keyboard.Key.f10:
            record_gif_with_watermark(prompt, duration=7, lang=lang)
    except Exception as e:
        print(f"{'Wystąpił błąd' if lang == 'pl' else 'An error occurred'}: {e}")

if __name__ == "__main__":
    lang = input("Choose language (en/pl): ").strip().lower()
    lang = 'en' if lang == 'en' else 'pl'

    while True:
        prompt = input("Enter watermark prompt for timechain (or 'q' to quit): " if lang == 'en' else 
                       "Wprowadź tekst monitu znaku wodnego na timechain (lub 'q' aby zakończyć): ").strip()
        if prompt.lower() == 'q':
            break
        if prompt:
            break
        print("Prompt cannot be empty. Please enter a valid prompt." if lang == 'en' else 
              "Monit nie może być pusty. Wprowadź prawidłowy tekst monitu.")

    if prompt.lower() != 'q':
        print(f"{'You entered' if lang == 'en' else 'Wprowadziłeś'} '{prompt}' {'as the watermark prompt' if lang == 'en' else 'jako monit znaku wodnego'}.")
        print("Press 'Prt Scr' to take a screenshot with watermark," if lang == 'en' else
              "Naciśnij 'Prt Scr', aby zrobić zrzut ekranu ze znakiem wodnym,")
        print("or 'F9' to record a 10-second video with watermark," if lang == 'en' else
              "lub 'F9', aby nagrać 10-sekundowe wideo ze znakiem wodnym,")
        print("or 'F10' to record a 21-second gif with watermark." if lang == 'en' else
              "lub 'F10', aby nagrać 21-sekundowy gif ze znakiem wodnym.")
        print("Press 'Ctrl+C' to end the program." if lang == 'en' else
              "Naciśnij 'Ctrl+C', aby zakończyć program.")

        with keyboard.Listener(on_press=lambda key: on_press(key, prompt, lang)) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\nProgram ended." if lang == 'en' else "\nProgram zakończony.")
