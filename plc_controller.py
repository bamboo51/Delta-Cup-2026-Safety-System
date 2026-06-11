# --- ไฟล์: plc_controller.py ---
import time
from pymodbus.client import ModbusTcpClient

# ==========================================
# ⚙️ ตั้งค่าการเชื่อมต่อ PLC (IP Address ของตู้ PLC)
# ==========================================
PLC_IP = "192.168.1.50"   # เปลี่ยนเป็น IP ของ PLC จริง
PLC_PORT = 502            # Port มาตรฐานของ Modbus TCP

# สมมติ Address (Register) ในตู้ PLC ที่ตกลงกับช่างไฟไว้
INTERLOCK_COIL = 0        # Address สั่งตัดไฟ (0 = ปกติ, 1 = ตัดไฟ/เบรก)
MANAGER_KEY_INPUT = 1     # Address อ่านค่ากุญแจรีเซ็ต (0 = ยังไม่ไข, 1 = Manager ไขกุญแจแล้ว)
SPEED_REGISTER = 100      # 🌟 (เพิ่มใหม่) Address สำหรับคุมความเร็ว Inverter (0-100%)

def trigger_interlock_and_wait():
    """
    ฟังก์ชันนี้จะทำงานเมื่อเกิดเหตุ CRITICAL
    1. สั่งตัดเครื่องจักร
    2. จับเวลา
    3. รอจนกว่า Manager จะไขกุญแจ
    4. คืนค่า Downtime (วินาที)
    """
    print(f"🔌 [PLC] กำลังเชื่อมต่อกับ PLC ที่ IP: {PLC_IP}...")
    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
    
    if not client.connect():
        print("❌ [PLC] Error: ไม่สามารถเชื่อมต่อตู้ PLC ได้! (จำลองว่า Downtime = 0 ไปก่อน)")
        return 0

    try:
        # 🛑 สเต็ป 1: สั่ง Interlock (ดับเครื่อง!)
        print("🛑 [PLC] ส่งสัญญาณ INTERLOCK! เครื่องจักรหยุดทำงาน!")
        client.write_coil(INTERLOCK_COIL, True) # ส่งไฟ 1 ไปที่ Coil
        
        # ⏱️ สเต็ป 2: เริ่มจับเวลา Downtime
        start_time = time.time()
        
        # 🔑 สเต็ป 3: วนลูปรอ Manager เอากุญแจมาเสียบ
        print("⏳ [PLC] ระบบล็อก... รอ Manager ไขกุญแจเพื่อปลดล็อก (Reset Key)...")
        while True:
            # อ่านค่าสถานะกุญแจจาก PLC
            result = client.read_discrete_inputs(MANAGER_KEY_INPUT, 1)
            is_key_turned = result.bits[0] 
            
            if is_key_turned == True:
                print("✅ [PLC] Manager ไขกุญแจแล้ว! อนุญาตให้เดินเครื่องต่อ")
                break # หลุดออกจากลูป
            
            time.sleep(1) # รอ 1 วินาทีแล้วเช็คใหม่ (ไม่ให้ CPU ทำงานหนักไป)

        # ⏱️ สเต็ป 4: สิ้นสุดการจับเวลา และคำนวณ
        end_time = time.time()
        downtime_seconds = int(end_time - start_time)
        
        # 🟢 สเต็ป 5: ปลดล็อก Interlock ให้เครื่องกลับมาทำงานได้
        client.write_coil(INTERLOCK_COIL, False) # ส่งไฟ 0 ไปที่ Coil
        
        print(f"📊 [PLC] สรุปเวลา Downtime สูญเสียไป: {downtime_seconds} วินาที")
        return downtime_seconds

    except Exception as e:
        print(f"❌ [PLC] เกิดข้อผิดพลาดระหว่างคุยกับ PLC: {e}")
        return 0
    finally:
        client.close() # ปิดการเชื่อมต่อเสมอเพื่อความปลอดภัย

# ==========================================
# 🐢 ฟังก์ชันที่ 2: ควบคุมความเร็ว (ลดความเร็ว / ฟื้นฟูอัตโนมัติ)
# ==========================================
def set_machine_speed(speed_percent: int):
    """
    ฟังก์ชันนี้ส่งค่าความเร็ว (0-100%) ไปบอก Inverter ผ่าน PLC
    - ถ้าส่ง 20 คือลดความเร็ว (ช่างอยู่ในโซน)
    - ถ้าส่ง 100 คือ Auto-Recovery (ช่างเดินออกไปแล้ว)
    """
    print(f"⚙️ [PLC] สั่งปรับความเร็วเครื่องจักรเป็น {speed_percent}%")
    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)

    if not client.connect():
        print("❌ [PLC] Error: ไม่สามารถเชื่อมต่อตู้ PLC เพื่อปรับความเร็วได้")
        return

    try:
        # ใช้ write_register สำหรับส่งข้อมูลตัวเลข (Analog/Data)
        client.write_register(SPEED_REGISTER, speed_percent)
    except Exception as e:
        print(f"❌ [PLC] เกิดข้อผิดพลาดในการปรับความเร็ว: {e}")
    finally:
        client.close()