# -*- coding: utf-8 -*-
import sys
import warnings
import os

# pymodbus 兼容性
try:
    from pymodbus.client import ModbusSerialClient
    from pymodbus.framer import BinaryPayloadDecoder
except ImportError:
    try:
        from pymodbus.client.sync import ModbusSerialClient
        from pymodbus.payload import BinaryPayloadDecoder
    except ImportError:
        print("请安装 pymodbus: pip install pymodbus")
        sys.exit(1)

# GUI
import tkinter as tk
from tkinter import messagebox

# 绘图
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# 忽略警告
warnings.filterwarnings("ignore")

# ==========================================
# 配置
# ==========================================
COM_PORT = 'COM3'
BAUD_RATE = 9600
UNIT_ID = 1
REGISTER_ADDRESS = 34
REGISTER_COUNT = 2
DATA_DIR = "sensor_data"
SAVE_INTERVAL = 10.0

# ==========================================
# Modbus 客户端
# ==========================================
client = ModbusSerialClient(
    port=COM_PORT,
    baudrate=BAUD_RATE,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=0.5
)

# ==========================================
# 数据缓冲
# ==========================================
class DataBuffer:
    def __init__(self):
        self.timestamps = []
        self.values = []
        self.max_size = 5000
        
    def append(self, timestamp, value):
        self.timestamps.append(timestamp)
        self.values.append(value)
        if len(self.timestamps) > self.max_size:
            self.timestamps.pop(0)
            self.values.pop(0)
    
    def get_statistics(self):
        if not self.values:
            return {'count': 0, 'min': 0, 'max': 0, 'avg': 0, 'current': 0}
        return {
            'count': len(self.values),
            'min': min(self.values),
            'max': max(self.values),
            'avg': sum(self.values) / len(self.values),
            'current': self.values[-1] if self.values else 0
        }
    
    def clear(self):
        self.timestamps = []
        self.values = []

# ==========================================
# 文件管理
# ==========================================
class FileManager:
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        self.current_file = None
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def generate_filename(self):
        from datetime import datetime
        beijing_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.data_dir, f"measurement_{beijing_time}.txt")
    
    def save_average(self, avg_value, count, start_time, end_time):
        try:
            from datetime import datetime
            start_str = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
            end_str = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")
            duration = end_time - start_time
            
            with open(self.current_file, 'a', encoding='utf-8') as f:
                f.write(f"{start_str} ~ {end_str}\n")
                f.write(f"  持续时间: {duration:.1f} 秒 | 数据点数: {count}\n")
                f.write(f"  10秒均值: {avg_value:.4f} mm\n")
                f.write("-" * 50 + "\n")
            return True
        except Exception as e:
            return False
    
    def write_header(self):
        try:
            from datetime import datetime
            beijing_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("位移传感器测量数据\n")
                f.write(f"开始时间: {beijing_time}\n")
                f.write(f"端口: {COM_PORT} | 波特率: {BAUD_RATE}\n")
                f.write("=" * 60 + "\n\n")
                f.write("[数据段]\n")
                f.write("-" * 60 + "\n")
            return True
        except:
            return False

# ==========================================
# 主界面
# ==========================================
class MeasurementPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("高精度位移监测与记录系统")
        self.root.geometry("1000x700")
        self.root.configure(bg='#1e1e1e')
        
        self.data_buffer = DataBuffer()
        self.file_manager = FileManager()
        
        self.is_measuring = False
        self.measurement_start_time = None
        self.segment_start_time = None
        self.segment_values = []
        self.last_update_time = 0
        self.is_connected = False
        self.save_count = 0
        
        self.create_widgets()
        self.connect_sensor()
        
        if self.is_connected:
            self.start_update_loop()
    
    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 控制面板
        control_frame = tk.Frame(main_frame, bg='#2d2d2d', relief='raised', bd=1)
        control_frame.pack(fill='x', pady=(0, 10))
        
        self.btn_measure = tk.Button(
            control_frame, text="开始测量", command=self.toggle_measurement,
            font=("SimHei", 14, "bold"), bg='#d9534f', fg='white',
            width=12, height=2, cursor='hand2'
        )
        self.btn_measure.pack(side='left', padx=10, pady=8)
        
        self.lbl_filename = tk.Label(
            control_frame, text="未开始测量", 
            font=("Arial", 11), fg='yellow', bg='#2d2d2d', anchor='w'
        )
        self.lbl_filename.pack(side='left', padx=20, fill='x', expand=True)
        
        self.lbl_save_count = tk.Label(
            control_frame, text="已保存: 0 次", 
            font=("Arial", 11), fg='#00ff00', bg='#2d2d2d'
        )
        self.lbl_save_count.pack(side='right', padx=20, pady=5)
        
        # 显示区域
        display_frame = tk.Frame(main_frame, bg='#1e1e1e')
        display_frame.pack(fill='both', expand=True)
        
        # 左侧
        left_frame = tk.Frame(display_frame, bg='#1e1e1e')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        self.lbl_value = tk.Label(
            left_frame, text="WAITING...", 
            font=("Arial", 48, "bold"), 
            fg="#00ff00", bg='#000000',
            width=12, relief="sunken", bd=3
        )
        self.lbl_value.pack(pady=5)
        
        self.lbl_unit = tk.Label(
            left_frame, text="单位: mm", 
            font=("Arial", 14), fg="#aaaaaa", bg='#1e1e1e'
        )
        self.lbl_unit.pack(pady=(0, 5))
        
        # 实时曲线
        self.fig = Figure(figsize=(8, 4), dpi=100, facecolor='#1e1e1e')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2d2d2d')
        self.ax.tick_params(colors='white')
        self.ax.set_xlabel('时间 (s)', color='white')
        self.ax.set_ylabel('位移 (mm)', color='white')
        self.ax.set_title('实时位移曲线', color='white')
        self.ax.grid(True, alpha=0.3)
        
        self.x_data = []
        self.y_data = []
        self.line, = self.ax.plot([], [], 'g-', linewidth=1)
        self.ax.set_xlim(0, 60)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True, pady=5)
        
        # 右侧统计
        right_frame = tk.Frame(display_frame, bg='#1e1e1e', width=250)
        right_frame.pack(side='right', fill='both')
        right_frame.pack_propagate(False)
        
        tk.Label(
            right_frame, text="📊 统计信息", 
            font=("SimHei", 14), fg="#ffffff", bg='#1e1e1e'
        ).pack(pady=(0, 10))
        
        stats_frame = tk.Frame(right_frame, bg='#2d2d2d', relief='raised', bd=1)
        stats_frame.pack(fill='x', pady=(0, 10))
        
        self.lbl_count = tk.Label(stats_frame, text="数据点数: 0", 
            font=("Arial", 11), fg='#00ff00', bg='#2d2d2d', anchor='w')
        self.lbl_count.pack(fill='x', padx=10, pady=3)
        
        self.lbl_min = tk.Label(stats_frame, text="最小值: --", 
            font=("Arial", 11), fg='white', bg='#2d2d2d', anchor='w')
        self.lbl_min.pack(fill='x', padx=10, pady=3)
        
        self.lbl_max = tk.Label(stats_frame, text="最大值: --", 
            font=("Arial", 11), fg='white', bg='#2d2d2d', anchor='w')
        self.lbl_max.pack(fill='x', padx=10, pady=3)
        
        self.lbl_avg = tk.Label(stats_frame, text="平均值: --", 
            font=("Arial", 11), fg='white', bg='#2d2d2d', anchor='w')
        self.lbl_avg.pack(fill='x', padx=10, pady=3)
        
        self.lbl_current = tk.Label(stats_frame, text="当前值: --", 
            font=("Arial", 11), fg='#00ff00', bg='#2d2d2d', anchor='w')
        self.lbl_current.pack(fill='x', padx=10, pady=3)
        
        seg_frame = tk.Frame(right_frame, bg='#2d2d2d', relief='raised', bd=1)
        seg_frame.pack(fill='x', pady=(0, 10))
        
        self.lbl_segment = tk.Label(seg_frame, text="当前段: 0 秒", 
            font=("Arial", 11), fg='yellow', bg='#2d2d2d', anchor='w')
        self.lbl_segment.pack(fill='x', padx=10, pady=3)
        
        self.lbl_segment_avg = tk.Label(seg_frame, text="段均值: --", 
            font=("Arial", 11), fg='yellow', bg='#2d2d2d', anchor='w')
        self.lbl_segment_avg.pack(fill='x', padx=10, pady=3)
        
        last_save_frame = tk.Frame(right_frame, bg='#2d2d2d', relief='raised', bd=1)
        last_save_frame.pack(fill='x', pady=(0, 10))
        
        self.lbl_last_save = tk.Label(last_save_frame, text="上次保存: --", 
            font=("Arial", 10), fg='#aaaaaa', bg='#2d2d2d', anchor='w', justify='left')
        self.lbl_last_save.pack(fill='x', padx=10, pady=5)
        
        # 状态栏
        self.status_frame = tk.Frame(self.root, bg='#2d2d2d', height=25)
        self.status_frame.pack(side='bottom', fill='x')
        
        self.lbl_status = tk.Label(
            self.status_frame, text="未连接", 
            font=("Arial", 10), fg="red", bg='#2d2d2d', anchor='w'
        )
        self.lbl_status.pack(side='left', padx=10)
        
        self.lbl_time = tk.Label(
            self.status_frame, text="", 
            font=("Arial", 10), fg="#00ff00", bg='#2d2d2d'
        )
        self.lbl_time.pack(side='right', padx=10)
        
        self.update_time_display()
    
    def update_time_display(self):
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.lbl_time.config(text=current_time)
        self.root.after(1000, self.update_time_display)
    
    def connect_sensor(self):
        if client.connect():
            self.is_connected = True
            self.lbl_status.config(
                text=f"✅ 已连接 | 端口: {COM_PORT} | 波特率: {BAUD_RATE}", 
                fg="#00ff00"
            )
        else:
            self.is_connected = False
            self.lbl_status.config(text=f"❌ 无法打开串口 {COM_PORT}", fg="red")
            messagebox.showerror("连接错误", f"无法打开串口 {COM_PORT}\n请检查端口设置或连接线。")
    
    def toggle_measurement(self):
        if not self.is_connected:
            messagebox.showwarning("未连接", "请先连接传感器")
            return
        
        if not self.is_measuring:
            self.start_measurement()
        else:
            self.stop_measurement()
    
    def start_measurement(self):
        self.data_buffer.clear()
        self.x_data = []
        self.y_data = []
        self.line.set_data([], [])
        self.ax.set_xlim(0, 60)
        self.canvas.draw()
        self.update_statistics()
        
        self.file_manager.current_file = self.file_manager.generate_filename()
        self.file_manager.write_header()
        
        self.segment_start_time = time.time()
        self.segment_values = []
        self.save_count = 0
        
        self.is_measuring = True
        self.measurement_start_time = time.time()
        
        self.btn_measure.config(text="停止测量", bg='#5cb85c')
        
        filename = os.path.basename(self.file_manager.current_file)
        self.lbl_filename.config(text=f"📁 {filename}", fg='#00ff00')
        self.lbl_status.config(text="🔄 测量中...", fg='yellow')
        
        self.schedule_save()
    
    def stop_measurement(self):
        if self.segment_values:
            self.save_current_segment()
        
        self.is_measuring = False
        
        self.btn_measure.config(text="开始测量", bg='#d9534f')
        self.lbl_filename.config(text="测量已停止", fg='yellow')
        self.lbl_status.config(text=f"✅ 测量结束 | 共 {self.save_count} 次保存", fg='#00ff00')
        self.lbl_segment.config(text="当前段: 0 秒")
        self.lbl_segment_avg.config(text="段均值: --")
        
        messagebox.showinfo("测量结束", f"数据已保存到:\n{self.file_manager.current_file}")
    
    def save_current_segment(self):
        if not self.segment_values or not self.file_manager.current_file:
            return
        
        avg = sum(self.segment_values) / len(self.segment_values)
        start = self.segment_start_time
        end = time.time()
        
        self.file_manager.save_average(avg, len(self.segment_values), start, end)
        
        self.save_count += 1
        self.lbl_save_count.config(text=f"已保存: {self.save_count} 次")
        self.lbl_last_save.config(text=f"上次保存:\n  {avg:.4f} mm\n  {len(self.segment_values)} 点")
        
        self.segment_start_time = time.time()
        self.segment_values = []
    
    def schedule_save(self):
        if not self.is_measuring:
            return
        self.root.after(int(SAVE_INTERVAL * 1000), self.auto_save)
    
    def auto_save(self):
        if not self.is_measuring:
            return
        self.save_current_segment()
        self.schedule_save()
    
    def start_update_loop(self):
        self.update_data()
    
    def update_data(self):
        if not self.is_connected:
            return
        
        import time
        current_time = time.time()
        
        if current_time - self.last_update_time >= 0.1:
            try:
                result = client.read_holding_registers(
                    address=REGISTER_ADDRESS,
                    count=REGISTER_COUNT,
                    slave=UNIT_ID
                )
                
                if not result.isError():
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        result.registers, byteorder=">", wordorder="<"
                    )
                    
                    raw_int_value = decoder.decode_32bit_int()
                    real_value = raw_int_value / 10000.0
                    
                    self.lbl_value.config(text=f"{real_value:.4f}")
                    self.data_buffer.append(current_time, real_value)
                    
                    if self.is_measuring:
                        self.segment_values.append(real_value)
                        
                        import time
                        seg_duration = current_time - self.segment_start_time
                        seg_avg = sum(self.segment_values) / len(self.segment_values) if self.segment_values else 0
                        self.lbl_segment.config(text=f"当前段: {seg_duration:.0f} 秒")
                        self.lbl_segment_avg.config(text=f"段均值: {seg_avg:.4f} mm")
                        
                        self.update_plot(current_time)
                    
                    self.last_update_time = current_time
                    
                else:
                    self.lbl_value.config(text="ERROR")
                    self.lbl_status.config(text="读取错误", fg="red")
                
            except Exception as e:
                self.lbl_value.config(text="ERROR")
                self.lbl_status.config(text=f"异常: {str(e)[:30]}", fg="red")
            
            self.update_statistics()
        
        self.root.after(100, self.update_data)
    
    def update_plot(self, current_time):
        if self.measurement_start_time is None:
            return
        
        cutoff_time = current_time - 60
        recent_ts = [t - self.measurement_start_time for t in self.data_buffer.timestamps if t >= cutoff_time]
        recent_vals = [v for t, v in zip(self.data_buffer.timestamps, self.data_buffer.values) if t >= cutoff_time]
        
        if recent_ts:
            self.line.set_data(recent_ts, recent_vals)
            
            max_time = max(recent_ts)
            if max_time > 60:
                self.ax.set_xlim(max_time - 60, max_time)
            else:
                self.ax.set_xlim(0, 60)
            
            if recent_vals:
                y_min = min(recent_vals)
                y_max = max(recent_vals)
                y_margin = (y_max - y_min) * 0.1 if y_max != y_min else 1
                self.ax.set_ylim(y_min - y_margin, y_max + y_margin)
            
            self.canvas.draw_idle()
    
    def update_statistics(self):
        stats = self.data_buffer.get_statistics()
        self.lbl_count.config(text=f"数据点数: {stats['count']}")
        self.lbl_min.config(text=f"最小值: {stats['min']:.4f} mm")
        self.lbl_max.config(text=f"最大值: {stats['max']:.4f} mm")
        self.lbl_avg.config(text=f"平均值: {stats['avg']:.4f} mm")
        self.lbl_current.config(text=f"当前值: {stats['current']:.4f} mm")
    
    def on_close(self):
        if self.is_measuring:
            self.stop_measurement()
        if self.is_connected:
            client.close()
        self.root.destroy()

# ==========================================
# 入口
# ==========================================
if __name__ == "__main__":
    import time
    root = tk.Tk()
    app = MeasurementPanel(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
