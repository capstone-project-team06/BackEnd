import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from app.utils.image_io import load_image_bgr_from_path
from app.classifiers import skin

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("--out", default=None, help="디버그 이미지 저장 경로 (예: outputs/skin_debug.png)")
    args = p.parse_args()

    bgr = load_image_bgr_from_path(args.image)
    res, debug_png = skin.classify(bgr, return_debug=bool(args.out))
    print(res)

    if args.out and debug_png:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(debug_png)
        print(f"[saved] {args.out} ({len(debug_png)} bytes)")