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
