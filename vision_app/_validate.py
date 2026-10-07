"""Vision — Validation Suite (auto-generated)"""
import subprocess, sys, time, io, base64, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance
import pandas as pd
import requests

BASE = "http://127.0.0.1:8000"

def request_json(method, url, **kwargs):
    response = requests.request(method, url, **kwargs)
    try:
        payload = response.json()
    except ValueError as exc:
        body = response.text.strip().replace("\n", " ")[:500]
        raise RuntimeError(
            f"{method} {url} returned HTTP {response.status_code} "
            f"with non-JSON response: {body!r}"
        ) from exc
    if not response.ok:
        raise RuntimeError(
            f"{method} {url} returned HTTP {response.status_code}: {payload}"
        )
    return payload

# ---------- GENERATORS ----------
def make_car(seed, size=(400, 300)):
    rng = np.random.default_rng(seed)
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    scene_type = seed % 4
    if scene_type == 0:
        for y in range(h):
            arr[y, :] = [int(100 + y*0.5), int(150 + y*0.3), int(200 + y*0.1)]
        arr[160:230, 50:350] = [220, 50, 50]
        arr[140:170, 120:280] = [180, 30, 30]
        arr[170:200, 100:150] = [130, 180, 220]
        arr[170:200, 250:300] = [130, 180, 220]
        arr[220:245, 80:130] = [30, 30, 30]
        arr[220:245, 270:320] = [30, 30, 30]
        arr[40:80, 320:360] = [255, 240, 100]
    elif scene_type == 1:
        arr[:] = [40, 50, 70]
        arr[180:240, 60:340] = [60, 120, 200]
        arr[150:180, 100:300] = [80, 150, 230]
        arr[160:180, 120:180] = [200, 220, 240]
        arr[160:180, 220:280] = [200, 220, 240]
        arr[235:260, 90:140] = [20, 20, 20]
        arr[235:260, 260:310] = [20, 20, 20]
        arr[260:, :] = [60, 55, 50]
    elif scene_type == 2:
        arr[:] = [200, 220, 240]
        arr[180:, :] = [80, 140, 60]
        arr[140:200, 40:360] = [230, 210, 60]
        arr[110:145, 100:300] = [200, 180, 40]
        arr[120:145, 130:180] = [150, 200, 230]
        arr[120:145, 220:270] = [150, 200, 230]
        arr[195:225, 70:120] = [25, 25, 25]
        arr[195:225, 280:330] = [25, 25, 25]
    else:
        arr[:] = [20, 20, 40]
        arr[200:250, 80:320] = [60, 160, 80]
        arr[170:205, 130:270] = [50, 140, 70]
        arr[180:200, 150:200] = [180, 220, 240]
        arr[180:200, 220:260] = [180, 220, 240]
        arr[245:270, 110:160] = [15, 15, 15]
        arr[245:270, 250:300] = [15, 15, 15]
        for _ in range(20):
            x, y = rng.integers(0, w), rng.integers(0, 100)
            arr[y, x] = [255, 255, 200]
    noise = rng.integers(-10, 10, arr.shape, dtype=np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def to_b64(img, quality=95):
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()

def transform(img, kind):
    if kind == "none": return img
    if kind == "compress30": return Image.open(io.BytesIO(base64.b64decode(to_b64(img, 30))))
    if kind == "compress50": return Image.open(io.BytesIO(base64.b64decode(to_b64(img, 50))))
    if kind == "crop10":
        w, h = img.size; return img.crop((int(w*0.05), int(h*0.05), int(w*0.95), int(h*0.95)))
    if kind == "crop20":
        w, h = img.size; return img.crop((int(w*0.1), int(h*0.1), int(w*0.9), int(h*0.9)))
    if kind == "watermark":
        i2 = img.copy(); ImageDraw.Draw(i2).text((20, 20), "OLX COPY", fill=(255, 0, 0)); return i2
    if kind == "brightness":
        return ImageEnhance.Brightness(img).enhance(1.3)
    return img

# ---------- PREPARE ----------
print("\n  [1/5] Generating test images...")
BASE_BRIO   = make_car(seed=42)
BASE_AVANZA = make_car(seed=88)
BASE_SUV    = make_car(seed=33)
BASE_SEDAN  = make_car(seed=77)

import imagehash
d1 = imagehash.phash(BASE_BRIO, hash_size=8) - imagehash.phash(BASE_AVANZA, hash_size=8)
d2 = imagehash.phash(BASE_BRIO, hash_size=8) - imagehash.phash(BASE_SUV, hash_size=8)
print(f"      pHash distance BRIO vs AVANZA: {d1}")
print(f"      pHash distance BRIO vs SUV   : {d2}")
assert d1 > 10 and d2 > 10, "Generator failed!"
print("      Generator OK")

# Re-init by hitting endpoint (will auto-create)
time.sleep(1)

# Register ONLY BRIO
print("\n  [2/5] Registering ONLY BRIO as protected...")
seed_result = request_json("POST", f"{BASE}/api/v1/seed-original", json={
    "listing_id": "OLX-PROTECTED-BRIO-001",
    "model": "Honda Brio 2021",
    "price": 175_000_000,
    "image_base_64": to_b64(BASE_BRIO),
})
print(f"      Registry: {seed_result['total_registry']} original(s)")

# ---------- BUILD TEST CASES ----------
print("\n  [3/5] Building test cases...")
P_BRIO = 175_000_000
P_AVANZA = 190_000_000
DFRAUD = "Jual cepat. Jangan bahas harga sama orang rumah ya, bilang aja saudara."
DNORM  = "Pajak hidup, surat lengkap, nego halus. Mobil terawat, siap cek."
DBU    = "BU cepat banting harga, pajak hidup, nego halus."
DPARAPHRASE = "Mobil siap cek langsung. Nanti ngobrol sama ibu saya aja ya, saya lagi keluar kota."

cases = []
def add(cat, exp, img, tk, title, price, desc, notes):
    cases.append({"cat":cat,"expected":exp,"base":img,"tk":tk,"title":title,
                   "price":price,"desc":desc,"notes":notes})

for tk in ["none","compress30","compress50","crop10","crop20","watermark","brightness"]:
    add("fraud_stolen", 1, BASE_BRIO, tk, "Honda Brio 2021", int(P_BRIO*0.5), DFRAUD, f"stolen+{tk}")
for tk in ["none","compress30"]:
    add("fraud_paraphrase", 1, BASE_BRIO, tk, "Honda Brio 2021", int(P_BRIO*0.5), DPARAPHRASE, f"paraphrase+{tk}")
add("fraud_typo", 1, BASE_BRIO, "none", "Honda Brio 2021", int(P_BRIO*0.5),
    "Jngn bhs hrga sma orng rmh, blng aja sodara.", "typo")
add("fraud_image_only", 1, BASE_BRIO, "none", "Honda Brio 2021", P_BRIO, DNORM, "image_only")

for tk in ["none","compress50","crop10","brightness"]:
    add("normal_avanza", 0, BASE_AVANZA, tk, "Toyota Avanza 2020", P_AVANZA, DNORM, f"avanza+{tk}")
for tk in ["none","compress50"]:
    add("normal_suv", 0, BASE_SUV, tk, "Honda Brio 2021", P_BRIO, DNORM, f"suv+{tk}")
for tk in ["none","compress50"]:
    add("normal_sedan", 0, BASE_SEDAN, tk, "Toyota Avanza 2020", P_AVANZA, DNORM, f"sedan+{tk}")
for tk in ["none","compress50"]:
    add("normal_bu", 0, BASE_AVANZA, tk, "Toyota Avanza 2020", int(P_AVANZA*0.58), DBU, f"BU_avanza+{tk}")
add("normal_bu", 0, BASE_SUV, "none", "Honda Brio 2021", int(P_BRIO*0.5), DBU, "BU_suv")
add("boundary_drop39", 0, BASE_AVANZA, "none", "Toyota Avanza 2020", int(P_AVANZA*0.61), DNORM, "drop39")
add("boundary_drop40", 1, BASE_BRIO, "none", "Honda Brio 2021", int(P_BRIO*0.60), DNORM, "drop40")

print(f"      Total: {len(cases)} cases")

# ---------- RUN ----------
print(f"\n  [4/5] Running {len(cases)} cases...")
results = []
t0 = time.time()
for i, c in enumerate(cases):
    try:
        img = transform(c["base"], c["tk"])
        res = request_json("POST", f"{BASE}/api/v1/fraud-detect/listings", json={
            "user_id": f"U{i:03d}", "listing_title": c["title"], "price": c["price"],
            "description": c["desc"], "image_base64_list": [to_b64(img)],
        }, timeout=10)
        iv = res['analysis_details']['image_validation']
        pv = res['analysis_details']['price_validation']
        l3 = res['analysis_details']['text_ai_analysis']
        results.append({
            "id": f"T{i+1:03d}", "cat": c["cat"], "expected": c["expected"],
            "status": res['status'], "score": res['fraud_score'],
            "predicted": 1 if res['fraud_score'] >= 80 else 0,
            "L1_dup": iv.get('is_duplicate', False),
            "L1_dist": iv.get('hamming_distance', iv.get('closest_hamming_distance')),
            "L2_anomaly": pv.get('anomaly_detected', False),
            "L3_tier1": len(l3.get('tier1_hits', [])),
            "L3_ai": res['meta']['ai_tier2_called'],
            "notes": c["notes"],
        })
    except Exception as e:
        print(f"      {c.get('notes','?')}: {e}")

df = pd.DataFrame(results)
df.to_csv("validation_results.csv", index=False)
elapsed = time.time()-t0
print(f"      Done in {elapsed:.1f}s (avg {elapsed/len(df)*1000:.0f}ms)")

# ---------- METRICS ----------
from statsmodels.stats.proportion import proportion_confint

TP = ((df['expected']==1) & (df['predicted']==1)).sum()
TN = ((df['expected']==0) & (df['predicted']==0)).sum()
FP = ((df['expected']==0) & (df['predicted']==1)).sum()
FN = ((df['expected']==1) & (df['predicted']==0)).sum()

def wci(s, n, alpha=0.05):
    if n == 0: return (0, 0)
    lo, hi = proportion_confint(s, n, alpha=alpha, method='wilson')
    return round(lo*100, 1), round(hi*100, 1)

prec = TP/(TP+FP) if (TP+FP) else 0
rec  = TP/(TP+FN) if (TP+FN) else 0
f1   = 2*prec*rec/(prec+rec) if (prec+rec) else 0
acc  = (TP+TN)/len(df)
fpr  = FP/(FP+TN) if (FP+TN) else 0
fnr  = FN/(FN+TP) if (FN+TP) else 0
spec = TN/(TN+FP) if (TN+FP) else 0

print("\n  " + "="*60)
print(f"   METRICS (n={len(df)}, threshold=80)")
print("  " + "="*60)
print(f"  TP={TP}  TN={TN}  FP={FP}  FN={FN}")
print(f"  Precision  : {prec*100:5.1f}%  [CI: {wci(TP,TP+FP)[0]}-{wci(TP,TP+FP)[1]}%]")
print(f"  Recall     : {rec*100:5.1f}%  [CI: {wci(TP,TP+FN)[0]}-{wci(TP,TP+FN)[1]}%]")
print(f"  F1-Score   : {f1:.3f}")
print(f"  Accuracy   : {acc*100:5.1f}%")
print(f"  FPR        : {fpr*100:5.1f}%")
print(f"  FNR        : {fnr*100:5.1f}%")
print("  " + "="*60)

# Save summary
summary = {
    "n": len(df), "threshold": 80,
    "TP": int(TP), "TN": int(TN), "FP": int(FP), "FN": int(FN),
    "precision": round(prec*100,1), "recall": round(rec*100,1), "f1": round(f1,3),
    "accuracy": round(acc*100,1), "specificity": round(spec*100,1),
    "fpr": round(fpr*100,1), "fnr": round(fnr*100,1),
    "precision_ci": wci(TP, TP+FP), "recall_ci": wci(TP, TP+FN),
}
with open("validation_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

# ---------- CHARTS ----------
print("\n  [5/5] Generating charts...")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.gridspec import GridSpec
from sklearn.metrics import roc_curve, auc, precision_recall_curve, average_precision_score
from PIL import Image as PILImage

# Inter font
try:
    from matplotlib import font_manager
    fd = os.path.join(os.path.dirname(__file__), ".fonts")
    os.makedirs(fd, exist_ok=True)
    fpath = os.path.join(fd, "Inter-var.ttf")
    # Download 4 static weights
    weights = {
        "Inter-Regular.ttf":  "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Regular.ttf",
        "Inter-Medium.ttf":   "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Medium.ttf",
        "Inter-SemiBold.ttf": "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-SemiBold.ttf",
        "Inter-Bold.ttf":     "https://github.com/rsms/inter/raw/v4.0/docs/font-files/Inter-Bold.ttf",
    }
    import urllib.request
    for fname, url in weights.items():
        fpath = os.path.join(fd, fname)
        if not os.path.exists(fpath):
            try:
                urllib.request.urlretrieve(url, fpath)
            except Exception:
                pass
        font_manager.fontManager.addfont(fpath)
    plt.rcParams['font.family'] = 'Inter'
    plt.rcParams['font.sans-serif'] = ['Inter', 'DejaVu Sans']
except Exception:
    pass
plt.rcParams['axes.unicode_minus'] = False

# Mega dashboard
fig = plt.figure(figsize=(22, 14))
fig.suptitle("Vision Validation Report — Complete Dashboard",
              fontsize=22, fontweight='bold', y=0.995)
gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3,
               top=0.94, bottom=0.06, left=0.05, right=0.97)

ax1 = fig.add_subplot(gs[0, 0])
fpr_c, tpr_c, _ = roc_curve(df['expected'], df['score'])
roc_auc = auc(fpr_c, tpr_c)
ax1.plot(fpr_c, tpr_c, 'b-', linewidth=2.5, label=f'AUC = {roc_auc:.3f}')
ax1.plot([0,1], [0,1], 'k--', alpha=0.5)
ax1.fill_between(fpr_c, tpr_c, alpha=0.15, color='blue')
ax1.set_xlabel('False Positive Rate', fontsize=11, fontweight='bold')
ax1.set_ylabel('True Positive Rate', fontsize=11, fontweight='bold')
ax1.set_title('ROC Curve', fontsize=13, fontweight='bold')
ax1.legend(loc='lower right'); ax1.grid(alpha=0.3)

ax2 = fig.add_subplot(gs[0, 1])
prec_c, rec_c, _ = precision_recall_curve(df['expected'], df['score'])
ap = average_precision_score(df['expected'], df['score'])
ax2.plot(rec_c, prec_c, 'g-', linewidth=2.5, label=f'AP = {ap:.3f}')
ax2.axhline(df['expected'].mean(), color='k', linestyle='--', alpha=0.5)
ax2.set_xlabel('Recall', fontsize=11, fontweight='bold')
ax2.set_ylabel('Precision', fontsize=11, fontweight='bold')
ax2.set_title('Precision-Recall Curve', fontsize=13, fontweight='bold')
ax2.legend(loc='lower left'); ax2.grid(alpha=0.3)

ax3 = fig.add_subplot(gs[0, 2])
ax3.axis('off')
metrics_data = [
    ["Metric", "Value", "95% CI"],
    ["n (total)", f"{len(df)}", "—"],
    ["TP/TN/FP/FN", f"{TP}/{TN}/{FP}/{FN}", "—"],
    ["Precision", f"{prec*100:.1f}%", f"[{wci(TP,TP+FP)[0]}, {wci(TP,TP+FP)[1]}]"],
    ["Recall", f"{rec*100:.1f}%", f"[{wci(TP,TP+FN)[0]}, {wci(TP,TP+FN)[1]}]"],
    ["F1-Score", f"{f1:.3f}", "—"],
    ["Accuracy", f"{acc*100:.1f}%", "—"],
    ["Specificity", f"{spec*100:.1f}%", "—"],
    ["FPR", f"{fpr*100:.1f}%", "—"],
    ["FNR", f"{fnr*100:.1f}%", "—"],
]
t = ax3.table(cellText=metrics_data, loc='center', cellLoc='center',
               colWidths=[0.42, 0.28, 0.3])
t.auto_set_font_size(False); t.set_fontsize(11); t.scale(1, 2.2)
for i in range(3):
    t[(0, i)].set_facecolor('#34495e')
    t[(0, i)].set_text_props(color='white', weight='bold')
ax3.set_title('Performance Metrics', fontsize=13, fontweight='bold', pad=12)

ax4 = fig.add_subplot(gs[1, 0])
cm = np.array([[TN, FP], [FN, TP]])
labels = np.array([[f"TN={TN}", f"FP={FP}"], [f"FN={FN}", f"TP={TP}"]])
sns.heatmap(cm, annot=labels, fmt='', cmap='RdYlGn', cbar=False, ax=ax4,
            xticklabels=['Pred Safe', 'Pred Fraud'],
            yticklabels=['Actual Safe', 'Actual Fraud'],
            annot_kws={"size": 15, "weight": "bold"},
            linewidths=3, linecolor='white', vmin=0, vmax=max(1, max(TP,TN)))
ax4.set_title(f'Confusion Matrix', fontsize=13, fontweight='bold')

ax5 = fig.add_subplot(gs[1, 1])
df['b_naive'] = df['L2_anomaly'].astype(int)
df['b_regex'] = (df['L3_tier1'] > 0).astype(int)
df['b_phash'] = df['L1_dup'].astype(int)

def eval_m(y, p):
    tp=((y==1)&(p==1)).sum(); tn=((y==0)&(p==0)).sum()
    fp=((y==0)&(p==1)).sum(); fn=((y==1)&(p==0)).sum()
    pr=tp/(tp+fp) if (tp+fp) else 0; rc=tp/(tp+fn) if (tp+fn) else 0
    f = 2*pr*rc/(pr+rc) if (pr+rc) else 0
    return pr*100, rc*100, f*100

methods = ["Vision", "Naive Price", "Regex", "pHash"]
data_m = [eval_m(df['expected'], df['predicted']),
          eval_m(df['expected'], df['b_naive']),
          eval_m(df['expected'], df['b_regex']),
          eval_m(df['expected'], df['b_phash'])]
x = np.arange(len(methods)); w = 0.25
for i, (label, color) in enumerate([('P','#3498db'),('R','#2ecc71'),('F1','#9b59b6')]):
    vals = [d[i] for d in data_m]
    bars = ax5.bar(x + i*w, vals, w, label=label, color=color, edgecolor='black')
    for bar, v in zip(bars, vals):
        ax5.text(bar.get_x()+bar.get_width()/2, v+1.5, f'{v:.0f}',
                  ha='center', fontsize=9, fontweight='bold')
ax5.set_xticks(x + w); ax5.set_xticklabels(methods, fontsize=10)
ax5.set_ylabel('Value (%)', fontsize=11, fontweight='bold')
ax5.set_title('Baseline Comparison', fontsize=13, fontweight='bold')
ax5.legend(fontsize=10); ax5.grid(axis='y', alpha=0.3); ax5.set_ylim(0, 115)

ax6 = fig.add_subplot(gs[1, 2])
sc = {'SAFE':'#2ecc71', 'SUSPICIOUS':'#f39c12', 'FLAGGED_HIGH_RISK':'#e74c3c'}
order = df.sort_values('score').reset_index(drop=True)
colors_ = [sc.get(s, '#95a5a6') for s in order['status']]
ax6.barh(range(len(order)), order['score'], color=colors_, edgecolor='black', linewidth=0.5)
ax6.axvline(40, color='orange', linestyle='--', linewidth=2, alpha=0.8)
ax6.axvline(80, color='red', linestyle='--', linewidth=2, alpha=0.8)
ax6.set_yticks([]); ax6.set_xlabel('Fraud Score', fontsize=11, fontweight='bold')
ax6.set_title(f'Score Distribution (n={len(df)})', fontsize=13, fontweight='bold')
ax6.grid(axis='x', alpha=0.3)

plt.savefig("validation_dashboard.png", dpi=180, bbox_inches='tight', facecolor='white')
plt.close()
print("      validation_dashboard.png")

# Vertical poster
charts = ["validation_roc_pr.png", "validation_baselines.png",
          "validation_confusion.png", "validation_scores.png"]

# Save individual charts
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(fpr_c, tpr_c, 'b-', linewidth=2.5, label=f'AUC = {roc_auc:.3f}')
ax.plot([0,1], [0,1], 'k--', alpha=0.5)
ax.set_xlabel('FPR'); ax.set_ylabel('TPR'); ax.set_title('ROC')
ax.legend(); ax.grid(alpha=0.3)
plt.savefig("validation_roc_pr.png", dpi=150, bbox_inches='tight')
plt.close()

print("\n  Validation complete!")
print(f"   Files saved in: {os.path.dirname(os.path.abspath('validation_dashboard.png'))}")
print(f"     - validation_results.csv")
print(f"     - validation_summary.json")
print(f"     - validation_dashboard.png")
