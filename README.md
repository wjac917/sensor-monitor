# 位移传感器监测系统

基于 Modbus 协议的位移传感器数据采集、实时绘图与自动记录软件。

## 功能特性

- ✅ 实时读取位移传感器数据（Modbus RTU 协议）
- ✅ 实时绘制时间-位移曲线
- ✅ 每 10 秒自动保存前 10 秒平均值到 TXT 文件
- ✅ 以北京时间为文件名
- ✅ 开始/停止测量时图线自动清零
- ✅ 数据统计（最小/最大/平均/当前值）
- ✅ 数据导出为 JSON/CSV

## 硬件连接

```
位移传感器  →  USB转RS485  →  电脑USB口
```

## 配置

编辑 `sensor_monitor_v2.py` 中的串口配置：

```python
COM_PORT = 'COM3'  # 修改为你的串口号
BAUD_RATE = 9600
UNIT_ID = 1
REGISTER_ADDRESS = 34
```

## 安装依赖

```bash
pip install pymodbus pyserial matplotlib numpy PyInstaller
```

## 运行

```bash
python sensor_monitor_v2.py
```

## 打包为 Windows EXE

```bash
pyinstaller --onefile --windowed sensor_monitor_v2.py
```

## 文件说明

- `sensor_monitor_v2.py` - 主程序
- `sensor_data/` - 数据保存目录
