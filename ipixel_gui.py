#!/usr/bin/env python3

import tkinter as tk
from tkinter import filedialog, messagebox, font
import argparse
import asyncio
import threading
import queue
import time
import os
import glob
import httpx
import sys
import webbrowser
import io
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw, GifImagePlugin
import ttkbootstrap as ttk

# Set AppUserModelID for Windows to handle taskbar icon correctly
if sys.platform == "win32":
    import ctypes
    myappid = 'sdolphin.mvlp.ipixel-ctrl.1' # arbitrary unique string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# New imports for advanced BLE handling
import json
from bleak import BleakClient, BleakScanner

# Add project root to path to allow importing ipixel_ctrl
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Correctly import the command modules from the new package structure
    from ipixel_ctrl.commands import write_data_png, write_data_gif, erase_data
    # Import spotipy for Spotify integration
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        messagebox.showerror("Dependency Error", "The 'spotipy' library is not installed.\nPlease run 'pip install spotipy'.")
        sys.exit(1)
    from ipixel_ctrl.commands import set_brightness, set_upside_down, set_clock_mode
except ImportError as e: # pragma: no cover
    messagebox.showerror("Import Error", f"Failed to import ipixel_ctrl module: {e}\n\nPlease run 'pip install -e .' from the project root.")
    sys.exit(1)

class BLEThread(threading.Thread):
    """A thread for managing the asyncio event loop and BLE communication."""
    def __init__(self, device_address, command_queue, status_queue):
        super().__init__()
        self.device_address = device_address
        self.command_queue = command_queue # This is a broadcast queue
        self.status_queue = status_queue
        self.loop = asyncio.new_event_loop()
        self.client = None
        self.daemon = True
        self._stop_event = None

 
    def stop(self):
        """Signals the thread to stop."""
        if self._stop_event:
            self._stop_event.set()
        self.command_queue.put_nowait(None) # Unblock queue.get()

    def disconnected_callback(self, client):
        """Handle unexpected disconnections."""
        print(f"Device {client.address} disconnected unexpectedly.")
        self.status_queue.put(f"BLE_DISCONNECTED:{client.address}")
        if self._stop_event:
            self._stop_event.set()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self._stop_event = asyncio.Event()
        self.status_queue.put(f"Connecting to {self.device_address}...")
        self.loop.run_until_complete(self.ble_worker())

    async def ble_worker(self):
        """Main worker for handling BLE connection and commands."""
        try:
            async with BleakClient(self.device_address, disconnected_callback=self.disconnected_callback) as client:
                self.client = client
                device_name = client.name if client.name else "iPixel Device"
                self.status_queue.put(f"BLE_CONNECTED_SUCCESS:{self.device_address}:{device_name}")
                print("Connected to the device")

                while not self._stop_event.is_set():
                    try:
                        # Use a timeout on the queue to allow the loop to check the stop event
                        payloads = await self.loop.run_in_executor(None, self.command_queue.get, True, 0.1)
                    except queue.Empty:
                        continue # No command, just loop and check stop event

                    if payloads is None: # Shutdown signal
                        break

                    try:
                        self.status_queue.put(f"Sending {len(payloads)} command(s)...")
                        for i, payload in enumerate(payloads):
                            print(f"Sending packet {i+1}/{len(payloads)}...")
                            await self.client.write_gatt_char("0000fa02-0000-1000-8000-00805f9b34fb", payload)

                        self.status_queue.put("Finished sending command.")
                    except Exception as e:
                        print(f"Error sending command: {e}")
                        self.status_queue.put(f"Error sending command: {e}")
                    finally:
                        self.command_queue.task_done()

        except Exception as e:
            self.status_queue.put(f"BLE_CONNECT_FAIL:{self.device_address}:{e}")
            print(f"Failed to connect to {self.device_address}: {e}")
            return # Exit if connection failed

        if self.client and self.client.is_connected:
            await self.client.disconnect()
        print("BLE thread finished.")
        self.status_queue.put(f"BLE_DISCONNECTED:{self.device_address}")

    async def send_payloads(self, payloads):
        """The original send function, adapted for the class."""
        if not self.client or not self.client.is_connected:
            raise ConnectionError("Device is not connected.")
        for payload in payloads:
            print(f"Sending payload: {payload.hex()}")
            await self.client.write_gatt_char("0000fa02-0000-1000-8000-00805f9b34fb", payload)
            await asyncio.sleep(0.02)

class MultiviewerThread(threading.Thread):
    """A thread for managing the connection to Multiviewer for F1."""
    def __init__(self, action_queue, status_queue):
        super().__init__()
        self.action_queue = action_queue
        self.status_queue = status_queue
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        url = "http://127.0.0.1:10101/api/graphql"
        graphql_query = {
            "query": "query { f1LiveTimingState { TrackStatus, RaceControlMessages } }"
        }
        last_status = None
        error_logged = False
        processed_messages = set()

        while not self._stop_event.is_set():
            sleep_duration = 0.1  # Faster polling for quicker response
            try:
                with httpx.Client(timeout=1.0) as client:
                    response = client.post(url, json=graphql_query)
                    response.raise_for_status()

                    data = response.json()
                    live_timing_state = data.get("data", {}).get("f1LiveTimingState", {})
                    if not live_timing_state:
                        time.sleep(0.5)
                        continue

                    track_status = live_timing_state.get("TrackStatus") or {}
                    status = str(track_status.get("Status", ""))

                    self.status_queue.put("MV_STATUS_CONNECTED")
                    error_logged = False

                    rc_data = live_timing_state.get("RaceControlMessages") or {}
                    rc_messages = rc_data.get("Messages", [])
                    for msg in rc_messages:
                        msg_utc = msg.get("Utc")
                        if msg_utc not in processed_messages:
                            processed_messages.add(msg_utc)
                            message_text = msg.get("Message", "")
                            if "SAFETY CAR IN THIS LAP" in message_text or "VIRTUAL SAFETY CAR ENDING" in message_text:
                                self.action_queue.put("ending")

                    if status and status != last_status:
                        last_status = status
                        print(f"Multiviewer status changed to: {status}")
                        action_map = {"1": "green", "2": "yellow", "4": "sc", "5": "red", "6": "vsc", "7": "ending"}
                        if status in action_map:
                            self.action_queue.put(action_map[status])

            except httpx.RequestError:
                if not error_logged:
                    self.status_queue.put("MV_STATUS_RETRYING")
                    error_logged = True
                sleep_duration = 1.0
            except Exception as e:
                print(f"An unexpected error in Multiviewer thread: {e}")
                sleep_duration = 1.0
            
            time.sleep(sleep_duration)
        print("Multiviewer thread finished.")
        self.status_queue.put("MV_STATUS_DISABLED") # Ensure status is updated on exit

class SpotifyThread(threading.Thread):
    """A thread for managing the connection to Spotify."""
    def __init__(self, action_queue, status_queue, client_id, client_secret, redirect_uri):
        super().__init__()
        self.action_queue = action_queue
        self.status_queue = status_queue
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.daemon = True
        self._stop_event = threading.Event()
        self.sp = None

    def stop(self):
        self._stop_event.set()

    def run(self):
        print("[Spotify] Thread started.")
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            self.status_queue.put("SPOTIFY_STATUS_ERROR:Missing credentials.")
            print("[Spotify] ERROR: Missing credentials.")
            return

        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope="user-read-currently-playing",
                open_browser=webbrowser.open
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            # This will trigger the auth flow if no token is cached
            self.sp.current_user() 
            print("[Spotify] Successfully connected to Spotify API.")
            self.status_queue.put("SPOTIFY_STATUS_CONNECTED")
        except Exception as e:
            self.status_queue.put(f"SPOTIFY_STATUS_ERROR:{e}")
            print(f"[Spotify] ERROR: Connection failed: {e}")
            return

        last_track_id = None # Initialize to None to force the first fetch
        while not self._stop_event.is_set():
            try:
                # print("[Spotify] Polling for current track...") # This can be noisy, uncomment if needed
                current_track = self.sp.current_user_playing_track()
                track_id = None
                if current_track and current_track.get('item'):
                    track_id = current_track['item']['id']
                    track_name = current_track['item']['name']
                else:
                    # This case handles when nothing is playing
                    if last_track_id is not None:
                        print("[Spotify] No track is currently playing.")
                        last_track_id = None # Reset to allow re-display if the same song plays again

                # Fetch if the track has changed OR if it's the very first run (last_track_id is None)
                if track_id and (track_id != last_track_id or last_track_id is None):
                    last_track_id = track_id
                    print(f"[Spotify] New track detected: {track_name}")

                    # Check if album art exists before trying to access it
                    images = current_track['item']['album'].get('images', [])
                    if images:
                        album_art_url = images[0]['url']
                        print("[Spotify] Downloading album art...")
                        with httpx.Client() as client:
                            response = client.get(album_art_url)
                            response.raise_for_status()
                            image_data = response.content

                        # Use PIL to open from bytes and save as a proper PNG to avoid format issues
                        try:
                            img = Image.open(io.BytesIO(image_data))
                            # Resize the image to 64x64 before saving
                            resized_img = img.resize((64, 64), Image.Resampling.LANCZOS).convert("RGBA")
                            # Optimize image by converting to a paletted format with 255 colors + transparency
                            # This significantly reduces file size for faster transfer.
                            try:
                                # This can fail on some images with complex palettes
                                optimized_img = resized_img.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
                            except Exception as quantize_error:
                                print(f"[Spotify] WARNING: Could not quantize image, falling back to RGBA. Error: {quantize_error}")
                                optimized_img = resized_img # Use the unoptimized RGBA image as a fallback
                            # Save in the same directory as the script to ensure a consistent location
                            with io.BytesIO() as output:
                                optimized_img.save(output, format="GIF", disposal=2) # Use disposal=2 for single-frame GIFs
                                optimized_img.save(output, format="GIF", disposal=2)  # Use disposal=2 for single-frame GIFs
                                self.action_queue.put(output.getvalue())
                            print("[Spotify] Album art resized, optimized as GIF, and queued for display.")
                        except Exception as pil_e:
                            print(f"[Spotify] ERROR: Could not process album art with PIL: {pil_e}") # pragma: no cover
                    else:
                        print(f"[Spotify] No album art found for track: {track_name}")

            except Exception as e:
                print(f"[Spotify] ERROR: An error occurred in the polling loop: {e}")
                last_track_id = None # Reset on error to allow re-fetching
            
            time.sleep(3) # Poll every 3 seconds
        print("[Spotify] Thread finished.")

class App(ttk.Window):
    def __init__(self):
        # Use ttkbootstrap Window with the 'superhero' dark theme
        super().__init__(themename="darkly")
        self.title("MVLP")

        # --- Icon and Font ---
        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")
        
        # Fonts will now be handled by the ttkbootstrap theme for universal compatibility.

        # --- Custom Red Accent Color ---
        # Create a new theme based on 'darkly' with a red accent
        try:
            darkly_theme = self.style.theme_definition("darkly")
            darkly_theme['colors']['primary'] = '#dc3545' # A nice red
            darkly_theme['colors']['active'] = '#bb2d3b'  # for hover
            self.style.theme_create("mvlp_theme", "darkly", darkly_theme)
            self.style.theme_use("mvlp_theme")
        except Exception: # Fallback if theme creation fails
            pass

        # --- Queues for threading ---
        self.mv_action_queue = queue.Queue()
        self.spotify_action_queue = queue.Queue()
        self.status_queue = queue.Queue() # For status updates from threads

        # --- Threading ---
        self.ble_threads = {} # Dict to hold a thread for each device
        self.spotify_thread = None
        self.mv_thread = None

        # --- State ---
        self.device_configs = {} # Dict to hold config for each device
        self.connected_devices = {} # Dict to hold connected device objects
        self.selected_device_address = None
        self.duplicate_h_var = tk.BooleanVar()
        self.brightness_var = tk.IntVar(value=100)
        self.flip_display_var = tk.BooleanVar()

        # self.current_device_address = None # Replaced by multi-device support
        self.is_sending_art = False # Lock to prevent album art spam
        self.gif_stop_timers = {} # Dictionary to hold stop timers for each device
        self.config_file = "ipixel_config.json"
        self.startup_actions_done = False # Flag to ensure startup actions run only once
        self.load_config()

        # --- GIF Mappings ---
        self.gif_map = {
            "green": "gifs/green.gif",
            "yellow": "gifs/yellow.gif",
            "red": "gifs/red.gif",
            "sc": "gifs/sc.gif",
            "vsc": "gifs/vsc.gif",
            "ending": "gifs/ending.gif",
            "current_action": None # To store the last MV action
        }

        # --- Resources ---
        self.unchecked_img = self.create_checkbox_image(False)
        self.checked_img = self.create_checkbox_image(True)


        # --- UI Setup ---
        self.columnconfigure(0, weight=1) # Main window column
        self.rowconfigure(0, weight=1) # Main window row for the main frame

        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)

        # --- Build Main View ---
        self.setup_mv_view(main_frame)
        self.setup_spotify_view(main_frame)

        # --- Create and hide secondary windows at startup ---
        self.devices_window = ttk.Toplevel(self)
        self.devices_window.withdraw() # Hide window before populating it
        self.devices_window.title("MVLP - Manage Devices")
        self.devices_window.geometry("550x600")
        self.devices_window.minsize(550, 400)
        if os.path.exists("icon.ico"): self.devices_window.iconbitmap("icon.ico")
        self.setup_devices_window(self.devices_window)
        self.devices_window.protocol("WM_DELETE_WINDOW", self.devices_window.withdraw)

        self.manual_send_window = ttk.Toplevel(self)
        self.manual_send_window.withdraw() # Hide window before populating it
        self.manual_send_window.title("MVLP - DEBUG")
        self.manual_send_window.minsize(550, 400)
        if os.path.exists("icon.ico"): self.manual_send_window.iconbitmap("icon.ico")
        self.setup_manual_send_window(self.manual_send_window)
        self.manual_send_window.protocol("WM_DELETE_WINDOW", self.manual_send_window.withdraw)

        self.status_label = ttk.Label(self, text="Status: Idle", bootstyle="primary")
        self.status_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        # Set main window initial size and minimum size
        self.update_idletasks()
        self.minsize(self.winfo_width() + 200, self.winfo_height())

        # Start queue processors
        self.process_status_queue()
        self.process_mv_action_queue()
        self.process_spotify_action_queue()

        # Automatically populate device list and connect to saved devices on startup
        self.after(100, self.populate_tree_from_config)
        if self.device_configs:
            self.after(200, self.start_connection_process)
        else:
            # If no config, open the devices window for the user
            self.after(200, self.open_devices_window)


    def setup_mv_view(self, parent):
        """Populate the main Multiviewer view with its controls."""
        mv_frame = ttk.LabelFrame(parent, text="Multiviewer for F1", padding=(10, 5))
        mv_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        mv_frame.columnconfigure(0, weight=1)
        
        self.is_mv_enabled = tk.BooleanVar(value=False)
        self.mv_checkbutton = ttk.Checkbutton(mv_frame, text="Enable Multiviewer Integration", variable=self.is_mv_enabled, command=self.toggle_multiviewer)
        self.mv_checkbutton.pack(anchor="w")

        self.mv_status_var = tk.StringVar(value="Disabled")
        self.mv_status_label = ttk.Label(mv_frame, textvariable=self.mv_status_var, bootstyle="secondary")
        self.mv_status_label.pack(anchor="w", padx=10, pady=5)

        # --- Buttons to open other windows ---
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="Manage Devices", command=self.open_devices_window, bootstyle="primary-outline").grid(row=0, column=0, sticky="ew", padx=5)
        ttk.Button(button_frame, text="DEBUG", command=self.open_manual_send_window, bootstyle="primary-outline").grid(row=0, column=1, sticky="ew", padx=5)

    def setup_spotify_view(self, parent):
        """Populate the main Spotify view with its controls."""
        spotify_frame = ttk.LabelFrame(parent, text="Spotify Album Art", padding=(10, 5))
        spotify_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=10)
        spotify_frame.columnconfigure(0, weight=1)

        self.is_spotify_enabled = tk.BooleanVar(value=False)
        spotify_check = ttk.Checkbutton(spotify_frame, text="Enable Spotify Integration", variable=self.is_spotify_enabled, command=self.toggle_spotify)
        spotify_check.pack(anchor="w")

        self.spotify_status_var = tk.StringVar(value="Disabled")
        self.spotify_status_label = ttk.Label(spotify_frame, textvariable=self.spotify_status_var, bootstyle="secondary")
        self.spotify_status_label.pack(anchor="w", padx=10, pady=5)

    def setup_manual_send_window(self, parent):
        """Populates the UI for the Manual Send window."""
        parent.columnconfigure(0, weight=1) # Make notebook expand
        parent.rowconfigure(0, weight=1)

        # --- Main Notebook for Tabs ---
        debug_notebook = ttk.Notebook(parent)
        debug_notebook.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        # --- Multiviewer Tab ---
        mv_debug_tab = ttk.Frame(debug_notebook, padding="10")
        debug_notebook.add(mv_debug_tab, text='Multiviewer')
        mv_debug_tab.columnconfigure(0, weight=1)

        # --- Populate Multiviewer Tab ---
        file_frame = ttk.LabelFrame(mv_debug_tab, text="File Selection", padding=(10, 5))
        file_frame.grid(row=0, column=0, sticky="ew")
        file_frame.columnconfigure(1, weight=1)
        ttk.Label(file_frame, text="Files:").grid(row=0, column=0, sticky="w")
        self.file_listbox = tk.Listbox(file_frame, selectmode=tk.EXTENDED, height=4, width=50)
        self.file_listbox.grid(row=0, column=1, sticky="ew")
        ttk.Button(file_frame, text="Browse...", command=self.browse_files).grid(row=1, column=1, sticky="e", pady=5)

        send_notebook = ttk.Notebook(mv_debug_tab)
        send_notebook.grid(row=1, column=0, sticky="ew", pady=5)
        self.png_frame = ttk.Frame(send_notebook, padding="10")
        send_notebook.add(self.png_frame, text='Image (PNG/JPG)')
        self.gif_frame = ttk.Frame(send_notebook, padding="10")
        send_notebook.add(self.gif_frame, text='Animation (GIF)')
        self.setup_png_tab()
        self.setup_gif_tab()

        self.debug_gif_frame = ttk.LabelFrame(mv_debug_tab, text="Quick Send GIFs", padding=(10, 5))
        self.debug_gif_frame.grid(row=2, column=0, sticky="ew", pady=5)
        self.populate_debug_gifs()

        action_frame = ttk.Frame(mv_debug_tab)
        action_frame.grid(row=3, column=0, sticky="ew", pady=10)
        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)
        self.erase_button = ttk.Button(action_frame, text="Erase All Buffers", command=self.start_erase, bootstyle="secondary")
        self.erase_button.grid(row=0, column=1, padx=5, sticky="ew")
        self.write_button = ttk.Button(action_frame, text="Write to All Devices", command=self.start_write, bootstyle="primary")
        self.write_button.grid(row=0, column=0, padx=5, sticky="ew")

    def setup_devices_window(self, parent):
        """Populate the Devices tab."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # --- Connected Devices List ---
        conn_frame = ttk.Frame(parent)
        conn_frame.grid(row=0, column=0, sticky="ew", pady=5)
        conn_frame.columnconfigure(0, weight=1)
        conn_frame.columnconfigure(1, weight=1)
        ttk.Button(conn_frame, text="Scan for Devices", command=self.start_device_scan, bootstyle="primary-outline").grid(row=0, column=0, padx=5, sticky="ew")
        ttk.Button(conn_frame, text="Reconnect Saved", command=self.start_connection_process, bootstyle="secondary-outline").grid(row=0, column=1, padx=5, sticky="ew")
        ttk.Button(conn_frame, text="Disconnect All", command=self.disconnect_all_devices).grid(row=0, column=2, padx=5)

        devices_frame = ttk.LabelFrame(parent, text="Connected Devices", padding=(10, 5))
        devices_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        devices_frame.columnconfigure(0, weight=1)
        devices_frame.rowconfigure(0, weight=1)

        self.device_tree = ttk.Treeview(devices_frame, columns=("name", "address", "status"), show=["headings", "tree"])
        self.device_tree.heading("name", text="Name")
        self.device_tree.heading("address", text="Address")
        self.device_tree.heading("status", text="Status")
        # Designate column #0 as the tree column to show images/checkboxes
        self.device_tree.column("#0", width=30, stretch=False, anchor="center")
        self.device_tree.column("name", width=150, stretch=True)
        self.device_tree.column("address", width=150)
        self.device_tree.column("status", width=100)
        self.device_tree.grid(row=0, column=0, sticky="nsew")
        self.device_tree.tag_configure('checked', image=self.checked_img)
        self.device_tree.tag_configure('unchecked', image=self.unchecked_img)
        self.device_tree.bind("<Button-1>", self.on_device_tree_click)

        # --- Image Options Frame (now per-device) ---
        self.options_frame = ttk.LabelFrame(parent, text="Device Options (Select a device)", padding=(10, 5))
        self.options_frame.grid(row=2, column=0, sticky="ew", pady=5)
        self.options_frame.columnconfigure(1, weight=1)

        ttk.Label(self.options_frame, text="Start Buffer (1-255):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.buffer_entry = ttk.Entry(self.options_frame, state=tk.DISABLED)
        self.buffer_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.auto_resize_var = tk.BooleanVar()
        self.resize_check = ttk.Checkbutton(self.options_frame, text="Auto-resize image to device dimensions", variable=self.auto_resize_var, state=tk.DISABLED)
        self.resize_check.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.options_frame, text="Device Width:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.width_entry = ttk.Entry(self.options_frame, state=tk.DISABLED)
        self.width_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(self.options_frame, text="Device Height:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.height_entry = ttk.Entry(self.options_frame, state=tk.DISABLED)
        self.height_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(self.options_frame, text="Anchor (e.g., 0x33):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.anchor_entry = ttk.Entry(self.options_frame, state=tk.DISABLED)
        self.anchor_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        # Add the per-device duplication checkbox
        self.duplicate_check = ttk.Checkbutton(self.options_frame, text="Duplicate Horizontally", variable=self.duplicate_h_var, state=tk.DISABLED)
        self.duplicate_check.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        # Add Brightness Slider
        ttk.Label(self.options_frame, text="Brightness:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        self.brightness_slider = ttk.Scale(self.options_frame, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.brightness_var, state=tk.DISABLED)
        self.brightness_slider.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        self.brightness_slider.bind("<ButtonRelease-1>", self.on_brightness_release)

        # Add Flip Display Checkbox
        self.flip_check = ttk.Checkbutton(self.options_frame, text="Flip Display 180°", variable=self.flip_display_var, state=tk.DISABLED, command=self.on_flip_change)
        self.flip_check.grid(row=7, column=1, padx=5, pady=5, sticky="w")

        # Add Clock Style Combobox
        ttk.Label(self.options_frame, text="Exit Clock Style:").grid(row=8, column=0, padx=5, pady=5, sticky="w")
        self.clock_style_var = tk.StringVar()
        self.clock_style_combo = ttk.Combobox(self.options_frame, textvariable=self.clock_style_var, values=[str(i) for i in range(1, 9)], state=tk.DISABLED, width=5)
        self.clock_style_combo.grid(row=8, column=1, padx=5, pady=5, sticky="w")

        # Add save button for device config
        ttk.Button(self.options_frame, text="Save Options", command=self.save_device_options, state=tk.DISABLED, bootstyle="success").grid(row=9, column=1, sticky="e", padx=5, pady=5)

    def setup_png_tab(self):
        self.join_files_var = tk.BooleanVar()
        ttk.Checkbutton(self.png_frame, text="Join image files into one", variable=self.join_files_var).pack(padx=5, pady=5, anchor="w")

    def setup_gif_tab(self):
        self.gif_frame.columnconfigure(1, weight=1)
        self.make_from_image_var = tk.BooleanVar()
        make_gif_check = ttk.Checkbutton(self.gif_frame, text="Make GIF from static images", variable=self.make_from_image_var)
        make_gif_check.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        ttk.Label(self.gif_frame, text="Frame Duration (ms):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.duration_entry = ttk.Entry(self.gif_frame)
        self.duration_entry.insert(0, "100")
        self.duration_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    def populate_debug_gifs(self):
        gif_dir = "gifs"
        if not os.path.isdir(gif_dir):
            ttk.Label(self.debug_gif_frame, text=f"'{gif_dir}' directory not found.").pack()
            return

        gif_files = glob.glob(os.path.join(gif_dir, "*.gif"))
        if not gif_files:
            ttk.Label(self.debug_gif_frame, text="No GIFs found in 'gifs' directory.").pack()
            return

        for i, gif_path in enumerate(gif_files):
            gif_name = os.path.splitext(os.path.basename(gif_path))[0].upper()
            btn = ttk.Button(self.debug_gif_frame, text=gif_name, command=lambda p=gif_path: self.send_debug_gif(p))
            btn.grid(row=i // 3, column=i % 3, padx=5, pady=5, sticky="ew")
            self.debug_gif_frame.columnconfigure(i % 3, weight=1)

    def browse_files(self):
        title = "Select Image or Animation Files"
        filetypes = [("Image/Animation Files", "*.gif *.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        
        files = filedialog.askopenfilenames(title=title, filetypes=filetypes)
        if files:
            self.file_listbox.delete(0, tk.END)
            for file in files:
                self.file_listbox.insert(tk.END, file)

    def create_checkbox_image(self, checked):
        """Creates a 16x16 PIL image for the checkbox."""
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Draw the box
        draw.rectangle((2, 2, 13, 13), outline="#888888", width=1)
        if checked:
            # Draw a crisp, manual checkmark
            draw.line([(4, 8), (7, 11), (12, 4)], fill="#dc3545", width=2)
        return ImageTk.PhotoImage(img)

    def load_icon_image(self, path, size):
        """Loads an image, resizes it, and returns a PhotoImage."""
        if not os.path.exists(path):
            # Return a transparent placeholder if icon not found
            return ImageTk.PhotoImage(Image.new("RGBA", size, (0,0,0,0)))
        
        img = Image.open(path).resize(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)

    def open_devices_window(self):
        if self.devices_window and self.devices_window.winfo_exists():
            self.devices_window.deiconify()
            self.devices_window.lift()

    def open_manual_send_window(self):
        if self.manual_send_window and self.manual_send_window.winfo_exists():
            self.manual_send_window.deiconify()
            self.manual_send_window.lift()


    def populate_tree_from_config(self):
        """Adds devices from the loaded config to the device tree if they aren't there."""
        for address in self.device_configs:
            if not self.device_tree.exists(address):
                # Add with a default name and disconnected status
                self.device_tree.insert("", "end", iid=address, values=("Saved Device", address, "Disconnected"), tags=('unchecked',))

    def start_connection_process(self):
        """Starts the connection process for all saved devices."""
        saved_addresses = self.device_configs.keys()
        if saved_addresses:
            self.status_label.config(text=f"Status: Reconnecting to {len(saved_addresses)} saved device(s)...")
            for address in saved_addresses:
                self.connect_to_device(address)
        else:
            self.status_label.config(text="Status: No saved devices to reconnect.")

    def start_device_scan(self):
        """Initiates a BLE device scan in a separate thread."""
        self.status_label.config(text="Status: No saved device. Scanning...")
        self.status_label.config(text="Status: Scanning for devices...")
        scan_thread = threading.Thread(target=self._scan_and_connect_worker, daemon=True)
        scan_thread.start()

    def _scan_and_connect_worker(self):
        """The actual scanning logic that runs in a thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Discover all devices, we can filter in the main thread if needed
            devices = loop.run_until_complete(BleakScanner.discover(timeout=5.0))

            if not devices:
                self.status_queue.put("Scan complete: No devices found.")
            else:
                # Let the main thread handle populating the list.
                self.after(0, self.populate_device_tree, devices)
                self.status_queue.put(f"Scan complete: Found {len(devices)} device(s).")
        except Exception as e:
            self.status_queue.put(f"Scan failed: {e}")

    def show_device_selection_dialog(self, devices):
        """Creates a Toplevel window to let the user choose a device."""
        dialog = tk.Toplevel(self)
        dialog.title("Select Device")
        dialog.transient(self)
        dialog.grab_set()
    

        ttk.Label(dialog, text="Multiple devices found. Please select one:").pack(padx=10, pady=10)

        listbox = tk.Listbox(dialog, height=len(devices))
        for device in devices:
            listbox.insert(tk.END, f"{device.name} ({device.address})")
        listbox.pack(padx=10, pady=5, fill=tk.X)
        listbox.selection_set(0)

        def on_connect():
            selected_indices = listbox.curselection()
            if selected_indices:
                selected_device = devices[selected_indices[0]]
                if selected_device.address not in self.connected_devices:
                    self.connect_to_device(selected_device.address)
                    self.connected_devices[selected_device.address] = selected_device
                dialog.destroy()

        ttk.Button(dialog, text="Connect", command=on_connect).pack(pady=10)

    def prompt_for_device_dimensions(self, address, name):
        """Shows a dialog to get width/height before connecting."""
        dialog = ttk.Toplevel(self)
        dialog.title("Set Device Dimensions")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Please set dimensions for {name}:", padding=(10,10)).pack()

        form_frame = ttk.Frame(dialog, padding=10)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="Width:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        width_entry = ttk.Entry(form_frame)
        width_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        width_entry.insert(0, "96")

        ttk.Label(form_frame, text="Height:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        height_entry = ttk.Entry(form_frame)
        height_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        height_entry.insert(0, "32")

        def on_confirm():
            try:
                width = int(width_entry.get())
                height = int(height_entry.get())
                self.device_configs[address] = {
                    'buffer': 1, 'auto_resize': True, 'width': width, 'height': height, 
                    'anchor': 0x33, 'duplicate_horizontally': False,
                    'brightness': 100, 'flip_display': False, 'clock_style': 7
                }
                dialog.destroy()
                self.connect_to_device(address)
            except ValueError:
                messagebox.showerror("Invalid Input", "Width and Height must be numbers.", parent=dialog)

        ttk.Button(dialog, text="Confirm & Connect", command=on_confirm, bootstyle="success").pack(pady=10)

    def connect_to_device(self, address):
        """Starts the main BLE communication thread for the selected device."""
        # Ensure there's a default config for this new device
        if address not in self.device_configs:
            self.device_configs[address] = {
                'buffer': 1, 'auto_resize': True, 'width': 96, 'height': 32, 'anchor': 0x33, 'duplicate_horizontally': False,
                'brightness': 100, 'flip_display': False, 'clock_style': 7
            }

        # Each device gets its own command queue for targeted commands.
        device_command_queue = queue.Queue()
        ble_thread = BLEThread(address, device_command_queue, self.status_queue)
        self.ble_threads[address] = ble_thread
        ble_thread.start()

    def disconnect_from_device(self, address):
        """Stops the BLE thread for a specific device."""
        if address in self.ble_threads and self.ble_threads[address].is_alive():
            self.ble_threads[address].stop()
            # The thread will emit a DISCONNECTED status on its own.
            print(f"Requested disconnect from {address}")

    def disconnect_all_devices(self):
        for address in list(self.ble_threads.keys()):
            self.disconnect_from_device(address)

    def populate_device_tree(self, devices):
        """Adds newly discovered devices to the Treeview without clearing it."""
        # Filter for devices that are likely iPixel displays and not already in the tree
        new_devices = [d for d in devices if d.name and ("iPixel" in d.name or "LED" in d.name) and not self.device_tree.exists(d.address)]
        
        for device in new_devices:
            # Check if it's already connected
            is_connected = device.address in self.ble_threads and self.ble_threads[device.address].is_alive()
            tag = 'checked' if is_connected else 'unchecked'
            status = "Connected" if is_connected else "Disconnected"
            self.device_tree.insert("", "end", iid=device.address, values=(device.name, device.address, status), tags=(tag,))

    def on_device_tree_click(self, event):
        """Handle clicks on the device tree to toggle connection or select for options."""
        region = self.device_tree.identify("region", event.x, event.y)
        if region == "heading":
            return # Ignore clicks on the header

        item_id = self.device_tree.identify_row(event.y)
        if not item_id:
            return

        # Update selection for options form
        self.selected_device_address = item_id
        self.device_tree.selection_set(item_id) # Visually select the row
        self.update_options_form(item_id)

        # Check if the click was on the checkbox area (the image tag)
        # This logic is now simpler: clicking toggles connection state.
        if region == "tree": # Clicks on the checkbox column
            current_tags = self.device_tree.item(item_id, "tags")
            if 'checked' in current_tags:
                self.disconnect_from_device(item_id)
            elif 'unchecked' in current_tags:
                # If we don't have a config, prompt for one first.
                if item_id not in self.device_configs or 'width' not in self.device_configs[item_id]:
                    device_name = self.device_tree.item(item_id, "values")[0]
                    self.prompt_for_device_dimensions(item_id, device_name)
                else:
                    # If config exists (from a saved session), connect directly.
                    self.connect_to_device(item_id)


    def update_options_form(self, address):
        """Update the options form with data for the given device address."""
        if address and address in self.device_configs:
            config = self.device_configs[address]
            state = tk.NORMAL
            self.options_frame.config(text=f"Device Options for {address}")

            self.buffer_entry.config(state=state)
            self.buffer_entry.delete(0, tk.END)
            self.buffer_entry.insert(0, str(config.get('buffer', 1)))

            self.auto_resize_var.set(config.get('auto_resize', False))
            self.resize_check.config(state=state)

            self.width_entry.config(state=state)
            self.width_entry.delete(0, tk.END)
            self.width_entry.insert(0, str(config.get('width', 96)))

            self.height_entry.config(state=state)
            self.height_entry.delete(0, tk.END)
            self.height_entry.insert(0, str(config.get('height', 32)))

            self.anchor_entry.config(state=state)
            self.anchor_entry.delete(0, tk.END)
            self.anchor_entry.insert(0, hex(config.get('anchor', 0x33)))
            
            self.duplicate_h_var.set(config.get('duplicate_horizontally', False))
            self.duplicate_check.config(state=state)

            self.brightness_var.set(config.get('brightness', 100))
            self.brightness_slider.config(state=state)

            self.flip_display_var.set(config.get('flip_display', False))
            self.flip_check.config(state=state)

            self.clock_style_var.set(str(config.get('clock_style', 7)))
            self.clock_style_combo.config(state=state)

            self.options_frame.winfo_children()[-1].config(state=state) # Enable save button
        else:
            state = tk.DISABLED
            self.options_frame.config(text="Device Options (Select a device)")
            # Disable all widgets in the options frame except the save button
            for widget in self.options_frame.winfo_children()[:-1]:
                if isinstance(widget, (ttk.Entry, ttk.Checkbutton, ttk.Scale)):
                    widget.config(state=state) # This will disable Combobox too
            self.options_frame.winfo_children()[-1].config(state=state) # Disable save button

    def on_brightness_release(self, event=None):
        """Called when the brightness slider is released."""
        if not self.selected_device_address or self.selected_device_address not in self.ble_threads:
            return
        
        brightness_val = self.brightness_var.get()
        params = argparse.Namespace(brightness=brightness_val)
        self.queue_command_for_device(self.selected_device_address, params, set_brightness.make, "Set Brightness")
        self.resend_current_mv_action()

    def on_flip_change(self):
        """Called when the flip display checkbox is changed."""
        if not self.selected_device_address or self.selected_device_address not in self.ble_threads:
            return
        
        is_flipped = self.flip_display_var.get()
        params = argparse.Namespace(upside_down=is_flipped)
        self.queue_command_for_device(self.selected_device_address, params, set_upside_down.make, "Set Orientation")
        self.resend_current_mv_action()

    def save_device_options(self):
        """Save the currently displayed options for the selected device."""
        if not self.selected_device_address:
            return
        try:
            config = {
                'buffer': int(self.buffer_entry.get()),
                'auto_resize': self.auto_resize_var.get(),
                'width': int(self.width_entry.get()),
                'height': int(self.height_entry.get()),
                'anchor': int(self.anchor_entry.get(), 0),
                'duplicate_horizontally': self.duplicate_h_var.get(),
                'brightness': self.brightness_var.get(),
                'flip_display': self.flip_display_var.get(),
                'clock_style': int(self.clock_style_var.get())
            }
            self.device_configs[self.selected_device_address] = config
            self.save_config()
            self.status_label.config(text=f"Status: Saved options for {self.selected_device_address}")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Could not save options: {e}")

    def load_config(self):
        """Loads the last device address from the config file."""
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
                self.device_configs = config_data.get('device_configs', {})
                # Load Spotify config if it exists
                spotify_config = config_data.get('spotify_config', {})
                self.spotify_client_id = spotify_config.get('client_id', '')
                self.spotify_client_secret = spotify_config.get('client_secret', '')
                print(f"Loaded device configs for: {list(self.device_configs.keys())}")
        except (FileNotFoundError, json.JSONDecodeError):
            print("No config file found or it's invalid. Will scan for devices.")
            self.device_configs = {}

    def save_config(self):
        """Saves the current device address to the config file."""
        try:
            with open(self.config_file, 'w') as f:
                # Prepare the full config data object
                config_data = {
                    'device_configs': self.device_configs,
                    'spotify_config': {
                        'client_id': getattr(self, 'spotify_client_id', ''),
                        'client_secret': getattr(self, 'spotify_client_secret', '')
                    }
                }
                json.dump(config_data, f, indent=4)
                print(f"Saved config file: {self.config_file}")
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def toggle_spotify(self):
        if self.is_spotify_enabled.get():
            # Check for credentials
            if not hasattr(self, 'spotify_client_id') or not self.spotify_client_id:
                self.prompt_for_spotify_credentials()
            else:
                self.start_spotify_thread()
        else:
            if self.spotify_thread and self.spotify_thread.is_alive():
                self.spotify_thread.stop()
                self.spotify_status_var.set("Disabled")
                self.spotify_status_label.config(bootstyle="secondary")
                print("Spotify thread stopped.")
            # Check if other integrations are running before reverting to clock
            self._check_and_set_idle_state()

    def start_spotify_thread(self):
        if self.spotify_thread and self.spotify_thread.is_alive():
            self.spotify_thread.stop()

        self.spotify_thread = SpotifyThread(
            self.spotify_action_queue, self.status_queue,
            self.spotify_client_id, self.spotify_client_secret,
            "http://localhost:8888/callback" # Standard redirect URI
        )
        self.spotify_thread.start()
        self.spotify_status_var.set("Connecting...")
        self.spotify_status_label.config(bootstyle="warning")

    def prompt_for_spotify_credentials(self):
        """Creates a dialog to get Spotify credentials from the user."""
        dialog = ttk.Toplevel(self)
        dialog.title("Spotify Credentials")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Enter your Spotify API credentials.", bootstyle="primary").pack(pady=(0, 10))
        instructions_frame = ttk.LabelFrame(main_frame, text="How to get your credentials", padding=10)
        instructions_frame.pack(fill=tk.X, pady=(0, 15))

        def open_spotify_dev_page(event=None):
            webbrowser.open("https://developer.spotify.com/dashboard", new=2)

        link_font = font.nametofont("TkDefaultFont").copy()
        link_font.configure(underline=True)

        step1_text = "1. Go to the Spotify Developer Dashboard."
        how_to_link = ttk.Label(instructions_frame, text=step1_text, bootstyle="info", cursor="hand2", font=link_font)
        how_to_link.pack(anchor="w")
        how_to_link.bind("<Button-1>", open_spotify_dev_page)

        instructions_text_part1 = (
            '2. Click "Create App", give it a name, and agree to the terms.\n'
            '3. Copy the "Client ID" and "Client Secret" into the fields below.\n'
            '4. Click "Edit Settings" on the Spotify page.\n'
            '5. In the "Redirect URIs" field, add this exact URL:'
        )
        ttk.Label(instructions_frame, text=instructions_text_part1, justify=tk.LEFT).pack(anchor="w", pady=(5, 0))

        uri_frame = ttk.Frame(instructions_frame)
        uri_frame.pack(fill=tk.X, padx=15, pady=5)
        redirect_uri = "http://localhost:8888/callback"
        uri_entry = ttk.Entry(uri_frame, bootstyle="readonly")
        uri_entry.insert(0, redirect_uri)
        uri_entry.config(state="readonly")
        uri_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(uri_frame, text="Copy", command=lambda: self.copy_to_clipboard(redirect_uri, dialog)).pack(side=tk.LEFT, padx=(5, 0))

        instructions_text_part2 = '6. Click "Save" on the Spotify page, then "Save & Connect" here.'
        ttk.Label(instructions_frame, text=instructions_text_part2, justify=tk.LEFT).pack(anchor="w", pady=(5, 0))

        # --- Input Fields ---
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X)
        form_frame.columnconfigure(1, weight=1)

        ttk.Label(form_frame, text="Client ID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        client_id_entry = ttk.Entry(form_frame, width=40)
        client_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Client Secret:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        client_secret_entry = ttk.Entry(form_frame, width=40, show="*")
        client_secret_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        def on_save():
            client_id = client_id_entry.get().strip()
            client_secret = client_secret_entry.get().strip()

            if not client_id or not client_secret:
                messagebox.showerror("Missing Info", "Both Client ID and Client Secret are required.", parent=dialog)
                return

            self.spotify_client_id = client_id
            self.spotify_client_secret = client_secret
            self.save_config()
            dialog.destroy()
            self.start_spotify_thread()

        ttk.Button(main_frame, text="Save & Connect", command=on_save, bootstyle="success").pack(pady=10)

    def copy_to_clipboard(self, text, parent_window):
        """Copies the given text to the clipboard."""
        parent_window.clipboard_clear()
        parent_window.clipboard_append(text)
        self.status_label.config(text="Status: Redirect URI copied to clipboard.")
        self.after(2000, lambda: self.status_label.config(text="Status: Idle"))

    def _check_and_set_idle_state(self):
        """Checks if any integrations are active and sets clock if not."""
        if not self.is_mv_enabled.get() and not self.is_spotify_enabled.get():
            print("No integrations active. Reverting to clock display.")
            self.send_clock_command_to_all()

    def toggle_multiviewer(self):
        if self.is_mv_enabled.get():
            if not self.mv_thread or not self.mv_thread.is_alive():
                self.mv_thread = MultiviewerThread(self.mv_action_queue, self.status_queue)
                self.mv_thread.start()
                print("Multiviewer thread started.")
                self.send_gif_from_path("gifs/mv.gif")
        else:
            if self.mv_thread and self.mv_thread.is_alive():
                self.mv_thread.stop()
                print("Multiviewer thread stopped.")
            
            # Manually update status when disabling
            self.mv_status_var.set("Disabled")
            self.mv_status_label.config(bootstyle="secondary")

            # The thread will now send MV_STATUS_DISABLED to the queue on exit,
            # which will be handled by process_status_queue for a reliable update.
            # Check if other integrations are running before reverting to clock
            self._check_and_set_idle_state()


    def process_status_queue(self):
        """Check for new status messages and update the GUI."""
        try:
            message = self.status_queue.get_nowait()
            # Message now contains address: "BLE_CONNECTED_SUCCESS:ADDR"

            if message.startswith("BLE_CONNECTED_SUCCESS"):
                parts = message.split(':', 1)
                address_and_name = parts[1].rsplit(':', 1)
                address, name = address_and_name[0], address_and_name[1]
                if not self.device_tree.exists(address):
                    # If the device isn't in the tree, add it now.
                    self.device_tree.insert("", "end", iid=address, values=(name, address, "Connected"), tags=('checked',))
                else:
                    # Otherwise, just update its status.
                    self.device_tree.item(address, values=(name, address, "Connected"), tags=('checked',))
                self.status_label.config(text=f"Status: Connected to {name} ({address}).")

                # Run startup actions on first successful connection
                if not self.startup_actions_done and self.is_mv_enabled.get() == False:
                    self.is_mv_enabled.set(True)
                    self.toggle_multiviewer()
                    self.startup_actions_done = True
                
                # Erase the device's memory before sending the initial GIF
                erase_params = argparse.Namespace(erase_all=True, buffer=[])
                self.queue_command_for_device(address, erase_params, erase_data.make, f"Erase on connect for {address}")

                # Send the startup GIF
                self.send_gif_from_path("gifs/mv.gif")

                self.save_config()
            elif message.startswith("BLE_DISCONNECTED"):
                address = message.split(':')[-1]
                if self.device_tree.exists(address):
                    self.device_tree.item(address, values=(self.device_tree.item(address, "values")[0], address, "Disconnected"), tags=('unchecked',))
                if self.selected_device_address == address:
                    self.update_options_form(None) # Disable form if selected device disconnects
                self.status_label.config(text="Status: Device disconnected.")
            elif message.startswith("BLE_CONNECT_FAIL"):
                parts = message.split(':', 1)
                address_and_error = parts[1].rsplit(':', 1)
                address, error_msg = address_and_error[0], address_and_error[1]
                if self.device_tree.exists(address):
                    self.device_tree.item(address, values=(self.device_tree.item(address, "values")[0], address, "Failed"), tags=('unchecked',))
                self.status_label.config(text=f"Status: Failed to connect to {address}. Retrying or scan needed.")
                if address in self.device_configs:
                    del self.device_configs[address] # Remove bad config
                    self.save_config()
            elif message == "MV_STATUS_CONNECTED":
                self.mv_status_var.set("Connected")
                self.mv_status_label.config(bootstyle="success")
            elif message == "MV_STATUS_RETRYING":
                self.mv_status_var.set("Retrying...")
                self.mv_status_label.config(bootstyle="warning")
            elif message == "MV_STATUS_DISABLED":
                self.mv_status_var.set("Disabled")
                self.mv_status_label.config(bootstyle="secondary")
            elif message.startswith("SPOTIFY_STATUS_"):
                status = message.replace("SPOTIFY_STATUS_", "")
                if status == "CONNECTED":
                    self.spotify_status_var.set("Connected")
                    self.spotify_status_label.config(bootstyle="success")
                    # This is a spotify-specific status, so we don't want it in the main label.
                    # We can just return here.
                else: # ERROR
                    error_msg = status.split(":", 1)[-1]
                    self.spotify_status_var.set(f"Error: {error_msg}")
                    self.spotify_status_label.config(bootstyle="danger")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_status_queue)

    def process_mv_action_queue(self):
        """Check for actions from the Multiviewer thread and send GIFs."""
        try:
            action = self.mv_action_queue.get_nowait()
            self.gif_map['current_action'] = action # Store the latest action
            self.send_mv_action(action)
        except queue.Empty:
            pass
        finally:
            self.after(50, self.process_mv_action_queue)
    
    def process_spotify_action_queue(self):
        """Check for actions from the Spotify thread (new album art)."""
        if self.is_sending_art: # Don't process new art if the last one is still sending
            self.after(100, self.process_spotify_action_queue)
            return
        try:
            image_data = self.spotify_action_queue.get_nowait()
            print(f"[Spotify] Action queue received art data. Setting lock.")
            self.is_sending_art = True # Set lock
            
            # Use a temporary file in memory to send the image data
            # The file object needs to be kept alive until the command is processed.
            # Since start_write is synchronous, this is safe.
            with io.BytesIO(image_data) as temp_file:
                temp_file.name = "temp_album_art.gif" # The library uses the name attribute to detect file type
                self.start_write(image_file_obj=temp_file)

        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_spotify_action_queue)

    def resend_current_mv_action(self):
        """Resends the last known Multiviewer action."""
        if self.gif_map['current_action']:
            self.after(100, self.send_mv_action, self.gif_map['current_action'])

    def send_mv_action(self, action):
        """Sends the GIF corresponding to a Multiviewer action."""
        gif_path = self.gif_map.get(action)
        if gif_path and os.path.exists(gif_path):
            print(f"MV Action: '{action}'. Sending GIF: {gif_path}")
            self.send_gif_from_path(gif_path)

    def send_debug_gif(self, gif_path):
        print(f"Debug: Sending GIF: {gif_path}")
        self.send_gif_from_path(gif_path)

    def send_gif_from_path(self, gif_path):
        self.file_listbox.delete(0, tk.END)
        self.file_listbox.insert(tk.END, gif_path)
        self.start_write()

    def start_erase(self):
        if not self.ble_threads:
            messagebox.showerror("Error", "Device is not connected.")
            return

        if not messagebox.askyesno("Confirm Erase", "Are you sure you want to erase ALL buffers on the device? This cannot be undone."):
            return

        params = argparse.Namespace(erase_all=True, buffer=[])
        make_function = erase_data.make

        # This command is the same for all devices, so we can use the broadcast queue
        self.queue_command_for_all(params, make_function, "Erase")

    def send_clock_command_to_all(self):
        """Sends the clock command to all connected devices, using their individual style settings."""
        if not self.ble_threads:
            return

        for address, thread in self.ble_threads.items():
            config = self.device_configs.get(address, {})
            style = config.get('clock_style', 7)  # Default to 7 if not set
            self.send_clock_command_to_device(address, style)

    def send_clock_command_to_device(self, address, style=1):
        """Sends the command to display the current time on the device."""
        if address not in self.ble_threads:
            return

        now = datetime.now()
        lang = 0 # 0 for International (DD/MM), 1 for China (MM/DD)
        params = argparse.Namespace(
            clock_mode_style=style,
            clock_mode_date=now.strftime("%Y-%m-%d"),
            clock_mode_time=now.strftime("%H:%M:%S"),
            clock_mode_lang=lang,
            clock_mode_show_date=True, # Hardcoded for simplicity
            clock_mode_show_24h=True,  # Hardcoded for simplicity
        )
        self.queue_command_for_device(address, params, set_clock_mode.make, f"Clock Style {style}")

    def start_write(self, image_file_obj=None):
        if not self.ble_threads:
            messagebox.showerror("Error", "Device is not connected.")
            return

        image_files = self.file_listbox.get(0, tk.END)
        if not image_files:
            messagebox.showerror("Error", "At least one image file must be selected.")
            # Allow proceeding if an in-memory object is provided
            if not image_file_obj:
                return
        
        # If an in-memory file object is passed, use it. Otherwise, use file paths.
        image_source = [image_file_obj] if image_file_obj else image_files

        # Cancel any previously scheduled GIF-to-static-frame timer.
        # This ensures a new write action overrides any pending "stop" commands for all devices.
        for timer_id in self.gif_stop_timers.values():
            self.after_cancel(timer_id)
        self.gif_stop_timers.clear()

        # Iterate over each connected device and queue a command for it.
        for address, thread in self.ble_threads.items():
            config = self.device_configs.get(address)
            if not config:
                print(f"Warning: No config found for connected device {address}. Skipping command.")
                continue

            try:
                # Common parameters
                common_params = {
                    'image_file': image_source,
                    'start_buffer': config['buffer'],
                    'auto_resize': config['auto_resize'],
                    'device_width': config['width'],
                    'device_height': config['height'],
                    'anchor': config['anchor'],
                    'duplicate_horizontally': config.get('duplicate_horizontally', False)
                    # Brightness and flip are sent as separate commands, not part of the image write
                }

                # Automatically detect if we should treat this as a GIF/animation
                is_gif = any(isinstance(f, str) and f.lower().endswith('.gif') for f in image_source)
                is_spotify_art = image_file_obj is not None
                
                if is_spotify_art: # Handle Spotify Album Art specifically
                    # Spotify art is a single GIF, never joined.
                    params = argparse.Namespace(**common_params, join_image_files=False)
                    params = argparse.Namespace(**common_params, join_image_files=False, make_from_image=0)
                    make_function = write_data_gif.make
                elif is_gif or self.make_from_image_var.get(): # Handle GIFs or creating a GIF from images
                    make_from_image = self.make_from_image_var.get()
                    duration = int(self.duration_entry.get()) if make_from_image else 0
                    params = argparse.Namespace(**common_params, make_from_image=duration)
                    make_function = write_data_gif.make
                else: # Handle standard PNGs/JPGs from the debug window
                    params = argparse.Namespace(**common_params, join_image_files=self.join_files_var.get())
                    make_function = write_data_png.make

                # Generate and queue the command for this specific device
                if is_gif:
                    # Only schedule the "stop" timer for specific color GIFs
                    gif_path = image_files[0]
                    gif_filename = os.path.basename(gif_path).lower()
                    stoppable_gif_names = ['green.gif', 'yellow.gif', 'red.gif', 'blue.gif', 'white.gif']
                    if gif_filename in stoppable_gif_names:
                        # Schedule the first frame to be sent after 3 seconds
                        self.gif_stop_timers[address] = self.after(3000, lambda a=address, p=gif_path: self.send_first_frame_of_gif(a, p))
                self.queue_command_for_device(address, params, make_function, f"Write for {address}")

            except ValueError as e:
                messagebox.showerror("Invalid Input", f"Please check your inputs for device {address}. Error: {e}")
                return # Stop on first error
        
        # If we were sending album art, release the lock now that commands are queued
        if self.is_sending_art:
            print("[Spotify] Art command queued. Releasing lock.")
            self.is_sending_art = False

    def queue_command_for_device(self, address, params, make_function, action_name):
        """Generates a payload and queues it for a specific device."""
        if address not in self.ble_threads:
            print(f"Warning: Attempted to queue command for disconnected device {address}")
            return

        ble_thread = self.ble_threads[address]
        try:
            self.status_label.config(text=f"Status: Generating payload for {action_name}...")
            payloads = make_function(params)
            ble_thread.command_queue.put(payloads) # Put on the specific device's queue
            self.status_label.config(text=f"Status: Queued '{action_name}' command.")
        except Exception as e:
            self.status_label.config(text=f"Status: Error - {e}")
            messagebox.showerror("Error", f"An error occurred: {e}")

    def queue_command_for_all(self, params, make_function, action_name):
        """Generates one payload and queues it for all connected devices."""
        for address in self.ble_threads:
            self.queue_command_for_device(address, params, make_function, f"{action_name} on {address}")

    def send_first_frame_of_gif(self, address, gif_path):
        """Extracts the first frame of a GIF and sends it as a static image."""
        if address not in self.ble_threads:
            print(f"Cannot send first frame: device {address} is no longer connected.")
            return

        print(f"Timer expired. Sending first frame of {gif_path} to {address}.")

        try:
            with Image.open(gif_path) as img:
                # Ensure we are on the first frame
                img.seek(0)
                # Convert to RGBA to handle transparency properly
                first_frame = img.convert("RGBA")

            # Get the config for the target device to perform resizing
            config = self.device_configs.get(address, {})
            device_width = config.get('width', 96)
            device_height = config.get('height', 32)

            # Resize using NEAREST for a crisp, pixel-perfect look
            resampling_filter = Image.Resampling.NEAREST if hasattr(Image, 'Resampling') else Image.NEAREST
            resized_frame = first_frame.resize((device_width, device_height), resample=resampling_filter)
            
            # Convert to RGB for saving as PNG
            final_frame = resized_frame.convert("RGB")

            # Use a temporary file to hold the frame
            temp_png_path = "temp_first_frame.png"
            final_frame.save(temp_png_path, "PNG")

            # Get the config for the target device
            config = self.device_configs.get(address, {})
            params = argparse.Namespace(
                image_file=[temp_png_path],
                start_buffer=config.get('buffer', 1),
                auto_resize=config.get('auto_resize', False),
                device_width=device_width,
                device_height=device_height,
                anchor=config.get('anchor', 0x33),
                join_image_files=False
            )
            self.queue_command_for_device(address, params, write_data_png.make, f"First Frame to {address}")

        except Exception as e:
            print(f"Error sending first frame of GIF: {e}")

if __name__ == "__main__":
    # Check if bleak is installed
    try:
        import bleak
    except ImportError:
        messagebox.showerror("Dependency Error", "The 'bleak' library is not installed.\nPlease run 'pip install bleak'.")
        sys.exit(1)

    app = App()

    def on_closing():
        app.send_clock_command_to_all()
        # Give BLE threads a moment to send the clock command
        time.sleep(0.2)

        threads_to_join = []
        if app.mv_thread and app.mv_thread.is_alive():
            app.mv_thread.stop()
            threads_to_join.append(app.mv_thread)
        if app.spotify_thread and app.spotify_thread.is_alive():
            app.spotify_thread.stop()
            threads_to_join.append(app.spotify_thread)
        for thread in app.ble_threads.values():
            if thread.is_alive():
                thread.stop()
                threads_to_join.append(thread)
        
        # Wait for threads to finish, with a timeout
        for thread in threads_to_join:
            thread.join(timeout=1.0)
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()
