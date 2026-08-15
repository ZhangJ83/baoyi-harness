@echo off
cd /d E:\project\agent\xiaopu
"C:\Users\zzz\.local\bin\uv.exe" run --offline --directory E:\project\agent\official_refs\terminal-bench python -c "import os,shutil,subprocess; print('docker=',shutil.which('docker')); print(os.environ.get('PATH')); c=subprocess.run(['docker','compose','-p','uvdiag','-f',r'E:\project\agent\official_refs\terminal-bench\original-tasks\hello-world\docker-compose.yaml','config'],capture_output=True,text=True); print('rc=',c.returncode); print(c.stdout); print(c.stderr)" > workspace\results\zzz_uv_compose_probe.log 2>&1
