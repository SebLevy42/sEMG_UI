import tkinter as tk
from tkinter import ttk, messagebox
#import UnicornPy
import numpy as np
import os
import datetime
from threading import Thread
import time
import pylsl

class SEMGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("sEMG Data Collection")

        self.create_widgets()

        self.device = None
        self.participant_label = ""
        self.expression = ""
        self.trial_number = 1
        self.acquisition_duration = 5  # seconds per phase
        self.data_folder = "Data"
        self.current_trial_label = ""
        self.is_collecting = False

    def create_widgets(self):
        # Participant Label
        tk.Label(self.root, text="Participant Label:").grid(row=0, column=0, padx=10, pady=10)
        self.participant_entry = tk.Entry(self.root)
        self.participant_entry.grid(row=0, column=1, padx=10, pady=10)

        # Connect to Unicorn Button
        self.connect_button = tk.Button(self.root, text="Connect to Unicorn", command=self.connect_to_unicorn)
        self.connect_button.grid(row=1, column=0, columnspan=2, pady=10)

        # Expression Selection
        tk.Label(self.root, text="Select Expression:").grid(row=2, column=0, padx=10, pady=10)
        self.expression_var = tk.StringVar(value="Smile")
        tk.Radiobutton(self.root, text="Smile", variable=self.expression_var, value="Smile").grid(row=2, column=1, sticky=tk.W)
        tk.Radiobutton(self.root, text="Frown", variable=self.expression_var, value="Frown").grid(row=2, column=1, sticky=tk.E)

        # Start Data Collection Button
        self.start_button = tk.Button(self.root, text="Begin Data Collection", command=self.start_data_collection)
        self.start_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Stop Data Collection Button
        self.stop_button = tk.Button(self.root, text="Stop Data Collection", command=self.stop_data_collection, state=tk.DISABLED)
        self.stop_button.grid(row=4, column=0, columnspan=2, pady=10)

        # Delete Last Trial Button
        self.delete_button = tk.Button(self.root, text="Delete Last Trial", command=self.delete_last_trial, state=tk.DISABLED)
        self.delete_button.grid(row=5, column=0, columnspan=2, pady=10)

        # Status Message
        self.status_label = tk.Label(self.root, text="Status: Not Connected")
        self.status_label.grid(row=6, column=0, columnspan=2, pady=10)

        # Countdown Label
        self.countdown_label = tk.Label(self.root, text="", font=("Helvetica", 24, "bold"))
        self.countdown_label.grid(row=7, column=0, columnspan=2, pady=10)

    def connect_to_unicorn(self):
        # Connect to the Unicorn Hybrid Black device
        try:
            deviceList = UnicornPy.GetAvailableDevices(True)
            if len(deviceList) <= 0 or deviceList is None:
                messagebox.showerror("Error", "No device available. Please pair with a Unicorn first.")
                return

            self.device = UnicornPy.Unicorn(deviceList[0])
            self.status_label.config(text=f"Connected to {deviceList[0]}")
            messagebox.showinfo("Success", f"Connected to {deviceList[0]}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")

    def start_data_collection(self):
        self.participant_label = self.participant_entry.get().strip()
        self.expression = self.expression_var.get()
        if not self.participant_label:
            messagebox.showerror("Error", "Please enter a participant label.")
            return
        if not self.device:
            messagebox.showerror("Error", "Please connect to a Unicorn device first.")
            return

        self.trial_number = self.get_next_trial_number()
        self.is_collecting = True

        self.status_label.config(text="Status: Collecting Data")
        self.start_button.config(state=tk.DISABLED)
        self.connect_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)

        # Start data collection in a separate thread
        collection_thread = Thread(target=self.collect_data)
        collection_thread.start()

    def get_next_trial_number(self):
        participant_folder = os.path.join(self.data_folder, self.participant_label)
        if not os.path.exists(participant_folder):
            return 1
        existing_files = os.listdir(participant_folder)
        trial_numbers = [int(f.split('_')[-1].split('.')[0]) for f in existing_files if f.startswith(f"{self.participant_label}_{self.expression}_")]
        if not trial_numbers:
            return 1
        return max(trial_numbers) + 1

    def collect_data(self):
        participant_folder = os.path.join(self.data_folder, self.participant_label)
        os.makedirs(participant_folder, exist_ok=True)

        try:
            # Create LSL streams
            info_unicorn = pylsl.StreamInfo('Unicorn', 'EEG', self.device.GetNumberOfAcquiredChannels(), UnicornPy.SamplingRate, 'float32', 'unicorn12345')
            info_event = pylsl.StreamInfo('Event', 'Markers', 2, 0, 'int32', 'event12345')
            outlet_unicorn = pylsl.StreamOutlet(info_unicorn)
            outlet_event = pylsl.StreamOutlet(info_event)

            # Collect data for a single trial
            self.current_trial_label = f"{self.participant_label}_{self.expression}_{self.trial_number}"
            data_file = os.path.join(participant_folder, f"{self.current_trial_label}.csv")
            self.device.StartAcquisition(False)

            phases = [
                ("Neutral", [0, 0]),
                ("100%", [3, 0] if self.expression == "Frown" else [0, 3]),
                ("Neutral", [0, 0]),
                ("60%", [2, 0] if self.expression == "Frown" else [0, 2]),
                ("Neutral", [0, 0]),
                ("30%", [1, 0] if self.expression == "Frown" else [0, 1]),
                ("Neutral", [0, 0])
            ]

            # Start a thread to write data to a file
            data_thread = Thread(target=self.write_data_to_file, args=(data_file, outlet_unicorn, outlet_event, phases))
            data_thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Data collection failed: {e}")

    def write_data_to_file(self, data_file, outlet_unicorn, outlet_event, phases):
        try:
            with open(data_file, "w") as file:
                numberOfAcquiredChannels = self.device.GetNumberOfAcquiredChannels()
                receiveBufferBufferLength = 1 * numberOfAcquiredChannels * 4
                receiveBuffer = bytearray(receiveBufferBufferLength)

                for phase, event_code in phases:
                    if not self.is_collecting:
                        break
                    self.status_label.config(text=f"Status: {phase}")
                    self.root.update()
                    self.countdown(5)

                    start_time = time.time()
                    while time.time() - start_time < self.acquisition_duration:
                        self.device.GetData(1, receiveBuffer, receiveBufferBufferLength)
                        data = np.frombuffer(receiveBuffer, dtype=np.float32, count=numberOfAcquiredChannels)
                        np.savetxt(file, [data], delimiter=',', fmt='%.3f', newline='\n')

                        # Push data to LSL streams
                        outlet_unicorn.push_sample(data.tolist())
                        outlet_event.push_sample(event_code)

                self.device.StopAcquisition()
                self.status_label.config(text="Status: Data Collection Completed")
                self.start_button.config(state=tk.NORMAL)
                self.connect_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
                self.delete_button.config(state=tk.DISABLED)
                self.is_collecting = False

        except Exception as e:
            messagebox.showerror("Error", f"Error during data streaming: {e}")

    def countdown(self, duration):
        try:
            for i in range(duration, 0, -1):
                self.countdown_label.config(text=str(i))
                self.root.update()
                time.sleep(1)
            self.countdown_label.config(text="")
        except Exception as e:
            messagebox.showerror("Error", f"Error during countdown: {e}")

    def stop_data_collection(self):
        self.is_collecting = False

    def delete_last_trial(self):
        if not self.current_trial_label:
            messagebox.showerror("Error", "No trial to delete.")
            return
        participant_folder = os.path.join(self.data_folder, self.participant_label)
        last_trial_file = os.path.join(participant_folder, f"{self.current_trial_label}.csv")
        if os.path.exists(last_trial_file):
            os.remove(last_trial_file)
            self.status_label.config(text=f"Deleted last trial: {self.current_trial_label}")
        else:
            messagebox.showerror("Error", "Last trial file not found.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SEMGApp(root)
    root.mainloop()
