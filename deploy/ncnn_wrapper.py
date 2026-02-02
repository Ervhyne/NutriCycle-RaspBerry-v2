"""
NCNN Inference Wrapper for NutriCycle
Replaces ultralytics YOLO inference with NCNN binary calls
"""

import subprocess
import json
import os
import tempfile
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional


class NCNNInference:
    """
    Wrapper for NCNN YOLOv8 inference.
    Drop-in replacement for ultralytics YOLO inference.
    """
    
    def __init__(self, param_path: str, bin_path: str, conf_threshold: float = 0.5):
        """
        Initialize NCNN inference wrapper.
        
        Args:
            param_path: Path to .param file
            bin_path: Path to .bin file
            conf_threshold: Confidence threshold (0.0 - 1.0)
        """
        self.param_path = str(Path(param_path).resolve())
        self.bin_path = str(Path(bin_path).resolve())
        self.conf_threshold = conf_threshold
        
        # Find NCNN binary
        script_dir = Path(__file__).parent
        self.ncnn_binary = script_dir / "ncnn" / "bin" / "yolo_ncnn"
        
        if not self.ncnn_binary.exists():
            raise FileNotFoundError(
                f"NCNN binary not found: {self.ncnn_binary}\n"
                f"Please run setup_ncnn_pi.sh first"
            )
        
        if not Path(self.param_path).exists():
            raise FileNotFoundError(f"Model param file not found: {self.param_path}")
        
        if not Path(self.bin_path).exists():
            raise FileNotFoundError(f"Model bin file not found: {self.bin_path}")
        
        # Class names (customize for your model)
        self.names = {0: 'foreign_object'}  # Update this based on your classes
        
        print(f"✅ NCNN Inference initialized")
        print(f"   Model: {Path(self.param_path).name}")
        print(f"   Binary: {self.ncnn_binary}")
        print(f"   Confidence: {self.conf_threshold}")
    
    def __call__(self, frame: np.ndarray, conf: Optional[float] = None, verbose: bool = False) -> List['NCNNResult']:
        """
        Run inference on a frame (mimics ultralytics API).
        
        Args:
            frame: Input image (BGR format, numpy array)
            conf: Confidence threshold override
            verbose: Ignored (for API compatibility)
        
        Returns:
            List containing single NCNNResult object
        """
        conf_threshold = conf if conf is not None else self.conf_threshold
        
        # Save frame to temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, frame)
        
        try:
            # Run NCNN inference
            result = subprocess.run(
                [
                    str(self.ncnn_binary),
                    self.param_path,
                    self.bin_path,
                    tmp_path,
                    str(conf_threshold)
                ],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            
            if result.returncode != 0:
                print(f"⚠️  NCNN inference failed: {result.stderr}")
                return [NCNNResult(frame, [], self.names)]
            
            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                detections = data.get('detections', [])
            except json.JSONDecodeError:
                print(f"⚠️  Failed to parse NCNN output: {result.stdout}")
                detections = []
            
            return [NCNNResult(frame, detections, self.names)]
        
        finally:
            # Cleanup temp file
            try:
                os.unlink(tmp_path)
            except:
                pass


class NCNNResult:
    """
    Result object that mimics ultralytics Results API.
    """
    
    def __init__(self, frame: np.ndarray, detections: List[Dict], names: Dict[int, str]):
        self.orig_img = frame
        self.detections = detections
        self.names = names
        
        # Create boxes object (mimics ultralytics)
        self.boxes = NCNNBoxes(detections)
    
    def plot(self, line_width: int = 2, font_size: int = 1) -> np.ndarray:
        """
        Draw bounding boxes on frame (mimics ultralytics plot()).
        
        Returns:
            Annotated image
        """
        annotated = self.orig_img.copy()
        
        for det in self.detections:
            x, y, w, h = det['x'], det['y'], det['w'], det['h']
            conf = det['conf']
            cls = det['cls']
            
            # Convert center coords to box coords
            x1 = int(x - w/2)
            y1 = int(y - h/2)
            x2 = int(x + w/2)
            y2 = int(y + h/2)
            
            # Draw box
            color = (0, 255, 0)  # Green
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, line_width)
            
            # Draw label
            label = f"{self.names.get(cls, str(cls))} {conf:.2f}"
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_size * 0.5, line_width)
            cv2.rectangle(annotated, (x1, y1 - text_h - 4), (x1 + text_w, y1), color, -1)
            cv2.putText(annotated, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, font_size * 0.5, (0, 0, 0), line_width)
        
        return annotated


class NCNNBoxes:
    """
    Boxes object that mimics ultralytics Boxes API.
    """
    
    def __init__(self, detections: List[Dict]):
        self._detections = detections
    
    def __len__(self):
        return len(self._detections)
    
    def __iter__(self):
        """Iterate over detections as NCNNBox objects."""
        for det in self._detections:
            yield NCNNBox(det)


class NCNNBox:
    """
    Individual box that mimics ultralytics Box API.
    """
    
    def __init__(self, detection: Dict):
        self._det = detection
        
        # Calculate xyxy format
        x, y, w, h = detection['x'], detection['y'], detection['w'], detection['h']
        x1 = x - w/2
        y1 = y - h/2
        x2 = x + w/2
        y2 = y + h/2
        self._xyxy = [[x1, y1, x2, y2]]
    
    @property
    def cls(self):
        return self._det['cls']
    
    @property
    def conf(self):
        return self._det['conf']
    
    @property
    def xyxy(self):
        """Return box coordinates in xyxy format."""
        class XYXYWrapper:
            def __init__(self, xyxy):
                self._xyxy = xyxy
            def tolist(self):
                return self._xyxy
        return XYXYWrapper(self._xyxy)


# Helper function for easy migration
def load_ncnn_model(model_path: str, conf: float = 0.5) -> NCNNInference:
    """
    Load NCNN model (auto-detects .param and .bin from path).
    
    Args:
        model_path: Path to model (can be .param, .bin, or base name)
        conf: Confidence threshold
    
    Returns:
        NCNNInference instance
    
    Example:
        # Old: model = YOLO('best.pt')
        # New: model = load_ncnn_model('deploy/ncnn/models/best-int8')
    """
    model_path = Path(model_path)
    
    # Remove extension if provided
    if model_path.suffix in ['.param', '.bin']:
        model_path = model_path.with_suffix('')
    
    param_path = model_path.with_suffix('.param')
    bin_path = model_path.with_suffix('.bin')
    
    return NCNNInference(str(param_path), str(bin_path), conf)


if __name__ == '__main__':
    # Test inference
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python ncnn_wrapper.py <model_base_path> <image_path>")
        print("Example: python ncnn_wrapper.py deploy/ncnn/models/best-int8 test.jpg")
        sys.exit(1)
    
    model_path = sys.argv[1]
    image_path = sys.argv[2]
    
    print(f"Loading model: {model_path}")
    model = load_ncnn_model(model_path)
    
    print(f"Running inference on: {image_path}")
    frame = cv2.imread(image_path)
    
    if frame is None:
        print(f"❌ Failed to load image: {image_path}")
        sys.exit(1)
    
    results = model(frame)
    
    print(f"✅ Detections: {len(results[0].boxes)}")
    for box in results[0].boxes:
        print(f"   Class: {box.cls}, Confidence: {box.conf:.2f}")
    
    # Save annotated image
    annotated = results[0].plot()
    output_path = "ncnn_result.jpg"
    cv2.imwrite(output_path, annotated)
    print(f"💾 Saved result to: {output_path}")
