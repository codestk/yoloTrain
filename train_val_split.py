"""
Train/val split with a FROZEN validation set.

- The list of validation images is stored in val_split.txt (one image file stem per line).
- If val_split.txt exists, those images always go to validation; everything else goes to train.
- If val_split.txt does not exist yet, the current data/validation/images folder is frozen as the
  validation set (keeps the split you already have). If that folder does not exist either,
  a new split is made with a fixed seed.
- Images that are NEW (never seen before) go to train, except a small deterministic share
  (--new_to_val, default 10%) that is added to validation so rare classes keep growing in val.
  The choice is based on the file name, so the same image always lands in the same set.
- Images never move from train to validation, so models trained earlier never "see" val images.
- Use --reset only if you really want a brand new split (old scores will no longer be comparable).
"""
from pathlib import Path
import argparse
import hashlib
import os
import random
import shutil
import sys

IMG_EXTS = {'.jpg', '.jpeg', '.png'}

parser = argparse.ArgumentParser()
parser.add_argument('--datapath', required=True, help='Folder with images/ and labels/')
parser.add_argument('--train_pct', default=.9, type=float, help='Train share for a brand new split only')
parser.add_argument('--new_to_val', default=.1, type=float, help='Share of NEW images added to validation')
parser.add_argument('--manifest', default='val_split.txt', help='File listing validation image stems')
parser.add_argument('--seen', default='seen_images.txt', help='File listing every image already split')
parser.add_argument('--seed', default=42, type=int)
parser.add_argument('--reset', action='store_true', help='Ignore the manifest and make a new split')
args = parser.parse_args()

data_path = args.datapath
if not os.path.isdir(data_path):
    print(f'ERROR: Directory "{data_path}" not found.')
    sys.exit(1)
if not (0.01 <= args.train_pct <= 0.99) or not (0.0 <= args.new_to_val <= 0.5):
    print('ERROR: train_pct must be .01-.99 and new_to_val must be 0-.5')
    sys.exit(1)

input_image_path = os.path.join(data_path, 'images')
input_label_path = os.path.join(data_path, 'labels')
if not os.path.isdir(input_image_path) or not os.path.isdir(input_label_path):
    print(f'ERROR: "images" or "labels" folder not found inside "{data_path}".')
    sys.exit(1)

cwd = os.getcwd()
train_img_path = os.path.join(cwd, 'data', 'train', 'images')
train_txt_path = os.path.join(cwd, 'data', 'train', 'labels')
val_img_path = os.path.join(cwd, 'data', 'validation', 'images')
val_txt_path = os.path.join(cwd, 'data', 'validation', 'labels')


def read_list(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}


def write_list(path, items):
    with open(path, 'w', encoding='utf-8') as f:
        for s in sorted(items):
            f.write(s + '\n')


def goes_to_val(stem, share):
    """Deterministic: the same file name always gives the same answer."""
    h = int(hashlib.md5(stem.encode('utf-8')).hexdigest()[:8], 16)
    return (h % 10000) < share * 10000


img_files = [p for p in Path(input_image_path).rglob('*') if p.suffix.lower() in IMG_EXTS]
all_stems = {p.stem for p in img_files}
print(f'Found {len(img_files)} image files.')

val_stems = None if args.reset else read_list(args.manifest)
seen = None if args.reset else read_list(args.seen)

if val_stems is not None:
    print(f'Using frozen validation list {args.manifest} ({len(val_stems)} images).')
    if seen is None:
        # Older manifest without a seen-list: treat everything present now as already seen.
        seen = set(all_stems)
elif not args.reset and os.path.isdir(val_img_path) and any(os.scandir(val_img_path)):
    val_stems = {p.stem for p in Path(val_img_path).iterdir() if p.suffix.lower() in IMG_EXTS}
    seen = set(all_stems)
    print(f'No {args.manifest} yet: freezing the CURRENT data/validation ({len(val_stems)} images).')
else:
    stems = sorted(all_stems)
    random.Random(args.seed).shuffle(stems)
    n_train = int(len(stems) * args.train_pct)
    val_stems = set(stems[n_train:])
    seen = set(all_stems)
    print(f'Making a NEW split with seed={args.seed} ({len(val_stems)} validation images).')

new_stems = all_stems - seen
new_val = {s for s in new_stems if goes_to_val(s, args.new_to_val)}
if new_stems:
    print(f'New images: {len(new_stems)} -> {len(new_val)} to validation, '
          f'{len(new_stems) - len(new_val)} to train.')
val_stems |= new_val
seen |= all_stems

missing = val_stems - all_stems
if missing:
    print(f'Note: {len(missing)} validation images listed in {args.manifest} are no longer in custom_data.')

write_list(args.manifest, val_stems)
write_list(args.seen, seen)

# Clean output folders and copy
for d in [train_img_path, train_txt_path, val_img_path, val_txt_path]:
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)

n_train = n_val = 0
for img in img_files:
    to_val = img.stem in val_stems
    dst_img, dst_txt = (val_img_path, val_txt_path) if to_val else (train_img_path, train_txt_path)
    shutil.copy(img, os.path.join(dst_img, img.name))
    txt = os.path.join(input_label_path, img.stem + '.txt')
    if os.path.exists(txt):  # no label file = background image
        shutil.copy(txt, os.path.join(dst_txt, img.stem + '.txt'))
    if to_val:
        n_val += 1
    else:
        n_train += 1

print(f'Train: {n_train} images, Validation: {n_val} images.')
print('Data splitting process complete.')
