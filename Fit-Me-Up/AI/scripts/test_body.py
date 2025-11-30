import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from app.utils.image_io import load_image_bgr_from_path
from app.classifiers import body

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    bgr = load_image_bgr_from_path(args.image)
    res = body.classify(bgr, return_debug=bool(args.out))
    print(res)

    if args.out and res.get("debug_image"):
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(res["debug_image"])
        print(f"[saved] {args.out}")