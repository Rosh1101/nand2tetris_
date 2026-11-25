#!/usr/bin/env python3
"""
Hack assembler (Nand to Tetris, ETCCNT301 capstone - Part B)

Usage:  python assembler.py Prog.asm --k 41
Output: Prog.hack  (same folder)

Extra feature chosen by K mod 3:
  0 -> write symbols.txt (all labels + variables with addresses)
  1 -> clear error messages with line numbers instead of crashing
  2 -> warning when the same label is defined twice
"""
import sys, os, re, argparse

COMP = {
    '0': '0101010', '1': '0111111', '-1': '0111010', 'D': '0001100',
    'A': '0110000', '!D': '0001101', '!A': '0110001', '-D': '0001111',
    '-A': '0110011', 'D+1': '0011111', 'A+1': '0110111', 'D-1': '0001110',
    'A-1': '0110010', 'D+A': '0000010', 'D-A': '0010011', 'A-D': '0000111',
    'D&A': '0000000', 'D|A': '0010101',
    'M': '1110000', '!M': '1110001', '-M': '1110011', 'M+1': '1110111',
    'M-1': '1110010', 'D+M': '1000010', 'D-M': '1010011', 'M-D': '1000111',
    'D&M': '1000000', 'D|M': '1010101',
}
# commutative aliases (e.g. A+D == D+A)
for alias, real in {'1+D': 'D+1', '1+A': 'A+1', 'A+D': 'D+A', 'A&D': 'D&A',
                    'A|D': 'D|A', 'M+D': 'D+M', 'M&D': 'D&M', 'M|D': 'D|M',
                    '1+M': 'M+1'}.items():
    COMP[alias] = COMP[real]

DEST = {'': '000', 'M': '001', 'D': '010', 'MD': '011', 'DM': '011', 'A': '100',
        'AM': '101', 'MA': '101', 'AD': '110', 'DA': '110', 'AMD': '111',
        'ADM': '111', 'MAD': '111', 'MDA': '111', 'DAM': '111', 'DMA': '111'}
JUMP = {'': '000', 'JGT': '001', 'JEQ': '010', 'JGE': '011', 'JLT': '100',
        'JNE': '101', 'JLE': '110', 'JMP': '111'}

SYMBOL_RE = re.compile(r'^[A-Za-z_.$:][\w.$:]*$')


class AsmError(Exception):
    pass


def predefined():
    t = {'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
         'SCREEN': 16384, 'KBD': 24576}
    for i in range(16):
        t['R%d' % i] = i
    return t


def clean(line):
    return line.split('//')[0].replace(' ', '').replace('\t', '').strip()


def first_pass(lines, feature):
    """Remove comments/blank lines, record label positions."""
    symbols = predefined()
    labels = {}          # user labels only (for symbols.txt)
    program = []         # (line_number, instruction)
    errors, warnings = [], []
    for num, raw in enumerate(lines, 1):
        line = clean(raw)
        if not line:
            continue
        if line.startswith('('):
            if not line.endswith(')') or not SYMBOL_RE.match(line[1:-1]):
                errors.append('Line %d: invalid label "%s"' % (num, raw.strip()))
                continue
            name = line[1:-1]
            if name in labels:
                warnings.append('Line %d: warning: label (%s) already defined '
                                'at ROM address %d' % (num, name, labels[name]))
            labels[name] = len(program)      # keeps latest definition
            symbols[name] = len(program)
        else:
            program.append((num, line))
    return symbols, labels, program, errors, warnings


def encode_c(line):
    dest, jump = '', ''
    body = line
    if '=' in body:
        dest, body = body.split('=', 1)
    if ';' in body:
        body, jump = body.split(';', 1)
    if dest not in DEST:
        raise AsmError('invalid destination "%s"' % dest)
    if body not in COMP:
        raise AsmError('invalid instruction "%s"' % line)
    if jump not in JUMP:
        raise AsmError('invalid jump "%s"' % jump)
    return '111' + COMP[body] + DEST[dest] + JUMP[jump]


def second_pass(program, symbols):
    """Translate to 16 bits; new variables start at RAM 16."""
    out, variables, errors = [], {}, []
    next_var = 16
    for num, line in program:
        try:
            if line.startswith('@'):
                sym = line[1:]
                if sym == '':
                    raise AsmError('invalid instruction "@"')
                if sym.isdigit():
                    val = int(sym)
                    if val > 32767:
                        raise AsmError('address %d too large (max 32767)' % val)
                else:
                    if not SYMBOL_RE.match(sym):
                        raise AsmError('invalid instruction "%s"' % line)
                    if sym not in symbols:
                        symbols[sym] = next_var
                        variables[sym] = next_var
                        next_var += 1
                    val = symbols[sym]
                out.append(format(val, '016b'))
            else:
                out.append(encode_c(line))
        except AsmError as e:
            errors.append('Line %d: %s' % (num, e))
    return out, variables, errors


def assemble(path, k):
    feature = k % 3
    with open(path) as f:
        lines = f.read().splitlines()

    symbols, labels, program, err1, warns = first_pass(lines, feature)
    code, variables, err2 = second_pass(program, symbols)
    errors = err1 + err2

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        if feature != 1:
            print('Assembly failed with %d error(s).' % len(errors), file=sys.stderr)
        else:
            print('Assembly stopped: %d error(s) found.' % len(errors), file=sys.stderr)
        return 1

    if feature == 2:
        for w in warns:
            print(w, file=sys.stderr)

    out_path = os.path.splitext(path)[0] + '.hack'
    with open(out_path, 'w') as f:
        f.write('\n'.join(code) + '\n')
    print('Wrote %s (%d instructions)' % (out_path, len(code)))

    if feature == 0:
        sym_path = os.path.join(os.path.dirname(os.path.abspath(path)), 'symbols.txt')
        with open(sym_path, 'w') as f:
            f.write('# Labels (ROM address)\n')
            for n, a in labels.items():
                f.write('%s\t%d\n' % (n, a))
            f.write('# Variables (RAM address)\n')
            for n, a in variables.items():
                f.write('%s\t%d\n' % (n, a))
        print('Wrote', sym_path)
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Hack assembler')
    ap.add_argument('asm')
    ap.add_argument('--k', type=int, required=True,
                    help='last two digits of your roll number')
    a = ap.parse_args()
    sys.exit(assemble(a.asm, a.k))
