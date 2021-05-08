import json, sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--imp-apl-prefix", action="store_true")
parser.add_argument("regfile")
args = parser.parse_args()

if args.imp_apl_prefix:
    prefix = "IMP_APL_"
else:
    prefix = ""

data = json.load(open(args.regfile))
for reg in data:
    name = reg['name']

    print(f"#define SYS_{prefix}{name} sys_reg({', '.join(str(i) for i in reg['enc'])})")

    if name[-4:-1] == "_EL":
        name = name[:-4]

    for fieldset in reg.get("fieldsets", []):
        if "instance" in fieldset:
            print(f"// {fieldset['instance']}")
        for f in fieldset["fields"]:
            fname = f["name"]
            msb, lsb = f["msb"], f["lsb"]

            if msb == lsb:
                print(f"#define {name}_{fname} BIT({lsb})")
            else:
                print(f"#define {name}_{fname} GENMASK({msb}, {lsb})")

    print()
