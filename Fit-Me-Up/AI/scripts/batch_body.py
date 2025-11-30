import argparse, os, glob
from app.utils.image_io import load_image_bgr_from_path
from app.classifiers import body

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input_dir", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--ext", default="jpg", help="jpg|jpeg|png")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(args.input_dir, f"*.{args.ext}")))
    for i, pth in enumerate(paths, 1):
        bgr = load_image_bgr_from_path(pth)
        res, dbg = body.classify(bgr, return_debug=True)
        print(f"[{i}/{len(paths)}] {os.path.basename(pth)} -> {res}")
        if dbg:
            out = os.path.join(args.out_dir, os.path.splitext(os.path.basename(pth))[0] + ".png")
            with open(out, "wb") as f:
                f.write(dbg)

if __name__ == "__main__":
    main()
