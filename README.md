# gem

## sh.py
Try to implement some useful text processing function in the flavor of Linux shell programming.

Here the demos:
1. Suppose you have a system resource monitor record
```txt
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
cat('usage-record.txt').grep('Time:2022-10-28 10', around=3).extract(r'CPU:(\d+%)').mean()
# ==>
15.71
```

2. Summary of AnonHugePage usage
```python
def sum_anon(pid):
  if pid is None: # iteration exhausted
    return None
  s = extract(r'AnonHugePages:\s+(\d\d+) kB', pathname=f'/proc/{pid}/smaps').sum()
  return f'AnonHugePages of {pid}: {s/1024} MB'
run('ps h -e -o pid').foreach('word', sum_anon).print()
# ==>
AnonHugePages of xxxx: nnn MB
AnonHugePages of yyyy: nnn MB
```

3. Echo content of files in /root
```python
run('ls /root').xargs('echo /root/{line}: ; cat /root/{line}').print()
```

4. Simulation of |, || and &&
```bash
find /etc/sh -name *.conf -type f | head -n 1
```
```python
run('find /etc/sh -name *.conf -type f').pipe('head -n 1')
```

```bash
[ -d /etc/sh ] || mkdir /etc/sh
```
```python
run('test -d /etc/sh').otherwise().run('mkdir /etc/sh')
```

```bash
[ -f /etc/sh/sh.conf ] && cat /etc/sh/sh.conf
```
```python
run('test -f /etc/sh/sh.conf').then().run('cat /etc/sh/sh.conf')
```

5. 
