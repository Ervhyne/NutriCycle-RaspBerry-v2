"""
NutriCycle Video Testing with NCNN Inference
Drop-in replacement for test_video.py using NCNN
"""

import argparse, time, cv2, os, sys
from pathlib import Path

# Add deploy directory to path
sys.path.insert(0, str(Path(__file__).parent))
from ncnn_wrapper import load_ncnn_model

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="ncnn/models/best-int8")
parser.add_argument("--source", default="1")  # "0" for webcam or "path/to/video.mp4"
parser.add_argument("--output", default=None)
parser.add_argument("--conf", type=float, default=0.5)
parser.add_argument("--flip", choices=['none','vertical','horizontal','180'], default='none',
                    help='Flip video: vertical=upside-down, horizontal, 180=rotate 180')
args = parser.parse_args()

if args.flip != 'none':
    print(f"Applying flip: {args.flip}")

source = int(args.source) if args.source.isdigit() else args.source

# Resolve model path
model_path = args.model
if not Path(model_path).with_suffix('.param').exists():
    # Try with deploy prefix
    alt = Path("deploy") / model_path
    if alt.with_suffix('.param').exists():
        model_path = str(alt)
    else:
        print(f"❌ Model not found: {model_path}.param")
        print(f"   Looked in: {Path(model_path).resolve()}")
        print(f"   And: {alt.resolve()}")
        sys.exit(1)

print(f"🔥 Loading NCNN model: {model_path}")
model = load_ncnn_model(model_path, conf=args.conf)

print(f"📹 Opening video source: {source}")
cap = cv2.VideoCapture(source)

if not cap.isOpened():
    print(f"❌ Failed to open video source: {source}")
    sys.exit(1)

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps_in = cap.get(cv2.CAP_PROP_FPS) or 20.0

print(f"   Resolution: {w}x{h} @ {fps_in:.1f} FPS")

out = None
if args.output:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(args.output, fourcc, fps_in, (w, h))
    print(f"💾 Recording to: {args.output}")

frame_count = 0
total_time = 0

print("✅ Starting inference (press 'q' to quit)")
print("=" * 50)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply requested flip before inference
        if args.flip != 'none':
            if args.flip == 'vertical':
                frame = cv2.flip(frame, 0)
            elif args.flip == 'horizontal':
                frame = cv2.flip(frame, 1)
            elif args.flip == '180':
                frame = cv2.flip(frame, -1)

        # Run inference
        t0 = time.time()
        results = model(frame, conf=args.conf)
        inference_time = time.time() - t0
        
        # Get annotated frame
        annotated = results[0].plot()
        
        # Calculate FPS
        frame_count += 1
        total_time += inference_time
        avg_fps = frame_count / total_time if total_time > 0 else 0
        
        # Add overlays
        cv2.putText(
            annotated,
            f"FPS: {avg_fps:.1f} | Inference: {inference_time*1000:.0f}ms",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        # Show detections count
        num_detections = len(results[0].boxes)
        if num_detections > 0:
            cv2.putText(
                annotated,
                f"Detections: {num_detections}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
        
        cv2.imshow("NCNN Inference", annotated)
        
        if out:
            out.write(annotated)
        
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

except KeyboardInterrupt:
    print("\n⚠️  Interrupted by user")

finally:
    print("=" * 50)
    print(f"📊 Statistics:")
    print(f"   Frames processed: {frame_count}")
    print(f"   Average FPS: {frame_count / total_time:.1f}" if total_time > 0 else "   Average FPS: N/A")
    print(f"   Average inference: {total_time / frame_count * 1000:.0f}ms" if frame_count > 0 else "   Average inference: N/A")
    
    cap.release()
    if out:
        out.release()
        print(f"✅ Video saved to: {args.output}")
    cv2.destroyAllWindows()
