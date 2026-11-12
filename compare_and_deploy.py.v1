"""
Compare a newly trained model with the current champion on the SAME validation set,
and deploy it only if it is better.

champion/best.pt      the best model so far (the one that should be in production)
champion/history/     every replaced champion, kept as a backup
champion/history.csv  log of every comparison

Usage:
  python compare_and_deploy.py --new runs/detect/<run>/weights/best.pt --dest <path1> --dest <path2>
"""
import argparse
import csv
import os
import shutil
import sys
from datetime import datetime

from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument('--new', required=True, help='best.pt of the new run')
parser.add_argument('--champion', default=os.path.join('champion', 'best.pt'))
parser.add_argument('--data', default='data.yaml')
parser.add_argument('--imgsz', default=640, type=int)
parser.add_argument('--batch', default=12, type=int)
parser.add_argument('--device', default='0')
parser.add_argument('--min_gain', default=0.0, type=float,
                    help='New model must beat the champion mAP50-95 by more than this')
parser.add_argument('--dest', action='append', default=[], help='Where to copy the winning model')
args = parser.parse_args()

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
champ_dir = os.path.dirname(args.champion) or '.'
hist_dir = os.path.join(champ_dir, 'history')
os.makedirs(hist_dir, exist_ok=True)


def evaluate(weights, tag):
    m = YOLO(weights).val(data=args.data, imgsz=args.imgsz, batch=args.batch, device=args.device,
                          plots=False, verbose=False, project='runs/compare', name=f'{ts}_{tag}',
                          exist_ok=True)
    return float(m.box.map), float(m.box.map50), float(m.box.mp), float(m.box.mr)


def deploy(src):
    for dst in args.dest:
        d = os.path.dirname(dst)
        if d and not os.path.isdir(d):
            print(f'  [skip] folder not found: {d}')
            continue
        if os.path.exists(dst):
            shutil.copy2(dst, dst + f'.bak_{ts}')
        shutil.copy2(src, dst)
        print(f'  [OK] copied to {dst}')


if not os.path.exists(args.new):
    print(f'[ERROR] New model not found: {args.new}')
    sys.exit(1)

print('Evaluating NEW model ...')
new = evaluate(args.new, 'new')
print(f'  NEW       mAP50-95={new[0]:.4f}  mAP50={new[1]:.4f}  P={new[2]:.4f}  R={new[3]:.4f}')

if os.path.exists(args.champion):
    print('Evaluating CHAMPION model on the same validation set ...')
    champ = evaluate(args.champion, 'champion')
    print(f'  CHAMPION  mAP50-95={champ[0]:.4f}  mAP50={champ[1]:.4f}  P={champ[2]:.4f}  R={champ[3]:.4f}')
    promote = new[0] > champ[0] + args.min_gain
else:
    champ = (float('nan'),) * 4
    print('No champion yet -> the new model becomes the champion.')
    promote = True

log = os.path.join(champ_dir, 'history.csv')
first = not os.path.exists(log)
with open(log, 'a', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    if first:
        w.writerow(['time', 'new_model', 'new_map50_95', 'new_map50', 'champ_map50_95', 'champ_map50', 'promoted'])
    w.writerow([ts, args.new, f'{new[0]:.4f}', f'{new[1]:.4f}', f'{champ[0]:.4f}', f'{champ[1]:.4f}', promote])

if promote:
    if os.path.exists(args.champion):
        shutil.copy2(args.champion, os.path.join(hist_dir, f'best_{ts}_replaced_{champ[0]:.4f}.pt'))
    shutil.copy2(args.new, args.champion)
    print(f'[PROMOTED] New model is better. Champion updated: {args.champion}')
    deploy(args.champion)
else:
    print(f'[KEPT] New model is NOT better ({new[0]:.4f} <= {champ[0]:.4f} + {args.min_gain}). '
          f'Production model unchanged.')
