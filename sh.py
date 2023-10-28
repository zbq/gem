import subprocess
from subprocess import STDOUT, DEVNULL, PIPE
import sys
import re
import textwrap
import locale
import math
import statistics
import threading

__all__ = [
    'run',
    'cat',
    'select',
    'grep',
    'cut',
    'sed',
    'foreach',
    'compact',
    'extract',
    'wc',
    'uniq',
    'sort',
    'tee',
    'asnum',
    'fsum',
    'fmean',
    'Result',
    'STDOUT',
    'DEVNULL',
    'PIPE',
]

def run(cmdline, /, *, stdin=None, stdout=PIPE, stderr=PIPE, encoding=None, errors=None):
    """
    run command line in a shell.
        stdin: string to be sent to child process or None
        stdout: PIPE(default, print to pipe)/DEVNULL(do not print)/None(print to console)
        stderr: PIPE/DEVNULL/None/STDOUT(redirect stderr to stdout)
        encoding: if None, detect by locale.getpreferredencoding()

    example:
        run("ls hello", stderr=STDOUT)
        run("cat hello", encoding='GBK')
        run("more", stdin="hello")
    """
    stdin_arg = None
    if stdin is not None:
        assert isinstance(stdin, str)
        stdin_arg = PIPE
    assert stdout in [PIPE, DEVNULL, None]
    assert stderr in [PIPE, DEVNULL, None, STDOUT]
    if encoding is None:
        encoding = locale.getpreferredencoding()
    with subprocess.Popen(cmdline, shell=True, stdin=stdin_arg, stdout=stdout, stderr=stderr, 
                          encoding=encoding, errors=errors) as proc:
        outs, errs = proc.communicate(stdin)
        return Result(outs, returncode=proc.returncode, stderr=errs)

def cat(pathname, /, *, encoding=None, errors=None, newline=None):
    """
    simulate `cat`, but support file encoding.
        encoding: the name of the encoding used to decode the file. The default encoding is platform dependent (whatever locale.getpreferredencoding() returns)
        errors: specifies how encoding and decoding errors are to be handled, include:
            'strict' to raise a ValueError exception if there is an encoding error. The None has the same effect.
            'ignore' ignores errors. Note that ignoring encoding errors can lead to data loss.
            'replace' causes a replacement marker (such as '?') to be inserted where there is malformed data.
            ...
    """
    try:
        with open(pathname, encoding=encoding, errors=errors, newline=newline) as file:
            return Result(file.read())
    except Exception as exp:
        return Result('', returncode=1, stderr=str(exp))

def _get_input(*, stdin=None, pathname=None, encoding=None, errors=None, newline=None):
    """
    return (result, error), if error, result is the error, else result is the input text.
    """
    narg = 0
    if stdin is not None:
        assert isinstance(stdin, str)
        narg += 1
    if pathname is not None:
        assert isinstance(pathname, str)
        narg += 1
    assert narg == 1, 'stdin or pathname, only one arg is accepted'
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors, newline=newline)
        if res:
            return res.stdout, False
        else:
            return res, True
    else:
        return stdin, False

def _find(lines, pattern, /, *, ignorecase=False, invert=False):
    """
    like `grep` but return matched indexes.
    """
    flags = 0
    if ignorecase:
        flags |= re.IGNORECASE
    indexes = []
    for i in range(len(lines)):
        m = re.search(pattern, lines[i], flags)
        if m:
            if not invert:
                indexes.append(i)
        else:
            if invert:
                indexes.append(i)
    return indexes

def _select(src, nums):
    res = []
    for num in nums:
        if isinstance(num, slice):
            res.extend(src.__getitem__(num))
        elif hasattr(num, '__iter__'):
            for n in num:
                res.append(src.__getitem__(n))
        else:
            res.append(src.__getitem__(num))
    return res

def select(*nums, stdin=None, pathname=None, encoding=None, errors=None):
    """
    select lines by index, range, slice.
    example:
        select(1, -1, range(2,4), slice(-3, -1), stdin="0\n1\n2\n3\n4\n5").compact(join_line=',')
        ===>
        1,5,2,3,3,4
    """
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines()
    return Result('\n'.join(_select(lines, nums)))

def _before(indexes, count, length):
    res = set()
    for index in indexes:
        if index < 0:
            index += length
        if index < 0 or index >= length:
            continue
        stop = index + 1
        start = stop - count - 1
        if start < 0:
            start = 0
        res.update(range(start, stop))
    return sorted(res)

def _after(indexes, count, length):
    res = set()
    for index in indexes:
        if index < 0:
            index += length
        if index < 0 or index >= length:
            continue
        start = index
        stop = start + count + 1
        if stop > length:
            stop = length
        res.update(range(start, stop))
    return sorted(res)

def _around(indexes, count, length):
    res = set()
    for index in indexes:
        if index < 0:
            index += length
        if index < 0 or index >= length:
            continue
        start = index - count
        if start < 0:
            start = 0
        stop = start + 2*count + 1
        if stop > length:
            stop = length
        res.update(range(start, stop))
    return sorted(res)

def grep(pattern, /, *, ignorecase=False, invert=False, before=None, around=None, after=None, stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `egrep` command.
        pattern: regular expression
        ignorecase: ignore case when search pattern
        invert: invert selection
        before: line count before the matched line, simulate `grep -B` command
        around: line count around the matched line, simulate `grep -C` command
        after: line count after the matched line, simulate `grep -A` command

    example:
        grep(r'Name:\s+\w+', stdin='  Name:   Tony\n  Age:    12')
        ===>
        Name:   Tony

        grep('t2', before=2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t0
        t1
        t2

        grep('t2', around=1, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t1
        t2
        t3

        grep('t2', after=2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t2
        t3
        t4
    """
    narg = 0
    for n in (before, around, after):
        if n is not None:
            assert isinstance(n, int)
            narg += 1
    assert narg <= 1, 'before/around/after, not more than one arg'
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines()
    indexes = _find(lines, pattern, ignorecase=ignorecase, invert=invert)
    if before is not None:
        indexes = _before(indexes, before, len(lines))
    elif around is not None:
        indexes = _around(indexes, around, len(lines))
    elif after is not None:
        indexes = _after(indexes, after, len(lines))

    if indexes:
        return Result('\n'.join(_select(lines, indexes)))
    else:
        return Result('', returncode=1)
    
def extract(pattern, /, *, ignorecase=False, join_group=' ', format_group=None, stdin=None, pathname=None, encoding=None, errors=None):
    """
    find matched string, matched string groups are formatted by `format_group` (if provided) or joined by `join_group`.
        pattern: regular expression
        ignorecase: ignore case when search pattern

    example:
        extract(r'(\w+):\s+(\w+)', stdin='  Name:   Tony\n  Age:    12', format_group='{0}={1}')
        ===>
        Name=Tony
        Age=12
    """
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    flags = 0
    if ignorecase:
        flags |= re.IGNORECASE
    res = []
    for line in text.splitlines():
        m = re.search(pattern, line, flags)
        if m:
            assert m.groups()
            if format_group is not None:
                res.append(format_group.format(*m.groups()))
            else:
                res.append(join_group.join(m.groups()))
    if res:
        return Result('\n'.join(res))
    else:
        return Result('', returncode=1)

def cut(*, delim=r'\s+', maxsplit=0, fields=(slice(0, None), ), join_field=' ', format_field=None, stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `cut` command.
        delim: delimiter(support regular expression)
        maxsplit: if maxsplit is nonzero, at most maxsplit splits occur for each line.
        fields: select fields before join/format
        join_field/format_field: selected fields are formatted by `format_field` (if provided) or joined by `join_field`

    example:
        cut(stdin="  Name:   Tony\n  Age:    12")
        ===>
        Name: Tony
        Age: 12
    """
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    res = []
    for line in text.splitlines():
        #parts = [p for p in re.split(delim, line) if (p and not p.isspace())] # strip blank field
        parts = _select(re.split(delim, line, maxsplit), fields)
        if format_field is not None:
            res.append(format_field.format(*parts))
        else:
            res.append(join_field.join(parts))
    if res:
        return Result('\n'.join(res))
    else:
        return Result('', returncode=1)

def sed(pattern, repl, /, *, count=0, ignorecase=False, stdin=None, pathname=None, encoding=None, errors=None):
    """
    substitute, simulate and enhancement of `sed "s/pattern/repl/xx" xxx`.
        count: maximum number of pattern occurrences to be replaced, if zero, all occurrences will be replaced.
        ignorecase: ignore case when search pattern

    example:
        sed(r'\s+', ' ', stdin="Name:   Tony\nAge: \t 12")
        ===>
        Name: Tony
        Age: 12

        sed(r'(\S+)\s+(\S+)', r'\g<1> "\g<2>"', stdin="Name:   Tony\nAge: \t 12")
        ===>
        Name: "Tony"
        Age: "12"
    """
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    flags = 0
    if ignorecase:
        flags |= re.IGNORECASE
    res = []
    for line in text.splitlines():
        line = re.sub(pattern, repl, line, count=count, flags=flags)
        res.append(line)
    return Result('\n'.join(res))

def foreach(type, proc, /, *, stdin=None, pathname=None, encoding=None, errors=None):
    """
    call `proc(text)` for each char/word/line until exhausted or `proc` return None.
    if `proc` return non-None, it will be appended to output. None will be passed to `proc` to indicate exhausted.
        type: iterate type, char/word/line
        proc: signature: proc(text:str|None) -> str|None
    """
    assert type in ('char', 'word', 'line'), 'valid iterate type: char, word, line'
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors, newline='') # do not translate newline for foreach('char')
    if err:
        return text
    def iterate(txts, res):
        for txt in txts:
            new = proc(txt)
            if new:
                res.append(new)
            elif new is None:
                return True
        return False
    res = []
    done = False
    if type == 'char':
        done = iterate(text, res)
    elif type == 'word':
        done = iterate(text.split(), res)
    else:
        done = iterate(text.splitlines(), res)
    if not done:
        iterate((None,), res) # tell proc no more text
    return Result(''.join(res))

def compact(*, strip=True, remove_empty_line=True, join_line=' ', stdin=None, pathname=None, encoding=None, errors=None):
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    res = []
    for line in text.splitlines():
        if strip:
            line = line.strip()
        if remove_empty_line and not line:
            continue
        res.append(line)
    return Result(join_line.join(res))

def wc(type, /, *, asnum=True, stdin=None, pathname=None, encoding=None, errors=None):
    """
    return count of 'char/word/line'.

        asnum: if true, convert to number
    """
    assert type in ('char', 'word', 'line'), 'valid wc type: char, word, line'
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors, newline='') # do not translate newline for wc('char')
    assert not err, f'failed to read from {pathname}'
    if type == 'char':
        length = len(text)
    elif type == 'word':
        length = len(text.split())
    else:
        length = len(text.splitlines())
    return length if asnum else Result(str(length))

def uniq(*, stdin=None, pathname=None, encoding=None, errors=None):
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines()
    if not lines:
        return Result('')
    res = [lines[0]]
    for i in range(1, len(lines)):
        if lines[i] != lines[i-1]:
            res.append(lines[i])
    return Result('\n'.join(res))

def sort(*, ascending=True, stdin=None, pathname=None, encoding=None, errors=None):
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines() # sorted(["0\n", "0"]) => ["0", "0\n"], so do not keep newline
    return Result('\n'.join(sorted(lines, reverse=not ascending)))

def tee(pathname, /, *, stdin, append=False, encoding=None, errors=None, newline=None):
    mode = 'a' if append else 'w'
    try:
        with open(pathname, mode, encoding=encoding, errors=errors, newline=newline) as fp:
            fp.write(stdin)
        return Result(stdin)
    except Exception as exp:
        return Result('', returncode=1, stderr=str(exp))

def asnum(*, int_base=10, flatten=True, stdin=None, pathname=None, encoding=None, errors=None):
    """
    find and convert to number

        int_base: base for integer, if it is not prefixed with 0xX,0bB,0oO
        flatten: if true, return [n, n, ...] instead of [[n, n, ...], [n, n, ...], ...]
    """
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    assert not err, f'failed to read from {pathname}'
    nums = []
    token_regex = '|'.join('(?P<%s>%s)' % pair for pair in [
        ('hex', r'[+-]?0[xX][0-9a-fA-F]+'),
        ('bin', r'[+-]?0[bB][01]+'),
        ('oct', r'[+-]?0[oO][0-7]+'),
        ('efloat', r'[+-]?\d+\.?\d*([eE]\d+)'),
        ('float', r'[+-]?\d+\.\d*'),
        ('int', r'[+-]?\d+'),
        ])
    for line in text.splitlines():
        if flatten:
            tmp = nums
        else:
            tmp = []
        for mo in re.finditer(token_regex, line):
            kind = mo.lastgroup
            value = mo.group()
            if kind in ('hex', 'bin', 'oct'):
                value = int(value, 0)
            elif kind in ('float', 'efloat'):
                value = float(value)
            else: # int
                value = int(value, int_base)
            tmp.append(value)
        if not flatten and tmp: # skip empty list
            nums.append(tmp)
    return nums

def fsum(*, int_base=10, stdin=None, pathname=None, encoding=None, errors=None):
    """
    return the sum of the numbers in the text.
    """
    nums = asnum(int_base=int_base, flatten=True, stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    return math.fsum(nums)

def fmean(*, int_base=10, stdin=None, pathname=None, encoding=None, errors=None):
    """
    return the mean of the numbers in the text.
    """
    nums = asnum(int_base=int_base, flatten=True, stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    return statistics.fmean(nums)

class Result:
    __thlocal = threading.local()
    __thlocal.cache = None
    @classmethod
    def cache(cls):
        return cls.__thlocal.cache

    def __init__(self, stdout, /, *, returncode=0, stderr=None):
        self._returncode = returncode
        self._stdout = stdout if stdout else ''
        self._stderr = stderr if stderr else ''

    @property
    def returncode(self):
        return self._returncode

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr

    def __bool__(self):
        return self._returncode == 0

    def cache_self(self):
        Result.__thlocal.cache = self
        return self

    def run(self, cmdline, /, *, stdout=PIPE, stderr=PIPE, encoding=None, errors=None):
        """
        simulate '|' in bash.
        """
        return run(cmdline, stdin=self._stdout, stdout=stdout, stderr=stderr, encoding=encoding, errors=errors)

    def select(self, *nums):
        return select(*nums, stdin=self._stdout)

    def grep(self, pattern, /, *, ignorecase=False, invert=False, before=None, around=None, after=None):
        return grep(pattern, ignorecase=ignorecase, invert=invert, before=before, around=around, after=after, stdin=self._stdout)

    def extract(self, pattern, /, *, ignorecase=False, join_group=' ', format_group=None):
        return extract(pattern, ignorecase=ignorecase, join_group=join_group, format_group=format_group, stdin=self._stdout)

    def cut(self, *, delim=r'\s+', maxsplit=0, fields=(slice(0, None), ), join_field=' ', format_field=None):
        return cut(delim=delim, maxsplit=maxsplit, fields=fields, join_field=join_field, format_field=format_field, stdin=self._stdout)

    def sed(self, pattern, repl, /, *, count=0, ignorecase=False):
        return sed(pattern, repl, count=count, ignorecase=ignorecase, stdin=self._stdout)

    def foreach(self, type, proc, /):
        return foreach(type, proc, stdin=self._stdout)

    def xargs(self, format, /, *, encoding=None, errors=None):
        """
        simulate `xargs` command.
            format: command line format, '{line}' in `format` will be replaced by each line of string
            
        example:
            run('find . -name \\*.txt').xargs('echo {line} && cat {line}') # echo and cat all .txt files
            run('find . -name \\*.txt').xargs('ls -l {line}') # list all .txt files
        """
        returncode = 0
        stdout = []
        stderr = []
        for line in self._stdout.splitlines():
            if not (line and not line.isspace()):
                continue
            res = run(format.format(line=line), encoding=encoding, errors=errors)
            if not res:
                returncode = 1
            stdout.append(res.stdout)
            stderr.append(res.stderr)
        return Result(''.join(stdout), returncode=returncode, stderr=''.join(stderr))

    def indent(self, prefix='  ', /, *, predicate=None):
        return Result(textwrap.indent(self._stdout, prefix, predicate))

    def dedent(self):
        return Result(textwrap.dedent(self._stdout))

    def compact(self, *, strip=True, remove_empty_line=True, join_line=' '):
        return compact(strip=strip, remove_empty_line=remove_empty_line, join_line=join_line, stdin=self._stdout)

    def wc(self, type, /, *, asnum=True):
        return wc(type, asnum=asnum, stdin=self._stdout)

    def uniq(self):
        return uniq(stdin=self._stdout)

    def sort(self, *, ascending=True):
        return sort(ascending=ascending, stdin=self._stdout)

    def tee(self, pathname, /, *, append=False, encoding=None, errors=None, newline=None):
        return tee(pathname, append=append, stdin=self._stdout, encoding=encoding, errors=errors, newline=newline)

    def asnum(self, /, *, int_base=10, flatten=True):
        return asnum(int_base=int_base, flatten=flatten, stdin=self._stdout)

    def fsum(self, /, *, int_base=10):
        return fsum(int_base=int_base, stdin=self._stdout)

    def fmean(self, /, *, int_base=10):
        return fmean(int_base=int_base, stdin=self._stdout)

    def print(self, *, prolog=None, body_end=None, epilog=None, file=sys.stdout):
        """
        print with optional prolog and epilog.

            body_end: if None, print newline if body not ends with newline
        """
        if prolog:
            print(prolog, end='', file=file, flush=True)
        if body_end is None:
            body_end = '' if self._stdout.endswith('\n') else '\n'
        print(self._stdout, end=body_end, file=file, flush=True)
        if epilog:
            print(epilog, end='', file=file, flush=True)

    def __repr__(self):
        text = self._stdout if self.__bool__() else self._stderr
        lines = text.splitlines()
        if len(lines) > 5:
            res = []
            res.extend(lines.__getitem__(slice(0,2)))
            res.append('... {} lines collapsed ...'.format(len(lines)-4))
            res.extend(lines.__getitem__(slice(-2, None)))
            return repr('\n'.join(res))
        else:
            return repr(text)

Result.run.__doc__ = run.__doc__
Result.select.__doc__ = select.__doc__
Result.grep.__doc__ = grep.__doc__
Result.cut.__doc__ = cut.__doc__
Result.sed.__doc__ = sed.__doc__
Result.foreach.__doc__ = foreach.__doc__
Result.compact.__doc__ = compact.__doc__
Result.extract.__doc__ = extract.__doc__
Result.wc.__doc__ = wc.__doc__
Result.uniq.__doc__ = uniq.__doc__
Result.sort.__doc__ = sort.__doc__
Result.tee.__doc__ = tee.__doc__
Result.asnum.__doc__ = asnum.__doc__
Result.fsum.__doc__ = fsum.__doc__
Result.fmean.__doc__ = fmean.__doc__

if __name__ == '__main__':
    def assert_eq(test, real, expect):
        assert real == expect, f'{test} failed\nExpect:\n{repr(expect)}\nReal:\n{repr(real)}'
    res = Result("0\n1\n2\n3\n4\n5")
    assert_eq('select', res.select(1, -1, range(2,4), slice(-3, -1)).stdout, '1\n5\n2\n3\n3\n4')

    res = Result('  Name:   Tony\n  Age:    12')
    assert_eq('grep', res.grep(r'Name:').stdout, '  Name:   Tony')
    assert_eq('invert grep', res.grep(r'Name:', invert=True).stdout, '  Age:    12')
    assert_eq('extract', res.extract(r'(\w+):\s+(\w+)', format_group='{0}={1}').stdout, 'Name=Tony\nAge=12')
    res = Result('a\n  \n\nb\n')
    assert_eq('invert grep preserve whitespace', res.grep(r'a', invert=True).stdout, '  \n\nb')
    assert_eq('grep nothing', res.grep(r'Name').__bool__(), False)
    assert_eq('invert grep nothing', res.grep(r'Name', invert=True).stdout, 'a\n  \n\nb')

    res = Result("t0\nt1\nt2\nt3\nt4\nt5\nt6")
    assert_eq('before pattern', res.grep('t2', before=2).stdout, 't0\nt1\nt2')
    assert_eq('after pattern', res.grep('t2', after=2).stdout, 't2\nt3\nt4')
    assert_eq('around pattern', res.grep('t2', around=1).stdout, 't1\nt2\nt3')
    assert_eq('grep nothing around pattern', res.grep('tx', around=1).__bool__(), False)

    res = Result("1, 2, 3, 4, 5, 6\nt1,    t2,t3, t4, t5, t6, t7, t8")
    assert_eq('cut', res.cut(delim=r',\s*', fields=(1, range(2, 4), slice(-2, None))).stdout,
              '2 3 4 5 6\nt2 t3 t4 t7 t8')
    assert_eq('cut', res.cut(delim=r',\s*', fields=(1, range(2, 4), slice(-2, None)), format_field='{0}x{4}').stdout,
              '2x6\nt2xt8')

    res = Result("Name:   Tony\nAge: \t 12")
    assert_eq('sed', res.sed(r'\s+', ' ').stdout, 'Name: Tony\nAge: 12')
    assert_eq('sed sub group repl', res.sed(r'(\S+)\s+(\S+)', r'\g<1> "\g<2>"').stdout, 'Name: "Tony"\nAge: "12"')

    res = Result('1 \r\n\n 2\n 3')
    def foreach_appendx(txt):
        if txt is None:
            return 'done'
        return 'x'+txt
    assert_eq('foreach char', res.foreach('char', foreach_appendx).stdout, 'x1x x\rx\nx\nx x2x\nx x3done')
    assert_eq('foreach word', res.foreach('word', foreach_appendx).stdout, 'x1x2x3done')
    assert_eq('foreach line', res.foreach('line', foreach_appendx).stdout, 'x1 xx 2x 3done')
    def foreach_break(txt):
        if txt.find('2') != -1:
            return None
        else:
            return txt
    assert_eq('foreach char break', res.foreach('char', foreach_break).stdout, '1 \r\n\n ')
    assert_eq('foreach word break', res.foreach('word', foreach_break).stdout, '1')
    assert_eq('foreach line break', res.foreach('line', foreach_break).stdout, '1 ')

    res = Result('1 \n\n 2\n 3')
    assert_eq('compact with strip', res.compact().stdout, '1 2 3')
    assert_eq('compact without strip', res.compact(strip=False, join_line=',').stdout, '1 , 2, 3')
    assert_eq('compact without remove empty line', res.compact(remove_empty_line=False, join_line=',').stdout, '1,,2,3')

    res = Result('1 \n 2\n 3')
    assert_eq('wc char', res.wc('char', asnum=False).stdout, '8')
    assert_eq('wc word', res.wc('word', asnum=False).stdout, '3')
    assert_eq('wc line', res.wc('line'), 3)

    res = Result('1\n1\n2\n 2')
    assert_eq('uniq', res.uniq().stdout, '1\n2\n 2')

    res = Result('1\n3\n2')
    assert_eq('sort ascending', res.sort().stdout, '1\n2\n3')
    assert_eq('sort descending', res.sort(ascending=False).stdout, '3\n2\n1')

    res = Result('hello1,-2,- 3x\n   \nhello x3e1 3.1 3.1e1\n0x12 -0o666 +0b11')
    assert_eq('asnum', res.asnum(flatten=False), [[1,-2,3], [3e1, 3.1, 3.1e1], [0x12, -0o666, 0b11]])
    assert_eq('asnum flatten', res.asnum(), [1,-2,3, 3e1, 3.1, 3.1e1, 0x12, -0o666, 0b11])

    res = Result('1\n2\n3')
    assert_eq('sum', res.fsum(), 6.0)
    assert_eq('mean', res.fmean(), 2.0)

    res = Result('1\n2\n3')
    assert_eq('xargs', res.xargs('echo {line}').stdout, "1\n2\n3\n")

    res = Result('''  Child:
      Name:Tony
        Age:12''')
    assert_eq('dedent', res.dedent().stdout, '''Child:
    Name:Tony
      Age:12''')
    assert_eq('dedent more', res.dedent().dedent().stdout, '''Child:
    Name:Tony
      Age:12''')

    res = Result('''Child:
    Name:Tony
      Age:12''')
    assert_eq('indent', res.indent('**').stdout, '''**Child:
**    Name:Tony
**      Age:12''')

    res = Result('')
    assert_eq('bool of success result is true', res.__bool__(), True)

    res = Result('', returncode=1)
    assert_eq('bool of fail result is false', res.__bool__(), False)

    res = Result('1\n2\n3')
    assert_eq('cache self return self', res.cache_self(), res)
    assert_eq('equal get from class and instance', res.cache(), Result.cache())
    res.grep('2').wc('line')
    assert_eq('get back from cache', res.cache(), res)
