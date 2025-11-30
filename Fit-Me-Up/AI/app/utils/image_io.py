import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io
import numpy as np
from PIL import Image
import cv2

def load_image_bgr_from_path(path: str) -> np.ndarray:
    """Read image from path as BGR numpy array."""
    img = Image.open(path).convert("RGB")
    return np.array(img)[:, :, ::-1]  # RGB -> BGR

def load_image_bgr_from_bytes(data: bytes) -> np.ndarray:
    """Read image from raw bytes as BGR numpy array."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return np.array(img)[:, :, ::-1]

def to_rgb(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

def crop_safe(img: np.ndarray, x1:int, y1:int, x2:int, y2:int) -> np.ndarray: 
    h, w = img.shape[:2] 
    x1, y1 = max(0, x1), max(0, y1) 
    x2, y2 = min(w, x2), min(h, y2) 
    if x2 <= x1 or y2 <= y1: return img[0:0, 0:0] 
    return img[y1:y2, x1:x2]

def save_bgr(path: str, bgr: np.ndarray) -> None:
    # 디렉터리 자동 생성 없이 단순 저장 (필요하면 os.makedirs 추가)
    cv2.imwrite(path, bgr)

def bgr_to_png_bytes(bgr: np.ndarray) -> bytes:
    success, buf = cv2.imencode(".png", bgr)
    return buf.tobytes() if success else b""
