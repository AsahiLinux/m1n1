#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import sys, pathlib
import serial
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

import argparse, pathlib
import logging
import re

from m1n1 import adt
from m1n1.utils import align_up

parser = argparse.ArgumentParser(description='Convert Audio nodes to Device Tree format')
parser.add_argument('--main-speaker', type=str, help="DT label for main speaker missing in ADT")
parser.add_argument('input', type=pathlib.Path)
args = parser.parse_args()

logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)

adt_data = args.input.read_bytes()
dt = adt.load_adt(adt_data)

adt2dt_compatible = {
    "audio-control,sn012776": '"ti,sn012776", "ti,tas2764"',
    "audio-control,cs42l84": '"cirrus,cs42l84"',
}

adt2dt_gpio_name = {
    "gpio0": "pinctrl_ap",
    "aop-gpio": "pinctrl_aop",
    "aop-gpio0": "pinctrl_aop",
    "nub-gpio": "pinctrl_nub",
    "nub-gpio0": "pinctrl_nub",
    "smc-gpio": "pinctrl_smc",
    "smc-gpio0": "pinctrl_smc",
}

dt_compat_sound = {
    "J314": '"apple,j314-macaudio", "apple,macaudio"',
    "J316": '"apple,j316-macaudio", "apple,macaudio"',
    "J414": '"apple,j414-macaudio", "apple,j314-macaudio", "apple,macaudio"',
    "J416": '"apple,j416-macaudio", "apple,j316-macaudio", "apple,macaudio"',
    "J504": '"apple,j504-macaudio", "apple,j314-macaudio", "apple,macaudio"',
    "J514": '"apple,j514-macaudio", "apple,j314-macaudio", "apple,macaudio"',
    "J516": '"apple,j516-macaudio", "apple,j316-macaudio", "apple,macaudio"',
}

gpios = {}
devices = {}

main_speaker = None
speakers = {}

pattern = re.compile('er_?([12])?$')

def speaker_dt(main, speaker, reset):
    reg = dev.reg[0] & 0xff
    dt_name = dev.name.removeprefix("audio-").replace('-', '_')
    sound_name = dt_name.removeprefix("speaker_").replace('_', ' ').title()
    dt_name = pattern.sub(r'\1', dt_name)
    irq_parent = gpios[main.interrupt_parent]

    num = speakers[getattr(dev, "AAPL,phandle")]

    imon_slot = main.speaker_config[num].isense_slot
    vmon_slot = main.speaker_config[num].vsense_slot

    print(f'''
	{dt_name}: codec@{reg:x} {{
		compatible = {adt2dt_compatible[dev.compatible[0]]};
		reg = <{reg:#x}>;
		{reset_gpio_or_regulator};
		#sound-dai-cells = <0>;
		sound-name-prefix = "{sound_name}";
		interrupts-extended = <&{irq_parent} {main.interrupts[0]} IRQ_TYPE_LEVEL_LOW>;
		ti,imon-slot-no = <{imon_slot}>;
		ti,vmon-slot-no = <{vmon_slot}>;
	}};''')

    return (main.speaker_config[num].rx_slot, dt_name)


def jack_dt(dev):
    reg = dev.reg[0] & 0xff
    # print(dev.function_reset)
    reset = gpios[dev.function_reset.phandle]
    irq_parent = gpios[dev.interrupt_parent]

    print(f'''
	jack_codec: codec@{reg:x} {{
		compatible = {adt2dt_compatible[dev.compatible[0]]};
		reg = <{reg:#x}>;
		reset-gpios = <&{reset} {dev.function_reset.args[0]} GPIO_ACTIVE_HIGH>;
		#sound-dai-cells = <0>;
		interrupts-extended = <&{irq_parent} {dev.interrupts[0]} IRQ_TYPE_LEVEL_LOW>;
		sound-name-prefix = "Jack";
	}};''')


# loop through all /arm-io children to enumerate gpio and i2c nodes
for dev in dt["/arm-io"]._children:
    if not hasattr(dev, "compatible"):
        continue
    if 'gpio,t8101' in dev.compatible or 'gpio,t6000' in dev.compatible:
        gpios[getattr(dev, "AAPL,phandle")] = adt2dt_gpio_name[dev.name]
        continue

    if 'i2c,s5l8940x' not in dev.compatible:
        continue

    i2c = dev
    devices[i2c.name] = []

    for node in i2c._children:

        if not node.name.startswith("audio"):
            continue

        if 'audio-control,sn012776' in node.compatible:
            devices[i2c.name].append(node)
            if hasattr(node, "speaker_config"):
                main_speaker = node
                speakers[getattr(node, "AAPL,phandle")] = 0
                for i in range(1, 6):
                    speakers[getattr(node, f"speaker{i}")] = i

        if 'audio-control,cs42l84' in node.compatible:
            devices[i2c.name].append(node)

        logger.debug(f"Found I2C device {node._path}")


if main_speaker is None:
    logger.error("main Speaker node not found")
    exit(1)

main_speaker.name = args.main_speaker

logger.info(f"Found speaker config in {main_speaker._path}, {speakers}")
speaker_labels = [''] * len(speakers)

logger.debug(main_speaker)

if len(speakers) == 1:
    pinctrl = gpios[main_speaker.function_reset.phandle]
    reset_gpio_or_regulator = (f'treset-gpios = <&{pinctrl} {main_speaker.function_reset.args[0]} GPIO_ACTIVE_HIGH>')
else:
    pinctrl = gpios[main_speaker.function_reset.phandle]
    pin = main_speaker.function_reset.args[0]
    pin_args = 'GPIO_ACTIVE_HIGH'
    print(f'''
/ {{
	speaker_sdz: fixed-regulator-sn012776-sdz {{
		compatible = "regulator-fixed";
		regulator-name = "sn012776-sdz";
		startup-delay-us = <5000>;
		gpios = <&{pinctrl} {pin} {pin_args}>;
		enable-active-high;
	}};
}};
''')
    reset_gpio_or_regulator = "SDZ-supply = <&speaker_sdz>"


for i2c, devs in devices.items():
    if len(devs) == 0:
        continue

    print(
f'''&{i2c} {{
	status = "okay";''')

    for dev in devs:
        if "audio-control,sn012776" in dev.compatible:
            (slot, label) = speaker_dt(main_speaker, dev, reset_gpio_or_regulator)
            if 'left' in label:
                speaker_labels[slot // 2] = label
            if 'right' in label:
                speaker_labels[(len(speakers) + slot) // 2] = label

        elif "audio-control,cs42l84" in dev.compatible:
            jack_dt(dev)

    print(f'}};\n')

model = " ".join([dt["product"].product_name.partition(' (')[0], dt.target_type])
compat = dt_compat_sound[dt.target_type[0:4]]
idle_mask_l = main_speaker.amp_tx_zd_config[0] & ((1 << (4 * len(speakers))) - 1)
idle_mask_r = main_speaker.amp_tx_zd_config[2] & ((1 << (4 * len(speakers))) - 1)

# TODO:
left_idx = 0
right_idx = len(speakers) // 2

speaker_sound_dai = ',\n\t\t\t\t\t    '.join([f'<&{x}>' for x in speaker_labels])

print(f'''
/ {{
	sound: sound {{
		compatible = {compat};
		model = "{model}";

		dai-link@0 {{
			link-name = "Speakers";
			dai-tdm-idle-mode-{left_idx} = "zero";
			dai-tdm-idle-mode-{right_idx} = "zero";
			dai-tdm-slot-tx-idle-mask-{left_idx} = <{idle_mask_l:#08x}>;
			dai-tdm-slot-tx-idle-mask-{right_idx} = <{idle_mask_r:#08x}>;

			cpu {{
				sound-dai = error; // TODO: likely: `<&mca 0>, <&mca 1>`
			}};
			codec {{
				sound-dai = {speaker_sound_dai};
			}};
		}};

		dai-link@1 {{
			link-name = "Headphone Jack";

			cpu {{
				sound-dai = error; // TODO: likely `<&mca 2>`
			}};
			codec {{
				sound-dai = <&jack_codec>;
			}};
		}};
	}};
}};''')


