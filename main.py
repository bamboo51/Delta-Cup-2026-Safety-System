# --- ไฟล์: main.py ---
import cv2
import numpy as np
from ultralytics import YOLO
import time

# ==========================================
# 📦 นำเข้าแผนกต่างๆ ที่เราแยกไฟล์ไว้ (Modular Imports)
# ==========================================
from logic_processor import process_frame_logic
from cloud_sender import send_to_firestore, upload_to_gcs
from plc_controller import trigger_interlock_and_wait, set_machine_speed

# ==========================================
# ⚙️ ตั้งค่าเริ่มต้น (Initialization)
# ==========================================
print("🤖 Loading YOLO Model...")
model = YOLO('best.pt') 

# 🎬 กำหนดพื้นที่ Danger Zone (ลองปรับให้เข้ากับมุมกล้องจริง)
danger_zone_polygon = np.array([
    [150, 300], [500, 300], [600, 450], [50, 450]
], np.int32)

# 📹 เปิดกล้อง (ช่วงทดสอบใช้ 0 คือกล้องเว็บแคมโน้ตบุ๊ก)
print("📹 Connecting to Camera...")
cap = cv2.VideoCapture(0) 

if not cap.isOpened():
    print("❌ Error: ไม่สามารถเปิดกล้องได้")
    exit()

# ระบบป้องกันการยิง Log ซ้ำซ้อน (Cooldown Timer)
last_alert_time = 0
ALERT_COOLDOWN = 5 # หน่วงเวลา 5 วินาที ก่อนจะส่ง Log ครั้งต่อไป

print("✅ System Ready! เริ่มการทำงาน Edge AI ตลอด 24 ชม.")

# ==========================================
# 🔄 วงลูปหลัก (Main Process Loop)
# ==========================================
while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️ Camera signal lost. Retrying...")
        time.sleep(2)
        cap = cv2.VideoCapture(0)
        continue

    # วาดเส้น Danger Zone สีแดงบนหน้าจอ
    cv2.polylines(frame, [danger_zone_polygon], isClosed=True, color=(0, 0, 255), thickness=2)

    # ----------------------------------------------------
    # 🧠 Phase 2 & 3: ส่งภาพไปให้สมองกลคิดวิเคราะห์
    # ----------------------------------------------------
    events = process_frame_logic(model, frame, danger_zone_polygon)

    # 🌟 [เพิ่มใหม่] ฟังก์ชัน Auto-Recovery: 
    # เช็คว่า ณ เสี้ยววินาทีนี้ "ไม่มีใครล้ำเส้นเลยใช่ไหม?" ถ้าใช่ ให้เครื่องวิ่ง 100%
    is_anyone_in_danger = any(event["is_inside_danger_zone"] for event in events)
    if not is_anyone_in_danger:
        set_machine_speed(100) # 🐇 ปลอดภัยแล้ว เหยียบคันเร่งเต็มสปีด!

    # ----------------------------------------------------
    # 🛡️ Phase 4: ประเมินความรุนแรง (Risk Matrix)
    # ----------------------------------------------------
    for event in events:
        severity = "SAFE"
        
        is_inside = event["is_inside_danger_zone"]
        has_helmet = event["has_helmet"]
        has_vest = event["has_vest"]

        # กฎการประเมิน
        if is_inside:
            if has_helmet and has_vest:
                severity = "HIGH"
                event_name = "Zone Intrusion (With Full PPE)"
            elif not has_helmet and not has_vest:
                severity = "CRITICAL"
                event_name = "Critical Intrusion (Missing All PPE)"
            elif not has_helmet and has_vest:
                severity = "CRITICAL"
                event_name = "Critical Intrusion (Missing Helmet)"
            elif has_helmet and not has_vest:
                severity = "CRITICAL"
                event_name = "Critical Intrusion (Missing Vest)"
        else: # กรณีอยู่นอกโซนอันตราย
            if not has_helmet and not has_vest:
                severity = "MEDIUM"
                event_name = "Missing All PPE (Outside Zone)"
            elif not has_helmet and has_vest:
                severity = "LOW"
                event_name = "Missing Helmet (Outside Zone)"
            elif has_helmet and not has_vest:
                severity = "LOW"
                event_name = "Missing Vest (Outside Zone)"
            else:
                severity = "SAFE"
                event_name = "Normal Operation"

        # ----------------------------------------------------
        # 🛑 Phase 5: ลงมือทำ (Cloud & PLC)
        # ----------------------------------------------------
        if severity != "SAFE":
            # ตรวจสอบระบบหน่วงเวลา (Cooldown)
            current_time = time.time()

            # 🔥 แก้ตรงนี้: ให้ส่ง Log เมื่อหมด Cooldown "หรือ" เมื่อเป็นเหตุการณ์ระดับ CRITICAL
            if (current_time - last_alert_time > ALERT_COOLDOWN) or (severity == "CRITICAL"):
                
                print(f"\n🚨 ALERT: ตรวจพบพฤติกรรมเสี่ยงระดับ {severity}!")
                
                # 🎨 ทริคพิเศษ: วาดกรอบสีแดงครอบคนทำผิด เพื่อให้รูปหลักฐานชัดเจน
                x1, y1, x2, y2 = map(int, event["box"])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, severity, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                # 1. ถ่ายภาพและอัปโหลดขึ้น GCS เป็นหลักฐาน
                # (ฟังก์ชันทำงานอยู่เบื้องหลัง ไม่กวนระบบหลัก)
                upload_to_gcs(frame, severity)
                
                # 2. แยกการทำงานระหว่าง IT กับ OT
                if severity == "CRITICAL":
                    plc_status = "Interlock_Triggered"
                    
                    # 🛑 สั่งดับเครื่อง PLC -> รอ Manager เสียบกุญแจ -> คืนค่า Downtime
                    downtime = trigger_interlock_and_wait() 
                    
                    # ☁️ ยิงข้อมูลทั้งหมดพร้อมเวลาที่เสียไปขึ้น Firestore ให้ Looker Studio อัปเดต
                    send_to_firestore(event, severity, plc_status, event_type=event_name, downtime_seconds=downtime)
                    
                elif severity == "HIGH":
                    #HIGH เครื่องจักรชลอเเต่ยังวิ่งต่อ
                    print("⚠️ ช่างใส่ PPE ครบล้ำเส้นโซน! -> ลดความเร็วเครื่องจักรเหลือ 20%")
                    set_machine_speed(20) # 🐢 ลดความเร็วทันที

                    plc_status = "Slow_Speed_Mode"
                    send_to_firestore(event, severity, plc_status, event_type=event_name, downtime_seconds=0)

                else: 
                    #LOW, MEDIUM เครื่องจักรยังวิ่งต่อ # ถ้าสถานะกลับมาเป็น SAFE, LOW, หรือ MEDIUM (เช่น ช่างเดินออกจากเส้นแดงแล้ว)         
                    plc_status = "Running"
                    send_to_firestore(event, severity, plc_status, event_type=event_name, downtime_seconds=0)

                # อัปเดตเวลาแจ้งเตือนล่าสุด
                last_alert_time = current_time

    # แสดงภาพสดออกทางหน้าจอคอมพิวเตอร์ Edge
    cv2.imshow('DENSO Smart Factory - Edge AI Monitor', frame)

    # กด 'q' เพื่อปิดระบบอย่างปลอดภัย
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Stopping System...")
        break

cap.release()
cv2.destroyAllWindows()