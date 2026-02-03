"""
NCNN Inference Wrapper using pyncnn (Python bindings)
Cleaner approach - no C++ binary compilation needed
"""

import numpy as np
import cv2
import ncnn
from pathlib import Path
from typing import List, Dict, Optional


class NCNNInferencePython:
    """
    Native Python NCNN inference using pyncnn.
    Drop-in replacement for ultralytics YOLO.
    """
    
    def __init__(self, param_path: str, bin_path: str, conf_threshold: float = 0.5, target_size: int = 512):
        """
        Initialize NCNN inference.
        
        Args:
            param_path: Path to .param file
            bin_path: Path to .bin file
            conf_threshold: Confidence threshold
            target_size: Input size (512 for NutriCycle model, or 320/416/640)
        """
        self.param_path = str(Path(param_path).resolve())
        self.bin_path = str(Path(bin_path).resolve())
        self.conf_threshold = conf_threshold
        self.target_size = target_size
        
        if not Path(self.param_path).exists():
            raise FileNotFoundError(f"Model param: {self.param_path}")
        if not Path(self.bin_path).exists():
            raise FileNotFoundError(f"Model bin: {self.bin_path}")
        
        # Load NCNN network
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = False
        self.net.opt.num_threads = 4
        
        self.net.load_param(self.param_path)
        self.net.load_model(self.bin_path)
        
        # Class names
        self.names = {0: 'foreign_object'}
        
        print(f"✅ NCNN Inference initialized (pyncnn)")
        print(f"   Model: {Path(self.param_path).name}")
        print(f"   Target size: {self.target_size}×{self.target_size}")
        print(f"   Confidence: {self.conf_threshold}")
    
    def __call__(self, frame: np.ndarray, conf: Optional[float] = None, verbose: bool = False) -> List['NCNNResult']:
        """
        Run inference on frame.
        
        Args:
            frame: BGR image
            conf: Confidence threshold override
            verbose: Ignored
        
        Returns:
            List with single NCNNResult
        """
        conf_threshold = conf if conf is not None else self.conf_threshold
        
        # Preprocess
        img_h, img_w = frame.shape[:2]
        scale = min(self.target_size / img_w, self.target_size / img_h)
        new_w, new_h = int(img_w * scale), int(img_h * scale)
        
        resized = cv2.resize(frame, (new_w, new_h))
        
        # Letterbox padding
        padded = np.full((self.target_size, self.target_size, 3), 114, dtype=np.uint8)
        pad_x = (self.target_size - new_w) // 2
        pad_y = (self.target_size - new_h) // 2
        padded[pad_y:pad_y+new_h, pad_x:pad_x+new_w] = resized
        
        # Convert to ncnn Mat
        mat_in = ncnn.Mat.from_pixels(
            padded,
            ncnn.Mat.PixelType.PIXEL_BGR,
            self.target_size,
            self.target_size
        )
        
        # Normalize
        mean_vals = []
        norm_vals = [1/255.0, 1/255.0, 1/255.0]
        mat_in.substract_mean_normalize(mean_vals, norm_vals)
        
        # Create extractor and run inference
        ex = self.net.create_extractor()
        ex.input("images", mat_in)
        
        mat_out = ncnn.Mat()
        ex.extract("output0", mat_out)
        
        # Parse detections
        detections = self._parse_detections(
            mat_out,
            conf_threshold,
            scale,
            pad_x,
            pad_y
        )
        
        return [NCNNResult(frame, detections, self.names)]
    
    def _parse_detections(self, mat_out, conf_threshold, scale, pad_x, pad_y):
        """Parse YOLOv8 output format."""
        detections = []
        
        # YOLOv8 output shape: [1, num_classes+4, num_proposals]
        # Transpose to [num_proposals, num_classes+4]
        c, h, w = mat_out.c, mat_out.h, mat_out.w
        
        # Convert to numpy for easier processing
        out_data = np.array(mat_out).reshape(c, -1).T  # [num_proposals, c]
        
        for row in out_data:
            # YOLOv8 format: [cx, cy, w, h, class_scores...]
            cx, cy, w, h = row[0], row[1], row[2], row[3]
            class_scores = row[4:]
            
            max_score = float(np.max(class_scores))
            if max_score < conf_threshold:
                continue
            
            max_cls = int(np.argmax(class_scores))
            
            # Convert back to original image coordinates
            x = (cx - pad_x) / scale
            y = (cy - pad_y) / scale
            w_orig = w / scale
            h_orig = h / scale
            
            detections.append({
                'x': x,
                'y': y,
                'w': w_orig,
                'h': h_orig,
                'conf': max_score,
                'cls': max_cls
            })
        
        return detections


class NCNNResult:
    """Result object mimicking ultralytics Results."""
    
    def __init__(self, frame: np.ndarray, detections: List[Dict], names: Dict[int, str]):
        self.orig_img = frame
        self.detections = detections
        self.names = names
        self.boxes = NCNNBoxes(detections)
    
    def plot(self, line_width: int = 2, font_size: int = 1) -> np.ndarray:
        """Draw bounding boxes."""
        annotated = self.orig_img.copy()
        
        for det in self.detections:
            x, y, w, h = det['x'], det['y'], det['w'], det['h']
            conf, cls = det['conf'], det['cls']
            
            x1 = int(x - w/2)
            y1 = int(y - h/2)
            x2 = int(x + w/2)
            y2 = int(y + h/2)
            
            color = (0, 255, 0)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, line_width)
            
            label = f"{self.names.get(cls, str(cls))} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_size * 0.5, line_width)
            cv2.rectangle(annotated, (x1, y1 - th - 4), (x1 + tw, y1), color, -1)
            cv2.putText(annotated, label, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 
                       font_size * 0.5, (0, 0, 0), line_width)
        
        return annotated


class NCNNBoxes:
    """Boxes collection."""
    def __init__(self, detections):
        self._detections = detections
    def __len__(self):
        return len(self._detections)
    def __iter__(self):
        for det in self._detections:
            yield NCNNBox(det)


class NCNNBox:
    """Single box."""
    def __init__(self, detection):
        self._det = detection
        x, y, w, h = detection['x'], detection['y'], detection['w'], detection['h']
        self._xyxy = [[x - w/2, y - h/2, x + w/2, y + h/2]]
    
    @property
    def cls(self):
        return self._det['cls']
    @property
    def conf(self):
        return self._det['conf']
    @property
    def xyxy(self):
        class Wrapper:
            def __init__(self, xyxy):
                self._xyxy = xyxy
            def tolist(self):
                return self._xyxy
        return Wrapper(self._xyxy)


def load_ncnn_model(model_path: str, conf: float = 0.5, target_size: int = 320):
    """
    Load NCNN model (Python native).
    
    Args:
        model_path: Base path (without extension)
        conf: Confidence threshold
        target_size: Input resolution
    
    Returns:
        NCNNInferencePython instance
    """
    model_path = Path(model_path)
    if model_path.suffix in ['.param', '.bin']:
        model_path = model_path.with_suffix('')
    
    param_path = model_path.with_suffix('.param')
    bin_path = model_path.with_suffix('.bin')
    
    return NCNNInferencePython(str(param_path), str(bin_path), conf, target_size)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python ncnn_wrapper_pyncnn.py <model_base> <image>")
        sys.exit(1)
    
    model = load_ncnn_model(sys.argv[1])
    frame = cv2.imread(sys.argv[2])
    
    if frame is None:
        print(f"❌ Failed to load: {sys.argv[2]}")
        sys.exit(1)
    
    results = model(frame)
    print(f"✅ Detections: {len(results[0].boxes)}")
    
    for box in results[0].boxes:
        print(f"   Class: {box.cls}, Conf: {box.conf:.2f}")
    
    annotated = results[0].plot()
    cv2.imwrite("result_pyncnn.jpg", annotated)
    print("💾 Saved: result_pyncnn.jpg")
