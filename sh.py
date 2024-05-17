import subprocess
from subprocess import STDOUT, DEVNULL, PIPE
import sys
import re
import textwrap
import locale
import math
import io
import statistics
from glob import glob as _glob
from datetime import datetime

__all__ = [
    'now',
    'glob',
    'run',
    'cat',
    'select',
    'grep',
    'grep_between',
    'cut',
    'sed',
    'iterate',
    'foreach',
    'compact',
    'extract',
    'wc',
    'distribution',
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


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def glob(pathname, root_dir=None):
    return Result('\n'.join(_glob(pathname, root_dir=root_dir, recursive=True)))


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
        encoding: the name of the encoding used to decode the file.
            The default encoding is platform dependent (whatever locale.getpreferredencoding() returns)
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
    assert narg == 1, 'stdin/pathname, accept one argument.'
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
    similar to `grep` but return matched indexes.
    """
    flags = 0
    if ignorecase:
        flags |= re.IGNORECASE
    indexes = set()
    for i in range(len(lines)):
        m = re.search(pattern, lines[i], flags)
        if m:
            if not invert:
                indexes.add(i)
        else:
            if invert:
                indexes.add(i)
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
        select(1, -1, range(2,4), slice(-3, -1), stdin="0\n1\n2\n3\n4\n5").compact(join_with=',')
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
    return res


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
    return res


def grep(pattern, /, *, ignorecase=False, invert=False, before=None, after=None, 
         stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `egrep` command.
        pattern: regular expression
        ignorecase: ignore case when search pattern
        invert: invert selection
        before: line count before the matched line, simulate `grep -B` command
        after: line count after the matched line, simulate `grep -A` command

    example:
        grep('Name:\\s+\\w+', stdin='  Name:   Tony\n  Age:    12')
        ===>
        Name:   Tony

        grep('t2', before=2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t0
        t1
        t2

        grep('t2', before=1, after=1, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
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
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines()
    indexes = _find(lines, pattern, ignorecase=ignorecase, invert=invert)
    if before is not None:
        assert isinstance(before, int)
        indexes = _before(indexes, before, len(lines))

    if after is not None:
        assert isinstance(after, int)
        indexes = _after(indexes, after, len(lines))

    if indexes:
        return Result('\n'.join(_select(lines, sorted(indexes))))
    else:
        return Result('', returncode=1)


def _find_first(lines, pattern, from_index, /, *, ignorecase=False):
    """
    similar to `_find` but return the first index.
    """
    flags = 0
    if ignorecase:
        flags |= re.IGNORECASE
    for i in range(from_index, len(lines)):
        m = re.search(pattern, lines[i], flags)
        if m:
            return i
    return None


def grep_between(pattern_beg, pattern_end, /, *, ignorecase=False, before=None, after=None,
                 stdin=None, pathname=None, encoding=None, errors=None):
    """
    grep text between `pattern_beg` and `pattern_end`.
    """
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines()
    indexes = set()
    idx_beg = 0
    while True:
        idx_beg = _find_first(lines, pattern_beg, idx_beg, ignorecase=ignorecase)
        if idx_beg is None:
            break
        idx_end = _find_first(lines, pattern_end, idx_beg+1, ignorecase=ignorecase)
        if idx_end is None:
            break
        indexes.update(range(idx_beg, idx_end+1))
        idx_beg = idx_end+1

    if before is not None:
        assert isinstance(before, int)
        indexes = _before(indexes, before, len(lines))

    if after is not None:
        assert isinstance(after, int)
        indexes = _after(indexes, after, len(lines))

    if indexes:
        return Result('\n'.join(_select(lines, sorted(indexes))))
    else:
        return Result('', returncode=1)


def extract(pattern, /, *, ignorecase=False, join_with=' ', format_with=None,
            stdin=None, pathname=None, encoding=None, errors=None):
    """
    find matched string, matched string groups are formatted by `format_with` (if provided) or joined by `join_with`.
        pattern: regular expression
        ignorecase: ignore case when search pattern

    example:
        extract('(\\w+):\\s+(\\w+)', stdin='  Name:   Tony\n  Age:    12', format_with='{0}={1}')
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
            if format_with is not None:
                res.append(format_with.format(*m.groups()))
            else:
                res.append(join_with.join(m.groups()))
    if res:
        return Result('\n'.join(res))
    else:
        return Result('', returncode=1)


def cut(*fields, delim=r'\s+', maxsplit=0, join_with=' ', format_with=None,
        stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `cut` command.
        delim: delimiter(support regular expression)
        maxsplit: if maxsplit is nonzero, at most maxsplit splits occur for each line.
        fields: select fields before join/format
        join_with/format_with: selected fields are formatted by `format_with` (if provided) or joined by `join_with`

    example:
        cut(0, 1, stdin="  Name:   Tony\n  Age:    12")
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
        if format_with is not None:
            res.append(format_with.format(*parts))
        else:
            res.append(join_with.join(parts))
    if res:
        return Result('\n'.join(res))
    else:
        return Result('', returncode=1)


def sed(pattern, repl, /, *, maxrepl=0, ignorecase=False, stdin=None, pathname=None, encoding=None, errors=None):
    """
    substitute, simulate and enhancement of `sed "s/pattern/repl/xx" xxx`.
        maxrepl: maximum number of pattern occurrences to be replaced, if zero, all occurrences will be replaced.
        ignorecase: ignore case when search pattern

    example:
        sed('\\s+', ' ', stdin="Name:   Tony\nAge: \t 12")
        ===>
        Name: Tony
        Age: 12

        sed('(\\S+)\\s+(\\S+)', '\\g<1> "\\g<2>"', stdin="Name:   Tony\nAge: \t 12")
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
        line = re.sub(pattern, repl, line, count=maxrepl, flags=flags)
        res.append(line)
    return Result('\n'.join(res))


def iterate(type, /, *, stdin=None, pathname=None, encoding=None, errors=None):
    """
    iterate as 'char/word/line'.
    """
    assert type in ('char', 'word', 'line'), 'valid iterate type: char, word, line'
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors, newline='') # do not translate newline for iterate('char')
    assert not err, f'failed to read from {pathname}'
    if type == 'char':
        return text
    elif type == 'word':
        return text.split()
    else:
        return text.splitlines()


def foreach(type, proc, /, *, stdin=None, pathname=None, encoding=None, errors=None):
    """
    call `proc(text)` for each char/word/line until exhausted or `proc` raise StopIteration.
    if `proc` return str, it will be appended to output.
        type: iterate type, char/word/line
        proc: signature: proc(text:str) -> str
    """
    res = []
    for txt in iterate(type, stdin=stdin, pathname=pathname, encoding=encoding, errors=errors):
        try:
            new = proc(txt)
            if new:
                assert isinstance(new, str)
                res.append(new)
        except StopIteration:
            break
    return Result(''.join(res))


def compact(*, strip=True, remove_empty_line=True, join_with=' ', stdin=None, pathname=None, encoding=None, errors=None):
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
    return Result(join_with.join(res))


def wc(type, /, *, return_num=True, stdin=None, pathname=None, encoding=None, errors=None):
    """
    return count of 'char/word/line'.

        return_num: if true, convert to number
    """
    length = len(iterate(type, stdin=stdin, pathname=pathname, encoding=encoding, errors=errors))
    return length if return_num else Result(str(length))


def distribution(type, /, *, return_map=True, stdin=None, pathname=None, encoding=None, errors=None):
    """
    return distribution of 'char/word/line'.

        return_map: if true, return distribution map
    """
    dist = {}
    for item in iterate(type, stdin=stdin, pathname=pathname, encoding=encoding, errors=errors):
        dist[item] = dist.get(item, 0) + 1
    if return_map:
        return dist
    else:
        sio = io.StringIO()
        for item in dist:
            sio.write(f'{dist[item]} {item}\n')
        return Result(sio.getvalue())


def uniq(*, ignorecase=False, stdin=None, pathname=None, encoding=None, errors=None):
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines()
    if not lines:
        return Result('')
    if ignorecase:
        cmplines = [line.casefold() for line in lines]
    else:
        cmplines = lines
    res = [lines[0]]
    for i in range(1, len(lines)):
        if cmplines[i] != cmplines[i-1]:
            res.append(lines[i])
    return Result('\n'.join(res))


def sort(*, ascending=True, ignorecase=False, stdin=None, pathname=None, encoding=None, errors=None):
    text, err = _get_input(stdin=stdin, pathname=pathname, encoding=encoding, errors=errors)
    if err:
        return text
    lines = text.splitlines() # sorted(["0\n", "0"]) => ["0", "0\n"], so do not keep newline
    return Result('\n'.join(sorted(lines, key=str.casefold if ignorecase else None, reverse=not ascending)))


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

    def pipe(self, cmdline, /, *, encoding=None, errors=None):
        """
        simulate '|' in bash.
        """
        return run(cmdline, stdin=self._stdout, stdout=PIPE, stderr=PIPE, encoding=encoding, errors=errors)

    def select(self, *nums):
        return select(*nums, stdin=self._stdout)

    def grep(self, pattern, /, *, ignorecase=False, invert=False, before=None, after=None):
        return grep(pattern, ignorecase=ignorecase, invert=invert, before=before, after=after, stdin=self._stdout)

    def grep_between(self, pattern_beg, pattern_end, /, *, ignorecase=False, before=None, after=None,
                     stdin=None, pathname=None, encoding=None, errors=None):
        return grep_between(pattern_beg, pattern_end, ignorecase=ignorecase, before=before, after=after, stdin=self._stdout)

    def extract(self, pattern, /, *, ignorecase=False, join_with=' ', format_with=None):
        return extract(pattern, ignorecase=ignorecase, join_with=join_with, format_with=format_with, stdin=self._stdout)

    def cut(self, *fields, delim=r'\s+', maxsplit=0, join_with=' ', format_with=None):
        return cut(*fields, delim=delim, maxsplit=maxsplit, join_with=join_with, format_with=format_with, stdin=self._stdout)

    def sed(self, pattern, repl, /, *, maxrepl=0, ignorecase=False):
        return sed(pattern, repl, maxrepl=maxrepl, ignorecase=ignorecase, stdin=self._stdout)

    def iterate(self, type, /):
        return iterate(type, stdin=self._stdout)

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

    def compact(self, *, strip=True, remove_empty_line=True, join_with=' '):
        return compact(strip=strip, remove_empty_line=remove_empty_line, join_with=join_with, stdin=self._stdout)

    def wc(self, type, /, *, return_num=True):
        return wc(type, return_num=return_num, stdin=self._stdout)

    def distribution(self, type, /, *, return_map=True):
        return distribution(type, return_map=return_map, stdin=self._stdout)

    def uniq(self, *, ignorecase=False):
        return uniq(ignorecase=ignorecase, stdin=self._stdout)

    def sort(self, *, ascending=True, ignorecase=False):
        return sort(ascending=ascending, ignorecase=ignorecase, stdin=self._stdout)

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


Result.pipe.__doc__ = run.__doc__
Result.select.__doc__ = select.__doc__
Result.grep.__doc__ = grep.__doc__
Result.cut.__doc__ = cut.__doc__
Result.sed.__doc__ = sed.__doc__
Result.iterate.__doc__ = iterate.__doc__
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
    assert_eq('extract', res.extract(r'(\w+):\s+(\w+)', format_with='{0}={1}').stdout, 'Name=Tony\nAge=12')
    res = Result('a\n  \n\nb\n')
    assert_eq('invert grep preserve whitespace', res.grep(r'a', invert=True).stdout, '  \n\nb')
    assert_eq('grep nothing', res.grep(r'Name').__bool__(), False)
    assert_eq('invert grep nothing', res.grep(r'Name', invert=True).stdout, 'a\n  \n\nb')

    res = Result("t0\nt1\nt2\nt3\nt4\nt5\nt6")
    assert_eq('before pattern', res.grep('t2', before=2).stdout, 't0\nt1\nt2')
    assert_eq('after pattern', res.grep('t2', after=2).stdout, 't2\nt3\nt4')
    assert_eq('around pattern', res.grep('t2', before=1, after=1).stdout, 't1\nt2\nt3')
    assert_eq('grep nothing around pattern', res.grep('tx', before=1, after=1).__bool__(), False)
    assert_eq('grep between around', res.grep_between('t2', 't4', before=1, after=1).stdout, 't1\nt2\nt3\nt4\nt5')

    res = Result("1, 2, 3, 4, 5, 6\nt1,    t2,t3, t4, t5, t6, t7, t8")
    assert_eq('cut', res.cut(1, range(2, 4), slice(-2, None), delim=r',\s*').stdout,
              '2 3 4 5 6\nt2 t3 t4 t7 t8')
    assert_eq('cut', res.cut(1, range(2, 4), slice(-2, None), delim=r',\s*', format_with='{0}x{4}').stdout,
              '2x6\nt2xt8')

    res = Result("Name:   Tony\nAge: \t 12")
    assert_eq('sed', res.sed(r'\s+', ' ').stdout, 'Name: Tony\nAge: 12')
    assert_eq('sed sub group repl', res.sed(r'(\S+)\s+(\S+)', r'\g<1> "\g<2>"').stdout, 'Name: "Tony"\nAge: "12"')

    res = Result('1 \r\n\n 2\n 3')
    def foreach_appendx(txt):
        return 'x'+txt
    assert_eq('foreach char', res.foreach('char', foreach_appendx).stdout, 'x1x x\rx\nx\nx x2x\nx x3')
    assert_eq('foreach word', res.foreach('word', foreach_appendx).stdout, 'x1x2x3')
    assert_eq('foreach line', res.foreach('line', foreach_appendx).stdout, 'x1 xx 2x 3')
    def foreach_break(txt):
        if txt.find('2') != -1:
            raise StopIteration
        else:
            return txt
    assert_eq('foreach char break', res.foreach('char', foreach_break).stdout, '1 \r\n\n ')
    assert_eq('foreach word break', res.foreach('word', foreach_break).stdout, '1')
    assert_eq('foreach line break', res.foreach('line', foreach_break).stdout, '1 ')
    assert_eq('iterate word', list(res.iterate('word')), ['1', '2', '3'])

    res = Result('1 \n\n 2\n 3')
    assert_eq('compact with strip', res.compact().stdout, '1 2 3')
    assert_eq('compact without strip', res.compact(strip=False, join_with=',').stdout, '1 , 2, 3')
    assert_eq('compact without remove empty line', res.compact(remove_empty_line=False, join_with=',').stdout, '1,,2,3')

    res = Result('1 \n 2\n 3')
    assert_eq('wc char', res.wc('char', return_num=False).stdout, '8')
    assert_eq('wc word', res.wc('word', return_num=False).stdout, '3')
    assert_eq('wc line', res.wc('line'), 3)

    res = Result('1\n2\n3\n2\n1')
    assert_eq('char dist', res.distribution('char')['1'], 2)
    assert_eq('char dist', res.distribution('char')['\n'], 4)
    assert_eq('word dist', res.distribution('word')['2'], 2)
    assert_eq('line dist', res.distribution('line')['2'], 2)
    assert_eq('line dist', res.distribution('line', return_map=False).sort().stdout, "1 3\n2 1\n2 2")

    res = Result('1\n1\n2\n 2')
    assert_eq('uniq', res.uniq().stdout, '1\n2\n 2')
    res = Result('a\nA\nB\nb\nb')
    assert_eq('case sensitive uniq', res.uniq().stdout, 'a\nA\nB\nb')
    assert_eq('case insensitive uniq', res.uniq(ignorecase=True).stdout, 'a\nB')

    res = Result('1\n3\n2')
    assert_eq('sort ascending', res.sort().stdout, '1\n2\n3')
    assert_eq('sort descending', res.sort(ascending=False).stdout, '3\n2\n1')
    res = Result('a\nB\nA\nb')
    assert_eq('case sensitive sort ascending', res.sort().stdout, 'A\nB\na\nb')
    assert_eq('case insensitive sort ascending', res.sort(ignorecase=True).stdout, 'a\nA\nB\nb')
    assert_eq('case insensitive sort decending', res.sort(ascending=False, ignorecase=True).stdout, 'B\nb\na\nA')

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
