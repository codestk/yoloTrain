"""
Build a YOLO dataset from a Label Studio JSON export + the images already on disk.
No images are exported through Docker, so the Label Studio storage does not grow.

Output (same layout as Label Studio's YOLO export, so train_val_split.py works unchanged):
  <out>/images/<file>      images (hard links when possible, otherwise copies)
  <out>/labels/<stem>.txt  YOLO labels (empty file = background image)
  <out>/classes.txt        copied from the FROZEN class list (default: classes.txt next to this script)

Rules
- Uses the latest non-cancelled annotation of each task. Tasks without such an annotation are
  SKIPPED (an unfinished task must not become a "nothing here" background image).
- A submitted annotation with no boxes = background image.
- Labels not in the frozen class list stop the script, because a changed class list makes the
  champion model incomparable. Update classes.txt deliberately if you really add a class.

Usage:
  python ls_json_to_yolo.py --json custom_data\\export.json --upload_dir D:\\docker\\label-studio\\media\\upload\\9 --out custom_data
"""
import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--json', required=True, help='Label Studio JSON export (list of tasks)')
ap.add_argument('--upload_dir', required=True, help='Folder that holds the uploaded images of the project')
ap.add_argument('--out', default='custom_data')
ap.add_argument('--classes', default=str(here / 'classes.txt'), help='Frozen class list, one name per line')
ap.add_argument('--copy', action='store_true', help='Always copy images instead of hard-linking')
args = ap.parse_args()

classes = [l.strip() for l in open(args.classes, encoding='utf-8') if l.strip()]
cls_id = {n: i for i, n in enumerate(classes)}

tasks = json.loads(Path(args.json).read_text(encoding='utf-8-sig'))
if isinstance(tasks, dict):
    tasks = tasks.get('tasks', [])
upload_dir = Path(args.upload_dir)
out = Path(args.out)
img_out, lab_out = out / 'images', out / 'labels'
img_out.mkdir(parents=True, exist_ok=True)
lab_out.mkdir(parents=True, exist_ok=True)
shutil.copy(args.classes, out / 'classes.txt')


def to_yolo(v):
    """Label Studio box (percent, top-left, optional rotation) -> YOLO cx, cy, w, h (0-1)."""
    x, y, w, h = v['x'], v['y'], v['width'], v['height']
    r = math.radians(v.get('rotation', 0) or 0)
    if r:
        # axis-aligned box around the rotated rectangle (rotation is around the top-left corner)
        pts = [(0, 0), (w, 0), (w, h), (0, h)]
        xs = [x + px * math.cos(r) - py * math.sin(r) for px, py in pts]
        ys = [y + px * math.sin(r) + py * math.cos(r) for px, py in pts]
        x, y, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    x0, y0 = max(0.0, x / 100), max(0.0, y / 100)
    x1, y1 = min(1.0, (x + w) / 100), min(1.0, (y + h) / 100)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


stats = dict(tasks=len(tasks), written=0, background=0, boxes=0, skipped_unlabeled=0,
             skipped_cancelled=0, missing_image=0, duplicate_name=0)
unknown = {}
seen_names = set()

for t in tasks:
    anns = [a for a in t.get('annotations', []) if not a.get('was_cancelled')]
    if not anns:
        if t.get('annotations'):
            stats['skipped_cancelled'] += 1
        else:
            stats['skipped_unlabeled'] += 1
        continue
    ann = max(anns, key=lambda a: (a.get('updated_at') or '', a.get('id') or 0))

    ref = t.get('data', {}).get('image', '')
    name = Path(ref.split('?')[0]).name or t.get('file_upload', '')
    src = upload_dir / name
    if not src.exists():
        stats['missing_image'] += 1
        if stats['missing_image'] <= 5:
            print(f'  [missing] {src}')
        continue
    if name in seen_names:
        stats['duplicate_name'] += 1
        continue
    seen_names.add(name)

    lines = []
    for r in ann.get('result', []):
        if r.get('type') != 'rectanglelabels':
            continue
        v = r['value']
        for label in v.get('rectanglelabels', []):
            if label not in cls_id:
                unknown[label] = unknown.get(label, 0) + 1
                continue
            box = to_yolo(v)
            if box:
                lines.append(f"{cls_id[label]} {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}")

    dst = img_out / name
    if dst.exists():
        dst.unlink()
    if args.copy:
        shutil.copy2(src, dst)
    else:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    (lab_out / (Path(name).stem + '.txt')).write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
    stats['written'] += 1
    stats['boxes'] += len(lines)
    stats['background'] += 0 if lines else 1

print(json.dumps(stats, indent=2))
if unknown:
    print(f'[ERROR] Labels not in {args.classes}: {unknown}')
    print('        The class list changed. Fix the labels in Label Studio, or update classes.txt on purpose')
    print('        (a new class list means the champion model has to be retrained).')
    sys.exit(2)
if stats['written'] == 0:
    print('[ERROR] No images written.')
    sys.exit(1)
if stats['missing_image'] > 0:
    print(f"[WARNING] {stats['missing_image']} images listed in the JSON were not found in {upload_dir}.")
print('Done.')
