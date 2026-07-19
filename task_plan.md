# M5 Max 编号与次级核入口修复计划

## 目标

让实机 `J716c / chip-id 0x6050` 在代码中被一致识别为 M5 Max，并修复或明确补齐 M5 锁定 RVBAR 条件下的次级 CPU 启动入口。

## 阶段

- [completed] 1. 核对 SoC、MIDR、ADT CPU/PMGR 数据与现有启动协议
- [pending] 2. 统一 M5 Max 编号和命名，避免以不存在或未证实的 chip-id 分流
- [in_progress] 3. 实现 M5 次级核入口所需的启动地址与触发路径
- [pending] 4. 增加静态/单元验证并完成全量构建
- [pending] 5. 汇总真机仍需验证的边界和操作步骤

## 约束

- 保留用户现有未跟踪的 `bringup/`、`m5-ioreg.txt`、`m5-sysctl.txt`。
- 不把编译成功等同于真机多核启动成功。
- 硬件寄存器写入必须有 ADT、现有代际代码或提交历史依据。

## 错误记录

| 错误 | 次数 | 处理 |
|---|---:|---|
| Firecrawl 精确检索无结果且未生成输出文件 | 1 | 改用本地 KDK、IORegistry、git 历史和更宽泛源码检索；不重复相同查询 |
| 误用 `CFG='TARGET T6050'` 触发全量构建失败 | 1 | 恢复默认 `build_cfg.h`，改用已有 Rust 产物完成 C/链接验证 |
