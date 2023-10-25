import subprocess
from subprocess import STDOUT, DEVNULL, PIPE
import sys
import re
import textwrap
import locale

__all__ = [
    'run',
    'cat',
    'grep',
    'before',
    'after',
    'around',
    'select',
    'cut',
    'sed',
    'foreach',
    'compact',
    'wc',
    'uniq',
    'sort',
    'asnum',
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
        assert isinstance(cmdline, str)
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

def _assert_exclusive(**kwargs):
    found = 0
    for kw in kwargs:
        if kwargs[kw] is not None:
            found += 1
    assert found == 1, f'{found} argument(s) provided, one and only one argument is required: {", ".join(kwargs.keys())}'

def grep(pattern, /, *, ignorecase=False, invert=False, group_sep=' ', stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `egrep` command.
        pattern: regular expression, if group is used, matched groups are joined by `group_sep`
        ignorecase: ignore case when search pattern
        invert: invert selection
        group_sep: separator of groups
        
    example:
        grep(r'(\S+):\s+(\S+)', group_sep=': ', stdin='  Name:   Tony\n  Age:    12')
        ===>
        Name: Tony
        Age: 12
    """
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    flags = 0
    if ignorecase:
        flags |= re.IGNORECASE
    res = []
    for line in text.splitlines():
        m = re.search(pattern, line, flags)
        if m:
            if not invert:
                if m.groups():
                    line = group_sep.join(m.groups())
                res.append(line)
        else:
            if invert:
                res.append(line)
    if res:
        return Result('\n'.join(res))
    else:
        return Result('', returncode=1)

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

def _select(src, *nums):
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
        select(1, -1, range(2,4), slice(-3, -1), stdin="0\n1\n2\n3\n4\n5").compact(join=',')
        ===>
        1,5,2,3,3,4
    """
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    lines = text.splitlines()
    return Result('\n'.join(_select(lines, *nums)))

def _before(*indexes, count, length):
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

def before(index, count, /, *, ignorecase=False, invert=False, stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `grep -B` command.
        index: line index or regexp
        count: line count before the matched line

    example:
        before(2, 2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        or
        before('t2', 2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t0
        t1
        t2
    """
    assert isinstance(index, (int, str))
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    lines = text.splitlines()
    if isinstance(index, int):
        indexes = _before(index, count=count, length=len(lines))
    else:
        # index is regexp pattern
        indexes = _find(lines, index, ignorecase=ignorecase, invert=invert)
        indexes = _before(*indexes, count=count, length=len(lines))
    return Result('\n'.join(_select(lines, *indexes)))

def _after(*indexes, count, length):
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

def after(index, count, /, *, ignorecase=False, invert=False, stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `grep -A` command.
        index: line index or regexp
        count: line count after the matched line

    example:
        after(2, 2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        or
        after('t2', 2, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t2
        t3
        t4
    """
    assert isinstance(index, (int, str))
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    lines = text.splitlines()
    if isinstance(index, int):
        indexes = _after(index, count=count, length=len(lines))
    else:
        # index is regexp pattern
        indexes = _find(lines, index, ignorecase=ignorecase, invert=invert)
        indexes = _after(*indexes, count=count, length=len(lines))
    return Result('\n'.join(_select(lines, *indexes)))

def _around(*indexes, count, length):
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

def around(index, count, /, *, ignorecase=False, invert=False, stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `grep -C` command.
        index: line index or regexp
        count: line count around the matched line

    example:
        around(2, 1, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        or
        around('t2', 1, stdin="t0\nt1\nt2\nt3\nt4\nt5\nt6")
        ===>
        t1
        t2
        t3
    """
    assert isinstance(index, (int, str))
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    lines = text.splitlines()
    if isinstance(index, int):
        indexes = _around(index, count=count, length=len(lines))
    else:
        # index is regexp pattern
        indexes = _find(lines, index, ignorecase=ignorecase, invert=invert)
        indexes = _around(*indexes, count=count, length=len(lines))
    return Result('\n'.join(_select(lines, *indexes)))

def cut(*, delim=r'\s+', maxsplit=0, fields=(slice(0, None), ), join=' ', format=None, stdin=None, pathname=None, encoding=None, errors=None):
    """
    simulate `cut` command.
        delim: delimiter(support regular expression)
        maxsplit: if maxsplit is nonzero, at most maxsplit splits occur for each line.
        fields: select fields before join/format
        join/format: selected fields are formatted by `format` (if provided) or joined by `join`

    example:
        cut(stdin="  Name:   Tony\n  Age:    12")
        ===>
        Name: Tony
        Age: 12
    """
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    res = []
    for line in text.splitlines():
        #parts = [p for p in re.split(delim, line) if (p and not p.isspace())] # strip blank field
        parts = _select(re.split(delim, line, maxsplit), *fields)
        if format is not None:
            res.append(format.format(*parts))
        else:
            res.append(join.join(parts))
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
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
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
    call `proc(text)` for each char/word/line until exhausted or `proc` return True
        type: iterate type, char/word/line
        proc: signature: proc(text) -> bool
    """
    assert type in ('char', 'word', 'line'), 'valid iterate type: char, word, line'
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return None
        text = res.stdout
    else:
        text = stdin
    if type == 'char':
        txts = text
    elif type == 'word':
        txts = text.split()
    else:
        txts = text.splitlines()
    for txt in txts:
        if proc(txt):
            break

def compact(*, strip=True, remove_empty_line=True, join=' ', stdin=None, pathname=None, encoding=None, errors=None):
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    res = []
    for line in text.splitlines():
        if strip:
            line = line.strip()
        if remove_empty_line and not line:
            continue
        res.append(line)
    return Result(join.join(res))

def wc(type, /, *, stdin=None, pathname=None, encoding=None, errors=None):
    assert type in ('char', 'word', 'line'), 'valid wc type: char, word, line'
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors, newline='') # do not translate newline for wc('char')
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    if type == 'char':
        length = len(text)
    elif type == 'word':
        length = len(text.split())
    else:
        length = len(text.splitlines())
    return Result(str(length))

def uniq(*, stdin=None, pathname=None, encoding=None, errors=None):
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    lines = text.splitlines()
    if not lines:
        return Result('')
    res = [lines[0]]
    for i in range(1, len(lines)):
        if lines[i] != lines[i-1]:
            res.append(lines[i])
    return Result('\n'.join(res))

def sort(*, ascending=True, stdin=None, pathname=None, encoding=None, errors=None):
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return res
        text = res.stdout
    else:
        text = stdin
    lines = text.splitlines() # sorted(["0\n", "0"]) => ["0", "0\n"], so do not keep newline
    return Result('\n'.join(sorted(lines, reverse=not ascending)))

def asnum(*, int_base=10, dim_reduction=False, stdin=None, pathname=None, encoding=None, errors=None):
    """
    find and convert to number, return None if can not read file.

        int_base: base for integer, if it is not prefixed with 0xX,0bB,0oO
        dim_reduction: when true, reduce dimension, return single if only one number, else return one-dimension list
    """
    _assert_exclusive(stdin=stdin, pathname=pathname)
    if pathname:
        res = cat(pathname, encoding=encoding, errors=errors)
        if not res:
            return None
        text = res.stdout
    else:
        text = stdin
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
        if dim_reduction:
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
            elif kind == 'int':
                value = int(value, int_base)
            tmp.append(value)
        if not dim_reduction and tmp: # skip empty list
            nums.append(tmp)
    if dim_reduction and len(nums) == 1:
        return nums[0]
    else:
        return nums

class Result:
    class NOP:
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, name):
            return self
        def __setattr__(self, name, value):
            return self
        @property
        def nop(self):
            return True
        def __bool__(self):
            return False

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

    @property
    def nop(self):
        return False

    def __bool__(self):
        return self._returncode == 0

    def then(self):
        """
        simulate '&&' in bash.
        """
        if self.__bool__():
            return self
        else:
            return Result.NOP()

    def otherwise(self):
        """
        simulate '||' in bash.
        """
        if self.__bool__():
            return Result.NOP()
        else:
            return self

    def run(self, cmdline, /, *, stdin=None, stdout=PIPE, stderr=PIPE, encoding=None, errors=None):
        return run(cmdline, stdin=stdin, stdout=stdout, stderr=stderr, encoding=encoding, errors=errors)

    def pipe(self, cmdline, /, *, stdout=PIPE, stderr=PIPE, encoding=None, errors=None):
        """
        simulate '|' in bash.
        """
        return run(cmdline, stdin=self._stdout, stdout=stdout, stderr=stderr, encoding=encoding, errors=errors)

    def grep(self, pattern, /, *, ignorecase=False, invert=False, group_sep=' '):
        return grep(pattern, ignorecase=ignorecase, invert=invert, group_sep=group_sep, stdin=self._stdout)

    def before(self, index, count, /, *, ignorecase=False, invert=False):
        return before(index, count, ignorecase=ignorecase, invert=invert, stdin=self._stdout)

    def after(self, index, count, /, *, ignorecase=False, invert=False):
        return after(index, count, ignorecase=ignorecase, invert=invert, stdin=self._stdout)

    def around(self, index, count, /, *, ignorecase=False, invert=False):
        return around(index, count, ignorecase=ignorecase, invert=invert, stdin=self._stdout)

    def select(self, *nums):
        return select(*nums, stdin=self._stdout)

    def cut(self, *, delim=r'\s+', maxsplit=0, fields=(slice(0, None), ), join=' ', format=None):
        return cut(delim=delim, maxsplit=maxsplit, fields=fields, join=join, format=format, stdin=self._stdout)

    def sed(self, pattern, repl, /, *, count=0, ignorecase=False):
        return sed(pattern, repl, count=count, ignorecase=ignorecase, stdin=self._stdout)

    def foreach(self, type, proc, /):
        foreach(type, proc, stdin=self._stdout)
        return self

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

    def compact(self, *, strip=True, remove_empty_line=True, join=' '):
        return compact(strip=strip, remove_empty_line=remove_empty_line, join=join, stdin=self._stdout)

    def wc(self, type, /):
        return wc(type, stdin=self._stdout)

    def uniq(self):
        return uniq(stdin=self._stdout)

    def sort(self, *, ascending=True):
        return sort(ascending=ascending, stdin=self._stdout)

    def asnum(self, /, *, int_base=10, dim_reduction=False):
        return asnum(int_base=int_base, dim_reduction=dim_reduction, stdin=self._stdout)

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

if __name__ == '__main__':
    def assert_eq(test, real, expect):
        assert real == expect, f'{test} failed\nExpect:\n{repr(expect)}\nReal:\n{repr(real)}'
    res = Result('  Name:   Tony\n  Age:    12')
    assert_eq('grep', res.grep(r'Name:').stdout, '  Name:   Tony')
    assert_eq('invert grep', res.grep(r'Name:', invert=True).stdout, '  Age:    12')
    assert_eq('group pattern grep', res.grep(r'(\S+):\s+(\S+)', group_sep=': ').stdout, 'Name: Tony\nAge: 12')
    res = Result('a\n  \n\nb\n')
    assert_eq('invert grep preserve whitespace', res.grep(r'a', invert=True).stdout, '  \n\nb')
    assert_eq('grep nothing', res.grep(r'Name').__bool__(), False)
    assert_eq('invert grep nothing', res.grep(r'Name', invert=True).stdout, 'a\n  \n\nb')

    res = Result("0\n1\n2\n3\n4\n5")
    assert_eq('select', res.select(1, -1, range(2,4), slice(-3, -1)).stdout, '1\n5\n2\n3\n3\n4')

    res = Result("t0\nt1\nt2\nt3\nt4\nt5\nt6")
    assert_eq('before line', res.before(2, 2).stdout, 't0\nt1\nt2')
    assert_eq('before pattern', res.before('t2', 2).stdout, 't0\nt1\nt2')
    assert_eq('after line', res.after(2, 2).stdout, 't2\nt3\nt4')
    assert_eq('after pattern', res.after('t2', 2).stdout, 't2\nt3\nt4')
    assert_eq('around line', res.around(2, 1).stdout, 't1\nt2\nt3')
    assert_eq('around pattern', res.around('t2', 1).stdout, 't1\nt2\nt3')

    res = Result("1, 2, 3, 4, 5, 6\nt1,    t2,t3, t4, t5, t6, t7, t8")
    assert_eq('cut', res.cut(delim=r',\s*', fields=(1, range(2, 4), slice(-2, None))).stdout,
              '2 3 4 5 6\nt2 t3 t4 t7 t8')
    assert_eq('cut', res.cut(delim=r',\s*', fields=(1, range(2, 4), slice(-2, None)), format='{0}x{4}').stdout,
              '2x6\nt2xt8')

    res = Result("Name:   Tony\nAge: \t 12")
    assert_eq('sed', res.sed(r'\s+', ' ').stdout, 'Name: Tony\nAge: 12')
    assert_eq('sed sub group repl', res.sed(r'(\S+)\s+(\S+)', r'\g<1> "\g<2>"').stdout, 'Name: "Tony"\nAge: "12"')

    res = Result('1 \n 2\n 3')
    tmp = []
    res.foreach('char', lambda txt: tmp.append(txt))
    assert_eq('foreach char', tmp, ['1', ' ', '\n', ' ', '2', '\n', ' ', '3'])
    tmp.clear()
    res.foreach('word', lambda txt: tmp.append(txt))
    assert_eq('foreach word', tmp, ['1', '2', '3'])
    tmp.clear()
    res.foreach('line', lambda txt: tmp.append(txt))
    assert_eq('foreach line', tmp, ['1 ', ' 2', ' 3'])
    tmp.clear()
    def break_foreach(txt):
        if txt == '2':
            return True
        else:
            tmp.append(txt)
    res.foreach('word', break_foreach)
    assert_eq('break foreach', tmp, ['1'])
    assert_eq('iterate non exist file', foreach('word', lambda txt: tmp.append(txt), pathname='non-exist-file'), None)

    res = Result('1 \n\n 2\n 3')
    assert_eq('compact with strip', res.compact().stdout, '1 2 3')
    assert_eq('compact without strip', res.compact(strip=False, join=',').stdout, '1 , 2, 3')
    assert_eq('compact without remove empty line', res.compact(remove_empty_line=False, join=',').stdout, '1,,2,3')

    res = Result('1 \n 2\n 3')
    assert_eq('wc char', res.wc('char').stdout, '8')
    assert_eq('wc word', res.wc('word').stdout, '3')
    assert_eq('wc line', res.wc('line').stdout, '3')

    res = Result('1\n1\n2\n 2')
    assert_eq('uniq', res.uniq().stdout, '1\n2\n 2')

    res = Result('1\n3\n2')
    assert_eq('sort ascending', res.sort().stdout, '1\n2\n3')
    assert_eq('sort descending', res.sort(ascending=False).stdout, '3\n2\n1')

    res = Result('hello1,-2,- 3x\n   \nhello x3e1 3.1 3.1e1\n0x12 -0o666 +0b11')
    assert_eq('asnum', res.asnum(), [[1,-2,3], [3e1, 3.1, 3.1e1], [0x12, -0o666, 0b11]])
    assert_eq('asnum reduce dim', res.asnum(dim_reduction=True), [1,-2,3, 3e1, 3.1, 3.1e1, 0x12, -0o666, 0b11])
    res = Result('Age:\n  12')
    assert_eq('asnum one num', res.asnum(dim_reduction=True), 12)


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
    assert_eq('success result is non nop', res.nop, False)
    assert_eq('then of success result is non nop', res.then().nop, False)
    assert_eq('otherwise of success result is nop', res.otherwise().nop, True)
    assert_eq('bool of nop is always false', res.otherwise().__bool__(), False)
    assert_eq('nop chain call', res.otherwise().dosth(1).then(2).dosthelse(3).nop, True)

    res = Result('', returncode=1)
    assert_eq('bool of fail result is false', res.__bool__(), False)
    assert_eq('fail result is non nop', res.nop, False)
    assert_eq('then of fail result is nop', res.then().nop, True)
    assert_eq('otherwise of fail result is non nop', res.otherwise().nop, False)

