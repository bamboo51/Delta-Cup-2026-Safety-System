from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO(r"runs\detect\runs\ppe_yolo26n-4\weights\best.pt")
    # {0: 'helmet', 1: 'gloves', 2: 'vest', 3: 'boots', 4: 'goggles', 5: 'none', 6: 'Person', 7: 'no_helmet', 8: 'no_goggle', 9: 'no_gloves', 10: 'no_boots'}

    exclude = {3, 10}  # boots, no_boots
    keep_classes = [k for k in model.names if k not in exclude]
    print("Keeping classes:", keep_classes, [model.names[k] for k in keep_classes])

    results = model.track(
        source="Delta_FactorySim_test.mp4",
        save=True,
        show=False,
        stream=True,
        classes=keep_classes,
        persist=True,
        conf=0.6,
    )

    for result in results:
        pass  # save=True handles output automatically

    print("Done! Check runs/detect/track*/")
