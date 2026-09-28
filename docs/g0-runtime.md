# G0 持久化与任务执行验证

本轮实现是可执行的基础设施试验，不是售后产品完成声明。入口位于 `baseline/backend/g0/`，不会被产品入口 `app.main` 导入。模型、维修指导、保修审批及企业接口均未启用。

## 数据与执行边界

1. API 验证模板管理员身份，拒绝匿名调用。请求参数通过严格结构校验，未知字段和非布尔确认值被拒绝。
2. 同一数据库事务写入运行、命令、输入事件及队列任务；失败整体回滚。相同命令 ID 重放返回原任务，更改内容返回 409。
3. 独立 Worker 从 PostgreSQL 队列领取任务，工作流在等待确认时保存检查点并结束任务。等待不是运行中的长任务。
4. 新输入先存为业务事件，再将事件引用交给新 Worker 恢复。流程核对该事件所属运行，不信任任意恢复载荷。
5. 结果通过唯一约束去重写入业务事件；重复投递不能增加第二条结果。检查点本身不能作为业务成功的证据。

## 库与迁移

固定依赖为 LangGraph 1.2.12、PostgreSQL 检查点包 3.1.2、Procrastinate 3.10.0，完整间接依赖及校验值在 `baseline/uv.lock`。仅通过官方库接口接入，不复制未标明来源的实现。

三个 schema 分别承载业务试验记录、流程检查点和队列。业务与队列迁移保存版本和 SQL 哈希；重复执行不清库，遇到未声明的版本变化拒绝继续。检查点采用库自带迁移。在首次使用前必须运行迁移，不在用户请求中动态建表。

连接仅允许显式启用的 `db:5432/yibu_g0_test` 和专用用户，拒绝连接参数覆盖及外部追踪。Compose 不暴露宿主机端口，不挂载 Docker socket，不接入现有业务库。

## 复现

进入 `baseline/`，先执行初始化，再依序运行下列阶段：

```powershell
pwsh -NoProfile -File scripts/initialize-g0.ps1
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Build -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Database -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Tests -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Write -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase RestartDatabase -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Database -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Read -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Workflow -ProjectName yibu-g0-public
pwsh -NoProfile -File scripts/run-g0.ps1 -Phase Lint -ProjectName yibu-g0-public
```

所有阶段必须使用相同项目名；不同项目名使用不同数据卷和证据目录。结果保存在 `baseline/evidence/<项目名>/`，凭据和原始日志默认不提交。仓库 G0 工作流使用临时 Linux 执行环境、随机口令和独立测试库执行相同入口。

## 未覆盖范围

- 当前串行化锁只用于 G0 兼容试验，尚未证明旧执行代次隔离。
- 尚未完成业务提交与检查点写入间的进程崩溃试验，也没有自动失联重试调度器。
- 尚未实现跨重试的模型预算与截止时间，因此不能启用真实模型任务。
- 当前确认只是固定测试输入，不代表用户满意、设备修复、人工接单或产品 E01-E28 验收。

## 一手技术依据

- [流程持久化](https://docs.langchain.com/oss/python/langgraph/persistence)：数据库保存流程位置。
- [中断与恢复](https://docs.langchain.com/oss/python/langgraph/interrupts)：恢复可能重新执行节点，因此副作用需幂等。
- [外部事务连接](https://procrastinate.readthedocs.io/en/stable/howto/production/external_connection.html)：业务写入和队列投递共享事务。
- [队列迁移](https://procrastinate.readthedocs.io/en/stable/howto/production/migrations.html)：升级不能仅替换包，必须管理数据库迁移。
