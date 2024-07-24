import UnicornPy
import numpy as np
import os
import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from pylsl import StreamInfo, StreamOutlet

class DataCollectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Data Collection UI")
        self.instructions = [
            ("Relax Face", 5, "Neutral", 0),
            ("Strong Expression", 5, "100%", 3),
            ("Relax Face", 5, "Neutral", 0),
            ("Medium Expression", 5, "60%", 2),
            ("Relax Face", 5, "Neutral", 0),
            ("Weak Expression", 5, "30%", 1),
            ("Relax Face", 10, "Neutral", 0),
            ("Strong Expression", 5, "100%", 3),
            ("Relax Face", 5, "Neutral", 0),
            ("Medium Expression", 5, "60%", 2),
            ("Relax Face", 5, "Neutral", 0),
            ("Weak Expression", 5, "30%", 1),
            ("Relax Face", 10, "Neutral", 0),
            ("Strong Expression", 5, "100%", 3),
            ("Relax Face", 5, "Neutral", 0),
            ("Medium Expression", 5, "60%", 2),
            ("Relax Face", 5, "Neutral", 0),
            ("Weak Expression", 5, "30%", 1),
            ("Relax Face", 10, "Neutral", 0),
            ("Strong Expression", 5, "100%", 3),
            ("Relax Face", 5, "Neutral", 0),
            ("Medium Expression", 5, "60%", 2),
            ("Relax Face", 5, "Neutral", 0),
            ("Weak Expression", 5, "30%", 1),
            ("Relax Face", 10, "Neutral", 0),
            ("Strong Expression", 5, "100%", 3),
            ("Relax Face", 5, "Neutral", 0),
            ("Medium Expression", 5, "60%", 2),
            ("Relax Face", 5, "Neutral", 0),
            ("Weak Expression", 5, "30%", 1)
        ]
        self.current_instruction = 0
        self.device = None
        self.file = None
        self.label = None
        self.expression_type = tk.StringVar(value="Smile")

        self.create_widgets()
        self.setup_device()
        self.setup_lsl()

    def create_widgets(self):
        self.label_frame = tk.Frame(self.root)
        self.label_frame.pack(pady=10)

        self.label_label = tk.Label(self.label_frame, text="Participant Label:")
        self.label_label.pack(side=tk.LEFT, padx=5)

        self.label_entry = tk.Entry(self.label_frame)
        self.label_entry.pack(side=tk.LEFT, padx=5)

        self.expression_choice_frame = tk.Frame(self.root)
        self.expression_choice_frame.pack(pady=10)

        self.expression_choice_label = tk.Label(self.expression_choice_frame, text="Expression Type:")
        self.expression_choice_label.pack(side=tk.LEFT, padx=5)

        self.expression_choice = ttk.Combobox(self.expression_choice_frame, textvariable=self.expression_type)
        self.expression_choice['values'] = ("Smile", "Frown")
        self.expression_choice.pack(side=tk.LEFT, padx=5)

        self.label = tk.Label(self.root, text="", font=("Helvetica", 18))
        self.label.pack(pady=20)

        self.start_button = tk.Button(self.root, text="Start", command=self.start_data_collection)
        self.start_button.pack(pady=20)

    def setup_device(self):
        try:
            deviceList = UnicornPy.GetAvailableDevices(True)
            if len(deviceList) <= 0 or deviceList is None:
                raise Exception("No device available. Please pair with a Unicorn first.")

            self.device = UnicornPy.Unicorn(deviceList[0])
            messagebox.showinfo("Device Connected", f"Connected to '{deviceList[0]}'.")

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.root.quit()

    def setup_lsl(self):
        self.data_info = StreamInfo('UnicornData', 'EEG', 18, UnicornPy.SamplingRate, 'float32', 'unicorn12345')
        #self.event_info = StreamInfo('UnicornEvents', 'Markers', 1, 0, 'int32', 'unicorn_events12345')
        
        self.data_outlet = StreamOutlet(self.data_info)
        #self.event_outlet = StreamOutlet(self.event_info)

    def start_data_collection(self):
        self.participant_label = self.label_entry.get().strip()
        if not self.participant_label:
            messagebox.showerror("Error", "Please enter a participant label.")
            return

        self.current_instruction = 0
        self.start_button.config(state=tk.DISABLED)
        self.expression_choice.config(state=tk.DISABLED)
        self.label_entry.config(state=tk.DISABLED)
        
        expression_type = self.expression_type.get()
        directory = os.path.join("Data", self.participant_label)
        if not os.path.exists(directory):
            os.makedirs(directory)
        file_name = f"{self.participant_label}_{expression_type}_1.csv"
        self.data_file_path = os.path.join(directory, file_name)
        counter = 1
        while os.path.exists(self.data_file_path):
            counter += 1
            self.data_file_path = os.path.join(directory, f"{self.participant_label}_{expression_type}_{counter}.csv")
        
        self.file = open(self.data_file_path, "wb")
        self.root.after(1000, self.show_next_instruction)

    def show_next_instruction(self):
        if self.current_instruction < len(self.instructions):
            instruction, duration, expression, event_code = self.instructions[self.current_instruction]
            if "Expression" in instruction:
                expression_mod = f"{self.expression_type.get()} {instruction.split()[0]}"
                event_code += 3 if self.expression_type.get() == "Frown" else 0
            else:
                expression_mod = instruction
            self.label.config(text=f"Prepare for: {expression_mod} ({expression})")
            self.root.after(5000, self.countdown, duration, expression_mod, expression, event_code)
        else:
            self.stop_data_collection()

    def countdown(self, duration, instruction, expression, event_code):
        for i in range(3, 0, -1):
            self.label.config(text=f"{instruction} ({expression}) in {i}")
            self.root.update()
            self.root.after(1000)
        self.label.config(text=f"{instruction} ({expression}) for {duration} seconds")
        #self.event_outlet.push_sample([event_code])
        self.root.after(duration * 1000, self.collect_data(event_code))
        self.current_instruction += 1

    def collect_data(self, event_code):
        FrameLength = 1
        try:
            numberOfAcquiredChannels = self.device.GetNumberOfAcquiredChannels()
            receiveBufferBufferLength = FrameLength * numberOfAcquiredChannels * 4
            receiveBuffer = bytearray(receiveBufferBufferLength)
            
            self.device.StartAcquisition(False)
            
            for _ in range(5 * UnicornPy.SamplingRate // FrameLength):
                self.device.GetData(FrameLength, receiveBuffer, receiveBufferBufferLength)
                data = np.frombuffer(receiveBuffer, dtype=np.float32, count=numberOfAcquiredChannels * FrameLength)
                data = np.append(data, np.float32(event_code))
                data = np.reshape(data, (FrameLength, numberOfAcquiredChannels+1))
                np.savetxt(self.file, data, delimiter=',', fmt='%.3f', newline='\n')
                self.data_outlet.push_chunk(data.tolist())
            
            self.device.StopAcquisition()

        except UnicornPy.DeviceException as e:
            messagebox.showerror("Device Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

        self.show_next_instruction()

    def stop_data_collection(self):
        self.file.close()
        messagebox.showinfo("Data Collection", "Data collection completed.")
        self.root.quit()

def main():
    root = tk.Tk()
    app = DataCollectionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
