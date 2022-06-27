import json, sys, re, math
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("regfile")
args = parser.parse_args()

data = json.load(open(args.regfile))

name_map = {}

for reg in data:
    name = reg['name']
    enc = reg['enc']
    name_map[f"s{enc[0]}_{enc[1]}_c{enc[2]}_c{enc[3]}_{enc[4]}"] = name

def reg_lookup(m):
    s = m.group(0)
    return name_map.get(s, s)

def hex_parse(m):
    v = int(m.group(0), 0)
    if v and (v & (v - 1)) == 0:
        bit = int(math.log2(v))
        return f"BIT({bit})"
    v ^= 0xffff_ffff_ffff_ffff
    if v and (v & (v - 1)) == 0:
        bit = int(math.log2(v))
        return f"~BIT({bit})"
    return m.group(0)

for line in sys.stdin:
    line = re.sub(r"s(\d+)_(\d+)_c(\d+)_c(\d+)_(\d+)", reg_lookup, line)
    line = re.sub(r"\b0x[0-9a-f]+\b", hex_parse, line)
    sys.stdout.write(line)
