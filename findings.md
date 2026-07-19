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
- 原 SMP 初次启动依赖全局 `target_cpu`：某核心超时后若继续启动下一核心，迟到核心会使用被覆盖的索引并写错 spin table。安全策略是在首次失败后中止批量启动并保留超时核心的目标状态。
- `origin/psci-via-efi` 的 `d30913b` 已提供按 MPIDR 查找复位栈的实现依据；该机制可独立于 PSCI 移植，用于核心首次握手后的 RVBAR 重入。
- M5 `function-enable_core` 不能用单一布尔值表示：需要分别记录 CPU 节点 mask 和校验通过的 Core function mask；J716c 的 18 个 CPU 预期两者均为 `0x0003ffff`。
