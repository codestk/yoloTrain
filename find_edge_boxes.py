"""
List Label Studio boxes that touch the image edge (half grains cut off by the frame).

Rule decided 2026-11-13: half grains at the image edge are NOT labelled.
This script finds the old boxes that still touch the edge so they can be removed
in Label Studio. It only reads the export; it never changes labels.

Usage (from D:\\yoloTrain):
    python find_edge_boxes.py
    python find_edge_boxes.py --json custom_data\\project-9-at-....json --margin 5

Output (in rice_audit_v2_output):
    edge_boxes.csv   one row per box
    edge_boxes.html  one row per task, with picture + link to open the task
"""
import argparse
import csv
import glob
import html
import json
import math
import os
import statistics
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--json', default=None,
                help='Label Studio JSON export. Default: newest custom_data/*.json, else project-9.json')
ap.add_argument('--margin', type=float, default=5,
                help='A box closer than this many pixels to the image edge counts as an edge box')
ap.add_argument('--ls-url', default='http://pc-max:8080')
ap.add_argument('--project', default='9')
ap.add_argument('--upload-dir', default=r'D:\docker\label-studio\media\upload\9',
                help='Folder with the original images (for the pictures in the HTML)')
ap.add_argument('--out', default='rice_audit_v2_output')
args = ap.parse_args()

here = Path(__file__).resolve().parent
json_path = args.json
if not json_path:
    found = sorted(glob.glob(str(here / 'custom_data' / '*.json')), key=os.path.getmtime)
    json_path = found[-1] if found else str(here / 'project-9.json')
print(f'Reading {json_path}')
tasks = json.loads(Path(json_path).read_text(encoding='utf-8-sig'))
if isinstance(tasks, dict):
    tasks = tasks.get('tasks', [])


def aabb_percent(v):
    """Label Studio box (percent, top-left, optional rotation) -> x0, y0, x1, y1 in percent."""
    x, y, w, h = v['x'], v['y'], v['width'], v['height']
    r = math.radians(v.get('rotation', 0) or 0)
    if r:
        pts = [(0, 0), (w, 0), (w, h), (0, h)]
        xs = [x + px * math.cos(r) - py * math.sin(r) for px, py in pts]
        ys = [y + px * math.sin(r) + py * math.cos(r) for px, py in pts]
        return min(xs), min(ys), max(xs), max(ys)
    return x, y, x + w, y + h


boxes = []  # every labelled box
for t in tasks:
    anns = [a for a in t.get('annotations', []) if not a.get('was_cancelled')]
    if not anns:
        continue
    ann = max(anns, key=lambda a: (a.get('updated_at') or '', a.get('id') or 0))
    ref = t.get('data', {}).get('image', '')
    name = Path(ref.split('?')[0]).name or t.get('file_upload', '')
    for r in ann.get('result', []):
        if r.get('type') != 'rectanglelabels':
            continue
        v = r['value']
        W = r.get('original_width') or 0
        H = r.get('original_height') or 0
        if not W or not H:
            continue
        x0, y0, x1, y1 = aabb_percent(v)
        px0, py0, px1, py1 = x0 * W / 100, y0 * H / 100, x1 * W / 100, y1 * H / 100
        sides = []
        if px0 <= args.margin:
            sides.append('left')
        if py0 <= args.margin:
            sides.append('top')
        if px1 >= W - args.margin:
            sides.append('right')
        if py1 >= H - args.margin:
            sides.append('bottom')
        for label in v.get('rectanglelabels', []):
            boxes.append(dict(
                task_id=t.get('id'), image=name, label=label, sides=sides,
                long_side=max(px1 - px0, py1 - py0),
                box_pct=(max(0, x0), max(0, y0), min(100, x1), min(100, y1)),
            ))

# typical size of each class, from boxes NOT at the edge -> how much of the grain is visible
normal = {}
for b in boxes:
    if not b['sides']:
        normal.setdefault(b['label'], []).append(b['long_side'])
median = {k: statistics.median(v) for k, v in normal.items()}

edge = [b for b in boxes if b['sides']]
for b in edge:
    m = median.get(b['label'])
    b['size_pct'] = round(100 * b['long_side'] / m) if m else None

out = here / args.out
out.mkdir(exist_ok=True)

def task_url(tid):
    return f"{args.ls_url}/projects/{args.project}/data?task={tid}"

with open(out / 'edge_boxes.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['task_id', 'task_url', 'image', 'label', 'edge', 'size_vs_normal_%'])
    for b in sorted(edge, key=lambda b: (b['label'], b['task_id'])):
        w.writerow([b['task_id'], task_url(b['task_id']), b['image'], b['label'],
                    '+'.join(b['sides']), b['size_pct'] if b['size_pct'] is not None else ''])

# ---- HTML: one row per task ----
by_task = {}
for b in edge:
    by_task.setdefault(b['task_id'], []).append(b)
order = sorted(by_task, key=lambda tid: min((b['size_pct'] or 999) for b in by_task[tid]))

counts = {}
for b in edge:
    counts[b['label']] = counts.get(b['label'], 0) + 1
count_html = ' · '.join(f"{html.escape(k)} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))

upload = Path(args.upload_dir)
rows = []
for tid in order:
    bs = by_task[tid]
    img = bs[0]['image']
    full = (args.upload_dir.rstrip('\\/') + '/' + img).replace('\\', '/')
    src = html.escape(('file:///' + full) if full[1:3] == ':/' else full)
    rects = ''.join(
        f'<div class="r" style="left:{b["box_pct"][0]:.2f}%;top:{b["box_pct"][1]:.2f}%;'
        f'width:{b["box_pct"][2]-b["box_pct"][0]:.2f}%;height:{b["box_pct"][3]-b["box_pct"][1]:.2f}%"></div>'
        for b in bs)
    rows.append((tid, img, src, rects, bs))

THAI = {'left': 'ซ้าย', 'right': 'ขวา', 'top': 'บน', 'bottom': 'ล่าง'}
tr = []
for tid, img, src, rects, bs in rows:
    lines = '<br>'.join(
        f'<b>{html.escape(b["label"])}</b> — ขอบ{"+".join(THAI[s] for s in b["sides"])}'
        + (f' — ขนาด {b["size_pct"]}% ของเม็ดปกติ' if b['size_pct'] is not None else '')
        for b in bs)
    tr.append(
        f'<tr id="t{tid}"><td><input type="checkbox" data-id="{tid}"></td>'
        f'<td><div class="pic"><img loading="lazy" src="{src}" alt="">{rects}</div></td>'
        f'<td>{lines}<div class="fn">{html.escape(img)}</div></td>'
        f'<td><a href="{task_url(tid)}" target="_blank" data-id="{tid}">เปิด task {tid}</a></td></tr>')

page = f"""<!doctype html><meta charset="utf-8"><title>กล่องชิดขอบภาพ</title>
<style>
body{{font:15px system-ui,sans-serif;margin:22px;background:#f5f7fa;color:#17212d}}
table{{border-collapse:collapse;background:#fff;width:100%}}
td,th{{border-bottom:1px solid #e5e7eb;padding:8px;vertical-align:top;text-align:left}}
th{{position:sticky;top:0;background:#e9edf3}}
.pic{{position:relative;width:320px;display:inline-block;background:#ddd}}
.pic img{{width:100%;display:block}}
.r{{position:absolute;border:2px solid #ff2a2a;box-sizing:border-box}}
.fn{{color:#667085;font-size:12px;margin-top:6px;overflow-wrap:anywhere}}
.note{{padding:10px;background:#fff8e7;border-radius:7px;margin:10px 0}}
tr.done td{{background:#c8f7d4}}
</style>
<h1>กล่องที่ชิดขอบภาพ ({len(edge)} กล่อง ใน {len(by_task)} task)</h1>
<div class="note">กติกา: เม็ดครึ่งเม็ดที่ถูกขอบภาพตัด <b>ไม่ต้องตีกล่อง</b> → เปิด task แล้วลบกล่องสีแดงที่เป็นเม็ดครึ่งเม็ด<br>
ถ้าเห็นเกือบเต็มเม็ดหรือเป็นแมลง/ของที่ยังชัด จะเก็บไว้ก็ได้ — ตัดสินจากภาพจริง<br>
เรียงจากกล่องที่ถูกตัดเยอะที่สุด (ขนาดเทียบเม็ดปกติน้อยสุด) ขึ้นก่อน · ติ๊กแล้วจำไว้ในเบราว์เซอร์นี้<br>
ข้อมูลจาก: {html.escape(os.path.basename(json_path))} · ระยะขอบ {args.margin:g} px</div>
<p>{count_html}</p>
<p id="stat"></p>
<table><tr><th>ตรวจแล้ว</th><th>ภาพ (กรอบแดง = กล่องชิดขอบ)</th><th>กล่อง</th><th>Label Studio</th></tr>
{''.join(tr)}
</table>
<script>
const KEY='edge_boxes_done';
let done={{}};try{{done=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
function save(){{try{{localStorage.setItem(KEY,JSON.stringify(done))}}catch(e){{}}}}
function paint(){{let n=0;document.querySelectorAll('input[data-id]').forEach(c=>{{const d=!!done[c.dataset.id];c.checked=d;
document.getElementById('t'+c.dataset.id).classList.toggle('done',d);if(d)n++}});
document.getElementById('stat').textContent='ตรวจแล้ว '+n+' / {len(by_task)} task';}}
document.addEventListener('change',e=>{{if(e.target.dataset.id){{done[e.target.dataset.id]=e.target.checked;save();paint()}}}});
document.addEventListener('click',e=>{{if(e.target.tagName==='A'&&e.target.dataset.id){{done[e.target.dataset.id]=true;save();paint()}}}});
paint();
</script>
"""
(out / 'edge_boxes.html').write_text(page, encoding='utf-8')

print(f'Edge boxes: {len(edge)} in {len(by_task)} tasks (of {len(boxes)} boxes total)')
for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
    print(f'  {k}: {v}')
print(f'Wrote {out / "edge_boxes.csv"}')
print(f'Wrote {out / "edge_boxes.html"}')
