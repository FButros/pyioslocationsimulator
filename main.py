import socket
import subprocess
import sys
import logging
import time
import json
import re
import threading
import tkinter as tk
from tkinter import messagebox, font, ttk, filedialog

logging.basicConfig(level=logging.INFO)
longitude_entry = None
latitude_entry = None
device_connected = False

def mount_developer_disk_image():
    try:
        result = subprocess.run(["pymobiledevice3", "mounter", "auto-mount"],
                                capture_output=True, text=True, check=True)
        if result.stderr:
            logging.error(f"Error in mounting Developer Disk Image: {result.stderr}")
            return False
        else:
            logging.info("Developer Disk Image successfully mounted.")
            return True
    except subprocess.CalledProcessError as e:
        logging.error(f"CalledProcessError: {e}")
        return False
    except OSError as e:
        logging.error(f"OS error: {e}")
        return False

def save_as():
    file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
    if file_path:
        with open(file_path, 'w') as file:
            file.write(f"{longitude_entry.get()},{latitude_entry.get()}")
        messagebox.showinfo("Save As", "Data saved successfully")

def load():
    file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
    if file_path:
        with open(file_path, 'r') as file:
            data = file.read().strip()
            try:
                long_str, lat_str = data.split(',')
                longitude = float(long_str.strip())
                latitude = float(lat_str.strip())

                if not validate_coordinates(longitude, latitude):
                    logging.error("Invalid longitude or latitude range after loading from file.")
                    show_message("Invalid longitude or latitude range. Please check the file.", "error")
                    return

                longitude_entry.delete(0, tk.END)
                longitude_entry.insert(0, str(longitude))
                latitude_entry.delete(0, tk.END)
                latitude_entry.insert(0, str(latitude))

                messagebox.showinfo("Load", "Data loaded successfully")
            except ValueError as e:
                logging.error(f"Error parsing longitude and latitude from file: {e}")
                show_message("Error parsing longitude and latitude. Please check the file format.", "error")


def show_message(message, message_type="info"):
    if message_type == "info":
        messagebox.showinfo("Information", message)
    elif message_type == "error":
        messagebox.showerror("Error", message)
    elif message_type == "warning":
        messagebox.showwarning("Warning", message)


def monitor_device_connection():
    global device_connected
    while True:
        new_device_connected = check_for_connected_devices()
        if new_device_connected != device_connected:
            device_connected = new_device_connected
            if device_connected:
                logging.info("Device connected")
            else:
                logging.info("No device connected")
        time.sleep(5)  # Check every 5 seconds


def find_free_port():
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                return s.getsockname()[1]
        except OSError as e:
            if attempt == max_attempts - 1:
                logging.error(f"Failed to find a free port after {max_attempts} attempts.")
                sys.exit(1)
            logging.warning(f"Error finding a free port (Attempt {attempt + 1}/{max_attempts}): {e}")
            time.sleep(1)


def get_host_ip():
    dns_server = "1.1.1.1"  # Use Cloudflare's DNS server
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((dns_server, 53))  # Use DNS server port 53
                return s.getsockname()[0]
        except OSError as e:
            if attempt == max_attempts - 1:
                logging.error(f"Failed to retrieve host IP after {max_attempts} attempts.")
                sys.exit(1)
            logging.warning(f"Error finding host IP (Attempt {attempt + 1}/{max_attempts}): {e}")
            time.sleep(1)


def validate_coordinates(longitude, latitude):
    logging.info(f"Validating coordinates: Longitude={longitude}, Latitude={latitude}")
    if -180 <= latitude <= 180 and -90 <= longitude <= 90:
        return True
    else:
        logging.error("Invalid longitude or latitude range.")
        return False



def run_command(command):
    try:
        subprocess.run(command, check=True, timeout=10)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running command: {e}")
        sys.exit(1)
    except subprocess.TimeoutExpired as e:
        logging.error(f"Command execution timed out: {e}")
        sys.exit(1)
    except OSError as e:
        logging.error(f"Error executing command: {e}")
        sys.exit(1)


def strip_ansi_codes(text):
    # Regular expression to match ANSI escape codes
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

def get_ios_version():
    try:
        result = subprocess.run(["pymobiledevice3", "usbmux", "list"],
                                capture_output=True, text=True, check=True)
        clean_output = strip_ansi_codes(result.stdout)
        if not clean_output.strip():
            logging.error("No output returned from 'pymobiledevice3 usbmux list'")
            return None

        logging.info(f"Cleaned command output: {clean_output}")
        devices = json.loads(clean_output)
        if devices:
            return devices[0]["ProductVersion"]
        else:
            logging.error("No connected iOS devices found.")
            return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving iOS version: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON output: {e}. Output: '{clean_output}'")
        return None



def set_location():
    global longitude_entry, latitude_entry

    try:
        longitude = float(longitude_entry.get())
        latitude = float(latitude_entry.get())

        if not validate_coordinates(longitude, latitude):
            logging.error("Invalid longitude or latitude range...")
            show_message(
                "Invalid longitude or latitude range. Please enter values within -180 to 180 for longitude and -90 to 90 for latitude.",
                "error")
            return

        ios_version = get_ios_version()
        if ios_version is None:
            show_message("Failed to retrieve iOS version. Please ensure a device is connected.", "error")
            return
        ios_major_version = int(ios_version.split('.')[0])  # Get major version

        if ios_major_version >= 17:
            command = [
                "pymobiledevice3", "developer", "dvt", "simulate-location", "set",
                "--rsd", host, str(port), "--", str(longitude), str(latitude)
            ]
        else:
            if not mount_developer_disk_image():
                messagebox.showerror("Error",
                                     "Failed to mount the Developer Disk Image. Please check the logs for more details.")
                return

        run_command(command)
        show_message(f"Location set to longitude: {longitude}, latitude: {latitude}")

    except ValueError:
        show_message("Invalid input for longitude or latitude. Please enter numeric values.", "error")



def check_for_connected_devices():
    try:
        result = subprocess.run(["pymobiledevice3", "usbmux", "list"],
                                capture_output=True,
                                text=True,
                                check=True,
                                timeout=10)
        clean_output = strip_ansi_codes(result.stdout)
        if clean_output.strip():  # Check if there is any output
            devices = json.loads(clean_output)
            return len(devices) > 0
        else:
            logging.info("No output returned from 'pymobiledevice3 usbmux list'")
            return False
    except subprocess.CalledProcessError as e:
        logging.error(f"CalledProcessError: {e}")
        return False
    except subprocess.TimeoutExpired as e:
        logging.error(f"TimeoutExpired: {e}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: {e}. Output: '{result.stdout}'")
        return False


def main():
    global longitude_entry, latitude_entry, device_connected

    # Create a separate thread for monitoring device connectivity
    monitor_thread = threading.Thread(target=monitor_device_connection, daemon=True)
    monitor_thread.start()

    try:
        global host, port
        host = get_host_ip()
        logging.info(f"Detected host IP: {host}")

        port = find_free_port()
        logging.info(f"Using free port: {port}")
    except ValueError:
        logging.error("Invalid longitude or latitude. Please enter numeric values.")
        sys.exit(1)

    # Create a Tkinter window for the GUI
    root = tk.Tk()
    root.title("Location Simulator")
    root.geometry("600x500")
    main_bg_color = 'white'  # Set your desired background color
    root.configure(bg=main_bg_color)

    style = ttk.Style()
    style.theme_use('clam')

    # Font setup for larger text
    modern_font = font.Font(family="Helvetica", size=12)  # Adjust the size as needed

    style.configure("Connected.TLabel", foreground="green")
    style.configure("Disconnected.TLabel", foreground="red")
    # Create a label to display connection status
    connection_status_label = ttk.Label(root, text="", foreground="red", font=modern_font, background=main_bg_color)
    connection_status_label.pack(pady=10)
    connection_status_label = ttk.Label(root, text="", style="Disconnected.TLabel", background=main_bg_color)
    connection_status_label.pack(pady=10)
    # Longitude input
    longitude_label = ttk.Label(root, text="Longitude:", font=modern_font, background=main_bg_color)
    longitude_label.pack()
    longitude_entry = ttk.Entry(root, font=modern_font, background=main_bg_color)
    longitude_entry.pack(pady=5)

    # Latitude input
    latitude_label = ttk.Label(root, text="Latitude:", font=modern_font, background=main_bg_color)
    latitude_label.pack()
    latitude_entry = ttk.Entry(root, font=modern_font)
    latitude_entry.pack(pady=5)

    # Set Location button
    set_location_button = ttk.Button(root, text="Set Location", command=set_location)
    set_location_button.pack(pady=10)


    # Save As button
    save_as_button = ttk.Button(root, text="Save As", command=save_as)
    save_as_button.pack(pady=5)

    # Load button
    load_button = ttk.Button(root, text="Load", command=load)
    load_button.pack(pady=10)

    # Instructions
    instructions = """Instructions:
       - Connect your iOS device.
       - Enter the desired longitude and latitude.
       - Click 'Set Location' to update the device's location.
       - To save your long/lat points click on Save.
       - To load your saved long/lat points click on load
       """
    instructions_label = ttk.Label(root, text=instructions, font=modern_font, justify=tk.LEFT, background=main_bg_color)
    instructions_label.pack(pady=25)

    # Create a label to display connection status with ttk styling

    # Function to update the connection status label
    def update_connection_status_label():
        global device_connected
        if device_connected:
            connection_status_label.config(text="Device connected", style="Connected.TLabel", background=main_bg_color)
        else:
            connection_status_label.config(text="No device connected", style="Disconnected.TLabel", background=main_bg_color)
        root.after(1000, update_connection_status_label)  # Update every 1 second

    update_connection_status_label()  # Start updating the label

    root.mainloop()


if __name__ == "__main__":
    main()
