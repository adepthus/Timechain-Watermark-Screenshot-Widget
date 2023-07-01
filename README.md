# Timechain Watermark Screenshot


This program is designed specifically to ensure the authenticity and integrity of recorded screenshots by creating a tamper-resistant timestamp. It provides a reliable and trustworthy method for capturing and timestamping screenshots, making them suitable for proof-keeping purposes.

Features:

- Retrieves the current blockchain block height and block hash from the Blockstream and Blockchain.info APIs.
- Calculates the Swatch Internet Time based on the current time.
- Adds a customizable watermark to the captured screenshot with the provided prompt text.
- Includes a timestamp signed by the confirmed block hash, block height, current local time, and Swatch Internet Time.
- Ensures that the timestamp cannot be tampered with or falsified, providing a reliable record of when the screenshot was taken.

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

Instructions:

Enter the desired watermark text prompt when prompted.
Press the "Print Screen" key to capture a screenshot with the watermark.
The screenshot will be saved as a PNG file with a unique filename that includes the timestamp, prompt text, and current block hash.

Note: Make sure to have the necessary dependencies installed before running the program.

To bardzo prosty program użyteczny w bardzo specyficznej sytuacji np. kiedy ktoś chciał by udowodnić że zarejestrował coś pierwszy,... np. SKYPE ID "BITCOIN" i nie tylko,... 

adepthus@getalby.com
