import json, sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("regfile")
args = parser.parse_args()

data = json.load(open(args.regfile))
for reg in data:
    name = reg['name']

    if name[-4:-1] == "_EL":
        name = name[:-4]

    if not reg.get("fieldsets", []):
        continue

    print(f"# {reg['name']}")
    print(f"class {name}(Register64):")

    for fieldset in reg.get("fieldsets", []):
        if "instance" in fieldset:
            print(f"# {fieldset['instance']}")
        for f in fieldset["fields"]:
            fname = f["name"]
            msb, lsb = f["msb"], f["lsb"]

            if msb == lsb:
                print(f"    {fname} = {lsb}")
            else:
                print(f"    {fname} = {msb}, {lsb}")

    print()
