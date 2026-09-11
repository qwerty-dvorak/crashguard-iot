from pathlib import Path
import hashlib,json,platform,subprocess,datetime
import numpy,scipy,matplotlib
r=Path(__file__).resolve().parents[1]
files=[r/'report.tex',r/'references.bib',r/'README.md',r/'reproduce.sh',*sorted((r/'analysis').rglob('*.py')),*sorted((r/'analysis').rglob('*.cpp')),*sorted((r/'analysis').rglob('*.h')),*sorted((r/'wokwi').glob('*'))]
files=[p for p in files if p.is_file()]
data=dict(executed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),platform=platform.platform(),python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,compiler=subprocess.check_output(['c++','--version'],text=True).splitlines()[0],sources={str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
(r/'results/provenance.json').write_text(json.dumps(data,indent=2))
files += list(sorted((r/'figures').iterdir()))
files += [r/'data/raw/PMC6660605_SupplementaryFiles.zip']
files += [p for p in sorted((r/'results').iterdir()) if p.suffix in ['.csv','.json','.tex'] and p.is_file()]
(r/'results/manifest.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+__import__('os').path.relpath(p,r)+'\n' for p in files))
