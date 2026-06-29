import os
import random

import cv2
import tqdm

VIDEO = "./Delta_FactorySim.mp4"
TRAIN_DIR = "dataset/images/train"
VAL_DIR = "dataset/images/val"
TEST_VIDEO = "./Delta_FactorySim_test.mp4"
VAL_RATIO = 0.2
SEED = 42

os.makedirs(TRAIN_DIR, exist_ok=True)
os.makedirs(VAL_DIR, exist_ok=True)

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
half_frames = total_frames // 2
stride = max(1, int(fps))
saved = []
fid = 0

with tqdm.tqdm(total=half_frames, desc="Reading", unit="frame") as pbar:
    while fid < half_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if fid % stride == 0:
            saved.append((fid, frame.copy()))
        fid += 1
        pbar.update(1)

# save the rest of video
fourcc = cv2.VideoWriter.fourcc(*"mp4v")
writer = cv2.VideoWriter(TEST_VIDEO, fourcc, fps, (width, height))
rest_frames = total_frames - half_frames

with tqdm.tqdm(total=rest_frames, desc="Saving rest video", unit="frame") as pbar:
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)
        pbar.update(1)

writer.release()
cap.release()

# split and write frames
random.seed(SEED)
random.shuffle(saved)
n_val = max(1, int(len(saved) * VAL_RATIO))

for i, (fid, frame) in enumerate(tqdm.tqdm(saved, desc="Writing", unit="frame")):
    dst = VAL_DIR if i < n_val else TRAIN_DIR
    cv2.imwrite(f"{dst}/{fid:07d}.jpg", frame)

print(f"Done. train={len(saved) - n_val}  val={n_val}")
