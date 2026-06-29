from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolo26n.pt")

    model.train(
        data="./dataset/ppe.yaml",
        epochs=100,
        imgsz=1280,
        batch=2,  # reduce to 8 if VRAM < 8 GB
        device=0,
        amp=True,
        project="runs",
        name="ppe_yolo26n",
        optimizer="MuSGD",  # official YOLO26 default
        # STAL + ProgLoss are on by default in YOLO26 — no flag needed
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        patience=20,
    )
