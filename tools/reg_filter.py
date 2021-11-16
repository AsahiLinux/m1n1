import json, sys, re
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

for line in sys.stdin:
    line = re.sub(r"s(\d+)_(\d+)_c(\d+)_c(\d+)_(\d+)", reg_lookup, line)
    sys.stdout.write(line)
