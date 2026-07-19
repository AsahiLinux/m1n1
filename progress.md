# M5 Max 修复进度

## 2026-07-19

- 完成初始项目审阅，确认当前主线只有早期 M5 bring-up 支持。
- 确认实机 M5 Max 的 SoC ID 为 `0x6050`，代码命名存在 `T6050/T6051` 偏差。
- 确认次级核问题不是简单漏加 switch case：C 侧已有 `0x88000` 分支，但提交记录真机未进入次级入口。
- 开始核对锁定 RVBAR、CPU start/status 寄存器以及 stage-1/stage-2 入口关系。
- 解码实机 CPU 节点：`function-enable_core = <pmgr-phandle, 'Core', BIT(cpu-id)>`，现有 SMP 未使用。
- Firecrawl 精确查询没有找到公开实现，且未生成结果文件；已记录，后续不重复该查询。
- 修改 `src/smp.c`：按 RVBAR 页地址比较；锁定 RVBAR 且不指向 m1n1 向量页时立即停止旧代启动写入，并报告 M5 `Core` 平台函数状态。
- 修改 `src/smp.c`：解析 CPU 节点 `function-enable_core`，校验 PMGR phandle、`Core` FourCC 和 `BIT(cpu-id)` 参数；增加 `Secondary CPUs: started/total` 汇总。
- 验证：`make format-check` 通过；`build/smp.o`、`build/m1n1.elf`、`build/m1n1-raw.elf`、`build/m1n1.macho` 和 `build/m1n1.bin` 已重新生成；`_vectors_start=0x4000`。
- 未完成：没有把 Apple 私有 `configMiscCores` 猜测移植到 m1n1；真机仍需确认锁定 RVBAR 的实际值以及 PMGR Core function 是否能由固件/已有 trampoline 触发。
- 最终复验：clang-format、`make format-check`、C/链接产物重建和 `git diff --check` 均通过；构建使用已存在的 `build/librust.a`，完整 Rust crate 重编译仍受本机 cargo `core`/build-std 环境限制。

## 2026-07-20

- 实现 SMP 优先级 1：新增 `smp_asm.h`，让 C 与 `start.S` 共享 CPU/栈常量。
- 选择性移植 MPIDR 复位栈机制：核心首次进入后登记 `mpidr -> stack`，后续 RVBAR 重入由汇编直接选择其私有栈。
- 修复迟到核心竞态：首次启动失败或超时后停止后续核心；超时时保留当前 `target_cpu` 和 reset stack，使迟到入口仍指向正确 spin table。
- 启动汇总现在同时报告总次级核数与实际尝试数。
- 验证通过：`start.o`、`smp.o`、ELF、raw ELF、Mach-O、bin 全部重新生成；`make format-check` 和 `git diff --check` 通过。
- 实现优先级 2：将全局 `m5_core_function_present` 替换为 `m5_cpu_node_mask` 和逐核 `m5_core_function_mask`。
- Core function 校验现在拒绝缺失的 PMGR phandle，并继续严格验证长度、PMGR phandle、`Core` FourCC 和 `BIT(cpu-id)`。
- M5 启动日志会打印完整 CPU/Core function mask；具体 CPU 失败时同时报告该 CPU bit 是 `valid` 还是 `missing`。
- 优先级 2 复验：`smp.o` 和全部最终镜像重新生成，格式检查与 diff 检查通过。
