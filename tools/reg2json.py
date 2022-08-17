import sys, re, json
from xml.etree import ElementTree

def insert_n(s, nb):
    sout = ""
    def sub(g):
        if g.group(2):
            a, b = int(g.group(1)), int(g.group(2)[1:])
            return nb[-a - 1:-b or None]
        else:
            a = int(g.group(1))
            return nb[-a - 1]

    s = re.sub(r'n\[(\d+)(:\d+)?\]', sub, s)
    s = "".join(s.split(":"))
    return int(s.replace("0b", ""), 2)

def parse_one(regs, xml):
    t = ElementTree.parse(xml)

    for reg in t.findall('registers/register'):
        data = {}

        name = reg.find('reg_short_name').text
        fullname = reg.find('reg_long_name').text

        if name.startswith("S3_") or name.startswith("SYS S1_"):
            continue

        array = reg.find('reg_array')

        start = end = 0

        if array:
            start = int(array.find("reg_array_start").text)
            end = int(array.find("reg_array_end").text)

        encs = {}
        accessors = {}

        for am in reg.findall('access_mechanisms/access_mechanism'):
            accessor = am.attrib["accessor"]
            if accessor.startswith("MSRimmediate"):
                continue
            ins = am.find("encoding/access_instruction").text.split(" ")[0]
            regname = accessor.split(" ", 1)[1]
            enc = {}
            for e in am.findall("encoding/enc"):
                enc[e.attrib["n"]] = e.attrib["v"]

            enc = enc["op0"], enc["op1"], enc["CRn"], enc["CRm"], enc["op2"]
            if regname in encs:
                assert encs[regname] == enc
            encs[regname] = enc
            accessors.setdefault(regname, set()).add(ins)

        if not encs:
            continue

        fieldsets = []

        width = None

        for fields_elem in reg.findall('reg_fieldsets/fields'):

            fieldset = {}

            if (instance_elem := fields_elem.find('fields_instance')) is not None:
                fieldset["instance"] = instance_elem.text

            fields = []

            set_width = int(fields_elem.attrib["length"])

            if width is None:
                width = set_width
            else:
                assert width == set_width

            single_field = False

            for f in fields_elem.findall('field'):

                if f.attrib.get("rwtype", None) in ("RES0", "RES1", "RAZ", "RAZ/WI", "RAO/WI", "UNKNOWN"):
                    continue
                msb, lsb = int(f.find('field_msb').text), int(f.find('field_lsb').text)

                assert not single_field

                if msb == width - 1 and lsb == 0:
                    continue

                if (name_elem := f.find('field_name')) is not None:
                    name = name_elem.text
                else:
                    assert not fields
                    continue

                field = {
                    "name": name,
                    "msb": msb,
                    "lsb": lsb,
                }
                fields.append(field)

            fields.sort(key=lambda x: x["lsb"], reverse=True)

            fieldset["fields"] = fields
            fieldsets.append(fieldset)

        for idx, n in enumerate(range(start, end + 1)):
            nb = "{0:064b}".format(n)[::-1]
            for name, enc in sorted(encs.items()):
                enc = tuple(insert_n(i, nb) for i in enc)
                data = {
                    "index": idx,
                    "name": name.replace("<n>", "%d" % n),
                    "fullname": fullname,
                    "enc": enc,
                    "accessors": sorted(list(accessors[name])),
                    "fieldsets": fieldsets,
                }

                if width is not None:
                    data["width"] = width

                yield data

if __name__ == "__main__":
    regs = []
    for i in sys.argv[1:]:
        regs.extend(parse_one(regs, i))

    json.dump(regs, sys.stdout)



