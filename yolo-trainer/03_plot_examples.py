import random
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

COLORS = {0: "lime", 1: "cyan", 2: "orange"}
NAMES = {0: "safety vest", 1: "safety hat", 2: "person"}


def plot_examples(split="train", n=6):
    img_dir = Path(f"dataset/images/{split}")
    lbl_dir = Path(f"dataset/labels/{split}")
    samples = random.sample(
        sorted(img_dir.glob("*.jpg")), min(n, len(list(img_dir.glob("*.jpg"))))
    )

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    for ax, img_path in zip(axes, samples):
        img = Image.open(img_path).convert("RGB")
        W, H = img.size
        ax.imshow(np.array(img))
        ax.set_title(img_path.name, fontsize=8)
        ax.axis("off")

        lbl_path = lbl_dir / (img_path.stem + ".txt")
        if not lbl_path.exists():
            continue

        with open(lbl_path) as f:
            for line in f.read().strip().splitlines():
                if not line:
                    continue
                cls_id, cx, cy, bw, bh = map(float, line.split())
                cls_id = int(cls_id)
                x1 = (cx - bw / 2) * W
                y1 = (cy - bh / 2) * H
                pw = bw * W
                ph = bh * H
                rect = patches.Rectangle(
                    (x1, y1),
                    pw,
                    ph,
                    linewidth=2,
                    edgecolor=COLORS.get(cls_id, "red"),
                    facecolor="none",
                )
                ax.add_patch(rect)
                ax.text(
                    x1,
                    y1 - 4,
                    NAMES.get(cls_id, str(cls_id)),
                    color=COLORS.get(cls_id, "red"),
                    fontsize=7,
                    backgroundcolor="black",
                )

    plt.suptitle(f"GDINO pseudo-labels — {split}", fontsize=12)
    plt.tight_layout()
    plt.savefig(f"preview_{split}.png", dpi=150)
    plt.show()
    print(f"Saved preview_{split}.png")


plot_examples("train", n=6)
