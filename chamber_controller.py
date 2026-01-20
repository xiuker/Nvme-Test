import serial
import time
from typing import Optional, Tuple
from logger import ConsoleLogger


class CRC16Modbus:
    @staticmethod
    def calculate(data: bytes) -> bytes:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


class ChamberController:
    def __init__(self, port: str, baudrate: int = 2400, bytesize: int = 8, 
                 parity: str = 'N', stopbits: int = 1, timeout: int = 2, 
                 command_set: int = 1, logger: Optional[ConsoleLogger] = None):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.command_set = command_set
        self.logger = logger
        self.serial_conn = None
        self.current_temperature = 0.0
        self.target_temperature = 0.0
        self.hold_time = 0
        self._connect()

    def _connect(self):
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout
            )
            if self.logger:
                self.logger.info(f'温箱串口连接成功: {self.port}')
        except Exception as e:
            if self.logger:
                self.logger.error(f'温箱串口连接失败: {e}')
            raise

    def _send_command(self, command: bytes) -> Optional[bytes]:
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.write(command)
                time.sleep(0.1)
                response = self.serial_conn.readall()
                return response
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f'发送串口命令失败: {e}')
            return None

    def _send_command_set1(self, command: bytes) -> Optional[bytes]:
        return self._send_command(command)

    def _send_command_set2(self, command: str) -> Optional[bytes]:
        return self._send_command(command.encode('ascii'))

    def start_chamber(self) -> bool:
        if self.command_set == 1:
            command = bytes.fromhex('01 05 1F 40 FF 00 8A 3A')
            response = self._send_command_set1(command)
        else:
            command = 'W9902A'
            response = self._send_command_set2(command)
        
        if response:
            if self.logger:
                self.logger.info('温箱启动命令发送成功')
            return True
        return False

    def stop_chamber(self) -> bool:
        if self.command_set == 1:
            command = bytes.fromhex('01 05 1F 41 FF 00 DB FA')
            response = self._send_command_set1(command)
        else:
            command = 'W9901A'
            response = self._send_command_set2(command)
        
        if response:
            if self.logger:
                self.logger.info('温箱停止命令发送成功')
            return True
        return False

    def read_temperature(self) -> Optional[float]:
        if self.command_set == 1:
            command = bytes.fromhex('01 03 1F 37 00 01 32 10')
            response = self._send_command_set1(command)
            
            if response and len(response) >= 7:
                temp_value = int.from_bytes(response[3:5], byteorder='big')
                temperature = temp_value / 10.0
                self.current_temperature = temperature
                if self.logger:
                    self.logger.debug(f'读取温箱温度: {temperature}°C')
                return temperature
        else:
            command = 'R99A'
            response = self._send_command_set2(command)
            
            if response and len(response) >= 40:
                try:
                    response_str = response.hex()
                    temp_section = response_str[56:80]
                    
                    if len(temp_section) >= 12:
                        temp_part = temp_section[:10]
                        sign_part = temp_section[10:12]
                        
                        temp_str = temp_part[:2] + '.' + temp_part[2:]
                        temperature = float(temp_str)
                        
                        if sign_part == '01':
                            temperature = -temperature
                        
                        self.current_temperature = temperature
                        if self.logger:
                            self.logger.debug(f'读取温箱温度: {temperature}°C')
                        return temperature
                except Exception as e:
                    if self.logger:
                        self.logger.error(f'解析温箱温度失败: {e}')
        
        return None

    def set_temperature(self, temperature: float) -> bool:
        self.target_temperature = temperature
        
        if self.command_set == 1:
            temp_value = int(temperature * 10)
            
            if temperature >= 0:
                temp_bytes = temp_value.to_bytes(2, byteorder='big')
            else:
                temp_value = 65536 + temp_value
                temp_bytes = temp_value.to_bytes(2, byteorder='big')
            
            command_data = bytes([0x01, 0x06, 0x1F, 0xA4]) + temp_bytes
            crc = CRC16Modbus.calculate(command_data)
            command = command_data + crc
            
            response = self._send_command_set1(command)
            
            if response:
                if self.logger:
                    self.logger.info(f'设定温箱温度: {temperature}°C')
                return True
        else:
            if temperature >= 0:
                sign = '0'
                abs_temp = temperature
            else:
                sign = '1'
                abs_temp = -temperature
            
            temp_str = f"{abs_temp:05.2f}".replace('.', '')
            temp_str = temp_str[:5]
            
            command = f'W01{temp_str}{sign}0000A'
            response = self._send_command_set2(command)
            
            if response:
                if self.logger:
                    self.logger.info(f'设定温箱温度: {temperature}°C')
                return True
        
        return False

    def wait_for_temperature(self, tolerance: float = 1.0, check_interval: int = 5, max_wait_time: int = 600) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            current_temp = self.read_temperature()
            
            if current_temp is not None:
                if abs(current_temp - self.target_temperature) <= tolerance:
                    if self.logger:
                        self.logger.info(f'温箱温度达到目标: {current_temp}°C')
                    return True
            
            time.sleep(check_interval)
        
        if self.logger:
            self.logger.warning(f'温箱温度未在{max_wait_time}秒内达到目标温度')
        return False

    def hold_temperature(self, hold_time: int) -> bool:
        self.hold_time = hold_time
        if self.logger:
            self.logger.info(f'温箱保温开始，保温时间: {hold_time}秒')
        
        time.sleep(hold_time)
        
        if self.logger:
            self.logger.info('温箱保温结束')
        return True

    def get_remaining_hold_time(self, start_time: float) -> int:
        elapsed = time.time() - start_time
        remaining = max(0, self.hold_time - int(elapsed))
        return remaining

    def close(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            if self.logger:
                self.logger.info('温箱串口连接已关闭')
