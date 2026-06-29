import os
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoProcessor, GroundingDinoForObjectDetection

MODEL_ID = "IDEA-Research/grounding-dino-tiny"
CLASSES = ["safety vest", "safety hat", "person"]
PROMPT = " . ".join(CLASSES) + " ."
BOX_TH = 0.35
TEXT_TH = 0.25
BATCH = 4
device = "cuda" if torch.cuda.is_available() else "cpu"

for SPLIT in ["train", "val"]:
    IMG_DIR = f"dataset/images/{SPLIT}"
    LBL_DIR = f"dataset/labels/{SPLIT}"
    os.makedirs(LBL_DIR, exist_ok=True)

    img_paths = sorted(Path(IMG_DIR).glob("*.jpg"))
    if not img_paths:
        continue

    print(f"\n[{SPLIT}] {len(img_paths)} images")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = GroundingDinoForObjectDetection.from_pretrained(MODEL_ID).to(device)

    def phrase_to_cls(phrase):
        phrase = phrase.lower()
        for i, cls in enumerate(CLASSES):
            if cls in phrase:
                return i
        return -1

    for start in range(0, len(img_paths), BATCH):
        batch_paths = img_paths[start : start + BATCH]
        images = [Image.open(p).convert("RGB") for p in batch_paths]
        target_sizes = torch.tensor([[img.height, img.width] for img in images])

        inputs = processor(
            images=images,
            text=[PROMPT] * len(images),
            return_tensors="pt",
            padding=True,
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)

        results = processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            threshold=BOX_TH,
            text_threshold=TEXT_TH,
            target_sizes=target_sizes,
        )

        for img, path, result in zip(images, batch_paths, results):
            W, H = img.size
            lines = []
            for box, phrase in zip(result["boxes"], result["labels"]):
                cls_id = phrase_to_cls(phrase)
                if cls_id == -1:
                    continue
                x1, y1, x2, y2 = box.tolist()
                cx = max(0.0, min(1.0, (x1 + x2) / 2 / W))
                cy = max(0.0, min(1.0, (y1 + y2) / 2 / H))
                bw = max(0.001, min(1.0, (x2 - x1) / W))
                bh = max(0.001, min(1.0, (y2 - y1) / H))
                lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            lbl_path = os.path.join(LBL_DIR, path.stem + ".txt")
            with open(lbl_path, "w") as f:
                f.write("\n".join(lines))
        print(f"  {min(start + BATCH, len(img_paths))}/{len(img_paths)}", end="\r")
    print(f"\n[{SPLIT}] Done → {LBL_DIR}")
