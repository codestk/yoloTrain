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
import math
import json
import os
import shutil
import sys
from datetime import datetime

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--new', required=True, help='best.pt of the new run')
    parser.add_argument('--champion', default=os.path.join('champion', 'best.pt'))
    parser.add_argument('--data', default='data.yaml')
    parser.add_argument('--imgsz', default=640, type=int)
    parser.add_argument('--batch', default=12, type=int)
    parser.add_argument('--device', default='0')
    parser.add_argument('--min_gain', default=0.0, type=float,
                        help='New model must beat the champion mAP50-95 by more than this')
    parser.add_argument('--max_class_drop', type=float, default=None,
                        help='Optional maximum absolute per-class AP50-95 drop; checks all represented classes')
    parser.add_argument('--snapshot', help='Validation snapshot manifest for this run')
    parser.add_argument('--class_weights', default='',
                        help='Weighted score for promotion, e.g. "Spider=3,Hair=3,dust_clump=3,Stone=2". '
                             'Classes not listed get weight 1. Empty = plain mAP50-95.')
    parser.add_argument('--dest', action='append', default=[], help='Where to copy the winning model')
    args = parser.parse_args()
    if not math.isfinite(args.min_gain) or args.min_gain < 0:
        parser.error('--min_gain must be finite and nonnegative')
    if args.max_class_drop is not None and (not math.isfinite(args.max_class_drop) or not 0 <= args.max_class_drop <= 1):
        parser.error('--max_class_drop must be between 0 and 1')
    weights_by_name = {}
    for item in filter(None, (x.strip() for x in args.class_weights.split(','))):
        name, _, value = item.partition('=')
        try:
            weights_by_name[name.strip()] = float(value)
        except ValueError:
            parser.error(f'--class_weights: bad item "{item}"')
        if not math.isfinite(weights_by_name[name.strip()]) or weights_by_name[name.strip()] < 0:
            parser.error(f'--class_weights: weight must be >= 0 in "{item}"')
    evaluations = {}
    model_names = {}


    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    champ_dir = os.path.dirname(args.champion) or '.'
    hist_dir = os.path.join(champ_dir, 'history')
    os.makedirs(hist_dir, exist_ok=True)


    def evaluate(weights, tag):
        model = YOLO(weights)
        model_names[tag] = model.names
        m = model.val(data=args.data, imgsz=args.imgsz, batch=args.batch, device=args.device,
                              plots=False, verbose=False, project='runs/compare', name=f'{ts}_{tag}',
                              exist_ok=True)
        scores = (float(m.box.map), float(m.box.map50), float(m.box.mp), float(m.box.mr))
        if not all(math.isfinite(v) for v in scores):
            raise ValueError(f'{tag}: non-finite validation scores')
        evaluations[tag] = {int(k): float(v) for k, v in zip(m.box.ap_class_index, m.box.ap)}
        if not evaluations[tag] or not all(math.isfinite(v) for v in evaluations[tag].values()):
            raise ValueError(f'{tag}: no valid per-class validation scores')
        return scores


    def weighted_score(tag, classes):
        names = model_names[tag]
        unknown = set(weights_by_name) - set(names.values())
        if unknown:
            raise ValueError(f'--class_weights: unknown class names {sorted(unknown)}')
        total = wsum = 0.0
        for k in classes:
            w = weights_by_name.get(names[k], 1.0)
            total += w * evaluations[tag][k]
            wsum += w
        return total / wsum if wsum else float('nan')


    def deploy(src):
        results = []
        for dst in args.dest:
            try:
                if not os.path.isdir(os.path.dirname(dst) or '.'):
                    raise FileNotFoundError(f'Destination folder missing: {dst}')
                if os.path.exists(dst):
                    shutil.copy2(dst, dst + f'.bak_{ts}')
                temporary = dst + f'.tmp_{ts}'
                try:
                    shutil.copy2(src, temporary)
                    os.replace(temporary, dst)
                finally:
                    if os.path.exists(temporary):
                        os.remove(temporary)
                results.append(dict(destination=dst, status='copied'))
                print(f'[DEPLOY OK] {dst}')
            except OSError as exc:
                results.append(dict(destination=dst, status='failed', error=str(exc)))
                print(f'[DEPLOY WARNING] {dst}: {exc}')
        return results


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
        if model_names['new'] != model_names['champion']:
            raise ValueError('New and champion class mappings differ; comparison rejected')
        if weights_by_name:
            common = sorted(set(evaluations['new']) & set(evaluations['champion']))
            score_new = weighted_score('new', common)
            score_champ = weighted_score('champion', common)
            names = model_names['new']
            print(f'  WEIGHTED  new={score_new:.4f}  champion={score_champ:.4f}  weights={weights_by_name}')
            for k in common:
                if names[k] in weights_by_name:
                    print(f'    {names[k]:24s} w={weights_by_name[names[k]]:<4g} new={evaluations["new"][k]:.3f}  champion={evaluations["champion"][k]:.3f}')
        else:
            score_new, score_champ = new[0], champ[0]
        promote = score_new > score_champ + args.min_gain
        if args.max_class_drop is not None:
            if evaluations['new'].keys() != evaluations['champion'].keys():
                raise ValueError('Validation class coverage differs')
            drops = {k: evaluations['champion'][k] - v for k, v in evaluations['new'].items()
                     if evaluations['champion'][k] - v > args.max_class_drop}
            if drops:
                print(f'[CLASS GUARD] Promotion rejected. AP drops: {drops}')
                promote = False
    else:
        champ = (float('nan'),) * 4
        score_new = score_champ = float('nan')
        print('No champion yet -> the new model becomes the champion.')
        promote = True

    report = dict(validation_snapshot=args.snapshot, new_model=args.new, scores_new=new, scores_champion=champ if os.path.exists(args.champion) else None,
                  min_gain=args.min_gain, max_class_drop=args.max_class_drop,
                  class_weights=weights_by_name or None,
                  score_new=score_new if math.isfinite(score_new) else None,
                  score_champion=score_champ if math.isfinite(score_champ) else None,
                  class_ap=evaluations, class_names=model_names, promotion_approved=promote)
    with open(os.path.join(hist_dir, f'comparison_{ts}.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
    log = os.path.join(champ_dir, 'history.csv')
    header = ['time', 'new_model', 'new_map50_95', 'new_map50', 'champ_map50_95', 'champ_map50', 'promoted',
              'new_score', 'champ_score', 'class_weights']
    if os.path.exists(log):
        with open(log, newline='', encoding='utf-8') as f:
            rows = list(csv.reader(f))
        if rows and rows[0] != header:  # older file: extend the header once, keep old rows
            rows[0] = header
            with open(log, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(rows)
    first = not os.path.exists(log)
    with open(log, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if first:
            w.writerow(header)
        w.writerow([ts, args.new, f'{new[0]:.4f}', f'{new[1]:.4f}', f'{champ[0]:.4f}', f'{champ[1]:.4f}', promote,
                    f'{score_new:.4f}', f'{score_champ:.4f}', args.class_weights])

    if promote:
        if os.path.exists(args.champion):
            shutil.copy2(args.champion, os.path.join(hist_dir, f'best_{ts}_replaced_{champ[0]:.4f}.pt'))
        shutil.copy2(args.new, args.champion)
        print(f'[PROMOTED] New model is better. Champion updated: {args.champion}')
        deployment = deploy(args.champion)
    else:
        deployment = []
        print(f'[KEPT] Promotion criteria not met (new score={score_new:.4f}, champion score={score_champ:.4f}, min_gain={args.min_gain}). '
              f'Production model unchanged.')

    report['deployment'] = deployment
    report['deployment_status'] = ('partial_failure' if any(x['status'] == 'failed' for x in deployment)
                                   else 'complete' if deployment else 'not_requested' if promote else 'not_promoted')
    with open(os.path.join(hist_dir, f'comparison_{ts}.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
    if report['deployment_status'] == 'partial_failure':
        return 3  # Training/comparison succeeded; deployment needs attention (2 is used by argparse errors).
    return 0

if __name__ == '__main__':
    sys.exit(main())
