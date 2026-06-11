# --- ไฟล์: logic_processor.py ---
import cv2
import numpy as np

# ==========================================
# 🧠 ฟังก์ชันที่ 1: ตรวจสอบการทับซ้อน (หาเจ้าของหมวก/เสื้อ)
# ==========================================
def is_overlapping(person_box, ppe_box, threshold=0.3):
    # แกะพิกัดกรอบ [x_min, y_min, x_max, y_max]
    x_left = max(person_box[0], ppe_box[0])
    y_top = max(person_box[1], ppe_box[1])
    x_right = min(person_box[2], ppe_box[2])
    y_bottom = min(person_box[3], ppe_box[3])

    # ถ้าพิกัดขัดแย้งกัน แปลว่ากรอบไม่ได้แตะกันเลย ให้ตอบ False ทันที
    if x_right < x_left or y_bottom < y_top:
        return False 

    # คำนวณพื้นที่ส่วนที่ซ้อนทับกัน และพื้นที่ของอุปกรณ์ (หมวก/เสื้อ)
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    ppe_area = (ppe_box[2] - ppe_box[0]) * (ppe_box[3] - ppe_box[1])

    # ป้องกัน Error หารด้วยศูนย์
    if ppe_area == 0:
        return False

    # ถ้าหมวก/เสื้อ ซ้อนทับอยู่ในกรอบคน เกิน threshold (เช่น 30%) ถือว่าใส่จริง
    return (intersection_area / ppe_area) > threshold

# ==========================================
# 🛑 ฟังก์ชันที่ 2: ตรวจสอบการเหยียบเส้นโซนอันตราย
# ==========================================
def is_feet_in_danger_zone(person_box, danger_zone_polygon):
    # หาพิกัด "ตรงกลาง-ด้านล่างสุด" ของกรอบคน (ตำแหน่งเท้า)
    x_center = (person_box[0] + person_box[2]) / 2
    y_bottom = person_box[3] 
    
    # ทำตัวเลขให้เป็นจำนวนเต็ม (Integer) เพื่อเตรียมเข้าสูตร OpenCV
    feet_point = (int(x_center), int(y_bottom))
    
    # เช็คว่าจุดของเท้า อยู่ข้างในขอบเขต Polygon หรือไม่ (0 หรือ 1 คือล้ำเส้น)
    result = cv2.pointPolygonTest(np.array(danger_zone_polygon), feet_point, measureDist=False)
    return result >= 0

# ==========================================
# 🚀 ฟังก์ชันหลัก: เส้นประสาทรวบรวมข้อมูล (Phase 2 & Phase 3)
# ==========================================
def process_frame_logic(model, frame, danger_zone_polygon):
    
    # 🤖 1. โยนภาพเข้า YOLO (Phase 2)
    # (ใช้ verbose=False เพื่อไม่ให้ Log ตัวหนังสือวิ่งรกหน้าจอ Terminal)
    results = model(frame, verbose=False) 
    
    # 🧺 2. สร้างตะกร้าเปล่ารอรับข้อมูล
    persons_list = []
    helmets_list = []
    vests_list = []

    # 🗂️ 3. จัด Category แยกลงตะกร้า
    for box in results[0].boxes:
        cls_id = int(box.cls[0])       # **หมายเหตุ:** 0=คน, 1=หมวก, 2=เสื้อ (แก้ให้ตรงกับที่ Train)
        conf = round(float(box.conf[0]), 2)
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        
        item_data = {"box": [x1, y1, x2, y2], "confidence": conf}
        
        if cls_id == 0:
            persons_list.append(item_data)
        elif cls_id == 1:
            helmets_list.append(item_data)
        elif cls_id == 2:
            vests_list.append(item_data)

    # 🧠 4. เริ่มการเปรียบเทียบการทับซ้อน (Phase 3)
    events_log = []
    
    for person in persons_list:
        has_helmet = False
        helmet_conf = 0.0  # เพิ่มตัวแปรเก็บค่า
        has_vest = False
        vest_conf = 0.0    # เพิ่มตัวแปรเก็บค่า
        
        # --- ค้นหาหมวก ---
        for i, helmet in enumerate(helmets_list):
            if is_overlapping(person["box"], helmet["box"]):
                has_helmet = True
                helmet_conf = helmet["confidence"] # 🔥 เก็บค่าความมั่นใจไว้ด้วย
                helmets_list.pop(i) # ทริคความเร็ว: เจอแล้วลบทิ้งเลย จะได้ไม่เช็คซ้ำ
                break 

        # --- ค้นหาเสื้อสะท้อนแสง ---
        for j, vest in enumerate(vests_list):
            if is_overlapping(person["box"], vest["box"]):
                has_vest = True
                vest_conf = vest["confidence"] # 🔥 เก็บค่าความมั่นใจไว้ด้วย
                vests_list.pop(j) # ทริคความเร็ว: เจอแล้วลบทิ้งเลย จะได้ไม่เช็คซ้ำ
                break
                
        # --- เช็คการล้ำเส้น ---
        is_inside = is_feet_in_danger_zone(person["box"], danger_zone_polygon)

        # 📦 5. สรุปผลเหตุการณ์ของ "คนๆ นี้" มัดรวมส่งออกไปให้ main.py
        events_log.append({
            "person_confidence": person["confidence"],
            "has_helmet": has_helmet,
            "helmet_confidence": helmet_conf, # 🔥 ส่งค่ากลับไปด้วย
            "has_vest": has_vest,
            "vest_confidence": vest_conf,     # 🔥 ส่งค่ากลับไปด้วย
            "is_inside_danger_zone": is_inside,
            "box": person["box"] # ส่งพิกัดคนกลับไปด้วย เผื่อไฟล์ main เอาไปวาดกรอบสีแดงแจ้งเตือน
        })
        
    return events_log