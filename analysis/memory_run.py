import subprocess, resource, time, sys, json
cmd = sys.argv[2:]; t = time.time()
p = subprocess.run(cmd, capture_output=True, text=True)
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
json.dump(dict(cmd=cmd, rc=p.returncode, seconds=time.time() - t, peak_rss_mb=ru.ru_maxrss / 1024, tail=p.stdout[-1500:] + p.stderr[-1500:]), open(sys.argv[1], 'w'), indent=1)
