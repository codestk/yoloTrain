#!/usr/bin/env python3
"""Rice Label Audit v2: YOLO label sanity checks, model disagreement, HTML review queue.

Install: pip install ultralytics pillow
Run: python rice_label_audit_v2.py --data D:\\yoloTrain\\custom_data --model D:\\yoloTrain\\runs\\detect\\train\\weights\\best.pt --base-url http://localhost:8080 --project-id 1 --tasks-json label_studio_tasks.json

Put the Label Studio JSON export at D:\\yoloTrain\\project-9.json. Task IDs are linked automatically.
No input dataset files are modified.
"""
import argparse, csv, json, html, math, re
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

IMAGE_EXT={'.jpg','.jpeg','.png','.bmp','.webp','.tif','.tiff'}
FIELDS=['priority','score','image','label','issue','reason','task_id','task_url','box_xyxy','confidence']

def get_images(root):
    p=root/'images'
    if not p.exists(): raise SystemExit(f'Missing images folder: {p}')
    return sorted(x for x in p.rglob('*') if x.suffix.lower() in IMAGE_EXT)

def filename_variants(name):
    """Normalize filename + Label Studio's optional 8-digit upload prefix."""
    name = Path(unquote(str(name).replace('\\', '/'))).name.lower().strip()
    options = {name} if name else set()
    # Strip only the Label Studio upload prefix, not arbitrary filename segments.
    if re.match(r'^[0-9a-f]{8}-', name):
        options.add(name[9:])
    return options


def parse_tasks(path):
    if not path:
        return {}
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f'[ERROR] Task JSON not found: {path}\nPlace project-9.json next to this Python script.')
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(obj, dict):
        obj = obj.get('tasks', obj.get('results', []))
    if not isinstance(obj, list):
        raise SystemExit('[ERROR] Project JSON must contain an array of Label Studio tasks.')
    out = {}
    for t in obj:
        if not isinstance(t, dict) or 'id' not in t:
            continue
        data = t.get('data') or {}
        for val in data.values():
            if not isinstance(val, str):
                continue
            name = Path(unquote(urlparse(val).path.replace('\\', '/'))).name
            if not name.lower().endswith(tuple(IMAGE_EXT)):
                continue
            for variant in filename_variants(name):
                out.setdefault(variant, set()).add(str(t['id']))
    print(f'[INFO] JSON loaded: {len(obj)} tasks, {len(out)} filename keys', flush=True)
    return out

def iou(a,b):
    x1=max(a[0],b[0]);y1=max(a[1],b[1]);x2=min(a[2],b[2]);y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    ar=lambda q:max(0,q[2]-q[0])*max(0,q[3]-q[1])
    return inter/max(ar(a)+ar(b)-inter,1e-12)

def read_boxes(path, nclasses):
    boxes=[];errors=[]
    if not path.exists():return boxes,['Label file missing']
    for ln,s in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        if not s.strip():continue
        v=s.split()
        try:
            if len(v)!=5: raise ValueError('expected 5 values')
            cid=int(v[0]); x,y,w,h=map(float,v[1:])
            if cid<0 or cid>=nclasses:raise ValueError('class out of range')
            if not all(math.isfinite(z) for z in (x,y,w,h)):raise ValueError('nonfinite coordinate')
            if w<=0 or h<=0 or x-w/2< -1e-6 or y-h/2< -1e-6 or x+w/2>1+1e-6 or y+h/2>1+1e-6:raise ValueError('invalid or out-of-range box')
            boxes.append((cid,(x-w/2,y-h/2,x+w/2,y+h/2)))
        except Exception as e:errors.append(f'Line {ln}: {e}')
    return boxes,errors

def csv_write(path, rows, fields):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def make_html(rows, out):
    # Entire page is self-contained. Review statuses persist in browser localStorage.
    payload=json.dumps(rows,ensure_ascii=False).replace('</','<\\/')
    doc='''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rice Label Audit v2</title>
<style>body{font:15px system-ui,sans-serif;margin:22px;background:#f5f7fa;color:#17212d}h1{margin-bottom:4px}.sub{color:#5b6471}input,select,button{padding:9px;border:1px solid #bbc3ce;border-radius:7px;background:white}button{cursor:pointer}.controls{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.stats{font-weight:600;margin:12px 0}table{width:100%;border-collapse:collapse;background:white}th,td{border-bottom:1px solid #e5e7eb;padding:9px;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#e9edf3}td.filename{max-width:280px;overflow-wrap:anywhere}td.reason{max-width:360px;overflow-wrap:anywhere}.high{color:#b42318;font-weight:700}.medium{color:#a15c00}.low{color:#475467}.done{background:#c8f7d4!important;color:#14532d}.done td{background:#c8f7d4!important}.done:hover td{background:#a9eebe!important}a{color:#1266b4}.pill{padding:3px 7px;border-radius:8px;background:#edf2fa}.note{padding:10px;background:#fff8e7;border-radius:7px;margin:10px 0}</style>
<h1>Rice Label Audit — Review Queue</h1><div class="sub">ติ๊กช่องตรวจแล้ว → ไฮไลต์สีเขียวและเปิด Task ใน Label Studio ทันที (เปิดแท็บใหม่)</div>
<div class="note">คะแนนเป็นลำดับความสำคัญในการตรวจ ไม่ใช่เปอร์เซ็นต์ความผิดพลาด หากไม่มีลิงก์ Task ให้ Export JSON จาก Label Studio แล้วรันสคริปต์ด้วย --tasks-json</div>
<div class="controls"><input id="q" placeholder="ค้นหาชื่อภาพ / class / issue" style="min-width:270px"><select id="priority"><option value="">ทุกระดับ</option><option>high</option><option>medium</option><option>low</option></select><select id="status"><option value="">ทุกสถานะ</option><option value="todo">ยังไม่ตรวจ</option><option value="done">ตรวจแล้ว</option></select><button id="export">Export สถานะ CSV</button><button id="reset">ล้างสถานะทั้งหมด</button></div>
<div class="stats" id="stats"></div><div style="overflow:auto"><table><thead><tr><th>ตรวจแล้ว</th><th>Priority</th><th>Score</th><th>Image</th><th>Issue / Reason</th><th>Task</th></tr></thead><tbody id="body"></tbody></table></div>
<script>const rows=__DATA__;const storageKey='rice-audit-v2:'+location.pathname;let saved={};try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){};
const el=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function key(r){return [r.image,r.issue,r.reason,r.box_xyxy].join('|')};function persist(){localStorage.setItem(storageKey,JSON.stringify(saved))}
function render(){let q=el('q').value.toLowerCase(),p=el('priority').value,s=el('status').value;let filtered=rows.filter(r=>(!p||r.priority===p)&&(!s||(s==='done'===!!saved[key(r)]))&&(!q||[r.image,r.issue,r.reason].join(' ').toLowerCase().includes(q)));
el('stats').textContent=`ทั้งหมด ${rows.length} รายการ | ตรวจแล้ว ${rows.filter(r=>saved[key(r)]).length} | แสดง ${filtered.length}`;
el('body').innerHTML=filtered.map(r=>`<tr class="${saved[key(r)]?'done':''}"><td><input type="checkbox" data-key="${esc(key(r))}" ${saved[key(r)]?'checked':''}></td><td class="${esc(r.priority)}">${esc(r.priority)}</td><td>${esc(r.score)}</td><td class="filename">${esc(r.image)}</td><td class="reason"><span class="pill">${esc(r.issue)}</span><div>${esc(r.reason)}</div></td><td>${r.task_url?`<a href="${esc(r.task_url)}" target="_blank" rel="noopener">Open Task ↗</a>`:'ไม่มี Task ID'}</td></tr>`).join('');
el('body').querySelectorAll('input[type=checkbox]').forEach(c=>c.addEventListener('change',()=>{
const r=rows.find(r=>key(r)===c.dataset.key);
if(c.checked && r && r.task_url){
  // Open synchronously in the user's checkbox gesture to avoid popup blocking.
  window.open(r.task_url,'_blank','noopener');
}
saved[c.dataset.key]=c.checked;persist();render()
}))}
['q','priority','status'].forEach(id=>el(id).addEventListener('input',render));el('reset').onclick=()=>{if(confirm('ล้างสถานะตรวจแล้วทั้งหมด?')){saved={};persist();render()}};
el('export').onclick=()=>{let lines=['image,issue,reason,reviewed'];for(let r of rows){let vals=[r.image,r.issue,r.reason,saved[key(r)]?'yes':'no'];lines.push(vals.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(','))}let blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv;charset=utf-8'});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='review_status.csv';a.click();URL.revokeObjectURL(a.href)};render();</script></html>'''
    (out/'review_queue.html').write_text(doc.replace('__DATA__',payload),encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(description='Non-destructive rice YOLO dataset audit + Label Studio review page')
    ap.add_argument('--data',required=True,help='Dataset root containing images/, labels/, classes.txt')
    ap.add_argument('--model',help='Ultralytics YOLO model path; omit for label-format-only checks')
    ap.add_argument('--imgsz',type=int,default=640);ap.add_argument('--conf',type=float,default=.50);ap.add_argument('--iou',type=float,default=.30,help='Human vs prediction match IoU threshold')
    ap.add_argument('--base-url',default='http://pc-max:8080');ap.add_argument('--project-id',type=int,default=9)
    ap.add_argument('--tasks-json',default=str(Path(__file__).resolve().parent / 'project-9.json'),help='Label Studio JSON export with task IDs (default: project-9.json next to script)')
    ap.add_argument('--output',default='rice_audit_v2_output');ap.add_argument('--device',default=None)
    args=ap.parse_args();root=Path(args.data);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    names=[s.strip() for s in (root/'classes.txt').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
    images=get_images(root);tasks=parse_tasks(args.tasks_json);model=None
    if args.model:
        from ultralytics import YOLO
        model=YOLO(args.model)
        mnames=[model.names[i] for i in range(len(model.names))]
        if names!=mnames:raise SystemExit('ERROR: classes.txt does not match model.names by index. Stopping to avoid wrong class comparisons.\nDataset: '+str(names)+'\nModel: '+str(mnames))
    issues=[];counts=Counter();type_counts=Counter();mapped=0;ambiguous=0
    for idx,img in enumerate(images,1):
        rel=img.relative_to(root/'images');lab=root/'labels'/rel.with_suffix('.txt')
        boxes,errors=read_boxes(lab,len(names))
        for cid,_ in boxes:counts[names[cid]]+=1
        candidates=set()
        for variant in filename_variants(img.name):
            candidates.update(tasks.get(variant, set()))
        tid=next(iter(candidates)) if len(candidates)==1 else ''
        if tid:mapped+=1
        elif len(candidates)>1:ambiguous+=1
        url=(f'{args.base_url.rstrip("/")}/projects/{args.project_id}/data?task={quote(tid)}' if tid and args.project_id else '')
        def add(priority,score,issue,reason,xy='',confidence=''):
            issues.append(dict(priority=priority,score=round(score,2),image=img.name,label=lab.name,issue=issue,reason=reason,task_id=tid,task_url=url,box_xyxy=xy,confidence=confidence))
            type_counts[issue]+=1
        for e in errors:add('high',100,'invalid_box',e)
        if model:
            from PIL import Image
            with Image.open(img) as im:w,h=im.size
            pred=model.predict(source=str(img),imgsz=args.imgsz,conf=args.conf,verbose=False,device=args.device)[0]
            predicted=[]
            if pred.boxes is not None:
                for b in pred.boxes:
                    cid=int(b.cls.item());conf=float(b.conf.item());xy=[float(v) for v in b.xyxy[0].tolist()]
                    predicted.append((cid,(xy[0]/w,xy[1]/h,xy[2]/w,xy[3]/h),conf))
            used=set()
            for pc,pb,confidence in predicted:
                overlaps=[(iou(pb,hb),j,hc) for j,(hc,hb) in enumerate(boxes) if j not in used]
                if overlaps:
                    overlap,j,hc=max(overlaps)
                else:overlap,j,hc=0,-1,-1
                if overlap>=args.iou:
                    used.add(j)
                    if hc!=pc:add('high',75+20*confidence,'class_disagreement',f'Human={names[hc]}, AI={names[pc]}, confidence={confidence:.2f}, IoU={overlap:.2f}',str(pb),f'{confidence:.3f}')
                else:
                    add('medium',40+45*confidence,'possible_missing_annotation',f'AI={names[pc]}, confidence={confidence:.2f}; unmatched box',str(pb),f'{confidence:.3f}')
            for j,(hc,hb) in enumerate(boxes):
                if j not in used:add('low',10,'human_box_not_matched',f'Human={names[hc]} has no overlapping AI detection; AI may have missed it',str(hb))
        if idx%100==0 or idx==len(images):print(f'Checked {idx}/{len(images)}',flush=True)
    issues.sort(key=lambda r:(-float(r['score']),r['image']))
    csv_write(out/'review_queue.csv',issues,FIELDS)
    csv_write(out/'class_counts.csv',[{'class':name,'count':counts[name]} for name in names],['class','count'])
    summary={'images':len(images),'classes':len(names),'issues':len(issues),'issues_by_type':dict(type_counts),'tasks_mapped':mapped,'ambiguous_task_matches':ambiguous,'warning':'Model disagreement is not proof of incorrect human annotation. Do not change labels just to reach zero alerts.'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    make_html(issues,out)
    print('Finished:',out);print(json.dumps(summary,ensure_ascii=False,indent=2))
    if mapped == 0: print('[WARNING] No task IDs matched. Check that project-9.json was exported from the same Label Studio project as this YOLO dataset.')

if __name__=='__main__':main()
