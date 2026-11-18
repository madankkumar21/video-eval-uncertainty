"""H7: can a person count the action from the same 8 frames the models saw?

Separates "the models don't use the video" from "8 sampled frames can't support counting".

  uv run python scripts/human_count.py sheet    # pick 20 items, write the blind sheet + an empty answer file
  uv run python scripts/human_count.py score    # grade the filled answer file against the dataset truth

The sheet (results/validation/human_count_sheet.html) shows each item's 8 frames, the question and
the options in the original order, i.e. exactly what the models saw on the unshuffled run. It holds
no answers. Items are chosen deterministically (seed 7) from the first 100, stratified by the true
answer value so the sample is not all "3". The answer file (human_count.csv) is filled by hand.

Pre-registered rule (docs/PHASE2_PLAN.md, H7): H7 holds if the person is right on at least 15 of 20 from the
frames alone. Falsified at 14 or fewer. A second pass over the misses with the full video says
whether the frames or the question were the problem.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import DATA_DIR, RESULTS_DIR  # noqa: E402
from core.stats import wilson  # noqa: E402

LETTERS = "ABC"
N_ITEMS = 20
SEED = 7
PASS_K = 15
FRAME_KEY = "f8-e768-q85"
MODEL_RUNS = {"haiku45": "haiku45-action_count-n100", "sonnet55": "sonnet55-action_count-n100",
              "opus55": "opus55-action_count-n100"}
VALIDATION = RESULTS_DIR / "validation"


def load_item_values(path: Path = VALIDATION / "item_values.json") -> dict:
    """item_id -> {answer, candidates} for items in file order (written by handoff_analysis.py --dump-items)."""
    return json.loads(path.read_text())


def select_items(values: dict, n: int = N_ITEMS, seed: int = SEED, pool: int = 100) -> list[str]:
    """n item ids from the first `pool`, stratified by answer value, proportional, seeded. Order shuffled."""
    ids = list(values)[:pool]
    by_answer: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        by_answer[values[i]["answer"]].append(i)
    rng = random.Random(seed)
    # largest-remainder apportionment of n across answer values
    quotas = {a: n * len(v) / len(ids) for a, v in by_answer.items()}
    take = {a: int(q) for a, q in quotas.items()}
    for a in sorted(quotas, key=lambda a: quotas[a] - take[a], reverse=True)[: n - sum(take.values())]:
        take[a] += 1
    chosen = []
    for a in sorted(by_answer):
        chosen += rng.sample(sorted(by_answer[a]), take[a])
    rng.shuffle(chosen)
    return chosen


def frames_dir(item_id: str, data_dir: Path = DATA_DIR) -> Path:
    task, stem = item_id.split(":", 1)
    return data_dir / "frames" / task / stem / FRAME_KEY


def question_for(item_id: str, data_dir: Path = DATA_DIR) -> str:
    """The question text from the dataset file (needs data/json/<task>.json, present after any run)."""
    task, stem = item_id.split(":", 1)
    rows = json.loads((data_dir / "json" / f"{task}.json").read_text())
    for r in rows:
        if Path(r["video"]).stem == stem:
            return r["question"]
    raise KeyError(item_id)


def write_sheet(chosen: list[str], values: dict, data_dir: Path = DATA_DIR, out_dir: Path = VALIDATION) -> tuple[Path, Path]:
    """An interactive sheet: click a letter, sure/unsure and impossible per item; progress is kept in
    localStorage; "Export CSV" downloads human_count.csv with the same columns the scorer reads.
    The sheet holds no answers. Click a frame to enlarge it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    head = """<!doctype html><meta charset='utf-8'><title>Human count sheet</title>
<style>
body{font-family:sans-serif;max-width:1100px;margin:2em auto;padding:0 1em}
.item{border-top:2px solid #ccc;padding:1.5em 0}.frames img{width:260px;margin:3px;cursor:zoom-in}
.opts{font-size:1.2em}.ctl{display:flex;flex-wrap:wrap;gap:.6em 1.6em;align-items:center;margin-top:.6em}
.ctl label{cursor:pointer;padding:.25em .6em;border:1px solid #bbb;border-radius:6px}
.ctl input[type=radio]{margin-right:.35em}.ctl label:has(input:checked){background:#2f6fb5;color:#fff;border-color:#2f6fb5}
.ctl input[type=text]{width:22em;padding:.3em}
#bar{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:.6em 0;display:flex;gap:1em;align-items:center;z-index:2}
#bar button{padding:.5em 1em;font-size:1em}.done{color:#3f9a5e;font-weight:600}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.9);display:none;align-items:center;justify-content:center;z-index:9}
#zoom img{max-width:96vw;max-height:96vh}.pass2{display:none}body.pass2on .pass2{display:flex}
</style>
<div id='bar'><b>Human count: 20 items, 8 frames each</b> <span id='prog'>0 / 20 answered</span>
<button id='export'>Export CSV</button><button id='copy'>Copy CSV</button>
<label><input type='checkbox' id='p2'> show full-video pass (step 4)</label><button id='reset'>Clear all</button></div>
<p>Same frames, question and option order the models saw. Count from the frames only. For each item click a letter,
sure or unsure, and whether the frames made a count impossible (still give a letter). Progress saves in this browser where storage is allowed; the Live CSV box at the top always shows the current answers.
When all 20 have a letter, press <b>Export CSV</b> and send the file. Do not open any results file until you have scored.</p>
<div id='zoom'><img></div>
<details id='csvbox'><summary>Live CSV (select all and copy if Export and Copy are blocked)</summary>
<textarea id='csvtext' readonly rows='12' onclick='this.select()' style='width:100%;font-family:monospace;font-size:12px'></textarea></details>
"""
    parts = [head]
    for k, i in enumerate(chosen, 1):
        d = frames_dir(i, data_dir)
        imgs = sorted(d.glob("*.jpg"))
        if len(imgs) != 8:
            raise FileNotFoundError(f"{i}: expected 8 frames in {d}, found {len(imgs)}")
        q = html.escape(question_for(i, data_dir))
        iid = html.escape(i)
        parts.append(f"<div class='item' data-n='{k}' data-id='{iid}'><h2>{k}. <code>{iid}</code></h2><div class='frames'>")
        for p in imgs:
            b = base64.b64encode(p.read_bytes()).decode()
            parts.append(f"<img src='data:image/jpeg;base64,{b}'>")
        parts.append("</div>")
        parts.append(f"<p class='opts'><b>{q}</b><br>" + " &nbsp; ".join(
            f"({L}) {html.escape(c)}" for L, c in zip(LETTERS, values[i]["candidates"])) + "</p>")
        letters = "".join(f"<label><input type='radio' name='letter{k}' value='{L}'>{L}</label>" for L in LETTERS[:len(values[i]["candidates"])])
        parts.append(f"<div class='ctl'><span>count:</span>{letters}</div>")
        parts.append(f"<div class='ctl'><span>confidence:</span><label><input type='radio' name='conf{k}' value='sure'>sure</label>"
                     f"<label><input type='radio' name='conf{k}' value='unsure'>unsure</label>"
                     f"<span>impossible from frames:</span><label><input type='radio' name='imp{k}' value='no'>no</label>"
                     f"<label><input type='radio' name='imp{k}' value='yes'>yes</label></div>")
        full = "".join(f"<label><input type='radio' name='full{k}' value='{L}'>{L}</label>" for L in LETTERS[:len(values[i]["candidates"])])
        parts.append(f"<div class='ctl pass2'><span>full video:</span>{full}"
                     f"<input type='text' name='note{k}' placeholder='note (label looks wrong, etc.)'></div></div>")
    script = """
<script>
(function(){
// Works with or without browser storage: the CSV is built from the buttons on the page, not from saved state.
const N=20, KEY='human_count_v1';
let store=null; try{ store=window.localStorage; store.getItem(KEY); }catch(e){ store=null; }
let saved={}; try{ saved=JSON.parse((store&&store.getItem(KEY))||'{}'); }catch(e){ saved={}; }
const seen={}, secs={};
function val(div,field){const el=div.querySelector("input[name^='"+field+"']:checked"); return el?el.value:'';}
function rowOf(div){const k=div.dataset.n; const note=div.querySelector('input[type=text]');
  return {n:k,id:div.dataset.id,letter:val(div,'letter'),conf:val(div,'conf'),imp:val(div,'imp'),
          seconds:secs[k]||(saved[k]&&saved[k].seconds)||'',full:val(div,'full'),note:note?note.value:''};}
function rows(){return Array.from(document.querySelectorAll('.item')).map(rowOf);}
function csv(){const esc=v=>{v=(v??'').toString(); return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;};
  const out=[['n','item_id','letter','confidence','impossible_from_frames','seconds','letter_full_video','note'].join(',')];
  rows().forEach(r=>out.push([r.n,r.id,r.letter,r.conf,r.imp,r.seconds,r.full,esc(r.note)].join(',')));
  return out.join('\\n')+'\\n';}
function save(){ if(!store) return; try{ const st={}; rows().forEach(r=>{st[r.n]=r;}); store.setItem(KEY,JSON.stringify(st)); }catch(e){} }
function refresh(){const n=rows().filter(r=>r.letter).length;
  const el=document.getElementById('prog'); if(el){el.textContent=n+' / '+N+' answered'; el.className=n===N?'done':'';}
  const ta=document.getElementById('csvtext'); if(ta) ta.value=csv();}
// restore saved selections, if storage worked last time
document.querySelectorAll('.item').forEach(div=>{const r=saved[div.dataset.n]; if(!r) return;
  [['letter',r.letter],['conf',r.conf],['imp',r.imp],['full',r.full]].forEach(([f,v])=>{
    if(v){const el=div.querySelector("input[name^='"+f+"'][value='"+v+"']"); if(el) el.checked=true;}});
  const note=div.querySelector('input[type=text]'); if(note&&r.note) note.value=r.note;});
// one delegated listener for every click and keystroke
document.addEventListener('change',e=>{const div=e.target.closest('.item'); if(!div) return;
  const k=div.dataset.n; if(e.target.name&&e.target.name.startsWith('letter')&&!secs[k]&&seen[k]) secs[k]=Math.round((Date.now()-seen[k])/1000);
  save(); refresh();});
document.addEventListener('input',e=>{ if(e.target.closest('.item')){save(); refresh();} });
if('IntersectionObserver' in window){const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){const k=e.target.dataset.n; if(!seen[k]) seen[k]=Date.now();}}),{threshold:.3});
  document.querySelectorAll('.item').forEach(d=>io.observe(d));}
const byId=id=>document.getElementById(id);
byId('export').onclick=()=>{refresh(); try{const b=new Blob([csv()],{type:'text/csv'}); const a=document.createElement('a');
  a.href=URL.createObjectURL(b); a.download='human_count.csv'; a.click();}catch(e){} const box=byId('csvbox'); if(box){box.open=true; box.scrollIntoView();}};
byId('copy').onclick=()=>{refresh(); const t=csv(); const done=()=>alert('CSV copied');
  const fail=()=>{const box=byId('csvbox'); if(box){box.open=true;} const ta=byId('csvtext'); if(ta){ta.focus(); ta.select();}};
  if(navigator.clipboard&&navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done,fail); else fail();};
byId('reset').onclick=()=>{if(confirm('Clear all answers on this page?')){document.querySelectorAll('.item input[type=radio]').forEach(i=>i.checked=false);
  document.querySelectorAll('.item input[type=text]').forEach(i=>i.value=''); try{store&&store.removeItem(KEY);}catch(e){} refresh();}};
byId('p2').onchange=e=>document.body.classList.toggle('pass2on',e.target.checked);
const zoom=byId('zoom'), zimg=zoom.querySelector('img');
document.querySelectorAll('.frames img').forEach(im=>im.onclick=()=>{zimg.src=im.src;zoom.style.display='flex';});
zoom.onclick=()=>zoom.style.display='none';
const box=byId('csvbox'); if(box) box.addEventListener('toggle',refresh);
refresh();
})();
</script>
"""
    parts.append(script)
    sheet = out_dir / "human_count_sheet.html"
    sheet.write_text("\n".join(parts))
    answers = out_dir / "human_count.csv"
    if not answers.exists():
        with open(answers, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["n", "item_id", "letter", "confidence", "impossible_from_frames", "seconds",
                        "letter_full_video", "note"])
            for k, i in enumerate(chosen, 1):
                w.writerow([k, i, "", "", "", "", "", ""])
    return sheet, answers


def write_pass2_sheet(values: dict, scored_path: Path = VALIDATION / "human_count.json",
                      answers_path: Path = VALIDATION / "human_count.csv",
                      data_dir: Path = DATA_DIR, out_dir: Path = VALIDATION) -> Path:
    """Step 4: the missed items with the full clip embedded. Shows the question and options only,
    never the answer. The Live CSV box carries the full-video letters back into human_count.csv."""
    scored = json.loads(scored_path.read_text())
    missed = [it["item_id"] for it in scored["items"] if not it["correct"]]
    first = {r["item_id"]: r for r in csv.DictReader(open(answers_path))}
    parts = ["""<!doctype html><meta charset='utf-8'><title>Human count: full-video pass</title>
<style>body{font-family:sans-serif;max-width:1000px;margin:2em auto;padding:0 1em}.item{border-top:2px solid #ccc;padding:1.5em 0}
video{width:100%;max-width:720px;background:#000}.opts{font-size:1.2em}.ctl{display:flex;flex-wrap:wrap;gap:.6em 1.6em;align-items:center;margin-top:.6em}
.ctl label{cursor:pointer;padding:.25em .6em;border:1px solid #bbb;border-radius:6px}.ctl label:has(input:checked){background:#2f6fb5;color:#fff;border-color:#2f6fb5}
.ctl input[type=text]{width:28em;padding:.3em}#bar{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:.6em 0;display:flex;gap:1em;align-items:center}
textarea{width:100%;font-family:monospace;font-size:12px}.first{color:#666}</style>
<div id='bar'><b>Full-video pass</b> <span id='prog'></span> <button id='export'>Export CSV</button></div>
<p>These are the items the frames-only count missed. Watch the whole clip, then click the count you see. Add a note if the
label looks wrong or the question is ambiguous. Your frames-only answer is shown so you can see what changed; the correct
answer is not shown.</p>
<details open><summary>Live CSV</summary><textarea id='csvtext' readonly rows='8' onclick='this.select()'></textarea></details>"""]
    for k, i in enumerate(missed, 1):
        stem = i.split(":")[1]
        q = html.escape(question_for(i, data_dir))
        opts = " &nbsp; ".join(f"({L}) {html.escape(c)}" for L, c in zip(LETTERS, values[i]["candidates"]))
        picks = "".join(f"<label><input type='radio' name='full{k}' value='{L}'>{L}</label>" for L in LETTERS[:len(values[i]["candidates"])])
        fr = first.get(i, {})
        parts.append(f"<div class='item' data-id='{html.escape(i)}'><h2>{k}. <code>{html.escape(i)}</code></h2>"
                     f"<video controls preload='metadata' src='../../data/videos/action_count/{stem}.mp4'></video>"
                     f"<p class='opts'><b>{q}</b><br>{opts}</p>"
                     f"<p class='first'>frames-only answer: {html.escape(fr.get('letter',''))} ({html.escape(fr.get('confidence',''))})</p>"
                     f"<div class='ctl'><span>count from the full clip:</span>{picks}"
                     f"<input type='text' name='note{k}' placeholder='note'></div></div>")
    parts.append(r"""
<script>
(function(){
function rows(){return Array.from(document.querySelectorAll('.item')).map(d=>{const r=d.querySelector('input[type=radio]:checked');
  return {id:d.dataset.id,letter:r?r.value:'',note:d.querySelector('input[type=text]').value};});}
function csv(){const esc=v=>/[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;
  return ['item_id,letter_full_video,note'].concat(rows().map(r=>[r.id,r.letter,esc(r.note)].join(','))).join('\n')+'\n';}
function refresh(){const n=rows().filter(r=>r.letter).length, N=rows().length;
  document.getElementById('prog').textContent=n+' / '+N+' answered'; document.getElementById('csvtext').value=csv();}
document.addEventListener('change',refresh); document.addEventListener('input',refresh);
document.getElementById('export').onclick=()=>{try{const b=new Blob([csv()],{type:'text/csv'});const a=document.createElement('a');
  a.href=URL.createObjectURL(b);a.download='human_count_pass2.csv';a.click();}catch(e){}};
refresh();
})();
</script>""")
    out = out_dir / "human_count_pass2.html"
    out.write_text("\n".join(parts))
    return out


def merge_pass2(pass2_csv: Path, answers_path: Path = VALIDATION / "human_count.csv") -> int:
    """Write letter_full_video and note from the pass-2 export into human_count.csv. Returns rows updated."""
    p2 = {r["item_id"]: r for r in csv.DictReader(open(pass2_csv))}
    rows = list(csv.DictReader(open(answers_path)))
    n = 0
    for r in rows:
        m = p2.get(r["item_id"])
        if m and m.get("letter_full_video"):
            r["letter_full_video"] = m["letter_full_video"]
            if m.get("note"):
                r["note"] = (r["note"] + "; " if r["note"] else "") + m["note"]
            n += 1
    with open(answers_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    return n



def score(values: dict, answers_path: Path = VALIDATION / "human_count.csv",
          results_dir: Path = RESULTS_DIR) -> dict:
    rows = list(csv.DictReader(open(answers_path)))
    ids = [r["item_id"] for r in rows]
    truth = {i: LETTERS[values[i]["candidates"].index(values[i]["answer"])] for i in ids}
    filled = [r for r in rows if r["letter"].strip()]
    if len(filled) != len(rows):
        raise ValueError(f"{len(rows) - len(filled)} items have no letter yet")
    correct = [r["letter"].strip().upper() == truth[r["item_id"]] for r in rows]
    k, n = sum(correct), len(rows)
    w = wilson(k, n)
    out = {"n": n, "correct": k, "acc": w.acc, "lo": w.lo, "hi": w.hi, "pass_k": PASS_K,
           "h7": "holds" if k >= PASS_K else "falsified",
           "one_flip_changes_verdict": k in (PASS_K - 1, PASS_K),
           "sure": {"n": 0, "correct": 0}, "unsure": {"n": 0, "correct": 0},
           "impossible_flagged": 0, "impossible_and_wrong": 0,
           "full_video": None, "models_on_these_items": {}, "items": []}
    for r, c in zip(rows, correct):
        conf = "sure" if r["confidence"].strip().lower().startswith("s") else "unsure"
        out[conf]["n"] += 1
        out[conf]["correct"] += int(c)
        imp = r["impossible_from_frames"].strip().lower() in ("y", "yes", "1", "true")
        out["impossible_flagged"] += int(imp)
        out["impossible_and_wrong"] += int(imp and not c)
        out["items"].append({"item_id": r["item_id"], "human": r["letter"].strip().upper(), "truth": truth[r["item_id"]],
                             "correct": c, "confidence": conf, "impossible": imp, "seconds": r.get("seconds", "")})
    fv = [r for r in rows if r.get("letter_full_video", "").strip()]
    if fv:
        fv_correct = sum(r["letter_full_video"].strip().upper() == truth[r["item_id"]] for r in fv)
        misses_rechecked = [r for r in fv if r["letter"].strip().upper() != truth[r["item_id"]]]
        out["full_video"] = {"rechecked": len(fv), "correct": fv_correct,
                             "misses_rechecked": len(misses_rechecked),
                             "misses_fixed_by_full_video": sum(
                                 r["letter_full_video"].strip().upper() == truth[r["item_id"]] for r in misses_rechecked)}
    for m, run in MODEL_RUNS.items():
        p = results_dir / f"{run}.jsonl"
        if p.exists():
            rr = {json.loads(l)["item_id"]: json.loads(l) for l in p.read_text().splitlines() if l.strip()}
            out["models_on_these_items"][m] = sum(bool(rr[i]["correct"]) for i in ids if i in rr)
    out["answer_mix"] = dict(Counter(values[i]["answer"] for i in ids))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sheet", "score", "pass2", "merge-pass2"])
    ap.add_argument("--csv", default=None, help="merge-pass2: the exported human_count_pass2.csv")
    ap.add_argument("--values", default=str(VALIDATION / "item_values.json"))
    a = ap.parse_args()
    values = load_item_values(Path(a.values))
    if a.cmd == "pass2":
        out = write_pass2_sheet(values)
        print(f"wrote {out}")
        return
    if a.cmd == "merge-pass2":
        n = merge_pass2(Path(a.csv))
        print(f"merged {n} full-video answers into human_count.csv; now run: score")
        return
    if a.cmd == "sheet":
        chosen = select_items(values)
        sheet, answers = write_sheet(chosen, values)
        print(f"wrote {sheet} ({len(chosen)} items) and {answers}; answer mix "
              f"{dict(Counter(values[i]['answer'] for i in chosen))}")
    else:
        out = score(values)
        dest = VALIDATION / "human_count.json"
        dest.write_text(json.dumps(out, indent=2))
        print(f"human {out['correct']}/{out['n']} = {out['acc']:.0%} [{out['lo']:.1%}, {out['hi']:.1%}]  "
              f"H7 {out['h7']} (pass at {PASS_K}); sure {out['sure']['correct']}/{out['sure']['n']}, "
              f"unsure {out['unsure']['correct']}/{out['unsure']['n']}; flagged impossible {out['impossible_flagged']} "
              f"(wrong on {out['impossible_and_wrong']}); models on these items {out['models_on_these_items']}; "
              f"full video {out['full_video']}; wrote {dest}")


if __name__ == "__main__":
    main()
