# Timechain Watermark Screenshot


This program is designed specifically to ensure the authenticity and integrity of recorded screenshots by creating a tamper-resistant timestamp. It provides a reliable and trustworthy method for capturing and timestamping screenshots, making them suitable for proof-keeping purposes.

Features:

- Take screenshots with customizable watermarks
- Record short videos (10 seconds) with watermarks
- Create GIFs (21 seconds) with watermarks
- Watermarks include:
  - User-defined text
  - Current time
  - Bitcoin Beat Time
  - Current Bitcoin block number
  - Current Bitcoin block hash
- Supports both English and Polish languages
- Cross-platform compatibility (Windows, macOS, Linux)


Benefits:

- Maintains the authenticity and integrity of recorded screenshots by creating a timestamp resistant to tampering and falsification.
- Provides a reliable and verifiable record of digital activity.
- Particularly useful in legal or compliance matters where accurate and authentic records are crucial.
- Helps protect interests and ensures proper documentation of actions.
- Enhances the trustworthiness of digital records by using blockchain data to validate the timestamp.

Dependencies:

- os: Provides a way to interact with the operating system.
- time: Allows time-related operations, such as retrieving the current time and formatting timestamps.
- keyboard: Enables capturing keypress events, used to trigger the screenshot capture.
- pyautogui: Provides screen capture capabilities to take screenshots.
- PIL: The Python Imaging Library, used for image manipulation and adding watermarks.
- requests: Used for making HTTP requests to retrieve blockchain block information from the APIs.

Requirements

- Python 3.7+
- pip (Python package installer)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/timechain-watermark-screenshot.git
   cd timechain-watermark-screenshot
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the script:
   ```
   python timechained.py
   ```

2. Choose your preferred language (English or Polish).

3. Enter the watermark prompt when asked.

4. Use the following keys:
   - `Print Screen`: Take a screenshot with watermark
   - `F9`: Record a 10-second video with watermark
   - `F10`: Record a 21-second GIF with watermark
   - `Ctrl+C`: End the program

## System-specific Requirements

### Windows
- Ensure Python is added to your PATH
- Install the Visual C++ Redistributable Packages

### macOS
- Install Xcode Command Line Tools:
  ```
  xcode-select --install
  ```

### Linux
- Install the following packages:
  ```
  sudo apt-get update
  sudo apt-get install python3-dev python3-pip python3-tk python3-opencv
  ```

## Troubleshooting

If you encounter font-related issues:
1. Ensure you have a font that supports the Bitcoin symbol (₿)
2. Update the `get_bitcoin_font()` function with the correct path to your font

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Note: Make sure to have the necessary dependencies installed before running the program.

To bardzo prosty program użyteczny w bardzo specyficznej sytuacji np. kiedy ktoś chciał by udowodnić że zarejestrował coś pierwszy,... 
adepthus@getalby.com
