#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,csv,sys,hashlib,platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]; OLD=R
sys.path.insert(0,str(OLD/'analysis'))
from generate_simulated_dataset import simulate_event,SCENARIOS,POSITIVE_SCENARIOS
from evaluate import metric_summary
for d in ['results','figures']: (R/d).mkdir(exist_ok=True)
# Compile the actual firmware translation unit against deterministic peripheral doubles.
base=['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I',str(R/'analysis/stubs')]
subprocess.run(base+['-I',str(R/'analysis/cloud'),str(R/'analysis/firmware_harness.cpp'),'-o',str(R/'analysis/firmware_harness')],check=True)
cases=['boot_absent','short_read','bus_error','calibration_motion','calibration_still','battery_adc','cancel','deadline','sample_gap','wifi_down','cloud_down','submitted','no_retry']
tests=[]
for c in cases:
 p=subprocess.run([str(R/'analysis/firmware_harness'),c],text=True,capture_output=True)
 (R/'results'/f'{c}.log').write_text(p.stdout+p.stderr)
 assert p.returncode==0,(c,p.stdout,p.stderr)
 tests.append(dict(case=c,passed=True,result=[l for l in p.stdout.splitlines() if l.startswith('RESULT')][0]))
subprocess.run(base+[str(R/'analysis/firmware_harness.cpp'),'-o',str(R/'analysis/firmware_offline')],check=True)
p=subprocess.run([str(R/'analysis/firmware_offline'),'deadline'],text=True,capture_output=True,check=True)
assert 'reason=not_configured' in p.stdout
(R/'results/offline.log').write_text(p.stdout)
tests.append(dict(case='offline',passed=True,result='RESULT offline_skipped alarm=1'))
(R/'results/firmware_tests.json').write_text(json.dumps(tests,indent=2))
# Frozen detector; a separate random stream produces a fresh evaluation set.
exe=OLD/'analysis/build/detector_replay'
header='event_id,label,scenario,time_ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps\n'
rng=np.random.default_rng(20260911)
source=R/'results/fresh_imu.csv'
with source.open('w') as f:
 f.write(header)
 for si,s in enumerate(SCENARIOS):
  for trial in range(30):
   a,g=simulate_event(s,rng)
   for i in range(len(a)):
    f.write(f'FRESH-{si:02}-{trial:02},{int(s in POSITIVE_SCENARIOS)},{s},{i*10},'+','.join(f'{v:.6f}' for v in [*a[i],*g[i]])+'\n')
with source.open() as inp,(R/'results/fresh_events.csv').open('w') as out:
 subprocess.run([str(exe)],stdin=inp,stdout=out,check=True)
rows=list(csv.DictReader((R/'results/fresh_events.csv').open()))
metrics=metric_summary(rows)
# Explicit event-level partition of original replay: 45/15/15 per scenario.
oldrows=list(csv.DictReader((OLD/'results/event_results.csv').open()))
part={x:[] for x in ['development','validation','test']}
for s in SCENARIOS:
 sr=[r for r in oldrows if r['scenario']==s]
 for j,r in enumerate(sr):part['development' if j<45 else 'validation' if j<60 else 'test'].append(r)
partition_metrics={k:metric_summary(v) for k,v in part.items()}
with (R/'results/splits.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['event_id','partition']);w.writerows((r['event_id'],k) for k,v in part.items() for r in v)
# Time-stepped constant-power cell discharge, explicit input sweep.
energy=[]
for load in [0.09,0.12,0.18]:
 for efficiency in [0.8,0.9,0.95]:
  charge=2.6*0.9;secs=0;initial=charge
  while charge>0:
   soc=max(charge/initial,0);voltage=3.0+1.2*soc
   current=5*load/(efficiency*voltage)
   charge-=current/3600;secs+=1
  energy.append(dict(load_ma=int(load*1000),efficiency=efficiency,runtime_h=secs/3600))
(R/'results/energy.csv').write_text('load_ma,efficiency,runtime_h\n'+''.join(f"{e['load_ma']},{e['efficiency']},{e['runtime_h']:.6f}\n" for e in energy))
fig,ax=plt.subplots(figsize=(7,3.3))
for eff in [.8,.9,.95]:
 e=[x for x in energy if x['efficiency']==eff];ax.plot([x['load_ma'] for x in e],[x['runtime_h'] for x in e],'o-',label=f'{100*eff:.0f}% boost efficiency')
ax.set(xlabel='5 V load (mA)',ylabel='Simulated runtime (h)');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(R/'figures/energy.pdf');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(9,3.5))
for j,(name,rs) in enumerate([('Original replay',oldrows),('Fresh seed',rows)]):
 vals=[]
 for s in SCENARIOS:
  sr=[r for r in rs if r['scenario']==s];vals.append(sum(int(r['crashguard_prediction'])==int(r['label']) for r in sr)/len(sr)*100)
 axs[j].barh([s.replace('_',' ') for s in SCENARIOS],vals,color=['#277b91']*7+['#c57437']*2);axs[j].set(xlim=(0,105),title=name,xlabel='Correct event decisions (%)');axs[j].tick_params(axis='y',labelsize=8)
fig.tight_layout();fig.savefig(R/'figures/scenarios.pdf');plt.close(fig)
summary=dict(fresh_seed=20260911,fresh_events=len(rows),fresh_metrics=metrics,partition_metrics=partition_metrics,energy=energy,tests_passed=len(tests),python=platform.python_version(),numpy=np.__version__,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
(R/'results/experiment_summary.json').write_text(json.dumps(summary,indent=2))
# Compact generated comparison table.
def texrow(name,m,n):
 return f"{name} & {m['tp']} & {m['tn']} & {m['fp']} & {m['fn']} & {100*(m['tp']+m['tn'])/n:.1f} & {100*m['sensitivity']:.1f} & {100*m['specificity']:.1f} & {m['f1']:.3f} \\\\\n"
s=''
for name,m in metrics.items():s+=texrow(name.replace(' comparison',''),m,len(rows))
(R/'results/fresh_table.tex').write_text(r'\begin{tabular}{@{}lrrrrrrrr@{}}\toprule Detector & TP & TN & FP & FN & Acc. & Sens. & Spec. & F1\\\midrule'+'\n'+s+r'\bottomrule\end{tabular}')
print(json.dumps({'fresh':metrics,'tests':len(tests),'energy':energy},indent=2))
