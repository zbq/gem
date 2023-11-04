# gem

## sh.py
Try to implement some useful text processing function in the flavor of Linux shell programming.

Here the demos:
1. Suppose you have a system resource monitor record usage-record.txt
```
Time:2022-10-28 09:59:30, CPU:10%, Memory:40%
Time:2022-10-28 09:59:40, CPU:10%, Memory:40%
Time:2022-10-28 09:59:50, CPU:10%, Memory:50%
Time:2022-10-28 10:00:00, CPU:20%, Memory:60%
Time:2022-10-28 10:00:10, CPU:40%, Memory:80%
Time:2022-10-28 10:00:20, CPU:10%, Memory:40%
Time:2022-10-28 10:00:30, CPU:10%, Memory:40%
```

You can get CPU usage around 10am:
```python
cat('usage-record.txt').grep('Time:2022-10-28 10', around=3).extract(r'CPU:(\d+%)').indent().print(prolog='CPU usage around 10am:\n')
# or
grep('Time:2022-10-28 10', around=3, pathname='usage-record.txt').extract(r'CPU:(\d+%)').indent().print(prolog='CPU usage around 10am:\n')
# ==>
CPU usage around 10am:
  10%
  10%
  10%
  20%
  40%
  10%
  10%
```

Save it to cpu-10am.txt before print:
```python
cat('usage-record.txt').grep('Time:2022-10-28 10', around=3).extract(r'CPU:(\d+%)').tee('cpu-10am.txt').indent().print(prolog='CPU usage around 10am:\n')
```

CPU average usage around 10am:
```python
cat('usage-record.txt').grep('Time:2022-10-28 10', around=3).extract(r'CPU:(\d+%)').fmean()
# ==>
15.71
```

2. Show a summary of AnonHugePage usage
```python
def sum_anon(pid):
  s = extract(r'AnonHugePages:\s+(\d\d+) kB', pathname=f'/proc/{pid}/smaps').fsum()
  return f'AnonHugePages of {pid}: {s/1024} MB'
run('ps h -e -o pid').foreach('word', sum_anon).print()
# ==>
AnonHugePages of xxxx: nnn MB
AnonHugePages of yyyy: nnn MB
```

3. To show content of first 5 conf files under /etc/sh/, with bash
```bash
find /etc/sh -name *.conf -type f | head -n 5 | xargs cat
```
or with sh.py
```python
run('find /etc/sh -name *.conf -type f').pipe('head -n 5').xargs('echo {line} && cat {line}').print()
```

4. Create directory if not exist, with bash
```bash
[ -d /etc/sh ] || mkdir /etc/sh
```
or with sh.py
```python
if not os.path.isdir('/etc/sh'):
    run('mkdir /etc/sh')
```

5. Show conf file content if exist, with bash
```bash
[ -f /etc/sh/sh.conf ] && cat /etc/sh/sh.conf
```
or with sh.py
```python
if os.path.isfile('/etc/sh/sh.conf'):
    run('cat /etc/sh/sh.conf', stdout=None)
# or
if os.path.isfile('/etc/sh/sh.conf'):
    cat(pathname='/etc/sh/sh.conf').print()
```

6. Suppose you have a `ps -e -o user,pid,rss,comm` record ps-record.txt
```
USER     PID    RSS  COMMAND
root       1   6820  systemd
chrony   634   1668  chronyd
root     645   2448  login
postfix 1058   3992  pickup
root    1112   2088  bash
```
You can get a user list with
```python
select(slice(1,None), pathname='ps-record.txt').cut(0).sort().uniq()
# ==>
chrony
postfix
root
```
get a summary of RSS with
```python
rss = select(slice(1,None), pathname='ps-record.txt').cut(0,2)
for user in rss.cut(0).sort().uniq().iterate('line'):
    print(user, rss.grep(rf'^{user} ').fsum())
# ==>
chrony 1668.0
postfix 3992.0
root 11356.0
```
or
```python
rss = select(slice(1,None), pathname='ps-record.txt').cut(0,2)
def sum_rss(user):
    print(user, rss.grep(rf'^{user} ').fsum())
rss.cut(0).sort().uniq().foreach('line', sum_rss)
```

7. Get kernel IRQ exception call trace
```python
run('dmesg').grep_between('irq \d+: nobody cared', 'Disabling IRQ #\d+').print()
```

