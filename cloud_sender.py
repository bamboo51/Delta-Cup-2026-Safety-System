# --- ไฟล์: cloud_sender.py ---
import cv2
import datetime
import uuid
from google.cloud import firestore
from google.cloud import storage

# ==========================================
# ⚙️ ตั้งค่าเริ่มต้นของ Google Cloud (Configuration)
# ==========================================
# เปลี่ยนชื่อเหล่านี้ให้ตรงกับโปรเจกต์ของคุณ Jet
PROJECT_ID = "project-439de91d-ea98-4ec7-861" # เช่น "delta-cup-safety-123"
BUCKET_NAME = "factory-safety-snapshots-jet" 
COLLECTION_NAME = "safety_violations_logs"

# สร้างตัวแทน (Client) สำหรับคุยกับระบบคลาวด์ 
# (ระบบจะดึงสิทธิ์จาก gcloud auth application-default ที่ทำไว้โดยอัตโนมัติ)
try:
    db = firestore.Client(project=PROJECT_ID)
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    print("☁️ เชื่อมต่อ Google Cloud (Firestore & Storage) สำเร็จ!")
except Exception as e:
    print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ Cloud: {e}")
    print("อย่าลืมรัน 'gcloud auth application-default login' ใน Terminal ก่อนรันโค้ดนะครับ")

# ==========================================
# 📸 ฟังก์ชันที่ 1: ส่งรูปภาพขึ้น Google Cloud Storage
# ==========================================
def upload_to_gcs(frame_image, severity):
    try:
        # 1. ตั้งชื่อไฟล์ให้ไม่ซ้ำกัน (รูปแบบ: ความรุนแรง_ปีเดือนวัน_เวลา_รหัสสุ่ม.jpg)
        # เช่น: CRITICAL_20260524_153022_a1b2c3.jpg
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:6] 
        file_name = f"{severity}_{timestamp_str}_{unique_id}.jpg"

        # 2. แปลงภาพ OpenCV (Numpy Array) ให้เป็นข้อมูล Bytes (เพื่อยิงขึ้นเน็ตโดยไม่ต้องเซฟลงเครื่อง)
        success, encoded_image = cv2.imencode('.jpg', frame_image)
        if not success:
            print("❌ เกิดข้อผิดพลาดในการเข้ารหัสรูปภาพ")
            return None
        image_bytes = encoded_image.tobytes()

        # 3. อัปโหลดขึ้น Bucket
        blob = bucket.blob(file_name)
        blob.upload_from_string(image_bytes, content_type='image/jpeg')

        # 4. สร้าง Public URL สำหรับเอาไปโชว์ใน Looker Studio
        # (เพราะคุณ Jet เปิดสิทธิ์ Storage Object Viewer ให้ allUsers ไว้แล้ว)
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{file_name}"
        print(f"📸 อัปโหลดรูปหลักฐานสำเร็จ: {public_url}")
        
        return public_url

    except Exception as e:
        print(f"❌ Error uploading to GCS: {e}")
        return None

# ==========================================
# 🔥 ฟังก์ชันที่ 2: ส่งข้อมูล JSON เข้า Firestore
# ==========================================
# เพิ่มพารามิเตอร์ image_url และ downtime_seconds เข้ามาเผื่อใช้งาน
def send_to_firestore(event_data, severity, plc_status, image_url=None, downtime_seconds=0, event_type="Unknown Event"):
    try:
        # 1. เตรียมข้อมูล JSON (Payload)
        current_time = datetime.datetime.now()
        
        payload = {
            "camera_id": "Cam_Zone_A", # สมมติชื่อกล้องไปก่อน
            "event_type": event_type,
            "severity": severity,
            
            # --- ดึงข้อมูลดิบมาจาก event_data (Phase 3) ---
            "is_inside_danger_zone": event_data.get("is_inside_danger_zone", False),
            "has_helmet": event_data.get("has_helmet", False),
            "helmet_confidence": event_data.get("helmet_confidence", 0.0),
            "has_vest": event_data.get("has_vest", False),
            "vest_confidence": event_data.get("vest_confidence", 0.0),
            "person_confidence": event_data.get("person_confidence", 0.0),
            
            # --- ข้อมูลผลลัพธ์ ---
            "plc_status": plc_status,
            "downtime_seconds": downtime_seconds,
            "timestamp": current_time
        }

        # 2. ยิงเข้า Firestore
        # ใช้ .add() เพื่อให้ระบบสร้าง Document ID (Auto-ID) ให้เอง ข้อมูลจะไม่ทับซ้อนกันแน่นอน 100%
        _, doc_ref = db.collection(COLLECTION_NAME).add(payload)
        
        print(f"🔥 บันทึกข้อมูลระดับ {severity} ลง Firestore สำเร็จ! (Doc ID: {doc_ref.id})")
        
        return doc_ref.id # ส่งคืน ID เผื่อไฟล์หลักต้องเอาไปใช้อัปเดตค่าเวลา Manager Reset
        
    except Exception as e:
        print(f"❌ Error sending to Firestore: {e}")
        return None