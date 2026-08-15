@echo off
cd /d E:\project\agent\xiaopu
python -c "import os,shutil,subprocess; print('docker=',shutil.which('docker')); print({k:v for k,v in os.environ.items() if 'DOCKER' in k or 'COMPOSE' in k or k.startswith('T_BENCH')}); c=subprocess.run(['docker','compose','version'],capture_output=True,text=True); print('rc=',c.returncode); print(c.stdout); print(c.stderr)" > workspace\results\zzz_python_compose_probe.log 2>&1
