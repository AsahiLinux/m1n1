import json, sys

data = json.load(open(sys.argv[1]))
for reg in data:
    name = reg['name']

    print(f"#define SYS_{name} sys_reg({', '.join(str(i) for i in reg['enc'])})")

    if name[-4:-1] == "_EL":
        name = name[:-4]

    for fieldset in reg["fieldsets"]:
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
