# -*- coding: utf-8 -*-
"""
Timechain Desktop Widget v6.6 (Ulepszone rozmieszczenie znaków wodnych)

Wyświetla dostosowywalny monit z danymi w czasie rzeczywistym i pozwala
na robienie zrzutów ekranu/nagrań z opcjonalnym, konfigurowalnym znakiem wodnym Timechain.

Nowości w v6.6:
- Ulepszono rozmieszczenie wielu znaków wodnych (style 3, 5, 8) - użycie siatki z marginesami.
- Zmniejszono domyślną przezroczystość (75%) i rozmiar (30) czcionki znaku wodnego.
- Poprawiono format nazwy zapisywanych plików na: TimechainProof(RRRRMMDD-GGMMSS)-prompt@pełny_hash.ext
- Poprawiono błąd uniemożliwiający start nagrywania wideo/GIF (komunikat "Capture Active").

Funkcje:
- (Reszta funkcji bez zmian...)
- Metadane dowodowe w plikach PNG.

Ograniczenia:
- Metadane nie są obecnie osadzane w plikach MP4 i GIF.

Wymagania:
- Python 3.x
- requests, pyautogui, Pillow, opencv-python, numpy, pynput
- **Dla zapisu wideo:** Odpowiednie kodeki w systemie (np. OpenH264, XVID).
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
from PIL import Image, ImageDraw, ImageFont, ImageOps
from PIL.PngImagePlugin import PngInfo
import cv2
import numpy as np
import pyautogui
from pynput import keyboard

# --- Obsługa wysokiej rozdzielczości DPI (Windows) ---
try:
    if platform.system() == "Windows":
        from ctypes import windll
        windll.user32.SetProcessDPIAware()
        logging.info("Próba ustawienia świadomości DPI (Windows).")
except ImportError:
    logging.warning("Moduł 'ctypes' niedostępny, nie można ustawić świadomości DPI.")
except Exception as e:
    logging.warning(f"Nie można ustawić świadomości DPI: {e}")

# --- Konfiguracja ---
CACHE_DIR_NAME = "timechain_widget_cache"
CACHE_TIME_SECONDS = 60
API_TIMEOUT_SECONDS = 10
FONT_FAMILY = "Segoe UI"
BASE_FONT_SIZE = 15
FONT_WEIGHT = "bold"
TEXT_COLOR = "white"
SHADOW_COLOR = "#333333"
SHADOW_OFFSET_X = 1
SHADOW_OFFSET_Y = 1
TRANSPARENT_COLOR = '#f0f0f0'
INITIAL_WINDOW_POSITION = "+100+100"
BLOCK_HEIGHT_URL = "https://blockstream.info/api/blocks/tip/height"
BLOCK_HASH_URL = "https://blockchain.info/q/latesthash"
ENABLE_DRAG_SCALING = True
MAX_SCALE_INCREASE = 0.3
SCALE_DISTANCE_FACTOR = 400
MIN_SCALED_FONT_SIZE = 10
SCREENSHOT_MODE_WIDGET = 'widget'
SCREENSHOT_MODE_WATERMARK = 'watermark'
DEFAULT_SCREENSHOT_MODE = SCREENSHOT_MODE_WIDGET
DEFAULT_WATERMARK_STYLE = "1"
WATERMARK_ANGLE = 33
WATERMARK_OPACITY = 75 # ZMIENIONO z 90
WATERMARK_FONT_SIZE = 30 # ZMIENIONO z 34
DEFAULT_VIDEO_DURATION_SECONDS = 10
DEFAULT_GIF_DURATION_SECONDS = 7
GIF_FRAME_DURATION_MS = 100
CAPTURE_SUBDIR = "Timechain_Captures"
VIDEO_FOURCC = "mp4v"
# VIDEO_FOURCC = "XVID"
# --- Koniec Konfiguracji ---

# --- Konfiguracja Logowania ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

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
        self._current_time_str = "..."
        self._beat_time_str = "@???"
        self._block_height_str = "..."
        self._block_hash_short_str = "..."
        self._full_block_hash_str = None
        self._last_error = None
        self.label_shadow: Label | None = None
        self.label_main: Label | None = None
        self._base_font_options = (FONT_FAMILY, BASE_FONT_SIZE, FONT_WEIGHT)
        self._current_font_options = self._base_font_options
        self._display_full_hash_permanently_var = BooleanVar(value=False)
        self.last_click_x = 0
        self.last_click_y = 0
        self._drag_start_x_root = 0
        self._drag_start_y_root = 0
        self._is_dragging = False
        self._screenshot_mode_var = StringVar(value=DEFAULT_SCREENSHOT_MODE)
        self._watermark_mode_var = StringVar(value=DEFAULT_WATERMARK_STYLE)
        self._active_capture_thread: threading.Thread | None = None
        self._video_duration_seconds = DEFAULT_VIDEO_DURATION_SECONDS
        self._gif_duration_seconds = DEFAULT_GIF_DURATION_SECONDS
        self._setup_ui()
        self._bind_events()
        logging.info("Uruchamianie wątku początkowego pobierania danych...")
        threading.Thread(target=self._initial_data_fetch_and_show, name="InitialFetch", daemon=True).start()
        self._setup_key_listener()
        logging.info("Widget zainicjalizowany.")

    def _setup_cache_dir(self) -> str | None:
        try:
            app_data_dir = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA') or tempfile.gettempdir()
            cache_path = os.path.join(app_data_dir, "TimechainWidget", CACHE_DIR_NAME)
            os.makedirs(cache_path, exist_ok=True)
            logging.info(f"Katalog cache ustawiony na: {cache_path}")
            return cache_path
        except Exception as e:
            logging.error(f"Nie udało się utworzyć katalogu cache: {e}")
            return None

    def _setup_ui(self):
        logging.debug("Konfiguracja UI...")
        self.master.attributes('-topmost', True)
        self.master.overrideredirect(True)
        self.master.config(bg=TRANSPARENT_COLOR)
        try:
            self.master.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        except tk.TclError:
            logging.warning(f"System może nie wspierać przezroczystości dla koloru {TRANSPARENT_COLOR}.")

        init_text = "Ładowanie..." if self.lang == 'pl' else "Loading..."
        self.label_shadow = Label(self.master, text=init_text, font=self._base_font_options, fg=SHADOW_COLOR, bg=TRANSPARENT_COLOR, justify=tk.LEFT, anchor='nw')
        self.label_shadow.place(x=SHADOW_OFFSET_X, y=SHADOW_OFFSET_Y)

        self.label_main = Label(self.master, text=init_text, font=self._base_font_options, fg=TEXT_COLOR, bg=TRANSPARENT_COLOR, justify=tk.LEFT, anchor='nw')
        self.label_main.place(x=0, y=0)

        self.master.geometry(INITIAL_WINDOW_POSITION)
        logging.debug("Konfiguracja UI zakończona.")

    def _bind_events(self):
        logging.debug("Przypisywanie zdarzeń...")
        for widget in [self.label_main, self.label_shadow, self.master]:
            widget.bind("<Button-1>", self._on_left_click_press)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._on_left_click_release)
            widget.bind("<Button-3>", self._on_right_click)

    def _on_left_click_press(self, event):
        self._is_dragging = True
        self.last_click_x = event.x
        self.last_click_y = event.y
        self._drag_start_x_root = event.x_root
        self._drag_start_y_root = event.y_root
        logging.debug(f"Rozpoczęto przeciąganie z ({event.x_root}, {event.y_root})")

    def _on_drag(self, event):
        if not self._is_dragging:
            return

        new_x = event.x_root - self.last_click_x
        new_y = event.y_root - self.last_click_y
        try:
            self.master.geometry(f"+{new_x}+{new_y}")
        except tk.TclError as e:
            logging.warning(f"Błąd podczas ustawiania geometrii okna w trakcie przeciągania: {e}")
            self._is_dragging = False
            return

        if ENABLE_DRAG_SCALING:
            distance = math.hypot(event.x_root - self._drag_start_x_root, event.y_root - self._drag_start_y_root)
            scale = 1.0 + min(MAX_SCALE_INCREASE, distance / SCALE_DISTANCE_FACTOR)
            new_font_size = max(MIN_SCALED_FONT_SIZE, int(round(BASE_FONT_SIZE * scale)))

            if new_font_size != self._current_font_options[1]:
                self._current_font_options = (FONT_FAMILY, new_font_size, FONT_WEIGHT)
                logging.debug(f"Skalowanie czcionki do rozmiaru: {new_font_size} (dystans: {distance:.1f})")
                try:
                    if self.master.winfo_exists() and self.label_main and self.label_shadow:
                         self.label_main.config(font=self._current_font_options)
                         self.label_shadow.config(font=self._current_font_options)
                         self._update_display(force_resize=True)
                except tk.TclError as e:
                    logging.warning(f"Błąd podczas zmiany czcionki przy skalowaniu: {e}")
                    self._is_dragging = False

    def _on_left_click_release(self, event):
        if not self._is_dragging:
            return
        self._is_dragging = False
        logging.debug("Zakończono przeciąganie.")

        if ENABLE_DRAG_SCALING and self._current_font_options != self._base_font_options:
            logging.debug("Przywracanie bazowego rozmiaru czcionki.")
            self._current_font_options = self._base_font_options
            try:
                if self.master.winfo_exists() and self.label_main and self.label_shadow:
                    self.label_main.config(font=self._base_font_options)
                    self.label_shadow.config(font=self._base_font_options)
                    self._update_display(force_resize=True)
            except tk.TclError as e:
                logging.warning(f"Błąd podczas przywracania czcionki po przeciąganiu: {e}")

    def _set_watermark_style(self, style_value):
        self._watermark_mode_var.set(style_value)
        self._screenshot_mode_var.set(SCREENSHOT_MODE_WATERMARK)
        logging.info(f"Ustawiono styl znaku wodnego: '{style_value}', Tryb przechwytywania: '{SCREENSHOT_MODE_WATERMARK}'")

    def _set_capture_mode_widget(self):
        self._screenshot_mode_var.set(SCREENSHOT_MODE_WIDGET)
        logging.info(f"Ustawiono tryb przechwytywania: '{SCREENSHOT_MODE_WIDGET}'")

    def _toggle_permanent_full_hash(self):
        is_full = self._display_full_hash_permanently_var.get()
        logging.info(f"Przełączono opcję wyświetlania hasha na: {'Pełny (stały)' if is_full else 'Skrócony'}")

        if is_full and (not self._full_block_hash_str or "Error" in self._full_block_hash_str):
             self._display_full_hash_permanently_var.set(False)
             error_message = (f"{'Brak danych lub błąd pobierania pełnego hasha.' if self.lang == 'pl' else 'Full hash data missing or there was an error fetching it.'}\n"
                              f"({self._full_block_hash_str or 'N/A'})")
             error_title = 'Błąd Danych Hasha' if self.lang == 'pl' else 'Hash Data Error'
             messagebox.showwarning(error_title, error_message, parent=self.master)
             logging.warning("Anulowano włączenie stałego wyświetlania pełnego hasha z powodu braku danych lub błędu.")
        elif self.master.winfo_exists():
             self._update_display(force_resize=True)

    def _configure_duration(self, capture_type: str):
        current_value, title, prompt_text, min_duration, max_duration = 0, "", "", 1, 300
        if capture_type == 'video':
            current_value = self._video_duration_seconds
            title = 'Czas Nagrywania Wideo' if self.lang == 'pl' else 'Video Recording Duration'
            prompt_text = f"{'Podaj czas nagrania wideo w sekundach' if self.lang == 'pl' else 'Enter video recording duration in seconds'} ({min_duration}-{max_duration}):"
        elif capture_type == 'gif':
            current_value = self._gif_duration_seconds
            title = 'Czas Nagrywania GIF' if self.lang == 'pl' else 'GIF Recording Duration'
            prompt_text = f"{'Podaj czas nagrania GIF w sekundach' if self.lang == 'pl' else 'Enter GIF recording duration in seconds'} ({min_duration}-{max_duration}):"
        else:
            logging.warning(f"Nieznany typ przechwytywania do konfiguracji czasu: {capture_type}")
            return

        new_duration = simpledialog.askinteger(title, prompt_text, parent=self.master,
                                               initialvalue=current_value,
                                               minvalue=min_duration, maxvalue=max_duration)
        if new_duration is not None:
            if capture_type == 'video':
                self._video_duration_seconds = new_duration
                logging.info(f"Ustawiono nowy czas nagrywania wideo: {new_duration}s")
            elif capture_type == 'gif':
                self._gif_duration_seconds = new_duration
                logging.info(f"Ustawiono nowy czas nagrywania GIF: {new_duration}s")

    def _on_right_click(self, event):
        popup = Menu(self.master, tearoff=0)
        popup.add_command(label=('Edytuj Monit' if self.lang == 'pl' else 'Edit Prompt'),
                          command=self._edit_widget)
        popup.add_checkbutton(label=('Pokaż Pełny Hash (stałe)' if self.lang == 'pl' else 'Show Full Hash (perm.)'),
                              variable=self._display_full_hash_permanently_var,
                              command=self._toggle_permanent_full_hash)
        popup.add_separator()
        popup.add_radiobutton(label=('Przechwyt: Widżet Widoczny' if self.lang == 'pl' else 'Capture: Widget Visible'),
                              variable=self._screenshot_mode_var,
                              value=SCREENSHOT_MODE_WIDGET,
                              command=self._set_capture_mode_widget)

        watermark_menu = Menu(popup, tearoff=0)
        popup.add_cascade(label=('Przechwyt: Znak Wodny (Ukryj Widget)' if self.lang == 'pl' else 'Capture: Watermark (Hide Widget)'),
                          menu=watermark_menu)
        watermark_styles = {
            "1": ('Styl 1: Wycentrowany' if self.lang == 'pl' else 'Style 1: Centered'),
            "3": ('Styl 2: 3 (Siatka)' if self.lang == 'pl' else 'Style 2: 3 (Grid)'),
            "5": ('Styl 3: 5 (Siatka)' if self.lang == 'pl' else 'Style 3: 5 (Grid)'),
            "8": ('Styl 4: 8 (Siatka)' if self.lang == 'pl' else 'Style 4: 8 (Grid)')
        }
        for value, label_text in watermark_styles.items():
             watermark_menu.add_radiobutton(label=label_text,
                                            variable=self._watermark_mode_var,
                                            value=value,
                                            command=lambda v=value: self._set_watermark_style(v))

        popup.add_separator()
        popup.add_command(label=f"{'Czas Wideo' if self.lang == 'pl' else 'Video Duration'}: {self._video_duration_seconds}s ({'Zmień' if self.lang == 'pl' else 'Change'}...)",
                          command=lambda: self._configure_duration('video'))
        popup.add_command(label=f"{'Czas GIF' if self.lang == 'pl' else 'GIF Duration'}: {self._gif_duration_seconds}s ({'Zmień' if self.lang == 'pl' else 'Change'}...)",
                          command=lambda: self._configure_duration('gif'))

        popup.add_separator()
        popup.add_command(label=('Zamknij Widget' if self.lang == 'pl' else 'Close Widget'),
                          command=self._close_widget)

        try:
            popup.tk_popup(event.x_root, event.y_root)
        finally:
            popup.grab_release()

    def _edit_widget(self):
        title = 'Edytuj Monit' if self.lang == 'pl' else 'Edit Prompt'
        label = 'Wprowadź nowy monit:' if self.lang == 'pl' else 'Enter new prompt:'
        new_prompt = simpledialog.askstring(title, label, parent=self.master, initialvalue=self.prompt)
        if new_prompt is not None and new_prompt.strip() and new_prompt.strip() != self.prompt:
            self.prompt = new_prompt.strip()
            logging.info(f"Zmieniono monit na: '{self.prompt}'")
            if self.master.winfo_exists():
                self._update_display(force_resize=True)

    def _close_widget(self):
        logging.info("Otrzymano żądanie zamknięcia widgetu...")
        self._cancel_update = True

        if self._key_listener_thread and self._key_listener_thread.is_alive():
            logging.info("Zatrzymywanie nasłuchiwania klawiatury...")
            self._key_listener_stop_event.set()

        if self.master.winfo_exists():
            self.master.after(50, self.master.destroy)
            logging.info("Zaplanowano zniszczenie głównego okna.")

    def _initial_data_fetch_and_show(self):
        logging.info("Rozpoczynanie początkowego pobierania danych...")
        self._fetch_and_update_data()
        logging.info("Początkowe pobieranie danych zakończone.")
        if self.master.winfo_exists():
            self.master.after(0, self._show_and_start_updates)

    def _show_and_start_updates(self):
        logging.info("Pokazywanie widgetu i rozpoczynanie cyklu aktualizacji...")
        try:
            if not self.master.winfo_exists():
                logging.warning("Okno widgetu już nie istnieje przed pokazaniem.")
                return

            self.master.update_idletasks()
            self._update_display(force_resize=True)
            self.master.deiconify()
            self.master.lift()
            self.master.update_idletasks()
            self._update_display(force_resize=True)

            logging.info("Widget jest teraz widoczny.")
            self._schedule_next_update()

        except Exception as e:
            logging.exception("Krytyczny błąd podczas pokazywania widgetu i startu aktualizacji:")
            error_title = 'Błąd Startowy Widgetu' if self.lang == 'pl' else 'Widget Startup Error'
            message = f"{'Wystąpił błąd podczas uruchamiania:' if self.lang == 'pl' else 'An error occurred during startup:'}\n{e}"
            try:
                messagebox.showerror(error_title, message, parent=self.master if self.master.winfo_exists() else None)
            except Exception as mb_error:
                logging.error(f"Nie udało się pokazać okna błędu startowego: {mb_error}")

            if self.master.winfo_exists():
                self.master.destroy()

    def _fetch_and_update_data(self):
        self._last_error = None
        start_time = time.time()
        try:
            logging.debug("Rozpoczynanie pobierania danych z API...")
            self._current_time_str = time.strftime('%H:%M:%S')
            results = {'beat': None, 'height': None, 'hash_short': None, 'hash_full': None}

            def fetch_api_data(url, key, process_func):
                api_result = self._get_api_data(url)
                results[key] = process_func(api_result)

            def process_beat_time(_):
                return self._get_swatch_internet_time()

            def process_height(data):
                return data if data and "Error" not in data else "Err"

            def process_hash(data):
                if isinstance(data, str) and len(data) == 64 and all(c in '0123456789abcdefABCDEF' for c in data):
                    results['hash_full'] = data
                    return f"{data[:6]}...{data[-4:]}"
                else:
                    results['hash_full'] = data if isinstance(data, str) else "Error: Invalid Type"
                    return data if isinstance(data, str) else "Error"

            threads = [
                threading.Thread(target=lambda: results.__setitem__('beat', process_beat_time(None)), daemon=True, name="FetchBeatTime"),
                threading.Thread(target=fetch_api_data, args=(BLOCK_HEIGHT_URL, 'height', process_height), daemon=True, name="FetchBlockHeight"),
                threading.Thread(target=fetch_api_data, args=(BLOCK_HASH_URL, 'hash_short', process_hash), daemon=True, name="FetchBlockHash")
            ]

            for t in threads: t.start()
            for t in threads: t.join(timeout=API_TIMEOUT_SECONDS + 1)

            self._beat_time_str = results.get('beat', "@Error")
            self._block_height_str = results.get('height', "Error")
            self._block_hash_short_str = results.get('hash_short', "Error")

            new_full_hash = results.get('hash_full')
            needs_refresh = False
            if self._full_block_hash_str != new_full_hash:
                self._full_block_hash_str = new_full_hash
                if self._display_full_hash_permanently_var.get():
                    needs_refresh = True

            if needs_refresh and self.master.winfo_exists():
                self.master.after(0, lambda: self._update_display(force_resize=True))

            duration = time.time() - start_time
            logging.debug(f"Pobrano dane: Czas={self._current_time_str}, Beat={self._beat_time_str}, Wysokość={self._block_height_str}, Hash={self._block_hash_short_str} (w {duration:.3f}s)")

        except Exception as e:
            self._last_error = f"Błąd aktualizacji danych: {e}"
            logging.exception("Wystąpił błąd podczas pobierania i przetwarzania danych API:")

    def _format_display_text(self) -> str:
        if self._last_error:
            return f"{self.prompt} - Błąd!\n({self._last_error})"

        height_str = self._block_height_str
        beat_str = self._beat_time_str
        time_str = self._current_time_str
        display_hash = ""
        hash_label = ""

        if self._display_full_hash_permanently_var.get():
            hash_label = 'Pełny Hash' if self.lang == 'pl' else 'Full Hash'
            full_hash = self._full_block_hash_str
            display_hash = full_hash if full_hash and "Error" not in full_hash else ('Błąd Pobierania' if self.lang == 'pl' else 'Fetch Error')
        else:
            hash_label = 'Hash'
            display_hash = self._block_hash_short_str

        line1 = f"{self.prompt}@"
        line2 = f"{'Czas' if self.lang == 'pl' else 'Time'}: {time_str} | BeatTime: {beat_str} | {'Blok' if self.lang == 'pl' else 'Block'}: {height_str}"
        line3 = f"{hash_label}: {display_hash}"

        return f"{line1}\n{line2}\n{line3}"

    def _update_display(self, force_resize=False):
        if self._cancel_update or not self.master.winfo_exists() or not self.label_main or not self.label_shadow:
            return

        display_text = self._format_display_text()

        try:
            current_font = self._current_font_options
            self.label_main.config(text=display_text, font=current_font)
            self.label_shadow.config(text=display_text, font=current_font)

            if force_resize:
                self.master.update_idletasks()
                main_width = self.label_main.winfo_reqwidth()
                main_height = self.label_main.winfo_reqheight()
                req_width = main_width + abs(SHADOW_OFFSET_X)
                req_height = main_height + abs(SHADOW_OFFSET_Y)

                if req_width > 0 and req_height > 0:
                    current_x = self.master.winfo_x()
                    current_y = self.master.winfo_y()
                    self.master.geometry(f"{req_width}x{req_height}+{current_x}+{current_y}")
                    logging.debug(f"Dostosowano rozmiar okna do: {req_width}x{req_height}")
                else:
                    logging.warning(f"Otrzymano nieprawidłowy wymagany rozmiar okna: {req_width}x{req_height}. Pomijanie zmiany rozmiaru.")

        except tk.TclError as e:
            logging.warning(f"Wystąpił błąd TclError podczas aktualizacji wyświetlania: {e}. Prawdopodobnie okno jest zamykane.")
            self._close_widget()
        except Exception as e:
            logging.exception("Nieoczekiwany błąd podczas aktualizacji wyświetlania:")

    def _schedule_next_update(self):
        if self._cancel_update or not self.master.winfo_exists():
            return
        self.master.after(1000, self._perform_update_cycle)

    def _perform_update_cycle(self):
        if self._cancel_update or not self.master.winfo_exists():
            return

        logging.debug("Rozpoczynanie cyklu aktualizacji...")
        threading.Thread(target=self._fetch_and_update_data, name="DataFetchWidget", daemon=True).start()

        self._current_time_str = time.strftime('%H:%M:%S')

        if self.master.winfo_exists():
            self._update_display(force_resize=False)
            self._schedule_next_update()

    def _get_api_data(self, url: str) -> str:
        cache_key = url.replace("https://", "").replace("/", "_").replace(":", "_") + ".cache"
        cache_file_path = os.path.join(self._cache_dir, cache_key) if self._cache_dir else None
        cached_data = None

        if cache_file_path and os.path.exists(cache_file_path):
            try:
                file_mod_time = os.path.getmtime(cache_file_path)
                cache_age = time.time() - file_mod_time
                if cache_age < CACHE_TIME_SECONDS:
                    with open(cache_file_path, 'r', encoding='utf-8') as f:
                        cached_data = f.read().strip()
                    if cached_data:
                        logging.debug(f"Użyto danych z cache (wiek: {cache_age:.1f}s) dla: {url[:40]}...")
                        return cached_data
                    else:
                        logging.warning(f"Plik cache {cache_file_path} jest pusty.")
                        cached_data = None
                else:
                    with open(cache_file_path, 'r', encoding='utf-8') as f:
                         cached_data = f.read().strip()
                    logging.debug(f"Cache jest przestarzały (wiek: {cache_age:.1f}s) dla: {url[:40]}...")
            except Exception as e:
                logging.warning(f"Nie udało się odczytać danych z cache {cache_file_path}: {e}")
                cached_data = None

        logging.debug(f"Pobieranie danych z sieci: {url[:40]}...")
        live_data = None
        error_reason = "Unknown Error"
        temp_file_path = None

        try:
            response = requests.get(url, timeout=API_TIMEOUT_SECONDS)
            response.raise_for_status()
            live_data = response.text.strip()
            if not live_data:
                raise ValueError("Otrzymano pustą odpowiedź z API")

            if cache_file_path:
                temp_file_path = cache_file_path + ".tmp"
                try:
                    with open(temp_file_path, 'w', encoding='utf-8') as f:
                        f.write(live_data)
                    os.replace(temp_file_path, cache_file_path)
                    logging.debug(f"Zapisano nowe dane do cache: {os.path.basename(cache_file_path)}")
                    temp_file_path = None
                except Exception as e:
                    logging.warning(f"Nie udało się zapisać danych do cache {cache_file_path}: {e}")

            return live_data

        except requests.exceptions.Timeout:
            error_reason = "Timeout"
            logging.error(f"Przekroczono czas oczekiwania na odpowiedź z: {url[:40]}...")
        except requests.exceptions.RequestException as e:
            error_reason = f"Błąd Sieci ({e.__class__.__name__})"
            logging.error(f"{error_reason} podczas połączenia z {url[:40]}...: {e}")
        except ValueError as e:
            error_reason = "Puste Dane"
            logging.error(f"{error_reason} otrzymane z {url[:40]}...: {e}")
        except Exception as e:
            error_reason = "Nieznany Błąd API"
            logging.exception(f"{error_reason} podczas pobierania danych z {url[:40]}...:")
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logging.debug(f"Usunięto tymczasowy plik cache: {temp_file_path}")
                except OSError as remove_error:
                    logging.warning(f"Nie można usunąć pliku tymczasowego {temp_file_path}: {remove_error}")

        if cached_data:
            logging.warning(f"Zwracanie przestarzałych danych z cache dla {url[:40]}... z powodu błędu: {error_reason}")
            return cached_data
        else:
            logging.error(f"Brak dostępnych danych (ani z sieci, ani z cache) dla {url[:40]}.... Zwracanie błędu.")
            return f"Error: {error_reason}"

    def _get_current_block(self) -> str:
        return self._block_height_str

    def _get_current_block_hash(self) -> str:
        return self._block_hash_short_str

    def _get_swatch_internet_time(self) -> str:
        try:
            now_utc = time.gmtime()
            total_seconds_bmt = (now_utc.tm_hour * 3600 + now_utc.tm_min * 60 + now_utc.tm_sec + 3600) % 86400
            beats = total_seconds_bmt / 86.4
            return f"@{int(beats):03}"
        except Exception as e:
            logging.error(f"Błąd obliczania czasu Swatch: {e}")
            return "@Error"

    def _get_font_path(self, font_family_name: str, fallback_paths: list[str]) -> str | None:
        try:
            ImageFont.truetype(font_family_name, 10)
            logging.debug(f"Znaleziono czcionkę systemową przez nazwę: {font_family_name}")
            return font_family_name
        except IOError:
             logging.debug(f"Nie znaleziono czcionki systemowej przez nazwę: {font_family_name}. Sprawdzanie ścieżek...")

        for path in fallback_paths:
            if os.path.exists(path):
                try:
                    ImageFont.truetype(path, 10)
                    logging.debug(f"Znaleziono czcionkę w ścieżce: {path}")
                    return path
                except Exception as e:
                    logging.debug(f"Plik {path} istnieje, ale nie można załadować czcionki: {e}")
                    continue
        logging.warning(f"Nie znaleziono odpowiedniej czcionki dla '{font_family_name}' ani w podanych ścieżkach.")
        return None

    def _get_symbol_font_path(self) -> str | None:
        paths = [
            "C:\\Windows\\Fonts\\seguisym.ttf",
            "C:\\Windows\\Fonts\\arialuni.ttf",
            "/System/Library/Fonts/Apple Symbols.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
            "/usr/share/fonts/google-noto/NotoSansSymbols2-Regular.ttf"
        ]
        return self._get_font_path("Symbol", paths)

    def _get_main_font_path(self) -> str | None:
        windows_paths = ["C:\\Windows\\Fonts\\segoeui.ttf", "C:\\Windows\\Fonts\\seguibld.ttf"]
        fallback_paths = [
            "/usr/share/fonts/truetype/msttcorefonts/Segoe_UI.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/System/Library/Fonts/LucidaGrande.ttc",
        ]
        if platform.system() == "Windows":
             return self._get_font_path(FONT_FAMILY, windows_paths + fallback_paths)
        else:
             return self._get_font_path(FONT_FAMILY, fallback_paths)

    def _create_watermark_text(self) -> str:
        height_str = self._block_height_str
        beat_str = self._beat_time_str
        time_str = self._current_time_str

        if self._full_block_hash_str and len(self._full_block_hash_str) == 64 and "Error" not in self._full_block_hash_str:
             block_hash_str = self._full_block_hash_str
        else:
             block_hash_str = self._block_hash_short_str

        if self.lang=='pl':
            text=f"{self.prompt}@\nCzas: {time_str} | BeatTime: {beat_str} | Blok: {height_str}\nHash: {block_hash_str}"
        else:
            text=f"{self.prompt}@\nTime: {time_str} | BeatTime: {beat_str} | Block: {height_str}\nHash: {block_hash_str}"
        return text

    # --- NOWA WERSJA _add_watermark_pil Z OBSŁUGĄ SIATKI ---
    def _add_watermark_pil(self, image: Image.Image, text: str) -> Image.Image:
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        width, height = image.size
        wm_mode = self._watermark_mode_var.get()
        num_watermarks = 1
        is_grid_based = False # Nowa flaga wskazująca na użycie siatki

        try:
            # Ustal liczbę znaków wodnych i czy użyć siatki
            if wm_mode in ["3", "5", "8"]:
                num_watermarks = int(wm_mode)
                is_grid_based = True
            else: # Domyślnie lub dla "1"
                wm_mode = "1"
                num_watermarks = 1
                is_grid_based = False
        except ValueError:
            logging.warning(f"Nieprawidłowa wartość trybu znaku wodnego '{wm_mode}'. Używanie domyślnego '1'.")
            wm_mode, num_watermarks, is_grid_based = "1", 1, False

        # --- Ładowanie czcionki (bez zmian w stosunku do poprzedniej poprawionej wersji) ---
        font_path = self._get_main_font_path() or self._get_symbol_font_path()
        font_size = WATERMARK_FONT_SIZE # Używa teraz nowej, mniejszej wartości
        font = None
        font_description = "domyślnej Pillow"
        try:
            if font_path:
                 font = ImageFont.truetype(font_path, font_size)
                 font_description = f"'{font_path}'"
            else:
                 raise IOError("Brak preferowanej ścieżki czcionki")
        except IOError:
            logging.warning(f"Nie można załadować preferowanej czcionki ({font_path or 'brak'}). Próba użycia domyślnej czcionki Pillow.")
            try: font = ImageFont.load_default(size=font_size)
            except TypeError: font = ImageFont.load_default()
            except Exception as e_load:
                logging.error(f"Nie można załadować nawet domyślnej czcionki Pillow: {e_load}.")
                return image
        except Exception as e:
            logging.error(f"Nieoczekiwany błąd ładowania czcionki '{font_path}': {e}. Używanie domyślnej.")
            font = ImageFont.load_default()

        logging.debug(f"Użyto czcionki {font_description} (rozmiar ~{font_size}) dla znaku wodnego.")
        # --- Koniec ładowania czcionki ---

        watermark_text = text

        # --- Obliczanie rozmiaru tekstu i tworzenie stempla (bez zmian) ---
        temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        text_bbox = (0, 0, 300, 100)
        try: text_bbox = temp_draw.textbbox((0, 0), watermark_text, font=font, spacing=4)
        except AttributeError:
            try: text_size = temp_draw.multiline_textsize(watermark_text, font=font, spacing=4); text_bbox = (0, 0, text_size[0], text_size[1])
            except AttributeError:
                try: text_size = temp_draw.textsize(watermark_text, font=font); text_bbox = (0, 0, text_size[0], text_size[1])
                except Exception as e_size: logging.error(f"Nie można zmierzyć rozmiaru tekstu WM: {e_size}")
        finally: del temp_draw
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        margin = 10
        stamp_width = text_width + 2 * margin + text_bbox[0]
        stamp_height = text_height + 2 * margin + text_bbox[1]
        stamp_image = None
        try: stamp_image = Image.new("RGBA", (int(stamp_width), int(stamp_height)), (0, 0, 0, 0))
        except ValueError:
            logging.warning(f"Nieprawidłowy obliczony rozmiar stempla WM ({stamp_width}x{stamp_height}). Używanie fallback 320x120.")
            stamp_image = Image.new("RGBA", (max(320, int(stamp_width)), max(120, int(stamp_height))), (0, 0, 0, 0))
            stamp_width, stamp_height = stamp_image.size
        draw_stamp = ImageDraw.Draw(stamp_image)
        text_x = margin + text_bbox[0]
        text_y = margin + text_bbox[1]
        alpha = int(255 * (WATERMARK_OPACITY / 100.0)) # Używa teraz nowej, mniejszej wartości
        shadow_color = (0, 0, 0, alpha)
        text_color = (255, 255, 255, alpha)
        shadow_offset = 2
        draw_stamp.text((text_x + shadow_offset, text_y + shadow_offset), watermark_text, font=font, fill=shadow_color, spacing=4)
        draw_stamp.text((text_x, text_y), watermark_text, font=font, fill=text_color, spacing=4)
        try: rotated_stamp = stamp_image.rotate(WATERMARK_ANGLE, resample=Image.Resampling.NEAREST, expand=True)
        except AttributeError: rotated_stamp = stamp_image.rotate(WATERMARK_ANGLE, resample=Image.NEAREST, expand=True)
        rotated_width, rotated_height = rotated_stamp.size
        # --- Koniec tworzenia stempla ---

        # --- NOWA LOGIKA POZYCJONOWANIA ---
        if is_grid_based:
            # Definicje pozycji w siatce 3x3 (row, col) dla różnych ilości WM
            # (0,0) to lewy górny róg, (2,2) to prawy dolny
            grid_positions = {
                3: [(0, 0), (2, 2), (1, 1)],  # Rogi + środek
                5: [(0, 0), (0, 2), (2, 0), (2, 2), (1, 1)], # 4 rogi + środek
                8: [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)] # Wszystkie oprócz środka
            }

            selected_cells = grid_positions.get(num_watermarks, [])
            if len(selected_cells) != num_watermarks:
                 logging.warning(f"Niezdefiniowane pozycje siatki dla {num_watermarks} znaków wodnych. Używanie losowego rozmieszczenia jako fallback.")
                 is_grid_based = False
            else:
                margin_percent = 0.05
                h_margin = int(width * margin_percent)
                v_margin = int(height * margin_percent)
                usable_width = width - 2 * h_margin
                usable_height = height - 2 * v_margin
                cell_width = usable_width / 3
                cell_height = usable_height / 3
                max_offset_x = int(cell_width * 0.10)
                max_offset_y = int(cell_height * 0.10)

                logging.debug(f"Rozmieszczanie {num_watermarks} znaków wodnych na siatce 3x3 z marginesami ({h_margin}px, {v_margin}px)")

                for i in range(num_watermarks):
                    if i >= len(selected_cells): break
                    row, col = selected_cells[i]
                    target_center_x = h_margin + (col + 0.5) * cell_width
                    target_center_y = v_margin + (row + 0.5) * cell_height
                    offset_x = random.randint(-max_offset_x, max_offset_x)
                    offset_y = random.randint(-max_offset_y, max_offset_y)
                    final_center_x = target_center_x + offset_x
                    final_center_y = target_center_y + offset_y
                    paste_x = int(final_center_x - rotated_width / 2)
                    paste_y = int(final_center_y - rotated_height / 2)
                    paste_x = max(0, min(paste_x, width - rotated_width))
                    paste_y = max(0, min(paste_y, height - rotated_height))

                    logging.debug(f"Wklejanie znaku wodnego {i+1}/{num_watermarks} (Siatka: {row},{col}) w ({paste_x},{paste_y})")
                    image.paste(rotated_stamp, (paste_x, paste_y), rotated_stamp)

        # Jeśli nie używamy siatki (np. num_watermarks = 1 lub fallback)
        if not is_grid_based:
            if num_watermarks == 1:
                pos_x = (width - rotated_width) // 2
                pos_y = (height - rotated_height) // 2
                logging.debug(f"Wklejanie pojedynczego wycentrowanego znaku wodnego w ({pos_x},{pos_y})")
                image.paste(rotated_stamp, (pos_x, pos_y), rotated_stamp)
            else: # Fallback do starej metody losowej
                 logging.debug(f"Używanie losowego rozmieszczenia (fallback) dla {num_watermarks} znaków wodnych.")
                 for i in range(num_watermarks):
                     max_x = max(0, width - rotated_width)
                     max_y = max(0, height - rotated_height)
                     pos_x = random.randint(0, max_x)
                     pos_y = random.randint(0, max_y)
                     logging.debug(f"Wklejanie znaku wodnego {i+1}/{num_watermarks} (Losowo-Fallback) w ({pos_x},{pos_y})")
                     image.paste(rotated_stamp, (pos_x, pos_y), rotated_stamp)

        return image
    # --- KONIEC NOWEJ WERSJI _add_watermark_pil ---

    def _add_watermark_cv2(self, frame: np.ndarray, text: str) -> np.ndarray:
        try:
            img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            wm_img_pil = self._add_watermark_pil(img_pil, text) # Używa teraz nowej wersji
            return cv2.cvtColor(np.array(wm_img_pil), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logging.error(f"Błąd podczas dodawania znaku wodnego do klatki CV2: {e}")
            return frame

    def _get_capture_filename(self, extension: str, mode: str) -> str:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        cleaned_prompt = "".join(c for c in self.prompt.replace(" ","_").replace("@","")[:20] if c.isalnum() or c in ('_','-'))
        if not cleaned_prompt: cleaned_prompt = "prompt"

        full_hash = self._full_block_hash_str
        hash_part = "HASH_N_A"

        if full_hash and len(full_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in full_hash):
            hash_part = full_hash
        else:
            logging.warning(f"Pełny hash '{full_hash}' nie jest dostępny lub poprawny dla nazwy pliku. Używanie skróconego/alternatywy.")
            short_hash = self._block_hash_short_str
            if short_hash and "Error" not in short_hash:
                 hash_part = "".join(c for c in short_hash.replace("...","").replace("Error","ERR").replace(":","").replace("@","") if c.isalnum() or c in ('_','-','.'))
                 if not hash_part: hash_part = "HASH_SHORT_INVALID"
            else:
                 hash_part = "HASH_UNAVAILABLE"

        filename = f"TimechainProof({timestamp})-{cleaned_prompt}@{hash_part}.{extension}"

        try:
            base_dir = os.getcwd()
            capture_dir_path = os.path.join(base_dir, CAPTURE_SUBDIR)
            os.makedirs(capture_dir_path, exist_ok=True)
            full_path = os.path.join(capture_dir_path, filename)
            logging.debug(f"Wygenerowano nazwę pliku przechwytywania (nowy format): {full_path}")
            return full_path
        except Exception as e:
            logging.error(f"Nie można utworzyć lub użyć katalogu '{CAPTURE_SUBDIR}' w '{base_dir}': {e}. Zapis w bieżącym katalogu.")
            return filename

    def _safely_restore_widget_visibility(self):
        try:
            if self.master.winfo_exists():
                logging.debug("Przywracanie widoczności widgetu...")
                self.master.deiconify()
                self.master.lift()
                self.master.update_idletasks()
                logging.debug("Widoczność widgetu została przywrócona.")
            else:
                logging.debug("Okno widgetu nie istnieje, nie można przywrócić widoczności.")
        except tk.TclError as e:
            logging.error(f"Błąd TclError podczas przywracania widoczności widgetu (prawdopodobnie zamykanie): {e}")
        except Exception as e:
            logging.error(f"Nieoczekiwany błąd podczas przywracania widoczności widgetu: {e}")

    def _capture_screenshot(self):
        capture_mode = self._screenshot_mode_var.get()
        file_path = self._get_capture_filename("png", capture_mode)
        watermark_style = self._watermark_mode_var.get() if capture_mode == SCREENSHOT_MODE_WATERMARK else 'N/A'
        logging.info(f"Rozpoczynanie zrzutu ekranu (Tryb: {capture_mode}, Styl WM: {watermark_style})...")
        original_visibility_state = False

        try:
            if capture_mode == SCREENSHOT_MODE_WATERMARK and self.master.winfo_viewable():
                logging.debug("Ukrywanie widgetu na czas zrzutu...")
                original_visibility_state = True
                self.master.withdraw()
                self.master.update_idletasks()
                time.sleep(0.15)

            screenshot_image = pyautogui.screenshot()
            logging.debug("Zrzut ekranu wykonany.")

            if capture_mode == SCREENSHOT_MODE_WATERMARK:
                watermark_text = self._create_watermark_text()
                logging.debug("Dodawanie znaku wodnego...")
                screenshot_image = self._add_watermark_pil(screenshot_image, watermark_text) # Używa nowej wersji

            metadata = PngInfo()
            capture_time = datetime.datetime.now().isoformat()
            metadata.add_text("Software", f"TimechainWidget v6.6") # Aktualizacja wersji
            metadata.add_text("CaptureTime", capture_time)
            metadata.add_text("Prompt", self.prompt)
            metadata.add_text("BlockHeight", self._block_height_str or "N/A")
            hash_to_embed = self._full_block_hash_str if self._full_block_hash_str and "Error" not in self._full_block_hash_str else (self._block_hash_short_str or "N/A")
            metadata.add_text("BlockHash", hash_to_embed)
            metadata.add_text("BeatTime", self._beat_time_str or "N/A")
            metadata.add_text("CaptureMode", capture_mode)
            if capture_mode == SCREENSHOT_MODE_WATERMARK:
                 metadata.add_text("WatermarkStyle", watermark_style)
            logging.debug("Metadane PNG przygotowane.")

            logging.debug(f"Zapisywanie PNG z metadanymi do {file_path}")
            screenshot_image.save(file_path, "PNG", pnginfo=metadata)
            success_message = 'Zrzut z metadanymi zapisano' if self.lang == 'pl' else 'Screenshot with metadata saved'
            logging.info(f"{success_message}: {file_path}")

        except Exception as e:
            logging.exception("Błąd podczas robienia zrzutu ekranu:")
            error_title = 'Błąd Zrzutu Ekranu' if self.lang == 'pl' else 'Screenshot Error'
            if self.master and self.master.winfo_exists():
                self.master.after(0, lambda err=e: messagebox.showerror(error_title, f"Błąd:\n{err}", parent=self.master))
            else:
                logging.error(f"Nie można pokazać błędu zrzutu ekranu (okno nie istnieje). Błąd: {e}")
        finally:
            if original_visibility_state:
                 self.master.after(0, self._safely_restore_widget_visibility)

    def _capture_video(self):
        capture_mode = self._screenshot_mode_var.get()
        fourcc_str = VIDEO_FOURCC
        file_extension = "mp4" if "mp4" in fourcc_str.lower() else "avi"
        file_path = self._get_capture_filename(file_extension, capture_mode)
        watermark_style = self._watermark_mode_var.get() if capture_mode == SCREENSHOT_MODE_WATERMARK else 'N/A'
        duration = self._video_duration_seconds
        logging.info(f"Rozpoczynanie nagrywania wideo (Tryb: {capture_mode}, WM: {watermark_style}, Czas: {duration}s, Kodek: {fourcc_str})...")

        video_writer = None
        original_visibility_state = False
        writer_initialized_successfully = False

        try:
            screen_size = pyautogui.size()
            fourcc_code = cv2.VideoWriter_fourcc(*fourcc_str)
            fps = 20.0
            logging.debug(f"Inicjalizacja VideoWriter: Ścieżka='{file_path}', FourCC='{fourcc_str}' ({fourcc_code}), FPS={fps}, Rozmiar={screen_size}")
            video_writer = cv2.VideoWriter(file_path, fourcc_code, fps, (screen_size.width, screen_size.height))

            if not video_writer.isOpened():
                logging.error(f"Nie można otworzyć VideoWriter! Sprawdź ścieżkę ('{file_path}') i dostępność kodeka ('{fourcc_str}').")
                error_message = (f"Błąd inicjalizacji nagrywania wideo.\nSprawdź uprawnienia zapisu/kodek '{fourcc_str}'." if self.lang == 'pl' else f"Failed to initialize video recording.\nCheck permissions/codec '{fourcc_str}'.")
                if self.master and self.master.winfo_exists():
                     self.master.after(0, lambda: messagebox.showerror('Błąd Nagrywania Wideo' if self.lang == 'pl' else 'Video Recording Error', error_message, parent=self.master))
                return

            writer_initialized_successfully = True
            logging.debug("VideoWriter pomyślnie zainicjalizowany.")
            watermark_text = self._create_watermark_text() if capture_mode == SCREENSHOT_MODE_WATERMARK else None
            start_time = time.time()

            if capture_mode == SCREENSHOT_MODE_WATERMARK and self.master.winfo_viewable():
                logging.debug("Ukrywanie widgetu na czas nagrywania wideo...")
                original_visibility_state = True
                self.master.withdraw()
                self.master.update_idletasks()
                time.sleep(0.15)

            frame_count = 0
            logging.info("Rozpoczęto przechwytywanie klatek wideo...")

            while (time.time() - start_time) < duration:
                if self._key_listener_stop_event.is_set():
                    logging.info("Nagrywanie wideo przerwane przez użytkownika.")
                    break
                try:
                    img = pyautogui.screenshot()
                    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                    if watermark_text:
                        frame = self._add_watermark_cv2(frame, watermark_text) # Używa nowej wersji _add_watermark_pil
                    video_writer.write(frame)
                    frame_count += 1
                except Exception as loop_err:
                    logging.error(f"Błąd w pętli przechwytywania klatki wideo: {loop_err}")
                    time.sleep(0.1)

            elapsed_time = time.time() - start_time
            logging.debug(f"Zakończono pętlę nagrywania wideo. Czas: {elapsed_time:.2f}s, Klatki: {frame_count}.")

            if not self._key_listener_stop_event.is_set() and frame_count > 0:
                label = 'Nagranie wideo zapisano' if self.lang == 'pl' else 'Video saved'
                logging.info(f"{label}: {file_path}")
            elif frame_count == 0:
                 logging.warning(f"Zakończono nagrywanie, 0 klatek przechwycono: {file_path}.")
                 if self.master.winfo_exists():
                      self.master.after(0, lambda: messagebox.showwarning('Błąd Nagrywania Wideo' if self.lang == 'pl' else 'Video Recording Warning','Nie przechwycono żadnych klatek wideo. Sprawdź logi.' if self.lang == 'pl' else 'No video frames were captured. Check logs.',parent=self.master))
            else:
                 logging.info(f"Nagrywanie przerwane, plik może być niekompletny: {file_path}")

        except Exception as e:
            logging.exception("Wystąpił ogólny błąd podczas nagrywania wideo:")
            error_title = 'Błąd Nagrywania Wideo' if self.lang == 'pl' else 'Video Recording Error'
            if self.master and self.master.winfo_exists():
                self.master.after(0, lambda err=e: messagebox.showerror(error_title, f"Błąd:\n{err}", parent=self.master))
            else:
                logging.error(f"Nie można pokazać błędu nagrywania wideo (okno nie istnieje). Błąd: {e}")
        finally:
            if original_visibility_state:
                self.master.after(0, self._safely_restore_widget_visibility)
            if writer_initialized_successfully and video_writer is not None:
                logging.debug("Zwalnianie VideoWriter...")
                video_writer.release()
                logging.debug("VideoWriter zwolniony.")
            elif video_writer is not None:
                logging.debug("VideoWriter nie został pomyślnie zainicjalizowany, ale próba zwolnienia.")
                video_writer.release()

            self._active_capture_thread = None
            logging.debug("Zresetowano flagę aktywnego nagrywania (wideo).")

    def _capture_gif(self):
        capture_mode = self._screenshot_mode_var.get()
        file_path = self._get_capture_filename("gif", capture_mode)
        watermark_style = self._watermark_mode_var.get() if capture_mode == SCREENSHOT_MODE_WATERMARK else 'N/A'
        duration = self._gif_duration_seconds
        frame_duration_ms = GIF_FRAME_DURATION_MS
        frame_interval_sec = frame_duration_ms / 1000.0

        logging.info(f"Rozpoczynanie nagrywania GIF (Tryb: {capture_mode}, WM: {watermark_style}, Czas: {duration}s, Klatka: {frame_duration_ms}ms)...")

        frames = []
        original_visibility_state = False

        try:
            watermark_text = self._create_watermark_text() if capture_mode == SCREENSHOT_MODE_WATERMARK else None
            start_time = time.time()
            last_capture_time = 0

            if capture_mode == SCREENSHOT_MODE_WATERMARK and self.master.winfo_viewable():
                logging.debug("Ukrywanie widgetu na czas nagrywania GIF...")
                original_visibility_state = True
                self.master.withdraw()
                self.master.update_idletasks()
                time.sleep(0.15)

            logging.info("Rozpoczęto przechwytywanie klatek GIF...")

            while (time.time() - start_time) < duration:
                if self._key_listener_stop_event.is_set():
                    logging.info("Nagrywanie GIF przerwane przez użytkownika.")
                    break
                current_time = time.time()
                if current_time - last_capture_time >= frame_interval_sec:
                    try:
                        frame_image = pyautogui.screenshot()
                        if watermark_text:
                            frame_image = self._add_watermark_pil(frame_image, watermark_text) # Używa nowej wersji
                        frames.append(frame_image)
                        last_capture_time = current_time
                        logging.debug(f"Przechwycono klatkę GIF nr {len(frames)}")
                    except Exception as frame_capture_error:
                        logging.error(f"Błąd podczas przechwytywania klatki GIF: {frame_capture_error}")
                        time.sleep(0.1)
                time.sleep(0.01)

            elapsed_time = time.time() - start_time
            logging.debug(f"Zakończono pętlę nagrywania GIF. Czas: {elapsed_time:.2f}s, Klatki: {len(frames)}.")

            if not frames:
                 logging.warning("Nie przechwycono żadnych klatek do GIF.")
                 if self.master.winfo_exists():
                      self.master.after(0, lambda: messagebox.showwarning('Błąd Nagrywania GIF' if self.lang == 'pl' else 'GIF Recording Warning','Nie przechwycono żadnych klatek GIF. Sprawdź logi.' if self.lang == 'pl' else 'No GIF frames were captured. Check logs.',parent=self.master))
            elif not self._key_listener_stop_event.is_set():
                logging.info(f"Zapisywanie {len(frames)} klatek do GIF: {file_path}...")
                try:
                    frames[0].save(file_path, save_all=True, append_images=frames[1:],
                                   duration=frame_duration_ms, loop=0, optimize=True)
                    label = 'Nagranie GIF zapisano' if self.lang == 'pl' else 'GIF saved'
                    logging.info(f"{label}: {file_path}")
                except Exception as save_err:
                     logging.exception(f"Błąd podczas zapisywania GIF: {save_err}")
                     error_title = 'Błąd Zapisu GIF' if self.lang == 'pl' else 'GIF Save Error'
                     if self.master and self.master.winfo_exists():
                          self.master.after(0, lambda err=save_err: messagebox.showerror(error_title, f"Błąd:\n{err}", parent=self.master))
                     else:
                          logging.error(f"Nie można pokazać błędu zapisu GIF. Błąd: {save_err}")
            else:
                 logging.info(f"Nagrywanie GIF przerwane, plik nie zapisany.")

        except Exception as e:
            logging.exception("Wystąpił ogólny błąd podczas nagrywania GIF:")
            error_title = 'Błąd Nagrywania GIF' if self.lang == 'pl' else 'GIF Recording Error'
            if self.master and self.master.winfo_exists():
                self.master.after(0, lambda err=e: messagebox.showerror(error_title, f"Błąd:\n{err}", parent=self.master))
            else:
                logging.error(f"Nie można pokazać błędu nagrywania GIF. Błąd: {e}")
        finally:
             if original_visibility_state:
                 self.master.after(0, self._safely_restore_widget_visibility)
             self._active_capture_thread = None
             logging.debug("Zresetowano flagę aktywnego nagrywania (GIF).")

    def _on_global_key_press(self, key):
        if self._key_listener_stop_event.is_set():
            return False

        try:
            target_function = None
            thread_name = None
            is_long_capture = False

            if key == keyboard.Key.print_screen:
                target_function = self._capture_screenshot
                thread_name = "ScreenshotThread"
                is_long_capture = False
            elif key == keyboard.Key.f9:
                target_function = self._capture_video
                thread_name = "VideoRecordThread"
                is_long_capture = True
            elif key == keyboard.Key.f10:
                target_function = self._capture_gif
                thread_name = "GifRecordThread"
                is_long_capture = True

            if target_function:
                logging.debug(f"Wykryto globalne wciśnięcie klawisza: {key}")

                if is_long_capture and self._active_capture_thread and self._active_capture_thread.is_alive():
                    logging.warning(f"Wciśnięto klawisz {key}, ale inne nagrywanie jest aktywne. Ignorowanie.")
                    if self.master.winfo_exists():
                        self.master.after(0, lambda: messagebox.showwarning(
                            'Nagrywanie Aktywne' if self.lang == 'pl' else 'Capture Active',
                            'Inne nagrywanie (Wideo/GIF) jest już w toku.' if self.lang == 'pl' else 'Another recording (Video/GIF) is already in progress.',
                            parent=self.master
                        ))
                    return True

                capture_thread = threading.Thread(target=target_function, name=thread_name, daemon=True)
                if is_long_capture:
                    self._active_capture_thread = capture_thread
                capture_thread.start()

        except Exception as e:
            logging.exception(f"Błąd w obsłudze globalnego skrótu klawiszowego {key}:")
        return True

    def _key_listener_run(self):
        logging.info("Wątek nasłuchujący klawiszy (pynput) został uruchomiony.")
        listener = None
        try:
            with keyboard.Listener(on_press=self._on_global_key_press) as listener:
                logging.debug("Listener pynput jest aktywny.")
                self._key_listener_stop_event.wait()
                logging.info("Otrzymano sygnał zatrzymania, zatrzymywanie listenera pynput...")
        except Exception as e:
            logging.exception("Wystąpił błąd w wątku nasłuchującym klawiszy (pynput):")
            system = platform.system()
            if system == "Linux": logging.error("Na Linuksie może to być problem z uprawnieniami lub Wayland/Xorg.")
            elif system == "Windows": logging.error("Na Windows może to być problem z uprawnieniami lub innym oprogramowaniem.")
            elif system == "Darwin": logging.error("Na macOS sprawdź uprawnienia 'Dostępność' w Ustawieniach Systemowych.")
        finally:
            logging.info("Wątek nasłuchujący klawiszy zakończył działanie.")
            if listener and listener.is_alive():
                try: listener.stop(); logging.debug("Jawnie zatrzymano listener pynput w finally.")
                except Exception as stop_err: logging.error(f"Błąd podczas zatrzymywania listenera pynput: {stop_err}")

    def _setup_key_listener(self):
        if self._key_listener_thread and self._key_listener_thread.is_alive():
            logging.warning("Listener klawiszy jest już aktywny.")
            return
        self._key_listener_stop_event.clear()
        self._key_listener_thread = threading.Thread(target=self._key_listener_run, name="KeyListenerThread", daemon=True)
        self._key_listener_thread.start()
        logging.info("Uruchomiono wątek nasłuchujący globalne skróty klawiszowe.")

# --- Główne Wykonanie Skryptu ---
if __name__ == "__main__":
    lang_input = input("Wybierz język / Select language (en/pl) [en]: ").strip().lower()
    selected_lang = 'pl' if lang_input == 'pl' else 'en'
    logging.info(f"Wybrano język: {selected_lang}")

    default_prompt = "TimechainProof"
    prompt_query = (f"Wprowadź swój monit (Enter = '{default_prompt}'): " if selected_lang == 'pl'
                    else f"Enter your prompt (Enter = '{default_prompt}'): ")
    user_prompt = input(prompt_query).strip() or default_prompt
    logging.info(f"Używany monit: '{user_prompt}'")

    print("\n" + ("-" * 45))
    print("--- Instrukcje Użytkowania ---" if selected_lang == 'pl' else "--- Usage Instructions ---")
    file_format_desc = "TimechainProof(RRRRMMDD-GGMMSS)-prompt@pełny_hash.ext"
    codec_note_pl = (f"UWAGA WIDEO/GIF: Nagrywanie może wymagać kodeków (np. '{VIDEO_FOURCC}') i uprawnień. Sprawdź logi.")
    codec_note_en = (f"VIDEO/GIF NOTE: Recording may require codecs (e.g., '{VIDEO_FOURCC}') and permissions. Check logs.")

    instr_pl = (
        f"Widget jest aktywny.\n"
        f"- Lewy Przycisk + Przeciągnij: Przesuń (dłuższe przeciągnięcie może powiększyć tekst).\n"
        f"- Prawy Przycisk: Menu (Edytuj monit, Widok hasha, Tryb przechwytu, Styl WM (Siatka), Czas Wideo/GIF, Zamknij).\n" # Zaktualizowano opis menu
        f"- Tryb 'Znak Wodny' ukrywa widget podczas przechwytywania.\n"
        f"- Zrzuty .png zawierają metadane.\n\n"
        f"Globalne Skróty Klawiszowe:\n"
        f"- PrintScreen (PrtScr): Zrzut ekranu (.png).\n"
        f"- F9: Nagraj wideo (.{'mp4' if VIDEO_FOURCC == 'mp4v' else 'avi'}).\n"
        f"- F10: Nagraj GIF (.gif).\n\n"
        f"Pliki zapisywane w '{CAPTURE_SUBDIR}' w formacie:\n  {file_format_desc}\n"
        f"{codec_note_pl}\n"
        f"Zamknij: Opcja w menu lub Ctrl+C w konsoli."
    )
    instr_en = (
        f"Widget is active.\n"
        f"- Left Button + Drag: Move (longer drag may enlarge text).\n"
        f"- Right Button: Menu (Edit prompt, Hash view, Capture mode, WM Style (Grid), Video/GIF duration, Close).\n" # Updated menu description
        f"- 'Watermark' mode hides the widget during capture.\n"
        f"- Screenshots (.png) include metadata.\n\n"
        f"Global Keyboard Shortcuts:\n"
        f"- PrintScreen (PrtScr): Take screenshot (.png).\n"
        f"- F9: Record video (.{'mp4' if VIDEO_FOURCC == 'mp4v' else 'avi'}).\n"
        f"- F10: Record GIF (.gif).\n\n"
        f"Files saved in '{CAPTURE_SUBDIR}' with format:\n  {file_format_desc}\n"
        f"{codec_note_en}\n"
        f"Close: Use menu option or Ctrl+C in console."
    )

    print(instr_pl if selected_lang == 'pl' else instr_en)
    print(f"{'-' * 45}\n")

    root = None
    app = None
    try:
        logging.debug("Tworzenie głównego okna Tkinter...")
        root = tk.Tk()
        logging.debug("Ukrywanie głównego okna Tkinter...")
        root.withdraw()

        logging.debug(f"Tworzenie instancji TimechainWidget...")
        app = TimechainWidget(root, user_prompt, selected_lang)
        logging.debug("Instancja TimechainWidget utworzona.")

        logging.info("Uruchamianie pętli Tkinter (mainloop)...")
        root.mainloop()
        logging.info("Pętla Tkinter (mainloop) zakończona.")

    except KeyboardInterrupt:
        logging.info("Wykryto KeyboardInterrupt (Ctrl+C). Zamykanie...")
        if app: app._close_widget()
        elif root and root.winfo_exists():
            try: root.destroy()
            except tk.TclError: pass
    except Exception as e:
        logging.exception("Wystąpił nieoczekiwany błąd krytyczny:")
        error_title = 'Błąd Krytyczny Aplikacji' if selected_lang == 'pl' else 'Application Critical Error'
        error_message = f"{'Wystąpił poważny błąd:' if selected_lang == 'pl' else 'A critical error occurred:'}\n\n{e}\n\n{'Sprawdź logi.' if selected_lang == 'pl' else 'Check logs.'}"
        try:
            temp_root = tk.Tk(); temp_root.withdraw(); messagebox.showerror(error_title, error_message, parent=None); temp_root.destroy()
        except Exception as mb_error:
            logging.error(f"Nie udało się wyświetlić okna błędu krytycznego: {mb_error}")
            print(f"\n!!! {error_title} !!!\n{error_message}\n", file=sys.stderr)
    finally:
        logging.info("Rozpoczynanie finalnego zamykania...")
        if app and hasattr(app, '_cancel_update') and not app._cancel_update:
            logging.warning("Widget nie został zamknięty poprawnie. Inicjowanie zamknięcia w finally.")
            app._close_widget()
        time.sleep(0.5)
        if app and app._key_listener_thread and app._key_listener_thread.is_alive():
             logging.warning("Wątek listenera wciąż aktywny w finally. Wymuszanie zatrzymania.")
             app._key_listener_stop_event.set()
             app._key_listener_thread.join(timeout=1.0)
             if app._key_listener_thread.is_alive(): logging.error("Nie udało się zatrzymać wątku listenera.")
        if root and root.winfo_exists():
             try: logging.debug("Niszczenie pozostałego okna root w finally."); root.destroy()
             except tk.TclError: pass
        logging.info("Aplikacja widgetu zakończyła działanie.")
        print("\nWidget został zamknięty." if selected_lang == 'pl' else "\nWidget closed.")
