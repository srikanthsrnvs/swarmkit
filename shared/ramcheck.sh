#!/usr/bin/env bash
# ramcheck.sh — memory picture from inside a sandbox (no docker here): the box's /proc/meminfo totals (shared by every
# container), THIS sandbox's cgroup usage/cap, and the host snapshot the host writes every 30 s to status/host.txt.
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
gb() { awk -v kb="$1" 'BEGIN{printf "%.1f", kb/1048576}'; }
mi() { awk -v k="$1" '$1==k":"{print $2}' /proc/meminfo; }
echo "## box memory (GB, from /proc/meminfo — whole machine, not just this sandbox)"
printf "total %s  used %s  available %s  swap_used %s\n" "$(gb "$(mi MemTotal)")" "$(gb $(( $(mi MemTotal) - $(mi MemAvailable) )))" "$(gb "$(mi MemAvailable)")" "$(gb $(( $(mi SwapTotal) - $(mi SwapFree) )))"
if [ -r /sys/fs/cgroup/memory.max ]; then
  cap=$(cat /sys/fs/cgroup/memory.max); cur=$(cat /sys/fs/cgroup/memory.current 2>/dev/null || echo 0)
  if [ "$cap" = max ]; then capg=unlimited; else capg="$(awk -v b="$cap" 'BEGIN{printf "%.0f GB", b/1073741824}')"; fi
  echo; echo "## this sandbox's cgroup: using $(awk -v b="$cur" 'BEGIN{printf "%.1f GB", b/1073741824}') of $capg (the kernel kills the biggest process here if you exceed the cap)"
  [ -r /sys/fs/cgroup/cpu.max ] && echo "cpu.max: $(cat /sys/fs/cgroup/cpu.max)  (quota period => cores of CPU time; nproc still shows all host cores)"
fi
echo; echo "## top 10 processes by RSS in this sandbox"
ps -eo rss,pid,user,etimes,comm,args --sort=-rss | head -11 | awk 'NR==1{printf "%8s %7s %-9s %8s %s\n","RSS_GB","PID","USER","UPTIME_S","CMD";next}{printf "%8.1f %7s %-9s %8s ",$1/1048576,$2,$3,$4; $1=$2=$3=$4=$5=""; print substr($0,1,110)}'
echo
if [ -r "$HERE/status/host.txt" ]; then echo "## host snapshot ($HERE/status/host.txt)"; cat "$HERE/status/host.txt"
else echo "(no host snapshot at $HERE/status/host.txt yet — run bin/swarm-status-writer on the host)"; nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv 2>/dev/null; fi
