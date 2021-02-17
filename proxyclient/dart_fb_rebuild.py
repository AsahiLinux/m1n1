from setup import *

# NOTE: this is going to leak memory if you run it more than once
p.dart_init(0x231304000)
p.dart_map(0x231304000, 0, 0x0423c000, 0x9e0df8000, 0x1500000)
p.dart_map(0x231304000, 0, 0x0573c000, 0x9e0df4000, 0x4000)
p.dart_map(0x231304000, 4, 0x05740000, 0x9e0d34000, 0xbc000)
p.dart_enable_device(0x231304000, 0)
p.dart_enable_device(0x231304000, 4)
