# M5 Max 修复发现

- 实机 `J716c / Mac17,6 / Apple M5 Max` 的 `/chosen/chip-id` 为 `0x6050`。
- 实机共有 18 核：两个 6 核 M cluster 和一个 6 核 P/Super cluster；启动核为 M 核。
- 当前源码把 MIDR part `0x64/0x65` 命名为 `T6050 M5 Pro`，把 `0x68/0x69` 命名为 `T6051 M5 Max`，与实机 SoC ID 不一致。
- 当前 C 侧 SMP 给 T6050/T6051 选择 `CPU_START_OFF_T6031 = 0x88000`，但引入提交明确记录次级核只上电、不进入 m1n1。
- M5 复用 `features_m4`，其中 `apple_sysregs_unlocked=false`，所以 m1n1 不改写锁定 RVBAR；入口必须由已有固件 RVBAR、启动 trampoline 或新的硬件协议保证。
- `function-enable_core` 的结构是 `{ phandle, FourCC, args[] }`。M5 CPU 节点的 phandle 为 `0x1e0`（PMGR），FourCC 为 `Core`，参数是从 bit 0 到 bit 17 的单核掩码。
- 当前 macOS 实机加载了 `AppleT6050PMGR.kext`；公开源码和本地 m1n1 中都没有 `Core` 平台函数的执行语义。
- 系统 kernel collection 是 IMG4 容器，`kmutil inspect` 能给出嵌入 kext 的虚拟地址和文件偏移，但磁盘内容不能直接作为普通 Mach-O 反汇编。
- `_vectors_start` 在当前链接布局为 `0x4000`，而 RVBAR 比较只保留 `[47:12]`；比较必须同时页对齐，否则合法入口会被误报为不匹配。
- M5 的 `ApplePMGR::configMiscCores` 会从内部运行时结构和 ADT 映射构造多组 `writeReg32` 调用；`AppleT6050PMGR::writeReg32` 还经过虚函数/基类回调。现有证据不足以安全地把它简化为两个裸 `CPU_START` 写入。
