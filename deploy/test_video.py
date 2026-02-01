import argparse, time, cv2, os, sys
from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="runs/detect/nutricycle_foreign_only/weights/best.pt")
parser.add_argument("--source", default="1")  # "0" for webcam or "path/to/video.mp4"
parser.add_argument("--output", default=None)
parser.add_argument("--conf", type=float, default=0.5)
parser.add_argument("--flip", choices=['none','vertical','horizontal','180'], default='none',
                    help='Flip video: vertical=upside-down, horizontal, 180=rotate 180')
args = parser.parse_args()

if args.flip != 'none':
    print(f"Applying flip: {args.flip}")

source = int(args.source) if args.source.isdigit() else args.source

# Resolve model path: try direct path, then try prefixing with AI-Model/
model_path = args.model
if not os.path.exists(model_path):
    alt = os.path.join("AI-Model", model_path) if not model_path.startswith("AI-Model") else None
    if alt and os.path.exists(alt):
        print(f"Using model: {alt}")
        model_path = alt
    else:
        print(f"Error: model '{args.model}' not found. Tried: '{args.model}'" + (f" and '{alt}'" if alt else ""))
        sys.exit(1)

# If ONNX model, ensure onnxruntime is available; if not try to fall back to .pt next to the ONNX file
if model_path.lower().endswith('.onnx'):
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        pt_candidate = model_path[:-5] + '.pt'
        if os.path.exists(pt_candidate):
            print(f"onnxruntime not found; switching to '{pt_candidate}' for inference.")
            model_path = pt_candidate
        else:
            print("onnxruntime not installed. Install it with: python -m pip install onnxruntime\nor use a .pt model instead.")
            sys.exit(1)

model = YOLO(model_path)
cap = cv2.VideoCapture(source)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps_in = cap.get(cv2.CAP_PROP_FPS) or 20.0

out = None
if args.output:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(args.output, fourcc, fps_in, (w, h))

while True:
    ret, frame = cap.read()
    if not ret: break

    # apply requested flip before inference (keeps annotations aligned)
    if args.flip != 'none':
        if args.flip == 'vertical':
            frame = cv2.flip(frame, 0)
        elif args.flip == 'horizontal':
            frame = cv2.flip(frame, 1)
        elif args.flip == '180':
            frame = cv2.flip(frame, -1)

    t0 = time.time()
    results = model(frame, conf=args.conf)
    annotated = results[0].plot()
    fps = 1.0 / max(1e-6, (time.time() - t0))
    cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
    cv2.imshow("YOLO Test", annotated)
    if out: out.write(annotated)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
if out: out.release()
cv2.destroyAllWindows()