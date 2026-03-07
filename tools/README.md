# Register definition tools

This folder contains various scripts that handle ARM and Apple register
symbolic definition used by `proxyclient` (see `proxyclient/m1n1/sysreg.py`).

## Script description

- `gen_reg_class.py` generates Python class from JSON register definition file
- `gen_reg_include.py` generates C include definition (see src/\*\_regs.h)
- `reg2json.py` generates JSON definition files from XML input
- `reg_filter.py` loads JSON register definition file and translates system
  register encoding to symbolic names

## Note on file location

There's two register definition files, `apple_regs.json` and `arm_regs.json`,
that were initially stored alongside these scripts.

Register now resides in the `proxyclient/m1n1` folder, so that `proxyclient`
can load them while avoiding path traversal, using Python's resource loader.
