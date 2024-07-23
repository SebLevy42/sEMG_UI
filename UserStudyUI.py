import tkinter as tk
from tkinter import messagebox
import UnicornPy
import numpy as np
import os
import datetime
import threading
from pylsl import StreamInfo, StreamOutlet
import time

class SEMGStudyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("sEMG Sensing Study")
        
        self.participant_label = tk.StringVar()
        self.expression_choice = tk.StringVar()
        self.is_collecting = False
        self.trial_number = 1
        self.device = None
        self.output_folder = "Data"
        self.data_file = None
        
        self.create_ui()
        self.lsl_streams = self.setup_lsl_streams()
    
    def create_ui(self):
        tk.Label(self.root, text="Participant Label:").grid(row=0, column=0)
        tk.Entry(self.root, textvariable=self.participant_label).grid(row=0, column=1)
        
        tk.Button(self.root, text="Connect to Unicorn", command=self.connect_to_unicorn).grid(row=1, column=0, columnspan=2)
        
        tk.Label(self.root, text="Choose Expression:").grid(row=2, column=0)
        tk.Radiobutton(self.root, text="Smile", variable=self.expression_choice, value="Smile").grid(row=2, column=1)
        tk.Radiobutton(self.root, text="Frown", variable=self.expression_choice, value="Frown").grid(row=2, column=2)
        
        tk.Button(self.root, text="Begin Data Collection", command=self.start_data_collection).grid(row=3, column=0, columnspan=2)
        tk.Button(self.root, text="Stop Data Collection", command=self.stop_data_collection).grid(row=4, column=0, columnspan=2)
        tk.Button(self.root, text="Delete Last Trial", command=self.delete_last_trial).grid(row=5, column=0, columnspan=2)
        
        self.countdown_label = tk.Label(self.root, text="", font=("Helvetica", 16, "bold"))
        self.countdown_label.grid(row=6, column=0, columnspan=3)
    
    def setup_lsl_streams(self):
        # Create LSL stream for raw data and events
        info_data = StreamInfo('UnicornRawData', 'EEG', 8, 250, 'float32', 'unicorn_raw_data')
        outlet_data = StreamOutlet(info_data)
        
        info_event = StreamInfo('UnicornEvent', 'Markers', 1, 0, 'int32', 'unicorn_event')
        outlet_event = StreamOutlet(info_event)
        
        return {'data': outlet_data, 'event': outlet_event}
    
    def connect_to_unicorn(self):
        try:
            device_list = UnicornPy.GetAvailableDevices(True)
            if not device_list:
                raise Exception("No device available. Please pair with a Unicorn first.")
            self.device = UnicornPy.Unicorn(device_list[0])
            num_channels = self.device.GetNumberOfAcquiredChannels()  # Get the number of channels
            messagebox.showinfo("Success", f"Connected to Unicorn device with {num_channels} channels.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def start_data_collection(self):
        if not self.device:
            messagebox.showerror("Error", "Please connect to Unicorn device first.")
            return
        
        if not self.participant_label.get():
            messagebox.showerror("Error", "Please enter participant label.")
            return
        
        if not self.expression_choice.get():
            messagebox.showerror("Error", "Please select an expression (Smile or Frown).")
            return
        
        self.is_collecting = True
        self.trial_number = self.get_next_trial_number()
        threading.Thread(target=self.collect_data).start()
    
    def stop_data_collection(self):
        self.is_collecting = False
    
    def delete_last_trial(self):
        last_trial_file = self.get_last_trial_file()
        if last_trial_file:
            os.remove(last_trial_file)
            messagebox.showinfo("Success", f"Deleted {last_trial_file}")
    
    def get_next_trial_number(self):
        label = self.participant_label.get()
        expression = self.expression_choice.get()
        folder_path = os.path.join(self.output_folder, label)
        os.makedirs(folder_path, exist_ok=True)
        existing_files = [f for f in os.listdir(folder_path) if f.startswith(f"{label}_{expression}")]
        return len(existing_files) + 1
    
    def get_last_trial_file(self):
        label = self.participant_label.get()
        expression = self.expression_choice.get()
        folder_path = os.path.join(self.output_folder, label)
        existing_files = sorted([f for f in os.listdir(folder_path) if f.startswith(f"{label}_{expression}")])
        if existing_files:
            return os.path.join(folder_path, existing_files[-1])
        return None
    
    def collect_data(self):
        label = self.participant_label.get()
        expression = self.expression_choice.get()
        trial_number = self.trial_number
        file_path = os.path.join(self.output_folder, label, f"{label}_{expression}_{trial_number:02d}.csv")
        
        FrameLength = 1
        AcquisitionDurationInSeconds = 35  # Total duration for the steps
        
        self.data_file = open(file_path, "wb")
        number_of_acquired_channels = self.device.GetNumberOfAcquiredChannels()
        receive_buffer_buffer_length = FrameLength * number_of_acquired_channels * 4
        receive_buffer = bytearray(receive_buffer_buffer_length)
        
        try:
            self.device.StartAcquisition(False)
            print("Data acquisition started.")
            
            steps = [
                (5, "Neutral", 0),
                (5, "Strong Expression", 3 if expression == "Frown" else 6),
                (5, "Neutral", 0),
                (5, "Medium Expression", 2 if expression == "Frown" else 5),
                (5, "Neutral", 0),
                (5, "Weak Expression", 1 if expression == "Frown" else 4),
                (5, "Neutral", 0)
            ]
            
            for duration, description, event_code in steps:
                if not self.is_collecting:
                    break
                
                for sec in range(duration, 0, -1):
                    self.update_countdown(f"{description} in {sec} seconds")
                    time.sleep(1)
                
                self.update_countdown(description)
                start_time = time.time()
                while time.time() - start_time < duration:
                    self.device.GetData(FrameLength, receive_buffer, receive_buffer_buffer_length)
                    data = np.frombuffer(receive_buffer, dtype=np.float32, count=number_of_acquired_channels * FrameLength)
                    data = np.reshape(data, (FrameLength, number_of_acquired_channels))
                    np.savetxt(self.data_file, data, delimiter=',', fmt='%.3f', newline='\n')
                    self.lsl_streams['data'].push_chunk(data.tolist())
                    self.lsl_streams['event'].push_sample([event_code])
                
                if not self.is_collecting:
                    break
            
            self.update_countdown("Data collection completed")
        except Exception as e:
            print(f"Error during data collection: {e}")
        finally:
            self.device.StopAcquisition()
            self.data_file.close()
            del receive_buffer
    
    def update_countdown(self, text):
        self.countdown_label.config(text=text)
    
    def on_closing(self):
        if self.device:
            self.device.StopAcquisition()
            del self.device
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SEMGStudyApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
