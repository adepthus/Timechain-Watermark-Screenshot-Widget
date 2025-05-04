# -*- coding: utf-8 -*-
"""
Timechain Desktop Widget v6.8.11 (Ulepszone Zapisywanie Plików i Stabilność)

Wyświetla dostosowywalny monit z danymi w czasie rzeczywistym i pozwala
na robienie zrzutów ekranu/nagrań z opcjonalnym, konfigurowalnym znakiem wodnym Timechain.

Nowości w v6.8.10:
- POPRAWIONO: Użycie pełnego hashu w nazwie pliku (jeśli dostępny).
- POPRAWIONO: Potencjalna poprawka dla edycji monitu w spakowanym .exe (parent=None).
- POPRAWIONO: coś tam poprawiono xD i coś jeszcze do poprawy
- POPRAWIONO: Dodatkowe zabezpieczenia przed błędami TclError przy zamykaniu okna.
- POPRAWIONO: Zabezpieczenia w obliczeniach pozycji znaku wodnego.
- Ulepszono: Cień, wyświetlanie na jasnym/ciemnym tle.
"""

import os
import sys
import time
import datetime
import requests
import tkinter as tk
from tkinter import simpledialog, Menu, Label, messagebox, StringVar, BooleanVar
import logging
import tempfile
import threading
import math
import platform
import random
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
import cv2

# --- Konfiguracja Logowania ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Sprawdzenie i Import Modułów ---
PIL_AVAILABLE = False
PYAUTOGUI_AVAILABLE = False
CV2_AVAILABLE = False
NUMPY_AVAILABLE = False
IMAGEGRAB_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    logging.debug("Moduł pyautogui zaimportowany.")
except ImportError:
    logging.warning("Brak modułu pyautogui. Podstawowa funkcjonalność przechwytywania może być ograniczona.")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor, PngImagePlugin
    try:
        from PIL import ImageGrab # ImageGrab może być w osobnym pakiecie lub niedostępny
        IMAGEGRAB_AVAILABLE = True
        logging.debug("Moduł PIL.ImageGrab zaimportowany.")
    except ImportError:
        logging.warning("Brak modułu PIL.ImageGrab. Funkcja auto-koloru może używać pyautogui.")
    PngInfo = PngImagePlugin.PngInfo
    PIL_AVAILABLE = True
    logging.debug("Moduł PIL (Pillow) zaimportowany.")
except ImportError as e:
    logging.critical(f"Brak wymaganego modułu Pillow (PIL): {e}. Zainstaluj: pip install Pillow")
    sys.exit(1) # Pillow jest kluczowy

try:
    import cv2
    CV2_AVAILABLE = True
    logging.debug("Moduł cv2 (opencv-python) zaimportowany.")
except ImportError:
    logging.warning("Brak modułu opencv-python. Nagrywanie wideo nie będzie dostępne.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
    logging.debug("Moduł numpy zaimportowany.")
except ImportError:
    logging.warning("Brak modułu numpy. Niektóre operacje na obrazach (szczególnie z cv2) mogą nie działać.")

# Sprawdzenie kluczowych zależności dla podstawowej funkcjonalności
if not PYAUTOGUI_AVAILABLE and not IMAGEGRAB_AVAILABLE:
     logging.critical("Brak modułu pyautogui i PIL.ImageGrab. Nie można przechwytywać ekranu.")
     sys.exit(1)
if not PIL_AVAILABLE:
    logging.critical("Brak modułu Pillow (PIL). Nie można przetwarzać obrazów ani zapisywać plików PNG/GIF.")
    sys.exit(1)

# Import pynput (opcjonalny)
HAVE_PYNPUT = False
try:
    from pynput import keyboard
    HAVE_PYNPUT = True
    logging.debug("Moduł pynput zaimportowany.")
except ImportError:
    logging.warning("Brak pynput. Skróty klawiszowe (PrintScreen, F9, F10) nie będą działać.")
    # Definicja atrap, aby reszta kodu się nie wywalała
    class DummyKey:
        def __init__(self, name): self.name = name
        def __eq__(self, other): return isinstance(other, DummyKey) and self.name == other.name
        def __hash__(self): return hash(self.name)
        def __str__(self): return f"DummyKey({self.name})"
    class keyboard:
        class Key:
            print_screen = DummyKey('print_screen')
            f9 = DummyKey('f9')
            f10 = DummyKey('f10')
        class Listener:
            def __init__(self, on_press=None, on_release=None, suppress=False):
                self._on_press = on_press
                self._on_release = on_release
                logging.info("Używam atrapy pynput.Listener.")
            def start(self): logging.debug("Atrapa listenera: start()")
            def stop(self): logging.debug("Atrapa listenera: stop()")
            def join(self, timeout=None): logging.debug("Atrapa listenera: join()")
            def __enter__(self): return self
            def __exit__(self, *args): pass

# --- Obsługa DPI (Windows) ---
if platform.system() == "Windows":
    try:
        from ctypes import windll
        # Preferowane jest SetProcessDpiAwarenessContext, ale wymaga nowszych Windows
        # Próbujemy najpierw nowszych metod
        try:
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            if windll.user32.SetProcessDpiAwarenessContext(-4): # Per Monitor v2
                 logging.debug("Ustawiono DPI awareness (Per Monitor v2).")
            elif windll.shcore.SetProcessDpiAwareness(2): # Per Monitor (starsze)
                 logging.debug("Ustawiono DPI awareness (per-monitor).")
            elif windll.user32.SetProcessDPIAware(): # System Aware
                 logging.debug("Ustawiono DPI awareness (system).")
        except AttributeError:
             # Jeśli nowsze metody zawiodą, spróbuj starszych
             if hasattr(windll.shcore, 'SetProcessDpiAwareness'):
                 windll.shcore.SetProcessDpiAwareness(2) # Per Monitor
                 logging.debug("Ustawiono DPI awareness (per-monitor - fallback shcore).")
             elif hasattr(windll.user32, 'SetProcessDPIAware'):
                 windll.user32.SetProcessDPIAware() # System Aware
                 logging.debug("Ustawiono DPI awareness (system - fallback user32).")
    except Exception as e:
        logging.warning(f"Nie udało się ustawić DPI awareness: {e}")

# --- Konfiguracja ---
VERSION = "6.8.10" # Zaktualizowana wersja z poprawkami
CACHE_DIR_NAME = "timechain_widget_cache"
CACHE_TIME_SECONDS = 60
API_TIMEOUT_SECONDS = 10
FONT_FAMILY = "Segoe UI"  # Domyślna czcionka, może być potrzebna ścieżka w niektórych systemach
BASE_FONT_SIZE = 15
FONT_WEIGHT = "bold"
DEFAULT_TEXT_COLOR = "white"
DEFAULT_SHADOW_COLOR = "#333333"
SHADOW_OFFSET_X = 1
SHADOW_OFFSET_Y = 1
TRANSPARENT_COLOR = '#f0f0f0'  # Kolor tła, który staje się przezroczysty
INITIAL_WINDOW_POSITION = "+100+100"
BLOCK_HEIGHT_URL = "https://blockstream.info/api/blocks/tip/height"
BLOCK_HASH_URL = "https://blockchain.info/q/latesthash"

ENABLE_DRAG_SCALING = True
MAX_SCALE_INCREASE = 0.3 # Maksymalne powiększenie czcionki podczas przeciągania (30%)
SCALE_DISTANCE_FACTOR = 400 # Odległość w pikselach powodująca MAX_SCALE_INCREASE
MIN_SCALED_FONT_SIZE = 10 # Minimalny rozmiar czcionki po skalowaniu

SCREENSHOT_MODE_WIDGET = 'widget'
SCREENSHOT_MODE_WATERMARK = 'watermark'
DEFAULT_SCREENSHOT_MODE = SCREENSHOT_MODE_WIDGET
DEFAULT_WATERMARK_STYLE = "1" # 1: Center, 3: Grid(3), 5: Grid(5), 8: Grid(8)
WATERMARK_ANGLE = 33 # Kąt obrotu znaku wodnego
WATERMARK_OPACITY = 75 # Przezroczystość znaku wodnego w procentach (0-100)
WATERMARK_FONT_SIZE = 30 # Rozmiar czcionki znaku wodnego

DEFAULT_VIDEO_DURATION_SECONDS = 10
DEFAULT_GIF_DURATION_SECONDS = 7
GIF_FRAME_DURATION_MS = 100 # Czas trwania klatki GIF w milisekundach
CAPTURE_SUBDIR = "Timechain_Captures" # Nazwa podkatalogu na zapisy
VIDEO_FOURCC = "mp4v" # Kodek dla MP4 (może wymagać instalacji kodeków systemowych), inne opcje: 'XVID', 'MJPG'

ENABLE_AUTO_COLOR_INVERSION = True # Czy automatycznie odwracać kolor tekstu na ciemny na jasnym tle
AUTO_COLOR_BRIGHTNESS_THRESHOLD = 200 # Próg jasności (0-255), powyżej którego kolor jest odwracany
INVERTED_TEXT_COLOR = DEFAULT_SHADOW_COLOR # Kolor tekstu na jasnym tle
INVERTED_SHADOW_COLOR = DEFAULT_TEXT_COLOR # Kolor cienia na jasnym tle
AUTO_COLOR_SAMPLE_SIZE = 20 # Rozmiar kwadratu (w pikselach) pod kursorem do próbkowania jasności

# --- Główna Klasa Widgetu ---
class TimechainWidget:
    def __init__(self, master: tk.Tk, initial_prompt: str, lang: str):
        self.master = master
        self.prompt = initial_prompt
        self.lang = lang
        self._cache_dir = self._setup_cache_dir()
        self._cancel_update = False
        self._key_listener_thread = None
        self._key_listener_stop_event = threading.Event()
        self._listener_instance = None # Przechowuje instancję listenera pynput
        self._update_timer = None

        # Dane dynamiczne
        self._current_time_str = "..."
        self._beat_time_str = "@???"
        self._block_height_str = "..."
        self._block_hash_short_str = "..."
        self._full_block_hash_str = None
        self._last_error = None

        # Stan UI
        self.label_shadow: Optional[Label] = None
        self.label_main: Optional[Label] = None
        self._base_font_options = (FONT_FAMILY, BASE_FONT_SIZE, FONT_WEIGHT)
        self._current_font_options = self._base_font_options
        self._display_full_hash_permanently_var = BooleanVar(value=False)
        self.last_click_x = 0
        self.last_click_y = 0
        self._drag_start_x_root = 0
        self._drag_start_y_root = 0
        self._is_dragging = False

        # Konfiguracja przechwytywania
        self._screenshot_mode_var = StringVar(value=DEFAULT_SCREENSHOT_MODE)
        self._watermark_mode_var = StringVar(value=DEFAULT_WATERMARK_STYLE)
        self._active_capture_thread: Optional[threading.Thread] = None
        self._video_duration_seconds = DEFAULT_VIDEO_DURATION_SECONDS
        self._gif_duration_seconds = DEFAULT_GIF_DURATION_SECONDS
        self._fixed_watermark_paste_positions: Optional[List[Tuple[int, int]]] = None
        self._video_gif_random_seed: Optional[int] = None

        # Konfiguracja wyglądu
        self._show_shadow_var = BooleanVar(value=True)
        self._current_text_color = DEFAULT_TEXT_COLOR
        self._current_shadow_color = DEFAULT_SHADOW_COLOR

        self._setup_ui()
        self._bind_events()
        threading.Thread(target=self._initial_data_fetch_and_show, name="InitialFetch", daemon=True).start()
        self._setup_key_listener()

    def _setup_cache_dir(self) -> Optional[str]:
        """Konfiguruje i zwraca ścieżkę do katalogu cache."""
        try:
            # Próba znalezienia odpowiedniego katalogu na dane aplikacji
            if platform.system() == "Windows":
                base_path = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
            elif platform.system() == "Darwin": # macOS
                base_path = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
            else: # Linux and other Unix-like
                base_path = os.getenv('XDG_CACHE_HOME') or os.path.join(os.path.expanduser("~"), ".cache")

            if not base_path or not os.path.isdir(base_path):
                # Fallback do katalogu tymczasowego, jeśli standardowe ścieżki zawiodą
                base_path = tempfile.gettempdir()
                logging.warning(f"Nie znaleziono standardowego katalogu danych aplikacji, używam tymczasowego: {base_path}")

            app_specific_dir = os.path.join(base_path, "TimechainWidget")
            cache_path = os.path.join(app_specific_dir, CACHE_DIR_NAME)
            os.makedirs(cache_path, exist_ok=True)
            logging.info(f"Katalog cache skonfigurowany w: {cache_path}")
            return cache_path
        except Exception as e:
            logging.error(f"Nie udało się utworzyć katalogu cache: {e}. Cache będzie wyłączony.")
            return None

    def _setup_ui(self) -> None:
        """Inicjalizuje interfejs użytkownika widgetu."""
        self.master.attributes('-topmost', True) # Zawsze na wierzchu
        self.master.overrideredirect(True) # Usuwa ramkę okna i przyciski
        self.master.config(bg=TRANSPARENT_COLOR)
        # Ustawienie przezroczystości (może nie działać na wszystkich systemach/menedżerach okien)
        try:
            self.master.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        except tk.TclError:
            logging.warning("System nie wspiera atrybutu -transparentcolor. Tło może nie być przezroczyste.")
        except Exception as e:
            logging.warning(f"Nieoczekiwany błąd przy ustawianiu przezroczystości: {e}")


        init_text = "Ładowanie..." if self.lang == 'pl' else "Loading..."
        # Etykieta cienia
        self.label_shadow = Label(self.master, text=init_text, font=self._base_font_options,
                                 fg=self._current_shadow_color, bg=TRANSPARENT_COLOR,
                                 justify=tk.LEFT, anchor='nw')
        if self._show_shadow_var.get():
            self.label_shadow.place(x=SHADOW_OFFSET_X, y=SHADOW_OFFSET_Y)

        # Główna etykieta
        self.label_main = Label(self.master, text=init_text, font=self._base_font_options,
                                fg=self._current_text_color, bg=TRANSPARENT_COLOR,
                                justify=tk.LEFT, anchor='nw')
        self.label_main.place(x=0, y=0)

        self.master.geometry(INITIAL_WINDOW_POSITION) # Początkowa pozycja okna

    def _bind_events(self) -> None:
        """Wiąże zdarzenia myszy z odpowiednimi metodami."""
        # Wiązanie zdarzeń dla głównego okna i etykiet, aby przeciąganie działało płynnie
        widgets_to_bind = [self.master, self.label_main, self.label_shadow]
        for widget in widgets_to_bind:
            if widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                widget.bind("<Button-1>", self._on_left_click_press) # Lewy przycisk wciśnięty
                widget.bind("<B1-Motion>", self._on_drag) # Lewy przycisk wciśnięty i ruch
                widget.bind("<ButtonRelease-1>", self._on_left_click_release) # Lewy przycisk puszczony
                widget.bind("<Button-3>", self._on_right_click) # Prawy przycisk kliknięty

    def _on_left_click_press(self, event: tk.Event) -> None:
        """Obsługa wciśnięcia lewego przycisku myszy (początek przeciągania)."""
        if not self.master.winfo_exists(): return
        self._is_dragging = True
        # Zapisanie pozycji kliknięcia względem lewego górnego rogu okna
        master_x = self.master.winfo_x()
        master_y = self.master.winfo_y()
        self.last_click_x = event.x_root - master_x
        self.last_click_y = event.y_root - master_y
        # Zapisanie globalnej pozycji startowej przeciągania (dla skalowania)
        self._drag_start_x_root = event.x_root
        self._drag_start_y_root = event.y_root

    def _on_drag(self, event: tk.Event) -> None:
        """Obsługa przeciągania okna i dynamicznego skalowania czcionki."""
        if not self._is_dragging or not self.master.winfo_exists():
            self._is_dragging = False # Na wszelki wypadek
            return

        # Obliczenie nowej pozycji okna
        new_x = event.x_root - self.last_click_x
        new_y = event.y_root - self.last_click_y
        try:
            self.master.geometry(f"+{new_x}+{new_y}")
        except tk.TclError:
            # Okno mogło zostać zniszczone w międzyczasie
            self._is_dragging = False
            if not self._cancel_update: self._close_widget()
            return

        # Dynamiczne skalowanie czcionki podczas przeciągania
        if ENABLE_DRAG_SCALING:
            distance = math.hypot(event.x_root - self._drag_start_x_root, event.y_root - self._drag_start_y_root)
            # Skala rośnie liniowo z odległością, z ograniczeniem MAX_SCALE_INCREASE
            scale = 1.0 + min(MAX_SCALE_INCREASE, distance / SCALE_DISTANCE_FACTOR)
            new_font_size = max(MIN_SCALED_FONT_SIZE, int(BASE_FONT_SIZE * scale))

            # Zaktualizuj czcionkę tylko jeśli rozmiar się zmienił
            if new_font_size != self._current_font_options[1]:
                self._current_font_options = (FONT_FAMILY, new_font_size, FONT_WEIGHT)
                try:
                    if self.label_main and self.label_main.winfo_exists():
                        self.label_main.config(font=self._current_font_options)
                    if self.label_shadow and self.label_shadow.winfo_exists():
                        self.label_shadow.config(font=self._current_font_options)
                    # Odśwież wyświetlanie, aby dostosować rozmiar okna do nowej czcionki
                    self.master.after_idle(lambda: self._update_display(force_resize=True))
                except tk.TclError:
                     if not self._cancel_update: self._close_widget()


    def _on_left_click_release(self, event: tk.Event) -> None:
        """Obsługa puszczenia lewego przycisku myszy (koniec przeciągania)."""
        if not self._is_dragging: return
        self._is_dragging = False

        # Sprawdź kolor tła po zakończeniu przeciągania
        if ENABLE_AUTO_COLOR_INVERSION and self.master.winfo_exists():
            self.master.after(50, self._check_and_update_widget_color) # Małe opóźnienie

        # Przywróć bazowy rozmiar czcionki, jeśli była skalowana
        if ENABLE_DRAG_SCALING and self._current_font_options != self._base_font_options:
            self._current_font_options = self._base_font_options
            try:
                if self.label_main and self.label_main.winfo_exists():
                    self.label_main.config(font=self._base_font_options)
                if self.label_shadow and self.label_shadow.winfo_exists():
                    self.label_shadow.config(font=self._base_font_options)
                # Odśwież wyświetlanie, aby dostosować rozmiar okna
                self.master.after(10, lambda: self._update_display(force_resize=True)) # Małe opóźnienie
            except tk.TclError:
                 if not self._cancel_update: self._close_widget()

    def _get_widget_background_brightness(self) -> Optional[float]:
        """Pobiera próbkę tła pod środkiem widgetu i oblicza średnią jasność."""
        if not self.master.winfo_exists() or not self.master.winfo_viewable():
            return None
        try:
            # Upewnij się, że geometria okna jest aktualna
            self.master.update_idletasks()

            width = self.master.winfo_width()
            height = self.master.winfo_height()
            x = self.master.winfo_x()
            y = self.master.winfo_y()

            if width <= 0 or height <= 0:
                logging.debug("Jasność tła: Nieprawidłowe wymiary widgetu.")
                return None

            # Środek widgetu
            center_x, center_y = x + width // 2, y + height // 2
            half_sample = AUTO_COLOR_SAMPLE_SIZE // 2

            # Definiowanie obszaru próbkowania na ekranie
            screen_size = pyautogui.size() if PYAUTOGUI_AVAILABLE else (0,0) # Potrzebujemy rozmiaru ekranu
            if not screen_size or screen_size == (0,0):
                if IMAGEGRAB_AVAILABLE:
                    # Próba uzyskania rozmiaru ekranu inaczej (może nie działać wszędzie)
                    try:
                         temp_im = ImageGrab.grab()
                         screen_size = temp_im.size
                    except Exception:
                         logging.warning("Nie można uzyskać rozmiaru ekranu dla próbkowania jasności.")
                         return None
                else:
                     logging.warning("Nie można uzyskać rozmiaru ekranu (brak pyautogui/ImageGrab).")
                     return None


            sample_x1 = max(0, center_x - half_sample)
            sample_y1 = max(0, center_y - half_sample)
            sample_x2 = min(screen_size[0], center_x + half_sample)
            sample_y2 = min(screen_size[1], center_y + half_sample)

            sample_width = sample_x2 - sample_x1
            sample_height = sample_y2 - sample_y1

            if sample_width <= 0 or sample_height <= 0:
                logging.debug("Jasność tła: Nieprawidłowy obszar próbkowania.")
                return None

            # Przechwytywanie małego obszaru ekranu
            screenshot = None
            if IMAGEGRAB_AVAILABLE:
                try:
                    screenshot = ImageGrab.grab(bbox=(sample_x1, sample_y1, sample_x2, sample_y2))
                except Exception as e:
                    logging.warning(f"Błąd ImageGrab.grab: {e}. Próba z pyautogui.")
                    screenshot = None # Resetuj, aby spróbować pyautogui

            if screenshot is None and PYAUTOGUI_AVAILABLE:
                try:
                    # Pyautogui używa regionu (x, y, width, height)
                    screenshot = pyautogui.screenshot(region=(sample_x1, sample_y1, sample_width, sample_height))
                except Exception as e:
                    logging.warning(f"Błąd pyautogui.screenshot: {e}")
                    return None # Obie metody zawiodły

            if screenshot is None:
                 logging.warning("Nie udało się przechwycić próbki tła.")
                 return None

            # Konwersja do skali szarości i obliczenie średniej jasności
            grayscale = screenshot.convert("L")
            if NUMPY_AVAILABLE:
                 # Użycie numpy jest szybsze
                 brightness_array = np.array(grayscale)
                 # Sprawdzenie, czy tablica nie jest pusta
                 if brightness_array.size == 0:
                     logging.warning("Pusta tablica jasności.")
                     return None
                 avg_brightness = float(np.mean(brightness_array))
            else:
                 # Fallback bez numpy (wolniejszy)
                 pixels = list(grayscale.getdata())
                 if not pixels:
                     logging.warning("Brak pikseli w próbce jasności.")
                     return None
                 avg_brightness = sum(pixels) / len(pixels)

            logging.debug(f"Średnia jasność tła: {avg_brightness:.2f}")
            return avg_brightness

        except tk.TclError:
             logging.warning("Błąd TclError podczas pobierania jasności tła (okno mogło zostać zamknięte).")
             if not self._cancel_update: self._close_widget()
             return None
        except Exception as e:
            # Logowanie innych, nieoczekiwanych błędów
            logging.warning(f"Nieoczekiwany błąd podczas analizy jasności tła: {e}", exc_info=False) # exc_info=False dla zwięzłości
            return None # Zwróć None, aby nie zmieniać koloru w razie błędu

    def _check_and_update_widget_color(self) -> None:
        """Sprawdza jasność tła i odwraca kolory widgetu w razie potrzeby."""
        if not ENABLE_AUTO_COLOR_INVERSION or not self.master.winfo_exists():
            return

        avg_brightness = self._get_widget_background_brightness()

        # Jeśli nie udało się uzyskać jasności, przywróć domyślne kolory (jeśli były zmienione)
        if avg_brightness is None:
            if self._current_text_color != DEFAULT_TEXT_COLOR:
                logging.debug("Przywracanie domyślnych kolorów z powodu błędu odczytu jasności.")
                self._current_text_color = DEFAULT_TEXT_COLOR
                self._current_shadow_color = DEFAULT_SHADOW_COLOR
                self._apply_color_update_to_labels()
            return

        # Sprawdź, czy należy odwrócić kolory
        should_invert = avg_brightness > AUTO_COLOR_BRIGHTNESS_THRESHOLD
        target_text_color = INVERTED_TEXT_COLOR if should_invert else DEFAULT_TEXT_COLOR
        target_shadow_color = INVERTED_SHADOW_COLOR if should_invert else DEFAULT_SHADOW_COLOR # Poprawka: Cień też powinien się odwracać

        # Zastosuj zmianę tylko jeśli docelowe kolory są inne niż obecne
        if self._current_text_color != target_text_color or self._current_shadow_color != target_shadow_color:
            logging.info(f"Zmiana kolorów widgetu (jasność tła: {avg_brightness:.1f}, odwrócone: {should_invert})")
            self._current_text_color = target_text_color
            self._current_shadow_color = target_shadow_color
            self._apply_color_update_to_labels()

    def _apply_color_update_to_labels(self):
        """Aktualizuje kolory etykiet (głównej i cienia)."""
        if not self.master.winfo_exists(): return
        try:
            if self.label_main and self.label_main.winfo_exists():
                self.label_main.config(fg=self._current_text_color)

            if self.label_shadow and self.label_shadow.winfo_exists():
                 if self._show_shadow_var.get():
                     self.label_shadow.config(fg=self._current_shadow_color)
                     # Upewnij się, że cień jest widoczny, jeśli powinien być
                     if not self.label_shadow.winfo_ismapped():
                         self.label_shadow.place(x=SHADOW_OFFSET_X, y=SHADOW_OFFSET_Y)
                 else:
                     # Ukryj cień, jeśli nie powinien być widoczny
                     if self.label_shadow.winfo_ismapped():
                         self.label_shadow.place_forget()

            # Odświeżenie może być potrzebne, ale unikaj force_resize, jeśli to tylko zmiana koloru
            self._update_display(force_resize=False)
        except tk.TclError:
            if not self._cancel_update: self._close_widget()


    def _set_watermark_style(self, style_value: str) -> None:
        """Ustawia styl znaku wodnego i przełącza tryb przechwytywania."""
        self._watermark_mode_var.set(style_value)
        self._screenshot_mode_var.set(SCREENSHOT_MODE_WATERMARK)
        # Nie ma potrzeby ukrywania widgetu tutaj, stanie się to podczas przechwytywania

    def _set_capture_mode_widget(self) -> None:
        """Ustawia tryb przechwytywania na 'widget widoczny'."""
        self._screenshot_mode_var.set(SCREENSHOT_MODE_WIDGET)
        # Upewnij się, że widget jest widoczny (jeśli był ukryty)
        if self.master.winfo_exists():
            # Użyj after(0, ...) aby wykonać to w pętli zdarzeń Tkinter
            self.master.after(0, self._safely_restore_widget_visibility)

    def _toggle_shadow(self) -> None:
        """Włącza lub wyłącza wyświetlanie cienia pod tekstem."""
        if not self.master.winfo_exists(): return
        show = self._show_shadow_var.get()
        try:
            if self.label_shadow and self.label_shadow.winfo_exists():
                if show:
                    # Pokaż cień z aktualnym kolorem cienia
                    self.label_shadow.config(fg=self._current_shadow_color) # Użyj aktualnego koloru
                    self.label_shadow.place(x=SHADOW_OFFSET_X, y=SHADOW_OFFSET_Y)
                else:
                    # Ukryj cień
                    self.label_shadow.place_forget()
            # Odśwież widget, wymuszając przeliczenie rozmiaru, bo cień wpływa na wymiary
            self.master.after_idle(lambda: self._update_display(force_resize=True))
        except tk.TclError:
            if not self._cancel_update: self._close_widget()


    def _toggle_permanent_full_hash(self) -> None:
        """Przełącza stałe wyświetlanie pełnego hasha bloku."""
        if not self.master.winfo_exists():
            # Jeśli okno nie istnieje, nie można włączyć, resetuj zmienną
            self._display_full_hash_permanently_var.set(False)
            return

        is_full = self._display_full_hash_permanently_var.get()
        # Sprawdź, czy mamy poprawny pełny hash, zanim pozwolimy go włączyć na stałe
        full_hash_ok = isinstance(self._full_block_hash_str, str) and len(self._full_block_hash_str) == 64 and all(c in '0123456789abcdefABCDEF' for c in self._full_block_hash_str.lower())

        if is_full and not full_hash_ok:
            # Jeśli użytkownik próbuje włączyć, ale nie ma danych, cofnij i pokaż błąd
            self._display_full_hash_permanently_var.set(False)
            error_message = ('Nie można włączyć pełnego hasha. Brak poprawnych danych.' if self.lang == 'pl' else 'Cannot enable full hash. Valid data missing.')
            # Pokaż błąd w głównym wątku Tkinter
            self.master.after(0, lambda: messagebox.showwarning('Błąd Danych Hasha' if self.lang == 'pl' else 'Hash Data Error', error_message, parent=self.master))
        else:
            # Jeśli wyłączamy lub mamy poprawne dane do włączenia, odśwież widok
             self.master.after_idle(lambda: self._update_display(force_resize=True)) # force_resize bo długość tekstu się zmienia

    def _configure_duration(self, capture_type: str) -> None:
        """Pozwala użytkownikowi skonfigurować czas trwania nagrania wideo lub GIF."""
        if not self.master.winfo_exists(): return

        current_value = self._video_duration_seconds if capture_type == 'video' else self._gif_duration_seconds
        title_pl = 'Czas Nagrywania Wideo' if capture_type == 'video' else 'Czas Nagrywania GIF'
        title_en = 'Video Recording Duration' if capture_type == 'video' else 'GIF Recording Duration'
        title = title_pl if self.lang == 'pl' else title_en
        prompt_text_pl = f"Podaj czas w sekundach (1-300):"
        prompt_text_en = f"Enter duration in seconds (1-300):"
        prompt_text = prompt_text_pl if self.lang == 'pl' else prompt_text_en

        try:
            # Użyj simpledialog do pobrania nowej wartości
            new_duration = simpledialog.askinteger(
                title,
                prompt_text,
                parent=self.master, # Ważne dla modalności okna dialogowego
                initialvalue=current_value,
                minvalue=1,
                maxvalue=300
            )

            # Jeśli użytkownik podał wartość (nie anulował)
            if new_duration is not None:
                if capture_type == 'video':
                    self._video_duration_seconds = new_duration
                    logging.info(f"Ustawiono czas nagrywania wideo na: {new_duration}s")
                else: # gif
                    self._gif_duration_seconds = new_duration
                    logging.info(f"Ustawiono czas nagrywania GIF na: {new_duration}s")
                # Menu kontekstowe nie aktualizuje się samo, ale wartość jest zmieniona dla następnego nagrania
        except Exception as e:
             # Obsługa błędów, np. gdy simpledialog nie może zostać wyświetlony
             self.master.after(0, lambda: messagebox.showerror('Błąd Konfiguracji' if self.lang == 'pl' else 'Configuration Error', f"Wystąpił błąd: {e}", parent=self.master))


    def _on_right_click(self, event: tk.Event) -> None:
        """Wyświetla menu kontekstowe po kliknięciu prawym przyciskiem."""
        if not self.master.winfo_exists(): return

        popup = Menu(self.master, tearoff=0) # tearoff=0 usuwa przerywaną linię na górze menu

        try:
            # --- Podstawowe akcje ---
            popup.add_command(label=('Edytuj Monit' if self.lang == 'pl' else 'Edit Prompt'), command=self._edit_widget)
            popup.add_separator()

            # --- Ustawienia Wyglądu ---
            appearance_menu = Menu(popup, tearoff=0)
            popup.add_cascade(label=('Ustawienia Wyglądu' if self.lang == 'pl' else 'Appearance Settings'), menu=appearance_menu)
            # Opcja Pokaż/Ukryj Cień
            appearance_menu.add_checkbutton(label=('Pokaż Cień' if self.lang == 'pl' else 'Show Shadow'),
                                            variable=self._show_shadow_var, command=self._toggle_shadow)
            # Opcja Pokaż Pełny Hash
            appearance_menu.add_checkbutton(label=('Pokaż Pełny Hash' if self.lang == 'pl' else 'Show Full Hash'),
                                            variable=self._display_full_hash_permanently_var, command=self._toggle_permanent_full_hash)
            popup.add_separator()

            # --- Tryb Przechwytywania ---
            capture_menu = Menu(popup, tearoff=0)
            popup.add_cascade(label=('Tryb Przechwytywania' if self.lang == 'pl' else 'Capture Mode'), menu=capture_menu)
            # Opcja: Widżet widoczny
            capture_menu.add_radiobutton(label=('Widżet Widoczny' if self.lang == 'pl' else 'Widget Visible'),
                                         variable=self._screenshot_mode_var, value=SCREENSHOT_MODE_WIDGET,
                                         command=self._set_capture_mode_widget)
            # Podmenu dla Znaków Wodnych
            watermark_submenu = Menu(capture_menu, tearoff=0)
            capture_menu.add_cascade(label=('Znak Wodny (Ukryj Widget)' if self.lang == 'pl' else 'Watermark (Hide Widget)'),
                                     menu=watermark_submenu)
            # Style znaków wodnych
            watermark_styles = {
                "1": ('Styl 1: Wycentrowany', 'Style 1: Centered'),
                "3": ('Styl 2: 3 (Siatka)', 'Style 2: 3 (Grid)'),
                "5": ('Styl 3: 5 (Siatka)', 'Style 3: 5 (Grid)'),
                "8": ('Styl 4: 8 (Siatka)', 'Style 4: 8 (Grid)')
            }
            for value, labels in watermark_styles.items():
                watermark_submenu.add_radiobutton(label=(labels[0] if self.lang == 'pl' else labels[1]),
                                                  variable=self._watermark_mode_var, value=value,
                                                  command=lambda v=value: self._set_watermark_style(v))
            popup.add_separator()

            # --- Czasy Nagrywania ---
            duration_menu = Menu(popup, tearoff=0)
            popup.add_cascade(label=('Czasy Nagrywania' if self.lang == 'pl' else 'Recording Durations'), menu=duration_menu)
            # Dynamiczne etykiety pokazujące aktualny czas
            duration_menu.add_command(label=f"{'Wideo' if self.lang == 'pl' else 'Video'}: {self._video_duration_seconds}s",
                                      command=lambda: self._configure_duration('video'))
            duration_menu.add_command(label=f"GIF: {self._gif_duration_seconds}s",
                                      command=lambda: self._configure_duration('gif'))
            popup.add_separator()

            # --- Zamknij ---
            popup.add_command(label=('Zamknij Widget' if self.lang == 'pl' else 'Close Widget'), command=self._close_widget)

            # Wyświetl menu w miejscu kliknięcia
            popup.tk_popup(event.x_root, event.y_root)

        finally:
            # Zwolnij przechwycenie myszy przez menu (ważne)
            popup.grab_release()

    # ----------- POPRAWIONA FUNKCJA _edit_widget -----------
    def _edit_widget(self) -> None:
        """Otwiera okno dialogowe do edycji tekstu monitu."""
        if not self.master.winfo_exists(): return

        title = 'Edytuj Monit' if self.lang == 'pl' else 'Edit Prompt'
        label = 'Wprowadź nowy monit:' if self.lang == 'pl' else 'Enter new prompt:'

        # Użyj simpledialog do pobrania nowego monitu
        # parent=None może pomóc w spakowanych aplikacjach (.exe), gdzie parent=self.master czasami zawodzi
        new_prompt = simpledialog.askstring(title, label,
                                            parent=None, # Usunięto parent=self.master - potencjalna poprawka dla .exe
                                            initialvalue=self.prompt) # Wartość początkowa w polu

        # Sprawdź, czy użytkownik coś wpisał i czy jest to różne od obecnego monitu
        if new_prompt is not None: # None oznacza, że użytkownik kliknął Anuluj
             new_prompt_stripped = new_prompt.strip()
             if new_prompt_stripped and new_prompt_stripped != self.prompt:
                 self.prompt = new_prompt_stripped
                 logging.info(f"Zmieniono monit na: {self.prompt}")
                 # Odśwież widok, wymuszając zmianę rozmiaru
                 # Użyj after_idle dla bezpieczeństwa w Tkinter
                 self.master.after_idle(lambda: self._update_display(force_resize=True))
             elif not new_prompt_stripped:
                 # Monit nie może być pusty
                 # Użyj after(0, ...) aby wykonać w głównym wątku Tkinter
                 self.master.after(0, lambda: messagebox.showwarning(
                     'Monit pusty' if self.lang == 'pl' else 'Empty Prompt',
                     'Monit nie może być pusty.' if self.lang == 'pl' else 'Prompt cannot be empty.',
                     parent=self.master # Tutaj parent=self.master dla messagebox jest zwykle OK
                 ))
             # Jeśli new_prompt == self.prompt, nic nie rób
    # ---------------------------------------------------------

    def _close_widget(self) -> None:
        """Rozpoczyna proces zamykania widgetu."""
        if self._cancel_update: # Jeśli proces zamykania już trwa
            return
        logging.info("Inicjowanie zamknięcia widgetu...")
        self._cancel_update = True # Ustaw flagę anulowania

        # Anuluj zaplanowany timer aktualizacji
        if self._update_timer:
            try:
                self.master.after_cancel(self._update_timer)
                logging.debug("Anulowano timer aktualizacji.")
            except Exception as e:
                 logging.warning(f"Błąd podczas anulowania timera: {e}")
            self._update_timer = None

        # Zatrzymaj nasłuchiwanie klawiszy (jeśli działa)
        if HAVE_PYNPUT and self._key_listener_thread and self._key_listener_thread.is_alive():
            logging.debug("Wysyłanie sygnału stop do wątku nasłuchującego klawisze.")
            self._key_listener_stop_event.set()
            # Nie czekaj tutaj na join, zrobimy to na końcu aplikacji

        # Zatrzymaj aktywny wątek przechwytywania (jeśli istnieje)
        # Wątki przechwytywania powinny same sprawdzać _cancel_update lub _key_listener_stop_event
        if self._active_capture_thread and self._active_capture_thread.is_alive():
            logging.info("Sygnalizowanie zatrzymania aktywnego wątku przechwytywania...")
            # Wątek powinien sam się zakończyć po sprawdzeniu flag

        # Zaplanuj bezpieczne zniszczenie okna Tkinter
        if self.master.winfo_exists():
            # Użyj `after` aby dać czas na zakończenie innych operacji
            self.master.after(50, self._safe_destroy)
        else:
             logging.debug("Okno master już nie istnieje podczas inicjowania zamykania.")


    def _safe_destroy(self) -> None:
        """Bezpiecznie niszczy główne okno Tkinter."""
        try:
            if self.master.winfo_exists():
                logging.info("Niszczenie okna głównego Tkinter.")
                self.master.destroy()
            else:
                 logging.debug("Próba zniszczenia okna, które już nie istnieje.")
        except tk.TclError as e:
            # Może się zdarzyć, jeśli okno zostanie zniszczone w międzyczasie
            logging.warning(f"Błąd TclError podczas niszczenia okna (prawdopodobnie już zniszczone): {e}")
        except Exception as e:
             logging.error(f"Nieoczekiwany błąd podczas niszczenia okna: {e}", exc_info=True)

    def _initial_data_fetch_and_show(self) -> None:
        """Pobiera początkowe dane i następnie pokazuje widget."""
        logging.debug("Rozpoczęcie początkowego pobierania danych.")
        self._fetch_and_update_data() # Pobierz dane pierwszy raz
        if not self._cancel_update and self.master.winfo_exists():
            # Użyj after(0, ...) aby wykonać operacje UI w głównym wątku
            logging.debug("Planowanie pokazania widgetu i rozpoczęcia aktualizacji.")
            self.master.after(0, self._show_and_start_updates)
        elif self._cancel_update:
            logging.info("Anulowano przed pokazaniem widgetu.")


    def _show_and_start_updates(self) -> None:
        """Pokazuje widget i rozpoczyna cykliczne aktualizacje."""
        if self._cancel_update or not self.master.winfo_exists():
            logging.debug("Pominięto pokazanie widgetu (anulowano lub okno nie istnieje).")
            return

        try:
            # Upewnij się, że widget jest gotowy do pokazania
            self.master.update_idletasks()

            # Zastosuj aktualne kolory przed pokazaniem
            if self.label_main: self.label_main.config(fg=self._current_text_color)
            if self.label_shadow and self._show_shadow_var.get(): self.label_shadow.config(fg=self._current_shadow_color)

            # Zaktualizuj tekst i rozmiar
            self._update_display(force_resize=True)

            # Pokaż okno
            self.master.deiconify() # Pokaż okno (jeśli było ukryte przez withdraw())
            self.master.lift() # Podnieś okno na wierzch
            self.master.attributes('-topmost', True) # Upewnij się, że jest na wierzchu

            logging.info("Widget pokazany. Rozpoczynanie cyklicznych aktualizacji.")

            # Sprawdź kolor tła po krótkiej chwili (daj czas na rendering)
            if ENABLE_AUTO_COLOR_INVERSION:
                self.master.after(300, self._check_and_update_widget_color)

            # Rozpocznij cykl aktualizacji
            self._schedule_next_update()

        except tk.TclError as e:
            logging.error(f"Błąd TclError podczas pokazywania widgetu: {e}")
            if not self._cancel_update: self._close_widget()
        except Exception as e:
             logging.error(f"Nieoczekiwany błąd podczas pokazywania widgetu: {e}", exc_info=True)
             if not self._cancel_update: self._close_widget()


    def _fetch_and_update_data(self) -> None:
        """Pobiera dane z API i aktualizuje wewnętrzne zmienne stanu."""
        if self._cancel_update: return

        logging.debug("Rozpoczęcie pobierania danych z API.")
        self._last_error = None # Resetuj ostatni błąd
        results = {'beat': None, 'height': None, 'hash_short': None, 'hash_full': None}
        fetch_errors = [] # Lista błędów z tego cyklu

        # Funkcja pomocnicza do bezpiecznego pobierania danych w wątku
        def fetch_api_data_safe(url: str, key: str, process_func) -> None:
            if self._cancel_update: return
            try:
                data = self._get_api_data(url) # Używa cache i timeout
                if data and "Error" not in data: # Podstawowa walidacja
                    processed_data = process_func(data)
                    results[key] = processed_data
                    # Jeśli przetwarzanie zwróci błąd, dodaj go do listy
                    if isinstance(processed_data, str) and "Error" in processed_data:
                         fetch_errors.append(f"{key}: Processing failed ({processed_data})")
                elif data and "Error" in data:
                    results[key] = data # Zapisz błąd pobierania
                    fetch_errors.append(f"{key}: Fetch failed ({data})")
                else:
                    # Puste dane lub inny problem
                    results[key] = "Error: No data"
                    fetch_errors.append(f"{key}: No data received")

            except Exception as e:
                error_msg = f"Error: {e.__class__.__name__}"
                results[key] = error_msg
                fetch_errors.append(f"{key}: Exception - {e}")
                logging.warning(f"Wyjątek podczas pobierania danych dla {key} ({url}): {e}")

        # Definicje funkcji przetwarzających dane
        def process_beat_time(_: Optional[str]) -> str: # Argument ignorowany
            return self._get_swatch_internet_time()

        def process_height(data: Optional[str]) -> str:
            # Prosta walidacja - czy jest liczbą
            if isinstance(data, str) and data.isdigit():
                return data
            else:
                logging.warning(f"Otrzymano nieprawidłową wysokość bloku: {data}")
                return "Error: Invalid Height"

        def process_hash(data: Optional[str]) -> str:
             # Walidacja hasha (64 znaki hex)
             if isinstance(data, str) and len(data) == 64 and all(c in '0123456789abcdefABCDEF' for c in data.lower()):
                 results['hash_full'] = data # Zapisz pełny hash
                 return f"{data[:6]}...{data[-4:]}" # Zwróć skróconą wersję
             else:
                 logging.warning(f"Otrzymano nieprawidłowy hash bloku: {data}")
                 results['hash_full'] = f"Error: Invalid Hash ({data[:20]}...)" if data else "Error: Invalid Hash (None)"
                 return "Error: Invalid Hash"

        # Tworzenie i uruchamianie wątków pobierających
        threads = [
            threading.Thread(target=lambda: results.__setitem__('beat', process_beat_time(None)), daemon=True, name="FetchBeatTime"),
            threading.Thread(target=fetch_api_data_safe, args=(BLOCK_HEIGHT_URL, 'height', process_height), daemon=True, name="FetchBlockHeight"),
            threading.Thread(target=fetch_api_data_safe, args=(BLOCK_HASH_URL, 'hash_short', process_hash), daemon=True, name="FetchBlockHash")
        ]

        for t in threads: t.start()
        # Czekaj na zakończenie wątków z timeoutem
        join_timeout = API_TIMEOUT_SECONDS + 2 # Daj trochę więcej czasu niż timeout API
        for t in threads: t.join(timeout=join_timeout)

        # Sprawdź, czy któryś wątek nadal działa (timeout)
        active_threads = [t.name for t in threads if t.is_alive()]
        if active_threads:
            error_msg = f"Timeout waiting for threads: {', '.join(active_threads)}"
            fetch_errors.append(error_msg)
            logging.warning(error_msg)

        # Zakończ, jeśli widget został anulowany w międzyczasie
        if self._cancel_update:
            logging.debug("Pobieranie danych przerwane (anulowano).")
            return

        # Aktualizuj zmienne stanu widgetu wynikami
        # Używaj .get() z domyślną wartością na wypadek, gdyby klucz nie istniał
        self._beat_time_str = results.get('beat') or "@ErrorBeat"
        self._block_height_str = results.get('height') or "ErrorHeight"
        self._block_hash_short_str = results.get('hash_short') or "ErrorHashShort"
        # _full_block_hash_str jest ustawiany w process_hash, ale upewnijmy się, że ma jakąś wartość
        self._full_block_hash_str = results.get('hash_full') # Może być None lub "Error: ..."

        # Zapisz skonsolidowany błąd, jeśli wystąpiły problemy
        if fetch_errors:
            self._last_error = "; ".join(fetch_errors)
            logging.warning(f"Błędy podczas pobierania danych: {self._last_error}")

        # Zgłoś potrzebę aktualizacji UI (zrobione w _perform_update_cycle)
        logging.debug("Zakończono pobieranie danych.")
        # Aktualizacja UI jest wywoływana po powrocie z wątku w _perform_update_cycle

    def _format_display_text(self) -> str:
        """Formatuje tekst do wyświetlenia w widgecie."""
        time_str = self._current_time_str
        height_str = self._block_height_str if "Error" not in self._block_height_str else "Błąd Wys." if self.lang == 'pl' else "Hgt Err"
        beat_str = self._beat_time_str if "Error" not in self._beat_time_str else "@???"

        # Wybierz hash do wyświetlenia
        if self._display_full_hash_permanently_var.get() and isinstance(self._full_block_hash_str, str) and "Error" not in self._full_block_hash_str:
            display_hash = self._full_block_hash_str
        elif self._block_hash_short_str and "Error" not in self._block_hash_short_str:
             display_hash = self._block_hash_short_str
        else:
            display_hash = ('Błąd Hasha' if self.lang == 'pl' else 'Hash Err')

        # Formatowanie monitu
        prompt_part = f"{self.prompt}@" if self.prompt.endswith('@') else f"{self.prompt} @"

        # Budowanie tekstu
        text_lines = [
            f"{prompt_part}",
            f"{'Czas' if self.lang == 'pl' else 'Time'}: {time_str} | BeatTime: {beat_str} | {'Blok' if self.lang == 'pl' else 'Block'}: {height_str}",
            f"{'Hash' if self.lang == 'pl' else 'Hash'}: {display_hash}"
        ]

        # Dodaj informację o błędzie, jeśli wystąpił
        if self._last_error:
            # Skróć komunikat błędu, jeśli jest zbyt długi
            error_display = self._last_error[:70] + ('...' if len(self._last_error) > 70 else '')
            text_lines.append(f"({'Błąd danych' if self.lang == 'pl' else 'Data error'}: {error_display})")

        return "\n".join(text_lines)

    def _update_display(self, force_resize: bool = False) -> None:
        """Aktualizuje tekst i potencjalnie rozmiar widgetu."""
        if self._cancel_update or not self.master.winfo_exists(): return
        # Sprawdź, czy etykiety istnieją (na wszelki wypadek)
        if not self.label_main or not self.label_main.winfo_exists():
            logging.warning("Próba aktualizacji nieistniejącej etykiety głównej.")
            return

        try:
            # Zaktualizuj czas lokalny
            self._current_time_str = time.strftime('%H:%M:%S')
            # Pobierz sformatowany tekst
            display_text = self._format_display_text()

            # Ustaw tekst i czcionkę dla głównej etykiety
            self.label_main.config(text=display_text, font=self._current_font_options, fg=self._current_text_color)

            # Ustaw tekst i czcionkę dla cienia (jeśli istnieje i jest włączony)
            if self.label_shadow and self.label_shadow.winfo_exists():
                if self._show_shadow_var.get():
                    self.label_shadow.config(text=display_text, font=self._current_font_options, fg=self._current_shadow_color)
                    # Upewnij się, że cień jest na miejscu
                    if not self.label_shadow.winfo_ismapped():
                        self.label_shadow.place(x=SHADOW_OFFSET_X, y=SHADOW_OFFSET_Y)
                elif self.label_shadow.winfo_ismapped(): # Ukryj, jeśli nie powinien być widoczny
                    self.label_shadow.place_forget()

            # Dostosuj rozmiar okna, jeśli tekst się zmienił lub wymuszono resize
            if force_resize:
                # update_idletasks() jest potrzebne, aby .winfo_reqwidth/height() zwróciły aktualne wartości
                self.master.update_idletasks()

                # Pobierz wymagany rozmiar głównej etykiety
                main_width = self.label_main.winfo_reqwidth()
                main_height = self.label_main.winfo_reqheight()

                # Uwzględnij przesunięcie cienia (jeśli jest widoczny) w wymaganym rozmiarze okna
                shadow_x_margin = abs(SHADOW_OFFSET_X) if self._show_shadow_var.get() and self.label_shadow and self.label_shadow.winfo_ismapped() else 0
                shadow_y_margin = abs(SHADOW_OFFSET_Y) if self._show_shadow_var.get() and self.label_shadow and self.label_shadow.winfo_ismapped() else 0

                req_width = main_width + shadow_x_margin
                req_height = main_height + shadow_y_margin

                # Ustaw nową geometrię tylko jeśli wymiary są poprawne
                if req_width > 0 and req_height > 0:
                    current_x = self.master.winfo_x()
                    current_y = self.master.winfo_y()

                    # Prosta ochrona przed ustawieniem okna poza ekranem (np. po zmianie rozdzielczości)
                    # To nie jest pełne rozwiązanie, ale zapobiega "zniknięciu" okna
                    screen_width = self.master.winfo_screenwidth()
                    screen_height = self.master.winfo_screenheight()
                    if current_x + req_width < 50: # Jeśli prawy brzeg jest blisko lewej krawędzi ekranu
                         current_x = 50
                    if current_y + req_height < 50: # Jeśli dolny brzeg jest blisko górnej krawędzi ekranu
                         current_y = 50
                    if current_x > screen_width - 50: # Jeśli lewy brzeg jest blisko prawej krawędzi
                         current_x = screen_width - req_width - 50
                    if current_y > screen_height - 50: # Jeśli górny brzeg jest blisko dolnej krawędzi
                         current_y = screen_height - req_height - 50

                    # Zabezpieczenie przed ujemnymi koordynatami, które mogą powodować problemy
                    current_x = max(0, current_x)
                    current_y = max(0, current_y)


                    self.master.geometry(f"{req_width}x{req_height}+{current_x}+{current_y}")
                else:
                    logging.warning(f"Obliczono nieprawidłowy rozmiar widgetu: {req_width}x{req_height}")

        except tk.TclError as e:
            # Obsługa błędu, który może wystąpić, jeśli okno zostanie zamknięte podczas aktualizacji
            logging.warning(f"Błąd TclError podczas aktualizacji wyświetlania: {e}")
            if not self._cancel_update: self._close_widget()
        except Exception as e:
             logging.error(f"Nieoczekiwany błąd podczas aktualizacji wyświetlania: {e}", exc_info=True)


    def _schedule_next_update(self) -> None:
        """Planuje następne wywołanie cyklu aktualizacji."""
        if self._cancel_update or not self.master.winfo_exists():
            return
        # Zaplanuj wywołanie _perform_update_cycle za 1000 ms (1 sekunda)
        self._update_timer = self.master.after(1000, self._perform_update_cycle)

    def _perform_update_cycle(self) -> None:
        """Wykonuje jeden cykl aktualizacji: pobiera dane, aktualizuje UI."""
        if self._cancel_update or not self.master.winfo_exists():
            return

        # Uruchom pobieranie danych w osobnym wątku, aby nie blokować UI
        threading.Thread(target=self._fetch_and_update_data, name="DataFetchWorker", daemon=True).start()

        # Zaktualizuj wyświetlanie (czas lokalny i potencjalnie stare dane, dopóki nowe nie przyjdą)
        # force_resize=False, bo zwykle tylko czas się zmienia co sekundę
        self._update_display(force_resize=False)

        # Sprawdzaj kolor tła co jakiś czas (np. co 10 sekund), a nie co sekundę
        if not hasattr(self, '_color_check_counter'): self._color_check_counter = 0
        self._color_check_counter = (self._color_check_counter + 1) % 10 # Licznik modulo 10
        if self._color_check_counter == 0 and ENABLE_AUTO_COLOR_INVERSION:
            # Sprawdź kolor w głównym wątku
            self.master.after(10, self._check_and_update_widget_color) # Małe opóźnienie

        # Zaplanuj następny cykl
        self._schedule_next_update()

    def _get_api_data(self, url: str) -> Optional[str]:
        """Pobiera dane z URL, używając cache."""
        cache_file = None
        if self._cache_dir:
            # Proste tworzenie klucza cache z URL
            cache_key = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_"))[:100]
            cache_file = os.path.join(self._cache_dir, cache_key + ".cache")

            # Sprawdź cache
            if os.path.exists(cache_file):
                try:
                    cache_age = time.time() - os.path.getmtime(cache_file)
                    if cache_age < CACHE_TIME_SECONDS:
                        logging.debug(f"Używam danych z cache dla {url} (wiek: {cache_age:.1f}s)")
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            return f.read().strip()
                except Exception as e:
                    logging.warning(f"Błąd odczytu cache {cache_file}: {e}")

        # Jeśli brak cache lub jest przestarzały, pobierz z sieci
        try:
            logging.debug(f"Pobieranie danych z API: {url}")
            headers = {'User-Agent': f'TimechainWidget/{VERSION}'}
            response = requests.get(url, timeout=API_TIMEOUT_SECONDS, headers=headers)
            response.raise_for_status() # Rzuci wyjątkiem dla błędów HTTP (4xx, 5xx)
            data = response.text.strip()

            # Zapisz do cache, jeśli pobrano poprawnie i cache jest włączony
            if cache_file and data:
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(data)
                    logging.debug(f"Zapisano dane do cache: {cache_file}")
                except Exception as e:
                    logging.warning(f"Błąd zapisu do cache {cache_file}: {e}")
            return data

        except requests.exceptions.Timeout:
            logging.warning(f"Timeout podczas pobierania {url}")
            error_msg = "Error: Timeout"
        except requests.exceptions.RequestException as e:
            logging.warning(f"Błąd żądania dla {url}: {e}")
            error_msg = f"Error: Request failed ({e.__class__.__name__})"
        except Exception as e:
             logging.error(f"Nieoczekiwany błąd podczas pobierania {url}: {e}", exc_info=True)
             error_msg = f"Error: Unexpected ({e.__class__.__name__})"


        # Jeśli wystąpił błąd, spróbuj zwrócić stare dane z cache jako fallback
        if cache_file and os.path.exists(cache_file):
            try:
                logging.warning(f"Zwracam przestarzałe dane z cache dla {url} z powodu błędu: {error_msg}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception as e:
                 logging.warning(f"Błąd odczytu przestarzałego cache {cache_file}: {e}")

        # Jeśli nie ma fallbacku, zwróć błąd
        return error_msg


    def _get_swatch_internet_time(self) -> str:
        """Oblicza aktualny czas Swatch Internet Time (@beats)."""
        try:
            # Użyj UTC+1 (Biel Mean Time - BMT)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            # Przesunięcie do strefy czasowej BMT (UTC+1)
            bmt_offset = datetime.timedelta(hours=1)
            now_bmt = now_utc + bmt_offset

            # Oblicz liczbę sekund od północy BMT
            total_seconds_bmt = (now_bmt.hour * 3600 + now_bmt.minute * 60 + now_bmt.second)

            # 1 beat = 1/1000 dnia = 86.4 sekundy
            beats = total_seconds_bmt / 86.4

            # Formatowanie do @ddd (000-999)
            return f"@{int(beats % 1000):03}" # Użyj modulo 1000 na wszelki wypadek
        except Exception as e:
            logging.error(f"Błąd obliczania Swatch Internet Time: {e}")
            return "@Error"

    # --- Funkcje Pomocnicze dla Przechwytywania ---

    def _get_font_path(self, font_name_preference: str, fallback_filenames: List[str]) -> Optional[str]:
        """Próbuje znaleźć ścieżkę do pliku czcionki."""
        # Najpierw sprawdź, czy system/PIL zna czcionkę po nazwie
        try:
            ImageFont.truetype(font_name_preference, 10)
            logging.debug(f"Znaleziono czcionkę systemową: {font_name_preference}")
            return font_name_preference
        except Exception:
            logging.debug(f"Czcionka systemowa '{font_name_preference}' niedostępna, szukam plików.")
            pass # Szukaj dalej w plikach

        # Standardowe lokalizacje czcionek
        font_dirs = []
        if platform.system() == "Windows":
            win_dir = os.environ.get("WINDIR", "C:\\Windows")
            if win_dir: font_dirs.append(os.path.join(win_dir, "Fonts"))
        elif platform.system() == "Darwin": # macOS
            font_dirs.extend(["/Library/Fonts", "/System/Library/Fonts", os.path.join(os.path.expanduser("~"), "Library", "Fonts")])
        else: # Linux / other Unix
            font_dirs.extend(["/usr/share/fonts", "/usr/local/share/fonts", os.path.join(os.path.expanduser("~"), ".fonts"), os.path.join(os.path.expanduser("~"), ".local/share/fonts")])

        # Dodaj bardziej generyczne fallbacki na koniec listy
        common_fallbacks = ["arial.ttf", "Arial.ttf", "verdana.ttf", "Verdana.ttf", "dejavusans.ttf", "DejaVuSans.ttf", " LiberationSans-Regular.ttf", "FreeSans.ttf", "NotoSans-Regular.ttf"]
        search_paths = fallback_filenames + [f for f in common_fallbacks if f not in fallback_filenames]

        # Szukaj plików czcionek
        for font_filename in search_paths:
            # Sprawdź, czy to już pełna ścieżka
            if os.path.isabs(font_filename) and os.path.exists(font_filename):
                try:
                    ImageFont.truetype(font_filename, 10)
                    logging.debug(f"Znaleziono czcionkę w podanej ścieżce: {font_filename}")
                    return font_filename
                except Exception:
                    continue # Spróbuj następnej

            # Szukaj w standardowych katalogach
            for font_dir in font_dirs:
                if not os.path.isdir(font_dir): continue # Pomiń jeśli katalog nie istnieje
                full_path = os.path.join(font_dir, font_filename)
                if os.path.exists(full_path):
                    try:
                        ImageFont.truetype(full_path, 10) # Sprawdź, czy PIL może ją załadować
                        logging.info(f"Znaleziono odpowiednią czcionkę: {full_path}")
                        return full_path
                    except Exception:
                        logging.debug(f"Plik {full_path} istnieje, ale PIL nie może go załadować.")
                        continue # Spróbuj następnego pliku/katalogu

        logging.warning(f"Nie znaleziono odpowiedniej czcionki dla '{font_name_preference}' ani fallbacków. Użycie domyślnej PIL.")
        return None # Zwróć None, jeśli nic nie znaleziono

    def _get_main_font_path(self) -> Optional[str]:
        """Zwraca ścieżkę do głównej czcionki widgetu (Segoe UI lub fallback)."""
        # Preferowane pliki dla Segoe UI na Windows
        windows_paths = []
        if platform.system() == "Windows":
             win_dir = os.environ.get("WINDIR", "C:\\Windows")
             if win_dir:
                  fonts_dir = os.path.join(win_dir, "Fonts")
                  windows_paths.extend([
                      os.path.join(fonts_dir, "segoeui.ttf"),
                      os.path.join(fonts_dir, "seguibld.ttf"), # Bold
                      os.path.join(fonts_dir, "segoeuil.ttf"), # Light
                      os.path.join(fonts_dir, "seguisb.ttf") # Semibold
                  ])
        # Wywołaj generyczną funkcję szukającą
        return self._get_font_path(FONT_FAMILY, windows_paths)


    def _create_watermark_text(self) -> str:
        """Tworzy tekst znaku wodnego na podstawie aktualnych danych."""
        # Użyj pełnego hasha, jeśli jest dostępny i poprawny, inaczej krótkiego
        hash_to_use = "Błąd Hasha" # Domyślnie
        if isinstance(self._full_block_hash_str, str) and len(self._full_block_hash_str) == 64:
             hash_to_use = self._full_block_hash_str
        elif self._block_hash_short_str and "Error" not in self._block_hash_short_str:
             hash_to_use = self._block_hash_short_str
        elif self._full_block_hash_str: # Nawet jeśli jest to błąd, pokaż go
            hash_to_use = self._full_block_hash_str

        height_str = self._block_height_str if "Error" not in self._block_height_str else "Błąd Wys." if self.lang == 'pl' else "Hgt Err"
        beat_str = self._beat_time_str if "Error" not in self._beat_time_str else "@???"

        prompt_part = f"{self.prompt}@" if self.prompt.endswith('@') else f"{self.prompt} @"

        # Zwróć sformatowany tekst wieloliniowy
        return (
            f"{prompt_part}\n"
            f"{'Czas' if self.lang == 'pl' else 'Time'}: {self._current_time_str} | BeatTime: {beat_str} | {'Blok' if self.lang == 'pl' else 'Block'}: {height_str}\n"
            f"{'Hash' if self.lang == 'pl' else 'Hash'}: {hash_to_use}"
        )

    def _calculate_grid_paste_positions_seeded(
        self, image_width: int, image_height: int, num_watermarks: int,
        rotated_stamp_width: int, rotated_stamp_height: int,
        random_generator: random.Random
    ) -> List[Tuple[int, int]]:
        """Oblicza pozycje wklejenia dla siatki znaków wodnych, używając ziarna losowości."""
        positions = []
        # Definicje komórek siatki 3x3 (indeksy: rząd, kolumna)
        grid_definitions = {
            # 0,0 0,1 0,2
            # 1,0 1,1 1,2
            # 2,0 2,1 2,2
            3: [(0, 0), (2, 2), (1, 1)],              # Rogi + środek
            5: [(0, 0), (0, 2), (2, 0), (2, 2), (1, 1)], # Rogi + środek
            8: [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)] # Wszystkie oprócz środka
        }

        selected_cells = grid_definitions.get(num_watermarks)
        if not selected_cells:
            logging.warning(f"Nieznana liczba znaków wodnych dla siatki: {num_watermarks}. Używam 1.")
            # Fallback do pojedynczego znaku wodnego na środku
            center_x = max(0, (image_width - rotated_stamp_width) // 2)
            center_y = max(0, (image_height - rotated_stamp_height) // 2)
            return [(center_x, center_y)]

        # Sprawdź, czy wymiary stempla są prawidłowe
        if rotated_stamp_width <= 0 or rotated_stamp_height <= 0:
             logging.error("Nieprawidłowe wymiary stempla dla obliczenia pozycji siatki.")
             return [] # Zwróć pustą listę, jeśli wymiary są złe

        # Margines od krawędzi obrazu
        fixed_margin = 20
        # Dostępny zakres dla lewego górnego rogu stempla
        range_x = image_width - 2 * fixed_margin - rotated_stamp_width
        range_y = image_height - 2 * fixed_margin - rotated_stamp_height

        # Jeśli stempel jest większy niż dostępny obszar, umieść go na 0,0
        if range_x <= 0 or range_y <= 0:
            logging.warning("Stempel znaku wodnego jest zbyt duży dla siatki, umieszczam na (0,0).")
            return [(0, 0)]

        # Oblicz bazowe punkty startowe dla komórek siatki 3x3
        start_points_x = [fixed_margin, fixed_margin + range_x // 2, fixed_margin + range_x]
        start_points_y = [fixed_margin, fixed_margin + range_y // 2, fixed_margin + range_y]

        # Dodaj małe losowe przesunięcie, aby nie były idealnie wyrównane
        max_offset = 15 # Maksymalne przesunięcie w pikselach

        for row, col in selected_cells:
            # Pobierz bazową pozycję dla komórki
            base_paste_x = start_points_x[col]
            base_paste_y = start_points_y[row]

            # Wygeneruj losowe przesunięcie
            offset_x = random_generator.randint(-max_offset, max_offset)
            offset_y = random_generator.randint(-max_offset, max_offset)

            # Oblicz finalną pozycję wklejenia, upewniając się, że mieści się w granicach obrazu
            paste_x = max(0, min(int(base_paste_x + offset_x), image_width - rotated_stamp_width))
            paste_y = max(0, min(int(base_paste_y + offset_y), image_height - rotated_stamp_height))

            positions.append((paste_x, paste_y))

        logging.debug(f"Obliczono {len(positions)} pozycji dla siatki {num_watermarks}.")
        return positions


    def _add_watermark_pil(self, image: Image.Image, text: str, predefined_paste_positions: Optional[List[Tuple[int, int]]] = None) -> Image.Image:
        """Dodaje znak wodny do obrazu PIL."""
        if not PIL_AVAILABLE:
            logging.error("Próba dodania znaku wodnego PIL bez zainstalowanego Pillow.")
            return image # Zwróć oryginalny obraz

        if not text:
             logging.warning("Pusty tekst znaku wodnego, pomijam dodawanie.")
             return image

        try:
            # Upewnij się, że obraz ma kanał alfa do wklejania przezroczystego znaku
            if image.mode != 'RGBA':
                image = image.convert('RGBA')

            width, height = image.size
            wm_mode = self._watermark_mode_var.get() # Pobierz styl '1', '3', '5', '8'
            num_watermarks = 1
            is_grid_based = False
            if wm_mode.isdigit() and int(wm_mode) in [3, 5, 8]:
                 num_watermarks = int(wm_mode)
                 is_grid_based = True
            elif wm_mode != "1":
                 logging.warning(f"Nieznany styl znaku wodnego '{wm_mode}', używam stylu '1'.")
                 wm_mode = "1"


            # --- Przygotowanie stempla znaku wodnego ---
            font_path = self._get_main_font_path()
            try:
                font = ImageFont.truetype(font_path, WATERMARK_FONT_SIZE) if font_path else ImageFont.load_default()
                if not font_path:
                     logging.warning("Używam domyślnej czcionki PIL dla znaku wodnego.")
            except IOError:
                logging.error(f"Nie można załadować czcionki {font_path}. Używam domyślnej.")
                font = ImageFont.load_default()

            # Zmierz rozmiar tekstu, aby utworzyć stempel odpowiedniej wielkości
            # Użyj textbbox dla dokładniejszego pomiaru, jeśli dostępny (nowsze Pillow)
            temp_img_for_measurement = Image.new("RGBA", (1, 1)) # Minimalny obrazek
            temp_draw = ImageDraw.Draw(temp_img_for_measurement)
            try:
                # textbbox zwraca (left, top, right, bottom)
                bbox = temp_draw.textbbox((0, 0), text, font=font, spacing=4, align="left") # align może pomóc
                # Rzeczywista szerokość i wysokość
                measured_text_width = bbox[2] - bbox[0]
                measured_text_height = bbox[3] - bbox[1]
                # Pozycja rysowania tekstu na stemplu, aby uwzględnić bbox[0], bbox[1]
                text_draw_x = -bbox[0]
                text_draw_y = -bbox[1]
            except AttributeError:
                # Starsza wersja Pillow - użyj multiline_textsize (mniej dokładne)
                size = temp_draw.multiline_textsize(text, font=font, spacing=4)
                bbox = (0, 0, size[0], size[1])
                measured_text_width = size[0]
                measured_text_height = size[1]
                text_draw_x = 0
                text_draw_y = 0
                logging.debug("Używam multiline_textsize do pomiaru tekstu znaku wodnego (starsze Pillow?).")


            del temp_draw
            del temp_img_for_measurement

            if measured_text_width <= 0 or measured_text_height <= 0:
                 logging.error("Obliczony rozmiar tekstu znaku wodnego jest nieprawidłowy.")
                 return image # Zwróć oryginalny obraz


            # Dodaj margines do stempla
            margin = 10
            stamp_width = max(1, measured_text_width + 2 * margin)
            stamp_height = max(1, measured_text_height + 2 * margin)

            # Pozycja tekstu na stemplu (z uwzględnieniem marginesu i bbox)
            final_text_x = margin + text_draw_x
            final_text_y = margin + text_draw_y

            # Utwórz obraz stempla (przezroczysty)
            stamp_image = Image.new("RGBA", (stamp_width, stamp_height), (0, 0, 0, 0))
            draw_stamp = ImageDraw.Draw(stamp_image)

            # Oblicz przezroczystość
            alpha = int(255 * (WATERMARK_OPACITY / 100.0))
            alpha = max(0, min(255, alpha)) # Upewnij się, że jest w zakresie 0-255

            # Pobierz kolory RGB (upewnij się, że są krotkami)
            try:
                wm_shadow_color_rgb = ImageColor.getrgb(self._current_shadow_color)
            except ValueError:
                logging.warning(f"Nieprawidłowy kolor cienia '{self._current_shadow_color}', używam czarnego.")
                wm_shadow_color_rgb = (0, 0, 0)
            try:
                wm_text_color_rgb = ImageColor.getrgb(self._current_text_color)
            except ValueError:
                logging.warning(f"Nieprawidłowy kolor tekstu '{self._current_text_color}', używam białego.")
                wm_text_color_rgb = (255, 255, 255)


            # Narysuj cień (jeśli włączony)
            if self._show_shadow_var.get():
                 shadow_offset_wm = 2 # Małe przesunięcie dla cienia na znaku wodnym
                 draw_stamp.text(
                     (final_text_x + shadow_offset_wm, final_text_y + shadow_offset_wm),
                     text,
                     font=font,
                     fill=(*wm_shadow_color_rgb, alpha), # Kolor cienia z przezroczystością
                     spacing=4,
                     align="left"
                 )

            # Narysuj główny tekst
            draw_stamp.text(
                (final_text_x, final_text_y),
                text,
                font=font,
                fill=(*wm_text_color_rgb, alpha), # Kolor tekstu z przezroczystością
                spacing=4,
                align="left"
            )

            # --- Obrót stempla ---
            rotated_stamp = stamp_image
            rotated_width, rotated_height = stamp_image.size
            if WATERMARK_ANGLE != 0:
                try:
                    # Wybierz metodę resampling (nowsze Pillow używa Image.Resampling)
                    resample_method = Image.Resampling.BICUBIC if hasattr(Image, 'Resampling') else Image.BICUBIC

                    # Obróć stempel, expand=True dostosowuje rozmiar obrazu
                    rotated_stamp = stamp_image.rotate(WATERMARK_ANGLE, resample=resample_method, expand=True)
                    rotated_width, rotated_height = rotated_stamp.size
                    logging.debug(f"Obrócono stempel o {WATERMARK_ANGLE} stopni. Nowy rozmiar: {rotated_width}x{rotated_height}")
                except Exception as e:
                    logging.error(f"Błąd podczas obracania stempla znaku wodnego: {e}")
                    # Użyj nieobróconego stempla jako fallback
                    rotated_stamp = stamp_image
                    rotated_width, rotated_height = stamp_image.size


            # --- Obliczanie pozycji wklejenia ---
            paste_locations = []
            if is_grid_based:
                if predefined_paste_positions:
                    # Użyj pozycji przekazanych (dla spójności w wideo/GIF)
                    paste_locations = predefined_paste_positions
                    logging.debug(f"Używam predefiniowanych {len(paste_locations)} pozycji dla siatki.")
                else:
                    # Oblicz pozycje dla siatki (pierwsza klatka lub pojedynczy obraz)
                    if self._video_gif_random_seed is None:
                         self._video_gif_random_seed = int(time.time() * 1000) % 100000 # Inicjalizuj ziarno
                         logging.debug(f"Zainicjalizowano ziarno losowości dla siatki WM: {self._video_gif_random_seed}")
                    random_generator = random.Random(self._video_gif_random_seed) # Użyj ziarna
                    paste_locations = self._calculate_grid_paste_positions_seeded(
                        width, height, num_watermarks, rotated_width, rotated_height, random_generator
                    )
                    # Zapisz obliczone pozycje dla przyszłych klatek (jeśli to wideo/GIF)
                    self._fixed_watermark_paste_positions = paste_locations
            else:
                # Pojedynczy znak wodny - wycentrowany
                paste_x = max(0, (width - rotated_width) // 2)
                paste_y = max(0, (height - rotated_height) // 2)
                paste_locations = [(paste_x, paste_y)]
                logging.debug(f"Obliczono pozycję dla pojedynczego WM: {paste_locations[0]}")


            # --- Wklejanie stempla(ów) na obraz ---
            if not paste_locations:
                 logging.warning("Brak obliczonych pozycji do wklejenia znaku wodnego.")
            else:
                 logging.info(f"Wklejanie {len(paste_locations)} znaków wodnych.")
                 for i, (paste_x, paste_y) in enumerate(paste_locations):
                      # Sprawdzenie, czy pozycja ma sens (czy stempel będzie częściowo widoczny)
                      if paste_x < width and paste_y < height and paste_x + rotated_width > 0 and paste_y + rotated_height > 0:
                           # Wklej stempel używając jego kanału alfa jako maski
                           image.paste(rotated_stamp, (paste_x, paste_y), rotated_stamp)
                      else:
                          logging.warning(f"Pominięto wklejanie znaku wodnego {i+1} w pozycji {paste_x},{paste_y} (poza widocznym obszarem).")

            return image

        except Exception as e:
             logging.error(f"Nieoczekiwany błąd podczas dodawania znaku wodnego PIL: {e}", exc_info=True)
             return image # Zwróć oryginalny obraz w razie błędu


    def _add_watermark_cv2(self, frame: np.ndarray, text: str, predefined_paste_positions: Optional[List[Tuple[int, int]]]) -> np.ndarray:
        """Dodaje znak wodny do klatki OpenCV (używając logiki PIL)."""
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE or not PIL_AVAILABLE:
            logging.error("Brak wymaganych modułów (cv2, numpy, PIL) do dodania znaku wodnego do klatki CV2.")
            return frame # Zwróć oryginalną klatkę

        try:
            # Konwertuj klatkę OpenCV (zwykle BGR) do obrazu PIL (RGB)
            if frame.ndim == 3 and frame.shape[2] == 4: # BGRA?
                 img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA))
                 logging.debug("Konwersja klatki BGRA -> RGBA (PIL)")
            elif frame.ndim == 3 and frame.shape[2] == 3: # BGR
                 img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                 logging.debug("Konwersja klatki BGR -> RGB (PIL)")
            elif frame.ndim == 2: # Grayscale
                 img_pil = Image.fromarray(frame).convert('RGB') # Konwertuj do RGB
                 logging.debug("Konwersja klatki Grayscale -> RGB (PIL)")
            else:
                 logging.error(f"Nierozpoznany format klatki OpenCV: shape={frame.shape}, dtype={frame.dtype}")
                 return frame


            # Dodaj znak wodny używając funkcji PIL
            wm_img_pil = self._add_watermark_pil(img_pil, text, predefined_paste_positions)

            # Konwertuj z powrotem do formatu OpenCV (BGR)
            # Upewnij się, że wynikowy obraz PIL jest RGB przed konwersją do numpy
            if wm_img_pil.mode != 'RGB':
                wm_img_pil = wm_img_pil.convert('RGB')

            frame_with_wm = cv2.cvtColor(np.array(wm_img_pil), cv2.COLOR_RGB2BGR)
            logging.debug("Konwersja klatki RGB (PIL) z WM -> BGR (CV2)")

            return frame_with_wm

        except Exception as e:
            logging.error(f"Błąd podczas dodawania znaku wodnego (CV2 <-> PIL): {e}", exc_info=True)
            return frame # Zwróć oryginalną klatkę w razie błędu

    # ----------- POPRAWIONA FUNKCJA _get_capture_filename -----------
    def _get_capture_filename(self, extension: str, mode: str) -> str:
        """Generuje unikalną nazwę pliku dla przechwyconego obrazu/wideo."""
        # Pobierz aktualny czas UTC
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")

        # Wyczyść monit użytkownika z niedozwolonych znaków
        # Zachowaj tylko litery, cyfry, podkreślenia i myślniki
        cleaned_prompt = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in self.prompt.replace(" ", "_"))[:25] # Ogranicz długość

        # Wybierz część hasha do nazwy pliku (pełny jeśli ok, krótki jeśli ok, inaczej N_A)
        hash_part = "N_A" # Domyślnie
        if isinstance(self._full_block_hash_str, str) and len(self._full_block_hash_str) == 64:
             # Użyj pełnego hasha (Uwaga: może wydłużyć nazwę pliku)
             hash_part = self._full_block_hash_str
        elif self._block_hash_short_str and "Error" not in self._block_hash_short_str:
             hash_part = self._block_hash_short_str.replace("...", "-") # Zastąp kropki myślnikiem
        elif self._full_block_hash_str: # Jeśli mamy tylko błąd w pełnym hashu, pokaż go
             hash_part = "ErrorHash" # Lub skrócona wersja błędu

        # Zbuduj bazową nazwę pliku
        # Dodaj tryb (widget/watermark) dla jasności
        filename_base = f"TimechainProof({timestamp})-[{mode}]-{cleaned_prompt}@{hash_part}"

        # Usuń znaki niedozwolone w nazwach plików Windows/Unix
        safe_filename_base = "".join(c if c not in r'<>:"/\|?*' else '_' for c in filename_base)

        # Ogranicz długość samej nazwy bazowej (bez rozszerzenia),
        # aby zmniejszyć ryzyko przekroczenia limitu ścieżki
        # np. 200 znaków - rozsądny kompromis
        MAX_BASE_FILENAME_LEN = 200
        if len(safe_filename_base) > MAX_BASE_FILENAME_LEN:
             logging.warning(f"Nazwa bazowa pliku skrócona do {MAX_BASE_FILENAME_LEN} znaków.")
             # Zachowaj początek i koniec, aby zachować unikalność
             keep_start = MAX_BASE_FILENAME_LEN // 2 - 10
             keep_end = MAX_BASE_FILENAME_LEN // 2 - 10
             safe_filename_base = safe_filename_base[:keep_start] + "..." + safe_filename_base[-keep_end:]


        # Połącz z rozszerzeniem
        filename = f"{safe_filename_base}.{extension.lower()}"

        # Znajdź katalog zapisu
        capture_dir = self._get_capture_directory() # Używa nowej, ulepszonej funkcji

        # Sprawdź unikalność i dodaj licznik, jeśli plik już istnieje
        full_path = os.path.join(capture_dir, filename)
        counter = 1
        original_safe_base = safe_filename_base # Zapamiętaj oryginalną bezpieczną nazwę

        while os.path.exists(full_path):
            # Dodaj licznik przed rozszerzeniem
            # Upewnij się, że nazwa z licznikiem też nie przekracza limitu
            suffix = f"_{counter}"
            if len(original_safe_base) + len(suffix) > MAX_BASE_FILENAME_LEN:
                 # Jeśli nawet z licznikiem jest za długo, skróć bazę jeszcze bardziej
                 cut_len = len(original_safe_base) + len(suffix) - MAX_BASE_FILENAME_LEN
                 safe_filename_base = original_safe_base[:-(cut_len + 3)] + "..." # +3 dla "..."
            else:
                 safe_filename_base = original_safe_base # Wróć do oryginału, jeśli jest miejsce

            filename = f"{safe_filename_base}{suffix}.{extension.lower()}"
            full_path = os.path.join(capture_dir, filename)
            counter += 1
            if counter > 100: # Zabezpieczenie przed nieskończoną pętlą
                 logging.error("Nie można znaleźć unikalnej nazwy pliku po 100 próbach.")
                 # Zwróć nazwę z bardzo dużym licznikiem lub dodaj mikrosekundy
                 timestamp_extra = datetime.datetime.now().strftime("%f")
                 filename = f"{original_safe_base}_{counter}_{timestamp_extra}.{extension.lower()}"
                 full_path = os.path.join(capture_dir, filename)
                 logging.warning(f"Użyto nazwy awaryjnej: {filename}")
                 break

        logging.info(f"Wygenerowano ścieżkę zapisu: {full_path}")
        return full_path
    # ---------------------------------------------------------


    def _get_capture_directory(self) -> str:
        """
        Zwraca katalog do zapisu plików przechwytywania.
        Preferuje podkatalog 'CAPTURE_SUBDIR' w katalogu aplikacji/skryptu.
        Zawiera mechanizmy fallback na wypadek problemów z uprawnieniami
        lub przy uruchamianiu jako spakowana aplikacja.
        """
        base_dir = None
        source_type = "unknown"

        # Krok 1: Określ katalog bazowy (skryptu lub pliku wykonywalnego)
        if getattr(sys, 'frozen', False) and hasattr(sys, 'executable'):
            # Aplikacja jest spakowana (np. przez PyInstaller)
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
            source_type = "frozen executable"
            logging.debug(f"Aplikacja spakowana, katalog bazowy (exe): {base_dir}")
        else:
            # Aplikacja uruchomiona jako skrypt .py
            try:
                # Użyj __file__ do znalezienia katalogu skryptu
                base_dir = os.path.dirname(os.path.abspath(__file__))
                source_type = "script"
                logging.debug(f"Aplikacja jako skrypt, katalog bazowy (__file__): {base_dir}")
            except NameError:
                # __file__ może nie być zdefiniowany (np. w interaktywnym interpreterze)
                base_dir = os.getcwd()
                source_type = "cwd fallback"
                logging.warning(f"Nie można określić katalogu skryptu (__file__), używam bieżącego katalogu roboczego: {base_dir}")

        if not base_dir or not os.path.isdir(base_dir):
             # Ostateczny fallback, jeśli wszystko inne zawiedzie
             base_dir = os.getcwd()
             source_type = "cwd ultimate fallback"
             logging.error(f"Nie udało się ustalić prawidłowego katalogu bazowego ({source_type}), używam CWD: {base_dir}")


        # Krok 2: Spróbuj utworzyć/użyć podkatalogu w katalogu bazowym
        target_capture_dir = os.path.join(base_dir, CAPTURE_SUBDIR)
        logging.debug(f"Preferowany katalog zapisu: {target_capture_dir}")

        try:
            # Utwórz podkatalog, jeśli nie istnieje
            if not os.path.exists(target_capture_dir):
                os.makedirs(target_capture_dir)
                logging.info(f"Utworzono katalog przechwytywania: {target_capture_dir}")
            elif not os.path.isdir(target_capture_dir):
                 # Istnieje plik o tej nazwie - to problem
                 logging.error(f"Ścieżka {target_capture_dir} istnieje, ale nie jest katalogiem.")
                 raise OSError(f"Path conflict: {target_capture_dir}")


            # Sprawdź uprawnienia do zapisu przez próbę utworzenia pliku testowego
            test_filename = f".write_test_{os.getpid()}_{random.randint(1000,9999)}"
            test_filepath = os.path.join(target_capture_dir, test_filename)
            can_write = False
            try:
                with open(test_filepath, 'w') as f_test:
                    f_test.write('test')
                os.remove(test_filepath) # Posprzątaj
                can_write = True
                logging.info(f"Potwierdzono możliwość zapisu w {target_capture_dir}.")
                return target_capture_dir # Sukces! Użyj podkatalogu.
            except Exception as write_e:
                logging.warning(f"Test zapisu do {target_capture_dir} nie powiódł się: {write_e}. Próba fallbacku.")
                # Usuń plik testowy, jeśli pozostał (np. przy błędzie uprawnień)
                if os.path.exists(test_filepath):
                    try: os.remove(test_filepath)
                    except Exception: pass


        except Exception as e:
            logging.error(f"Błąd podczas próby użycia/tworzenia {target_capture_dir}: {e}. Próba fallbacku.")

        # Krok 3: Fallback - spróbuj zapisać w katalogu bazowym
        logging.warning(f"Fallback: Próba zapisu w katalogu bazowym: {base_dir}")
        try:
            test_filename = f".write_test_base_{os.getpid()}_{random.randint(1000,9999)}"
            test_filepath = os.path.join(base_dir, test_filename)
            can_write_base = False
            try:
                with open(test_filepath, 'w') as f_test:
                    f_test.write('test')
                os.remove(test_filepath)
                can_write_base = True
                logging.info(f"Potwierdzono możliwość zapisu w katalogu bazowym {base_dir}.")
                return base_dir # Sukces! Użyj katalogu bazowego.
            except Exception as write_e:
                logging.error(f"Test zapisu do katalogu bazowego {base_dir} również nie powiódł się: {write_e}. Próba ostatecznego fallbacku.")
                if os.path.exists(test_filepath):
                    try: os.remove(test_filepath)
                    except Exception: pass

        except Exception as e:
            logging.error(f"Błąd podczas sprawdzania zapisu w katalogu bazowym {base_dir}: {e}. Próba ostatecznego fallbacku.")


        # Krok 4: Ostateczny Fallback - użyj katalogu tymczasowego systemu
        try:
            temp_dir = tempfile.gettempdir()
            # Opcjonalnie: utwórz podkatalog w katalogu tymczasowym
            final_capture_dir = os.path.join(temp_dir, f"TimechainWidgetCaptures_{os.getpid()}")
            os.makedirs(final_capture_dir, exist_ok=True) # Utwórz, jeśli nie istnieje
            # Zakładamy, że katalog tymczasowy jest zapisywalny, ale można dodać test
            logging.critical(f"KRYTYCZNY FALLBACK: Nie można zapisać ani w {target_capture_dir}, ani w {base_dir}. Używam katalogu tymczasowego: {final_capture_dir}")
            return final_capture_dir
        except Exception as e:
             # Jeśli nawet to zawiedzie...
             emergency_dir = os.getcwd() # Ostatnia deska ratunku
             logging.critical(f"NIE MOŻNA UTWORZYĆ KATALOGU NAWET W TEMP! Błąd: {e}. Używam CWD jako ostateczności: {emergency_dir}")
             return emergency_dir


    def _safely_restore_widget_visibility(self) -> None:
        """Przywraca widoczność widgetu (jeśli był ukryty)."""
        if not self.master.winfo_exists(): return
        try:
            # Sprawdź, czy stan to 'withdrawn' (ukryty przez withdraw())
            if self.master.state() == 'withdrawn':
                logging.debug("Przywracanie widoczności widgetu.")
                self.master.deiconify() # Pokaż
                self.master.lift() # Na wierzch
                self.master.attributes('-topmost', True) # Upewnij się, że jest na wierzchu
                self.master.update_idletasks() # Zastosuj zmiany

                # Sprawdź kolor po przywróceniu widoczności
                if ENABLE_AUTO_COLOR_INVERSION:
                    self.master.after(200, self._check_and_update_widget_color) # Daj czas na rendering
            # else: Widget jest już widoczny, nic nie rób
        except tk.TclError as e:
            logging.warning(f"Błąd TclError podczas przywracania widoczności widgetu: {e}")
            # Jeśli okno zostało zniszczone w międzyczasie
            if not self._cancel_update: self._close_widget()
        except Exception as e:
             logging.error(f"Nieoczekiwany błąd podczas przywracania widoczności: {e}", exc_info=True)


    def _hide_widget_for_capture(self) -> None:
        """Ukrywa widget (jeśli jest widoczny) na czas przechwytywania."""
        if self.master.winfo_exists() and self.master.state() != 'withdrawn':
            logging.debug("Ukrywanie widgetu na czas przechwytywania.")
            try:
                self.master.withdraw() # Ukryj okno
                self.master.update_idletasks() # Zastosuj zmianę natychmiast
            except tk.TclError as e:
                 logging.warning(f"Błąd TclError podczas ukrywania widgetu: {e}")
                 if not self._cancel_update: self._close_widget()
            except Exception as e:
                 logging.error(f"Nieoczekiwany błąd podczas ukrywania widgetu: {e}", exc_info=True)


    # --- Główne Funkcje Przechwytywania ---

    def _capture_screenshot(self) -> None:
        """Wykonuje zrzut ekranu (PNG) z opcjonalnym znakiem wodnym."""
        # Sprawdzenie warunków przed rozpoczęciem
        if self._cancel_update:
            logging.info("Przechwytywanie PNG anulowane (widget zamykany).")
            return
        if self._active_capture_thread and self._active_capture_thread.is_alive():
            logging.warning("Przechwytywanie PNG odrzucone: inny wątek przechwytywania jest aktywny.")
            # Opcjonalnie: Pokaż użytkownikowi komunikat
            self.master.after(0, lambda: messagebox.showwarning(
                'Przechwytywanie Aktywne' if self.lang == 'pl' else 'Capture Active',
                'Inny proces przechwytywania jest już w toku.' if self.lang == 'pl' else 'Another capture process is already running.',
                parent=self.master
            ))
            return

        # Ustaw bieżący wątek jako aktywny wątek przechwytywania
        self._active_capture_thread = threading.current_thread()
        logging.info("Rozpoczęcie przechwytywania zrzutu ekranu (PNG)...")

        capture_mode = self._screenshot_mode_var.get()
        file_path = self._get_capture_filename("png", capture_mode)
        original_visibility_state = False # Czy widget był widoczny przed ukryciem?

        try:
            # Sprawdź, czy widget jest widoczny i czy trzeba go ukryć
            widget_was_visible = False
            if self.master.winfo_exists():
                 widget_was_visible = self.master.state() != 'withdrawn'

            if capture_mode == SCREENSHOT_MODE_WATERMARK and widget_was_visible:
                original_visibility_state = True
                # Ukryj widget w głównym wątku Tkinter
                self.master.after(0, self._hide_widget_for_capture)
                time.sleep(0.2) # Daj systemowi chwilę na ukrycie okna

            # Wykonaj zrzut ekranu
            screenshot_image = None
            primary_capture_method = "pyautogui" if PYAUTOGUI_AVAILABLE else "ImageGrab" if IMAGEGRAB_AVAILABLE else "none"

            if primary_capture_method == "pyautogui":
                 try:
                     screenshot_image = pyautogui.screenshot()
                 except Exception as e_pg:
                     logging.error(f"Błąd pyautogui.screenshot: {e_pg}. Próba z ImageGrab.")
                     if IMAGEGRAB_AVAILABLE:
                         try: screenshot_image = ImageGrab.grab()
                         except Exception as e_ig: logging.error(f"Błąd ImageGrab.grab: {e_ig}")
                     else: logging.error("ImageGrab niedostępny.")

            elif primary_capture_method == "ImageGrab":
                 try:
                     screenshot_image = ImageGrab.grab()
                 except Exception as e_ig:
                     logging.error(f"Błąd ImageGrab.grab: {e_ig}. Próba z pyautogui.")
                     if PYAUTOGUI_AVAILABLE:
                          try: screenshot_image = pyautogui.screenshot()
                          except Exception as e_pg: logging.error(f"Błąd pyautogui.screenshot: {e_pg}")
                     else: logging.error("Pyautogui niedostępny.")
            else:
                 raise RuntimeError("Brak dostępnej metody przechwytywania ekranu (pyautogui/ImageGrab).")


            if screenshot_image is None:
                raise RuntimeError("Nie udało się wykonać zrzutu ekranu (obie metody zawiodły lub zwróciły None).")
            logging.debug(f"Zrzut ekranu wykonany (rozmiar: {screenshot_image.size}).")

            # Dodaj znak wodny, jeśli tryb to 'watermark'
            if capture_mode == SCREENSHOT_MODE_WATERMARK:
                logging.debug("Dodawanie znaku wodnego do zrzutu PNG...")
                # Resetuj ziarno i pozycje przed dodaniem do pojedynczego obrazu
                self._video_gif_random_seed = None
                self._fixed_watermark_paste_positions = None
                watermark_text = self._create_watermark_text()
                screenshot_image = self._add_watermark_pil(screenshot_image, watermark_text)

            # Przygotuj metadane PNG
            metadata = PngInfo()
            metadata.add_text("Software", f"TimechainWidget v{VERSION}")
            metadata.add_text("CaptureTimeUTC", datetime.datetime.now(datetime.timezone.utc).isoformat())
            metadata.add_text("Prompt", self.prompt)
            metadata.add_text("BlockHeight", self._block_height_str or "N/A")
            metadata.add_text("BlockHashFull", self._full_block_hash_str or "N/A")
            metadata.add_text("BlockHashShort", self._block_hash_short_str or "N/A")
            metadata.add_text("BeatTime", self._beat_time_str or "N/A")
            metadata.add_text("CaptureMode", capture_mode)
            if capture_mode == SCREENSHOT_MODE_WATERMARK:
                metadata.add_text("WatermarkStyle", self._watermark_mode_var.get())
                metadata.add_text("WatermarkOpacity", str(WATERMARK_OPACITY))
                metadata.add_text("WatermarkAngle", str(WATERMARK_ANGLE))
            # Można dodać więcej metadanych, np. rozdzielczość, system operacyjny

            # Zapisz obraz PNG z metadanymi
            logging.debug(f"Zapisywanie obrazu PNG do: {file_path}")
            screenshot_image.save(file_path, "PNG", pnginfo=metadata)

            # Sprawdź, czy plik został poprawnie zapisany
            if not os.path.exists(file_path):
                raise IOError(f"Plik PNG nie został utworzony po zapisie: {file_path}")
            if os.path.getsize(file_path) == 0:
                os.remove(file_path) # Usuń pusty plik
                raise IOError(f"Zapisany plik PNG jest pusty: {file_path}")

            logging.info(f"Zrzut ekranu zapisano pomyślnie: {file_path} (rozmiar: {os.path.getsize(file_path)} bajtów)")

            # Pokaż komunikat o sukcesie (w głównym wątku)
            msg_pl = f"Zrzut ekranu zapisano:\n{file_path}"
            msg_en = f"Screenshot saved:\n{file_path}"
            self.master.after(0, lambda: messagebox.showinfo(
                'Zapisano' if self.lang == 'pl' else 'Saved',
                msg_pl if self.lang == 'pl' else msg_en,
                parent=self.master
            ))

        except Exception as e:
            # Logowanie błędu i pokazanie komunikatu użytkownikowi
            logging.error(f"Błąd podczas przechwytywania zrzutu ekranu PNG: {e}", exc_info=True)
            error_msg_pl = f"Wystąpił błąd podczas zapisu zrzutu ekranu:\n{e}"
            error_msg_en = f"An error occurred while saving the screenshot:\n{e}"
            self.master.after(0, lambda: messagebox.showerror(
                'Błąd Zrzutu' if self.lang == 'pl' else 'Screenshot Error',
                error_msg_pl if self.lang == 'pl' else error_msg_en,
                parent=self.master
            ))
        finally:
            # Przywróć widoczność widgetu, jeśli był ukryty
            if original_visibility_state:
                # Użyj `after` aby wykonać w głównym wątku
                self.master.after(50, self._safely_restore_widget_visibility)

            # Zresetuj flagę aktywnego wątku przechwytywania
            self._active_capture_thread = None
            logging.debug("Zakończono wątek przechwytywania PNG.")


    def _capture_video(self) -> None:
        """Nagrywa wideo ekranu (MP4/AVI) przez określony czas z opcjonalnym znakiem wodnym."""
        # Sprawdzenia wstępne
        if self._cancel_update:
             logging.info("Przechwytywanie wideo anulowane (widget zamykany).")
             return
        if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
            logging.error("Nagrywanie wideo niemożliwe: brak modułów opencv-python lub numpy.")
            self.master.after(0, lambda: messagebox.showerror(
                 'Brak Modułów' if self.lang == 'pl' else 'Modules Missing',
                 'Nagrywanie wideo wymaga zainstalowania opencv-python i numpy.' if self.lang == 'pl' else 'Video recording requires opencv-python and numpy to be installed.',
                 parent=self.master
             ))
            return
        if self._active_capture_thread and self._active_capture_thread.is_alive():
            logging.warning("Przechwytywanie wideo odrzucone: inny wątek przechwytywania jest aktywny.")
            self.master.after(0, lambda: messagebox.showwarning(
                'Przechwytywanie Aktywne' if self.lang == 'pl' else 'Capture Active',
                'Inny proces przechwytywania jest już w toku.' if self.lang == 'pl' else 'Another capture process is already running.',
                parent=self.master
            ))
            return

        self._active_capture_thread = threading.current_thread()
        logging.info(f"Rozpoczęcie nagrywania wideo ({self._video_duration_seconds}s)...")

        capture_mode = self._screenshot_mode_var.get()
        # Określ rozszerzenie na podstawie kodeka
        file_extension = "mp4" if "mp4" in VIDEO_FOURCC.lower() else "avi" if "av" in VIDEO_FOURCC.lower() else "mkv" # Domyślne MKV?
        file_path = self._get_capture_filename(file_extension, capture_mode)
        duration = self._video_duration_seconds
        video_writer = None
        original_visibility_state = False
        # Resetuj/Inicjalizuj stan znaku wodnego dla tego nagrania
        self._fixed_watermark_paste_positions = None
        self._video_gif_random_seed = None
        frame_count = 0 # Licznik klatek zainicjowany tutaj


        try:
            # Pobierz rozmiar ekranu (użyj preferowanej metody)
            screen_size = None
            if PYAUTOGUI_AVAILABLE:
                 try: screen_size = pyautogui.size()
                 except Exception as e: logging.warning(f"Pyautogui.size() error: {e}")
            if screen_size is None and IMAGEGRAB_AVAILABLE:
                 try:
                      temp_im = ImageGrab.grab()
                      if temp_im: screen_size = temp_im.size
                 except Exception as e: logging.warning(f"ImageGrab.grab() for size error: {e}")

            if screen_size is None or not all(s > 0 for s in screen_size):
                 raise RuntimeError("Nie można określić rozmiaru ekranu.")

            width, height = screen_size
            logging.debug(f"Rozmiar ekranu dla wideo: {width}x{height}")

            # Inicjalizuj VideoWriter
            # Sprawdź poprawność FourCC
            if not isinstance(VIDEO_FOURCC, str) or len(VIDEO_FOURCC) != 4:
                 logging.error(f"Nieprawidłowy kod FourCC: '{VIDEO_FOURCC}'. Używam 'mp4v'.")
                 fourcc_code = "mp4v"
            else:
                 fourcc_code = VIDEO_FOURCC

            fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
            # Ustaw FPS (klatki na sekundę) - 20.0 to rozsądna wartość
            fps = 20.0
            logging.debug(f"Inicjalizacja VideoWriter: {file_path}, FourCC: {fourcc_code}, FPS: {fps}, Rozmiar: {width}x{height}")
            video_writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))

            if not video_writer.isOpened():
                # To częsty problem, jeśli brakuje odpowiednich kodeków w systemie
                error_msg = f"Nie można otworzyć VideoWriter dla pliku: {file_path}. Sprawdź kodek ({fourcc_code}) i uprawnienia do zapisu."
                logging.error(error_msg)
                # Spróbuj z innym kodekiem jako fallback? Np. 'XVID' dla AVI
                if fourcc_code != 'XVID':
                    logging.warning("Próba fallbacku na kodek XVID (wymaga rozszerzenia .avi)")
                    file_extension = "avi"
                    file_path = self._get_capture_filename(file_extension, capture_mode) # Nowa nazwa pliku
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    video_writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
                    if not video_writer.isOpened():
                         error_msg += "\nFallback na XVID również zawiódł."
                         raise IOError(error_msg)
                    else:
                         logging.info("Fallback na XVID udany. Zapisuję jako AVI.")
                else:
                     raise IOError(error_msg) # Jeśli 'XVID' już był próbowany


            # Przygotuj tekst znaku wodnego (jeśli potrzebny)
            watermark_text = None
            if capture_mode == SCREENSHOT_MODE_WATERMARK:
                watermark_text = self._create_watermark_text()
                logging.debug("Znak wodny włączony dla wideo.")
                # Jeśli siatka, oblicz stałe pozycje dla spójności
                if self._watermark_mode_var.get().isdigit() and int(self._watermark_mode_var.get()) in [3, 5, 8]:
                     num_wm = int(self._watermark_mode_var.get())
                     # Potrzebujemy przybliżonych wymiarów stempla, aby obliczyć pozycje
                     # Stworzymy tymczasowy stempel tylko do pomiaru
                     try:
                         font_path_wm = self._get_main_font_path()
                         font_wm = ImageFont.truetype(font_path_wm, WATERMARK_FONT_SIZE) if font_path_wm else ImageFont.load_default()
                         temp_img_wm = Image.new("RGBA", (1,1))
                         temp_draw_wm = ImageDraw.Draw(temp_img_wm)
                         bbox_wm = temp_draw_wm.textbbox((0,0), watermark_text, font=font_wm, spacing=4)
                         stamp_w_approx = bbox_wm[2] - bbox_wm[0] + 20 # Szerokość + marginesy
                         stamp_h_approx = bbox_wm[3] - bbox_wm[1] + 20 # Wysokość + marginesy
                         # Utwórz tymczasowy obrócony stempel tylko dla rozmiaru
                         temp_stamp_img = Image.new("RGBA", (max(1,stamp_w_approx), max(1,stamp_h_approx)), (0,0,0,0))
                         resample_m = Image.Resampling.BICUBIC if hasattr(Image, 'Resampling') else Image.BICUBIC
                         rotated_temp_stamp = temp_stamp_img.rotate(WATERMARK_ANGLE, resample=resample_m, expand=True)
                         rotated_w, rotated_h = rotated_temp_stamp.size

                         # Zainicjuj ziarno i generator losowości
                         self._video_gif_random_seed = int(time.time() * 1000) % 100000
                         random_gen = random.Random(self._video_gif_random_seed)
                         # Oblicz i zapisz pozycje
                         self._fixed_watermark_paste_positions = self._calculate_grid_paste_positions_seeded(
                             width, height, num_wm, rotated_w, rotated_h, random_gen
                         )
                         logging.info(f"Obliczono {len(self._fixed_watermark_paste_positions)} stałych pozycji dla siatki wideo/GIF.")
                         del temp_img_wm, temp_draw_wm, temp_stamp_img, rotated_temp_stamp # Zwolnij pamięć

                     except Exception as e_calc:
                          logging.error(f"Błąd podczas obliczania pozycji siatki WM: {e_calc}. Znak wodny może być wycentrowany.")
                          self._fixed_watermark_paste_positions = None # Fallback do centrowania


            # Ukryj widget, jeśli trzeba
            widget_was_visible = False
            if self.master.winfo_exists():
                 widget_was_visible = self.master.state() != 'withdrawn'

            if capture_mode == SCREENSHOT_MODE_WATERMARK and widget_was_visible:
                original_visibility_state = True
                self.master.after(0, self._hide_widget_for_capture)
                time.sleep(0.2) # Czas na ukrycie

            # Pętla nagrywania
            start_time = time.monotonic() # Użyj monotonicznego zegara
            #frame_count = 0 # Przeniesiono inicjalizację wyżej
            last_frame_time = start_time
            min_frame_interval = 1.0 / fps # Minimalny czas między klatkami

            logging.info("Rozpoczęto pętlę nagrywania klatek wideo...")
            while time.monotonic() - start_time < duration:
                 # Sprawdź, czy nie anulowano lub nie zatrzymano z zewnątrz
                 if self._cancel_update or self._key_listener_stop_event.is_set():
                     logging.info("Nagrywanie wideo przerwane przez użytkownika lub zamknięcie.")
                     break

                 current_time = time.monotonic()
                 # Przechwytuj klatkę tylko jeśli minął minimalny interwał
                 if current_time >= last_frame_time + min_frame_interval:
                     # Przechwyć klatkę
                     img = None
                     capture_method = "pyautogui" if PYAUTOGUI_AVAILABLE else "ImageGrab" if IMAGEGRAB_AVAILABLE else "none"
                     try:
                         if capture_method == "pyautogui":
                              img = pyautogui.screenshot()
                         elif capture_method == "ImageGrab":
                              img = ImageGrab.grab()
                         else: # Powinno być obsłużone wcześniej, ale na wszelki wypadek
                              break # Zakończ pętlę, jeśli nie ma jak przechwytywać
                     except Exception as e_capture:
                          logging.warning(f"Błąd przechwytywania klatki wideo ({capture_method}): {e_capture}")
                          # Pomiń tę klatkę, spróbuj następną
                          time.sleep(0.01) # Krótka pauza
                          continue

                     if img is None:
                         logging.warning("Nie udało się przechwycić klatki wideo (zwrócono None).")
                         time.sleep(0.01)
                         continue

                     # Konwertuj obraz PIL do formatu OpenCV (BGR)
                     try:
                          frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                     except Exception as e_conv:
                          logging.error(f"Błąd konwersji klatki PIL->CV2: {e_conv}")
                          continue # Pomiń tę klatkę

                     # Dodaj znak wodny (jeśli włączony)
                     if watermark_text:
                          try:
                              # Przekaż obliczone pozycje, jeśli są dostępne
                              frame = self._add_watermark_cv2(frame, watermark_text, self._fixed_watermark_paste_positions)
                          except Exception as e_wm:
                               logging.error(f"Błąd dodawania znaku wodnego do klatki wideo: {e_wm}")
                               # Kontynuuj bez znaku wodnego dla tej klatki? Lub przerwij? Kontynuujmy.

                     # Zapisz klatkę do pliku wideo
                     try:
                          video_writer.write(frame)
                          frame_count += 1
                     except Exception as e_write:
                          logging.error(f"Błąd zapisu klatki wideo: {e_write}")
                          # Jeśli zapis zawodzi, prawdopodobnie nie ma sensu kontynuować
                          break


                     last_frame_time = current_time # Zaktualizuj czas ostatniej zapisanej klatki
                 else:
                      # Czekaj krótko, aby nie zużywać 100% CPU
                      time.sleep(0.005) # 5ms


            logging.info(f"Zakończono pętlę nagrywania. Przechwycono {frame_count} klatek.")

        except Exception as e:
             # Ogólna obsługa błędów (np. problem z rozmiarem ekranu, inicjalizacją VideoWriter)
             logging.error(f"Krytyczny błąd podczas nagrywania wideo: {e}", exc_info=True)
             error_msg_pl = f"Wystąpił błąd podczas nagrywania wideo:\n{e}"
             error_msg_en = f"An error occurred during video recording:\n{e}"
             # Pokaż błąd w głównym wątku
             self.master.after(0, lambda: messagebox.showerror(
                 'Błąd Nagrywania' if self.lang == 'pl' else 'Recording Error',
                 error_msg_pl if self.lang == 'pl' else error_msg_en,
                 parent=self.master
             ))

        finally:
             # --- Sprzątanie ---
             logging.debug("Rozpoczęcie sprzątania po nagrywaniu wideo.")
             # Zamknij plik wideo (bardzo ważne!)
             if video_writer is not None and video_writer.isOpened():
                 logging.debug("Zwalnianie obiektu VideoWriter.")
                 try:
                      video_writer.release()
                 except Exception as e_release:
                      logging.error(f"Błąd podczas zwalniania VideoWriter: {e_release}")
             video_writer = None # Upewnij się, że jest None

             # Przywróć widoczność widgetu, jeśli był ukryty
             if original_visibility_state:
                 self.master.after(50, self._safely_restore_widget_visibility)

             # Sprawdź, czy plik został utworzony i czy nie jest pusty
             if os.path.exists(file_path):
                  try:
                      file_size = os.path.getsize(file_path)
                      if file_size > 0 and frame_count > 0:
                           logging.info(f"Wideo zapisano pomyślnie: {file_path} (klatki: {frame_count}, rozmiar: {file_size} bajtów)")
                           msg_pl = f"Nagrywanie wideo zakończone.\nZapisano: {file_path}"
                           msg_en = f"Video recording finished.\nSaved: {file_path}"
                           self.master.after(0, lambda: messagebox.showinfo(
                               'Zapisano' if self.lang == 'pl' else 'Saved',
                               msg_pl if self.lang == 'pl' else msg_en,
                               parent=self.master
                           ))
                      else:
                           # Plik jest pusty lub nie zapisano klatek - usuń go
                           logging.warning(f"Plik wideo {file_path} jest pusty (rozmiar: {file_size}, klatki: {frame_count}). Usuwanie.")
                           try:
                                os.remove(file_path)
                           except Exception as e_remove:
                                logging.error(f"Nie można usunąć pustego pliku wideo {file_path}: {e_remove}")
                           # Poinformuj użytkownika o problemie (jeśli nie było innego błędu)
                           if not any(isinstance(arg, Exception) for arg in sys.exc_info() if arg): # Sprawdź czy nie ma aktywnego wyjątku
                                self.master.after(0, lambda: messagebox.showerror(
                                    'Błąd Nagrywania' if self.lang == 'pl' else 'Recording Error',
                                    'Nie udało się zapisać poprawnych danych wideo.' if self.lang == 'pl' else 'Failed to save valid video data.',
                                    parent=self.master
                                ))
                  except Exception as e_check:
                       logging.error(f"Błąd podczas sprawdzania zapisanego pliku wideo {file_path}: {e_check}")

             elif frame_count > 0: # Nie istnieje, ale próbowaliśmy zapisywać
                 logging.error(f"Plik wideo {file_path} nie został utworzony, mimo próby zapisu {frame_count} klatek.")
                 # Poinformuj użytkownika (jeśli nie było innego błędu)
                 if not any(isinstance(arg, Exception) for arg in sys.exc_info() if arg):
                      self.master.after(0, lambda: messagebox.showerror(
                          'Błąd Zapisu' if self.lang == 'pl' else 'Saving Error',
                          'Nie udało się utworzyć pliku wideo.' if self.lang == 'pl' else 'Failed to create video file.',
                          parent=self.master
                      ))


             # Zresetuj flagę aktywnego wątku i stan WM
             self._active_capture_thread = None
             self._fixed_watermark_paste_positions = None
             self._video_gif_random_seed = None
             logging.debug("Zakończono wątek przechwytywania wideo.")


    def _capture_gif(self) -> None:
        """Nagrywa animowany GIF ekranu przez określony czas z opcjonalnym znakiem wodnym."""
        # Sprawdzenia wstępne
        if self._cancel_update:
             logging.info("Przechwytywanie GIF anulowane (widget zamykany).")
             return
        if not PIL_AVAILABLE:
            logging.error("Nagrywanie GIF niemożliwe: brak modułu Pillow.")
            self.master.after(0, lambda: messagebox.showerror(
                 'Brak Modułu' if self.lang == 'pl' else 'Module Missing',
                 'Nagrywanie GIF wymaga zainstalowanego Pillow.' if self.lang == 'pl' else 'GIF recording requires Pillow to be installed.',
                 parent=self.master
             ))
            return
        # Sprawdź, czy jest metoda przechwytywania
        if not PYAUTOGUI_AVAILABLE and not IMAGEGRAB_AVAILABLE:
             logging.error("Nagrywanie GIF niemożliwe: brak pyautogui i ImageGrab.")
             self.master.after(0, lambda: messagebox.showerror(
                 'Brak Modułu' if self.lang == 'pl' else 'Module Missing',
                 'Nagrywanie GIF wymaga pyautogui lub PIL.ImageGrab.' if self.lang == 'pl' else 'GIF recording requires pyautogui or PIL.ImageGrab.',
                 parent=self.master
             ))
             return

        if self._active_capture_thread and self._active_capture_thread.is_alive():
            logging.warning("Przechwytywanie GIF odrzucone: inny wątek przechwytywania jest aktywny.")
            self.master.after(0, lambda: messagebox.showwarning(
                'Przechwytywanie Aktywne' if self.lang == 'pl' else 'Capture Active',
                'Inny proces przechwytywania jest już w toku.' if self.lang == 'pl' else 'Another capture process is already running.',
                parent=self.master
            ))
            return

        self._active_capture_thread = threading.current_thread()
        logging.info(f"Rozpoczęcie nagrywania GIF ({self._gif_duration_seconds}s)...")

        capture_mode = self._screenshot_mode_var.get()
        file_path = self._get_capture_filename("gif", capture_mode)
        duration = self._gif_duration_seconds
        frame_interval = max(0.02, GIF_FRAME_DURATION_MS / 1000.0) # Sekundy, min 20ms (50 FPS max)
        frames: List[Image.Image] = [] # Lista do przechowywania klatek (obrazów PIL)
        original_visibility_state = False
        # Resetuj/Inicjalizuj stan znaku wodnego
        self._fixed_watermark_paste_positions = None
        self._video_gif_random_seed = None


        try:
            # Pobierz rozmiar ekranu (potrzebny do obliczenia pozycji WM)
            screen_size = None
            if PYAUTOGUI_AVAILABLE:
                 try: screen_size = pyautogui.size()
                 except Exception as e: logging.warning(f"Pyautogui.size() error: {e}")
            if screen_size is None and IMAGEGRAB_AVAILABLE:
                 try:
                      temp_im = ImageGrab.grab()
                      if temp_im: screen_size = temp_im.size
                 except Exception as e: logging.warning(f"ImageGrab.grab() for size error: {e}")

            if screen_size is None or not all(s > 0 for s in screen_size):
                 logging.warning("Nie można określić rozmiaru ekranu dla GIF WM. Pozycje siatki mogą być niedokładne.")
                 width, height = -1, -1 # Ustaw nieprawidłowe wymiary
            else:
                 width, height = screen_size
                 logging.debug(f"Rozmiar ekranu dla GIF: {width}x{height}")


            # Przygotuj tekst znaku wodnego i oblicz stałe pozycje (jeśli siatka)
            watermark_text = None
            if capture_mode == SCREENSHOT_MODE_WATERMARK:
                watermark_text = self._create_watermark_text()
                logging.debug("Znak wodny włączony dla GIF.")
                if self._watermark_mode_var.get().isdigit() and int(self._watermark_mode_var.get()) in [3, 5, 8] and width > 0 and height > 0:
                     num_wm = int(self._watermark_mode_var.get())
                     try:
                         # Podobnie jak w wideo, oblicz przybliżone wymiary i pozycje
                         font_path_wm = self._get_main_font_path()
                         font_wm = ImageFont.truetype(font_path_wm, WATERMARK_FONT_SIZE) if font_path_wm else ImageFont.load_default()
                         temp_img_wm = Image.new("RGBA", (1,1))
                         temp_draw_wm = ImageDraw.Draw(temp_img_wm)
                         bbox_wm = temp_draw_wm.textbbox((0,0), watermark_text, font=font_wm, spacing=4)
                         stamp_w_approx = bbox_wm[2] - bbox_wm[0] + 20
                         stamp_h_approx = bbox_wm[3] - bbox_wm[1] + 20
                         temp_stamp_img = Image.new("RGBA", (max(1,stamp_w_approx), max(1,stamp_h_approx)), (0,0,0,0))
                         resample_m = Image.Resampling.BICUBIC if hasattr(Image, 'Resampling') else Image.BICUBIC
                         rotated_temp_stamp = temp_stamp_img.rotate(WATERMARK_ANGLE, resample=resample_m, expand=True)
                         rotated_w, rotated_h = rotated_temp_stamp.size

                         self._video_gif_random_seed = int(time.time() * 1000) % 100000
                         random_gen = random.Random(self._video_gif_random_seed)
                         self._fixed_watermark_paste_positions = self._calculate_grid_paste_positions_seeded(
                             width, height, num_wm, rotated_w, rotated_h, random_gen
                         )
                         logging.info(f"Obliczono {len(self._fixed_watermark_paste_positions)} stałych pozycji dla siatki GIF.")
                         del temp_img_wm, temp_draw_wm, temp_stamp_img, rotated_temp_stamp
                     except Exception as e_calc:
                          logging.error(f"Błąd podczas obliczania pozycji siatki WM dla GIF: {e_calc}. Znak wodny może być wycentrowany.")
                          self._fixed_watermark_paste_positions = None


            # Ukryj widget, jeśli trzeba
            widget_was_visible = False
            if self.master.winfo_exists():
                 widget_was_visible = self.master.state() != 'withdrawn'

            if capture_mode == SCREENSHOT_MODE_WATERMARK and widget_was_visible:
                original_visibility_state = True
                self.master.after(0, self._hide_widget_for_capture)
                time.sleep(0.2) # Czas na ukrycie

            # Pętla przechwytywania klatek
            start_time = time.monotonic()
            last_capture_time = start_time - frame_interval # Aby przechwycić pierwszą klatkę od razu

            logging.info("Rozpoczęto pętlę przechwytywania klatek GIF...")
            while time.monotonic() - start_time < duration:
                 if self._cancel_update or self._key_listener_stop_event.is_set():
                     logging.info("Przechwytywanie GIF przerwane przez użytkownika lub zamknięcie.")
                     break

                 current_time = time.monotonic()
                 if current_time >= last_capture_time + frame_interval:
                     # Przechwyć klatkę (jako obraz PIL)
                     img = None
                     capture_method = "pyautogui" if PYAUTOGUI_AVAILABLE else "ImageGrab" if IMAGEGRAB_AVAILABLE else "none"
                     try:
                         if capture_method == "pyautogui":
                              img = pyautogui.screenshot()
                         elif capture_method == "ImageGrab":
                              img = ImageGrab.grab()
                         else:
                              break # Zakończ pętlę
                     except Exception as e_capture:
                          logging.warning(f"Błąd przechwytywania klatki GIF ({capture_method}): {e_capture}")
                          time.sleep(0.01)
                          continue # Pomiń tę klatkę

                     if img is None:
                         logging.warning("Nie udało się przechwycić klatki GIF (zwrócono None).")
                         time.sleep(0.01)
                         continue

                     # Dodaj znak wodny (jeśli włączony)
                     frame_to_append = img
                     if watermark_text:
                          try:
                              # Użyj _add_watermark_pil, przekazując stałe pozycje
                              frame_to_append = self._add_watermark_pil(img, watermark_text, self._fixed_watermark_paste_positions)
                          except Exception as e_wm:
                               logging.error(f"Błąd dodawania znaku wodnego do klatki GIF: {e_wm}")
                               # Dodaj oryginalną klatkę bez WM

                     # Dodaj przetworzoną klatkę do listy
                     # Konwersja do RGB może zmniejszyć rozmiar pliku GIF, ale traci przezroczystość (jeśli była)
                     # Dla GIF lepiej użyć .quantize() dla optymalizacji palety, ale to bardziej złożone.
                     # Na razie zostawmy w oryginalnym formacie lub konwertujmy do RGB. Spróbujmy RGB.
                     try:
                          # Użycie copy() może zapobiec problemom z modyfikacją tego samego obiektu
                          frames.append(frame_to_append.copy().convert('RGB'))
                     except Exception as e_conv:
                          logging.error(f"Błąd konwersji/kopiowania klatki GIF: {e_conv}. Pomijam klatkę.")


                     last_capture_time = current_time
                 else:
                      time.sleep(0.005) # Czekaj krótko

            logging.info(f"Zakończono pętlę przechwytywania GIF. Zebrano {len(frames)} klatek.")

            # Zapisz GIF, jeśli zebrano jakieś klatki
            if not frames:
                if not self._cancel_update: # Tylko jeśli nie anulowano celowo
                     raise RuntimeError("Nie zebrano żadnych klatek do utworzenia pliku GIF.")
                else:
                     logging.info("Anulowano przed zebraniem klatek GIF.")
                     # Nie pokazuj błędu, jeśli anulowano
            else:
                logging.debug(f"Zapisywanie {len(frames)} klatek do pliku GIF: {file_path}")
                # Pierwsza klatka inicjuje plik, reszta jest dołączana
                # save_all=True - zapisz wszystkie klatki
                # append_images=frames[1:] - lista pozostałych klatek
                # duration=GIF_FRAME_DURATION_MS - czas wyświetlania każdej klatki w ms
                # loop=0 - zapętlaj w nieskończoność
                # optimize=True - może pomóc zmniejszyć rozmiar pliku
                try:
                     frames[0].save(
                         file_path,
                         save_all=True,
                         append_images=frames[1:],
                         duration=GIF_FRAME_DURATION_MS,
                         loop=0,
                         optimize=True # Włącz optymalizację
                     )
                except Exception as e_save:
                     logging.error(f"Błąd podczas zapisu pliku GIF (optymalizacja włączona): {e_save}")
                     # Spróbuj zapisać bez optymalizacji jako fallback
                     try:
                          logging.warning("Próba zapisu GIF bez optymalizacji...")
                          frames[0].save(
                              file_path,
                              save_all=True,
                              append_images=frames[1:],
                              duration=GIF_FRAME_DURATION_MS,
                              loop=0,
                              optimize=False
                          )
                     except Exception as e_save_no_opt:
                          logging.critical(f"Błąd podczas zapisu pliku GIF (nawet bez optymalizacji): {e_save_no_opt}", exc_info=True)
                          raise IOError(f"Nie można zapisać pliku GIF: {e_save_no_opt}") from e_save_no_opt


                # Sprawdź, czy plik został poprawnie zapisany
                if not os.path.exists(file_path):
                     raise IOError(f"Plik GIF nie został utworzony po zapisie: {file_path}")
                if os.path.getsize(file_path) == 0:
                     os.remove(file_path)
                     raise IOError(f"Zapisany plik GIF jest pusty: {file_path}")

                logging.info(f"GIF zapisano pomyślnie: {file_path} (klatki: {len(frames)}, rozmiar: {os.path.getsize(file_path)} bajtów)")
                msg_pl = f"Nagrywanie GIF zakończone.\nZapisano: {file_path}"
                msg_en = f"GIF recording finished.\nSaved: {file_path}"
                self.master.after(0, lambda: messagebox.showinfo(
                    'Zapisano' if self.lang == 'pl' else 'Saved',
                    msg_pl if self.lang == 'pl' else msg_en,
                    parent=self.master
                ))


        except Exception as e:
             # Ogólna obsługa błędów
             logging.error(f"Krytyczny błąd podczas nagrywania GIF: {e}", exc_info=True)
             error_msg_pl = f"Wystąpił błąd podczas nagrywania GIF:\n{e}"
             error_msg_en = f"An error occurred during GIF recording:\n{e}"
             # Pokaż błąd w głównym wątku (tylko jeśli nie anulowano)
             if not self._cancel_update:
                  self.master.after(0, lambda: messagebox.showerror(
                      'Błąd GIF' if self.lang == 'pl' else 'GIF Error',
                      error_msg_pl if self.lang == 'pl' else error_msg_en,
                      parent=self.master
                  ))

        finally:
            # --- Sprzątanie ---
            logging.debug("Rozpoczęcie sprzątania po nagrywaniu GIF.")
            # Przywróć widoczność widgetu
            if original_visibility_state:
                self.master.after(50, self._safely_restore_widget_visibility)

            # Wyczyść listę klatek, aby zwolnić pamięć
            frames.clear()

             # Sprawdź czy plik istnieje i nie jest pusty (jeśli nie było wyjątku wcześniej)
            if 'e' not in locals() and os.path.exists(file_path): # Jeśli nie było wyjątku w try
                 try:
                      if os.path.getsize(file_path) == 0:
                           logging.warning(f"Plik GIF {file_path} jest pusty po zakończeniu. Usuwanie.")
                           os.remove(file_path)
                 except Exception as e_final_check:
                      logging.error(f"Błąd podczas finalnego sprawdzania pliku GIF {file_path}: {e_final_check}")


            # Zresetuj flagę aktywnego wątku i stan WM
            self._active_capture_thread = None
            self._fixed_watermark_paste_positions = None
            self._video_gif_random_seed = None
            logging.debug("Zakończono wątek przechwytywania GIF.")

    # --- Obsługa Globalnych Skrótów Klawiszowych (pynput) ---

    def _on_global_key_press(self, key: Any) -> None:
        """Obsługuje naciśnięcia globalnych skrótów klawiszowych."""
        if self._cancel_update or not HAVE_PYNPUT: # Sprawdź też czy pynput jest dostępne
            return

        # Mapowanie klawiszy na akcje (funkcja, nazwa dla wątku)
        actions = {
            keyboard.Key.print_screen: (self._capture_screenshot, "Screenshot"),
            keyboard.Key.f9: (self._capture_video, "Video"),
            keyboard.Key.f10: (self._capture_gif, "GIF")
        }

        # Normalizuj klucz (niektóre systemy mogą zwracać różne obiekty dla tego samego klawisza)
        # Proste porównanie z predefiniowanymi obiektami pynput powinno działać
        matched_action = None
        for k, action in actions.items():
             # Porównanie __eq__ powinno działać dla obiektów Key z pynput
             # Sprawdzenie hasattr jest dla bezpieczeństwa, gdyby key nie był obiektem Key
             if hasattr(key, 'name') and hasattr(k, 'name') and key.name == k.name:
                  matched_action = action
                  break
             elif key == k: # Porównanie bezpośrednie dla pewności
                 matched_action = action
                 break

        if matched_action:
             func, name = matched_action
             logging.info(f"Wykryto globalny skrót klawiszowy: {key}. Akcja: {name}")

             # Sprawdź, czy inny wątek przechwytywania już działa
             # Dodatkowe sprawdzenie tutaj, chociaż funkcje _capture_* też to robią
             if self._active_capture_thread and self._active_capture_thread.is_alive():
                 logging.warning(f"Próba uruchomienia {name} przez skrót, ale inny wątek przechwytywania jest aktywny.")
                 # Można dodać powiadomienie dźwiękowe lub wizualne? Na razie tylko log.
                 # Pokaż komunikat w Tkinter
                 self.master.after(0, lambda: messagebox.showwarning(
                     'Nagrywanie Aktywne' if self.lang == 'pl' else 'Recording Active',
                     'Inne nagrywanie jest już w toku.' if self.lang == 'pl' else 'Another recording is already in progress.',
                     parent=self.master
                 ))
                 return

             # Uruchom akcję w osobnym wątku, aby nie blokować listenera ani UI
             capture_thread = threading.Thread(target=func, name=f"CaptureWorker-{name}", daemon=True)
             capture_thread.start()


    def _key_listener_run(self) -> None:
        """Główna pętla działania dla wątku nasłuchującego klawisze."""
        if not HAVE_PYNPUT: return

        logging.info("Wątek nasłuchujący klawisze (pynput) uruchomiony.")
        # Utwórz listener wewnątrz wątku
        # suppress=False - nie blokuje zdarzeń dla innych aplikacji
        try:
             # Używamy bloku with, aby zapewnić poprawne zarządzanie zasobami listenera
             with keyboard.Listener(on_press=self._on_global_key_press, suppress=False) as self._listener_instance:
                  # Czekaj na sygnał zatrzymania
                  self._key_listener_stop_event.wait() # Blokuje wątek do czasu ustawienia zdarzenia
                  logging.info("Otrzymano sygnał stop dla listenera klawiszy.")
        except Exception as e:
             # Obsługa błędów inicjalizacji lub działania listenera
             logging.error(f"Krytyczny błąd w wątku listenera klawiszy pynput: {e}", exc_info=True)
             # Spróbuj poinformować użytkownika
             try:
                 # Użyj after, aby komunikat pojawił się w głównym wątku
                 self.master.after(0, lambda: messagebox.showerror(
                      'Błąd Pynput' if self.lang == 'pl' else 'Pynput Error',
                      f"Wystąpił błąd wewnętrzny w module nasłuchującym klawisze:\n{e}\nSkróty klawiszowe mogą nie działać."
                      if self.lang == 'pl' else f"An internal error occurred in the key listener module:\n{e}\nHotkeys might not work.",
                      parent=self.master
                  ))
             except Exception:
                 pass # Jeśli nawet to zawiedzie, trudno.
        finally:
            # Listener powinien zostać automatycznie zatrzymany przez `with`,
            # ale na wszelki wypadek, jeśli wyszliśmy inaczej.
            if hasattr(self, '_listener_instance') and self._listener_instance and hasattr(self._listener_instance, 'stop'):
                 try:
                      self._listener_instance.stop()
                      logging.debug("Jawnie zatrzymano listener pynput w bloku finally.")
                 except Exception as e_stop:
                      logging.error(f"Błąd podczas jawnego zatrzymywania listenera: {e_stop}")
            self._listener_instance = None # Wyczyść referencję
            logging.info("Wątek nasłuchujący klawisze zakończony.")


    def _setup_key_listener(self) -> None:
        """Konfiguruje i uruchamia wątek nasłuchujący globalne skróty klawiszowe."""
        if not HAVE_PYNPUT:
            logging.warning("Nie uruchomiono nasłuchiwania klawiszy (brak pynput).")
            return

        # Sprawdź, czy wątek już nie działa
        if self._key_listener_thread and self._key_listener_thread.is_alive():
            logging.warning("Próba ponownego uruchomienia wątku nasłuchującego klawisze.")
            return

        try:
            # Resetuj zdarzenie stop przed uruchomieniem
            self._key_listener_stop_event.clear()
            # Utwórz i uruchom wątek
            self._key_listener_thread = threading.Thread(target=self._key_listener_run, name="KeyListenerThread", daemon=True)
            self._key_listener_thread.start()
            logging.info("Wątek nasłuchujący klawisze został uruchomiony.")
        except Exception as e:
            logging.error(f"Nie udało się uruchomić wątku nasłuchującego klawisze: {e}", exc_info=True)
            # Poinformuj użytkownika
            self.master.after(0, lambda: messagebox.showerror(
                 'Błąd Pynput' if self.lang == 'pl' else 'Pynput Error',
                 f"Nie można uruchomić nasłuchiwania skrótów klawiszowych:\n{e}" if self.lang == 'pl' else f"Could not start the hotkey listener:\n{e}",
                 parent=self.master
             ))


# --- Główna część skryptu ---
if __name__ == "__main__":
    # Domyślne wartości
    lang = 'en'
    prompt = "TimechainProof"

    # Sprawdź, czy skrypt jest uruchomiony interaktywnie
    is_interactive = False
    try:
         # sys.stdin.isatty() sprawdza, czy standardowe wejście jest terminalem
         is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
         # Może się nie udać w niektórych środowiskach (np. IDLE bez konsoli)
         is_interactive = False
         logging.debug("Nie można jednoznacznie określić trybu interaktywnego.")


    if is_interactive:
        print(f"--- Timechain Desktop Widget v{VERSION} Setup ---")
        try:
            # Wybór języka
            lang_input = input("Wybierz język / Select language (en/pl) [en]: ").strip().lower()
            if lang_input == 'pl':
                lang = 'pl'
                print("Wybrano język polski.")
            else:
                lang = 'en'
                print("Language set to English.")

            # Wprowadzenie monitu
            prompt_label = "Wprowadź monit" if lang == 'pl' else "Enter prompt"
            prompt_input = input(f"{prompt_label} [{prompt}]: ").strip()
            if prompt_input: # Jeśli użytkownik coś wpisał
                prompt = prompt_input
            print(f"{'Używany monit' if lang == 'pl' else 'Using prompt'}: {prompt}")

        except EOFError:
             print("\nDetekcja końca pliku (EOF), używam domyślnych ustawień.")
             is_interactive = False # Traktuj jak nieinteraktywny
        except Exception as e_input:
             print(f"\nWystąpił błąd podczas konfiguracji interaktywnej: {e_input}")
             print("Używam domyślnych ustawień.")
             is_interactive = False

    else:
        logging.info(f"Uruchomiono w trybie nieinteraktywnym, używam domyślnych ustawień (lang='{lang}', prompt='{prompt}').")

    # Inicjalizacja Tkinter
    root = tk.Tk()
    root.withdraw() # Ukryj główne okno root, używamy tylko widgetu

    # Utwórz instancję widgetu
    app = None
    try:
         app = TimechainWidget(root, prompt, lang)

         # Uruchom główną pętlę Tkinter
         logging.info("Uruchamianie głównej pętli Tkinter.")
         root.mainloop()
         # mainloop() blokuje działanie do momentu zamknięcia ostatniego okna Tkinter
         logging.info("Główna pętla Tkinter zakończona.")

    except KeyboardInterrupt:
        print("\nPrzechwycono KeyboardInterrupt (Ctrl+C). Zamykanie...")
        logging.info("Przechwycono KeyboardInterrupt (Ctrl+C).")
        # Proces zamykania jest inicjowany w bloku finally

    except tk.TclError as e_tcl:
         logging.critical(f"Krytyczny błąd Tcl/Tk: {e_tcl}", exc_info=True)
         # Spróbuj pokazać błąd, jeśli to możliwe
         try:
             parent_for_error = None
             if 'root' in locals() and isinstance(root, tk.Tk) and root.winfo_exists():
                 parent_for_error = root
             messagebox.showerror('Krytyczny Błąd Tk' if lang == 'pl' else 'Critical Tk Error', f"Błąd Tcl/Tk: {e_tcl}\nAplikacja zostanie zamknięta.", parent=parent_for_error)
         except Exception: pass # Jeśli nawet messagebox zawiedzie
         # Proces zamykania w finally

    except Exception as e_main:
        # Inne nieoczekiwane błędy podczas inicjalizacji lub działania
        logging.critical(f"Nieoczekiwany błąd krytyczny w głównym bloku: {e_main}", exc_info=True)
        try:
            parent_for_error = None
            if 'root' in locals() and isinstance(root, tk.Tk) and root.winfo_exists():
                parent_for_error = root
            messagebox.showerror('Błąd Krytyczny' if lang == 'pl' else 'Critical Error', f"Wystąpił nieoczekiwany błąd:\n{e_main}\nAplikacja zostanie zamknięta. Sprawdź logi.", parent=parent_for_error)
        except Exception: pass
        # Proces zamykania w finally

    finally:
        # --- Końcowe sprzątanie ---
        logging.info("Rozpoczęcie finalnego sprzątania aplikacji.")
        # Upewnij się, że proces zamykania widgetu został zainicjowany
        if app and not app._cancel_update:
            logging.debug("Inicjowanie zamykania widgetu w bloku finally.")
            app._close_widget() # To zaplanuje zniszczenie okna i zatrzymanie wątków

        # Poczekaj chwilę na zakończenie wątków (zwłaszcza listenera)
        if HAVE_PYNPUT and app and app._key_listener_thread and app._key_listener_thread.is_alive():
             logging.debug("Oczekiwanie na zakończenie wątku listenera klawiszy...")
             app._key_listener_stop_event.set() # Upewnij się, że sygnał został wysłany
             app._key_listener_thread.join(timeout=1.0) # Poczekaj maksymalnie 1 sekundę
             if app._key_listener_thread.is_alive():
                  logging.warning("Wątek listenera klawiszy nie zakończył się w oczekiwanym czasie.")

        # Poczekaj na zakończenie wątku przechwytywania (jeśli nadal działa)
        if app and app._active_capture_thread and app._active_capture_thread.is_alive():
             logging.debug("Oczekiwanie na zakończenie aktywnego wątku przechwytywania...")
             # Wątki przechwytywania powinny reagować na _cancel_update lub _key_listener_stop_event
             app._active_capture_thread.join(timeout=2.0) # Daj mu więcej czasu
             if app._active_capture_thread.is_alive():
                  logging.warning("Aktywny wątek przechwytywania nie zakończył się w oczekiwanym czasie.")


        # Upewnij się, że okno root jest zniszczone (jeśli _safe_destroy nie zadziałało)
        try:
             # Sprawdź, czy root został zdefiniowany i jest obiektem Tk
             if 'root' in locals() and isinstance(root, tk.Tk) and root.winfo_exists():
                  logging.debug("Niszczenie okna root w bloku finally (na wszelki wypadek).")
                  root.destroy()
        except Exception as e_destroy_final:
             logging.error(f"Błąd podczas ostatecznego niszczenia okna root: {e_destroy_final}")


        logging.info("Aplikacja zakończona.")
        # Zakończ proces z kodem 0 (sukces)
        sys.exit(0)
