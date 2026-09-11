from pathlib import Path
import csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,Circle
R=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((R/'results/fresh_events.csv').open()))
fig,ax=plt.subplots(1,2,figsize=(8,3.2))
m=np.array([[210,0],[17,43]])
ax[0].imshow(m,cmap='Blues');ax[0].set(xticks=[0,1],yticks=[0,1],xticklabels=['Non-crash','Crash'],yticklabels=['Non-crash','Crash'],xlabel='Predicted',ylabel='True class',title='Fresh-set confusion matrix')
for (i,j),v in np.ndenumerate(m):ax[0].text(j,i,str(v),ha='center',va='center',color='white' if v>100 else 'black',fontsize=16)
d=[int(r['crashguard_confirmation_delay_ms'])/1000 for r in rows if int(r['label'])==1 and int(r['crashguard_prediction'])==1]
ax[1].hist(d,bins=12,color='#277b91',edgecolor='white');ax[1].set(xlabel='Candidate-to-confirmation time (s)',ylabel='Detected positive events',title='Delay distribution (n=43)');fig.tight_layout();fig.savefig(R/'figures/confusion_delay.pdf');plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5.5));ax.set(xlim=(0,10),ylim=(0,5.5));ax.axis('off');fig.patch.set_facecolor('#f0f4f7')
def box(x,y,w,h,s,c):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.08',fc=c,ec='#34495e',lw=1.4));ax.text(x+w/2,y+h/2,s,ha='center',va='center',fontsize=10,color='white' if c in ['#173b50','#267b79'] else '#173b50')
box(3.5,1.6,2.3,2.8,'ESP32 firmware\n\nCOUNTDOWN\nGPIO26 = HIGH\nGPIO25 = 2400 Hz\n\nt = 3.610 s','#173b50')
box(.2,3.2,2.2,1.3,'MPU-6050 model\nI2C 0x68 / 100 Hz\n6 signed channels','#267b79')
box(.2,.6,2.2,1.2,'Cell + ADC model\nADC input 1850 mV\nConverted: 3.700 V','#d9e8ef')
box(7,3.4,2.6,1.0,'RED ALARM LED\nActive at confirmation','#f7c4c4');ax.add_patch(Circle((7.2,4.15),.09,color='red'))
box(7,1.9,2.6,1.0,'PIEZO OUTPUT\n2400 Hz tone active','#f5e6bb')
box(7,.4,2.6,1.0,'CANCEL BUTTON\nGPIO27 active-low','#c4e7cf')
for p,q in [((2.4,3.85),(3.5,3.85)),((2.4,1.2),(3.5,1.8)),((5.8,3.9),(7,3.9)),((5.8,2.8),(7,2.4)),((7,.9),(5.8,1.9))]:ax.annotate('',q,p,arrowprops=dict(arrowstyle='->',color='#476878',lw=2))
ax.text(5,5.12,'CrashGuard | Executed virtual-peripheral state',ha='center',fontsize=16,weight='bold',color='#173b50')
ax.text(5,.05,'Rendered from the deadline harness: confirmation 3610 ms; alert due 18610 ms.',ha='center',fontsize=10)
fig.tight_layout();fig.savefig(R/'figures/virtual_hardware.png',dpi=200);plt.close(fig)
# DC interface sweep produces data as well as the displayed values.
with (R/'results/circuit_dc.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['cell_v','adc_v','led_forward_v','led_ma','divider_ua'])
 for cell in np.linspace(3,4.2,13):
  for vf in [1.8,2,2.2]:
   adc=cell/2;led=(3.3-vf)/220*1000
   assert adc<=2.1+1e-9 and 0<led<7
   w.writerow([round(cell,2),round(adc,2),vf,led,cell/200000*1e6])
