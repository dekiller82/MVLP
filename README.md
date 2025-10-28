# MVLP - Multiviewer LED Panel

MVLP is an application that connects your iPixel-compatible LED panel to [Multiviewer](https://multiviewer.app/). It automatically displays the current track status—such as green flags, yellow flags, and safety cars—on your LED panel, providing instant visual feedback during a race.

![MVLP Screenshot](https://i.imgur.com/dSzoiTl.png)

**Note:** This project was entirely *vibecoded*. It works, but expect rough edges, unfinished logic, and behavior that may not always be predictable.

## Features
 
- **Automatic F1 Track Status**: Displays Green, Yellow, Red, Safety Car, and VSC status automatically.  
- **Auto-Discovery**: Scans for and finds your iPixel panels on startup.  
- **Device Management**: Remembers your devices and automatically reconnects on future launches.  
- **Full Device Control**: A dedicated window to manage connected devices, adjust brightness, flip the display 180°, and configure panel-specific settings.  

## Requirements

- An iPixel-compatible LED matrix panel.  
- A computer with Python 3.8+ and Bluetooth.  
- [Multiviewer](https://multiviewer.app/) installed and running on the same computer.  

## Installation

1.  **Clone the Repository**: First, download the project files to your computer.
    ```bash
    git clone https://github.com/dekiller82/MVLP.git
    cd ipixel-ctrl
    ```

2.  **Install Dependencies**: This project requires several Python libraries. You can install them all with a single command from the project's root directory.
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the Application**: Launch the application from your terminal.
    ```bash
    python ipixel_gui.py
    ```
2.  **First-Time Setup**:
    - On the first run (or if no devices are saved), the "Manage Devices" window will open automatically.
    - Click "Scan for Devices".
    - Once your panel appears in the list, click the checkbox next to it. You will be prompted to enter the panel's width and height.
    - After confirming, the app will connect and remember your device.
3.  **Normal Use**: On subsequent launches, the app will automatically find and reconnect to your saved devices. The Multiviewer integration will start, and your panel will be ready for the race!



## Acknowledgements

This project builds upon the foundational reverse-engineering work done by sdolphin-JP in the original command-line tool
https://github.com/sdolphin-JP/ipixel-ctrl.


## Related Links
- [App(Apple)](https://apps.apple.com/jp/app/ipixel-color/id1562961996)
- [App(Google)](https://play.google.com/store/apps/details?id=com.wifiled.ipixels)
