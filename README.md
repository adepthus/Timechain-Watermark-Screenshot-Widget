# Timechain Watermark Screenshot Widget

A minimalist desktop widget for capturing tamper-proof screenshots, videos, and GIFs with blockchain-based timestamps and customizable watermarks. Designed for authenticity and integrity in digital proof-keeping, ideal for legal, compliance, or personal documentation needs.

# Features

Tamper-Resistant Proofs: Embeds real-time blockchain data (Bitcoin block height, hash) and Swatch Internet Time in captures.
Customizable Watermarks: Add user-defined text, time, and blockchain info with adjustable styles (centered or grid: 3, 5, or 8 watermarks).
Capture Modes:

- Screenshots (.png) with embedded metadata.

- Videos (.mp4/.avi, configurable duration, default 10s).

- GIFs (.gif, configurable duration, default 7s).

Global Hotkeys: PrintScreen: Capture screenshot.

- F9: Record video.
- F10: Record GIF.

Cross-Platform: Supports Windows, macOS, and Linux.

Bilingual: English and Polish language support.

Enhanced Watermarking: Improved grid-based watermark placement (styles 3, 5, 8) with reduced opacity (75%) and font size (30).

File Naming: Structured as TimechainProof(YYYYMMDD-HHMMSS)-prompt @ full_hash.ext.

# Benefits

Ensures authenticity with blockchain-validated timestamps.
Reliable for legal or compliance documentation.
Enhances trust in digital records.
Simple, lightweight, and user-friendly.

# Dependencies

Python 3.7+
Libraries: requests, pyautogui, Pillow, opencv-python, numpy, pynput
Video codecs: OpenH264 or XVID (system-dependent)

Installation

Clone the repository:
```
git clone https://github.com/adepthus/Timechain-Watermark-Screenshot-Widget.git
cd Timechain-Watermark-Screenshot-Widget
```
 Install dependencies:
```
pip install -r requirements.txt
```
# Usage
Run the script:
```
python timechain-widget.py
```
Select language (en or pl) and enter a custom prompt (default: TimechainProof).

Interact with the widget:

Drag (Left Click): Move widget; longer drag scales text.
Right Click: Access menu to edit prompt, toggle full hash, set capture mode, configure watermark style, adjust video/GIF duration, or close.

Hotkeys: Use PrintScreen, F9, or F10 for captures.

Captures are saved in the Timechain_Captures directory with metadata (PNG only).

System-Specific Requirements:

Windows:

  - Add Python to PATH.

  - Install Visual C++ Redistributable Packages.

macOS

Install Xcode Command Line Tools:

```
xcode-select --install
```
Linux

Install dependencies:
```
sudo apt-get update
sudo apt-get install python3-dev python3-pip python3-tk python3-opencv
```
Limitations:

Metadata not embedded in MP4/GIF files.
Video/GIF recording requires appropriate system codecs.
Font issues may require manual path updates in _get_main_font_path().

Troubleshooting:
Font Issues: Ensure a compatible font (e.g., Segoe UI) is available or update font paths.
Codec Errors: Verify OpenH264/XVID codecs are installed for video recording.

Hotkey Conflicts: Check for conflicting applications using PrintScreen, F9, or F10.

Contributing:

Contributions are welcome! Fork the repository, make changes, and submit a Pull Request.

License:

Licensed under the MIT License. See LICENSE for details.

# Author 
@adepthus 

Secure your digital proofs with Timechained watermark Widget—where blockchain meets simplicity.
