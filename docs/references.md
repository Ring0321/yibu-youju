# 参考文献与技术依据

资料核查日期：2026-09-27。以下为设计依据，不是本项目已实现能力或达到论文实验结果的证明。

## 与设计的对应关系

| 设计问题 | 参考依据 | 本项目的使用范围 |
| --- | --- | --- |
| 如何检索知识并推进交互 | [1]、[2] | 为候选理解、检索和工具交互提供基础；不以模型输出代替业务授权或实机验证 |
| 如何记录来源与操作影响 | [3] | 借鉴实体、活动、责任主体及派生关系；设备动作影响规则仍需独立审核 |
| 如何判断证据是否排除未解决状态 | [4] | 借鉴模型与观察一致性的诊断思想；有限模型内无反例不等于真实设备正常 |
| 如何中断和恢复人工确认流程 | [5] | 处理节点重放与副作用幂等；业务事实不能只依赖检查点 |
| 如何避免重复建单与并发覆盖 | [6] | 依据隔离语义设计事务和条件更新，再以并发测试验收 |
| 如何限制外部资料中的恶意指令 | [7] | 外部输入按数据处理、最小权限和服务端校验；不宣称完全消除注入风险 |
| 如何评测真实任务完成 | [8] | 对照实际业务终态、规则遵守与重复运行表现；物理效果另行验证 |

项目拟验证的增量是“动作感知证据更新 + 相容反例驱动复测 + 分级结果及人工接续”的组合机制。不能将 RAG、工具调用或普通工作流本身作为原创理论。

## 文献

[1] LEWIS P, PEREZ E, PIKTUS A, et al. [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html)[C]//Advances in Neural Information Processing Systems. 2020, 33.

[2] YAO S, ZHAO J, YU D, et al. [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)[EB/OL]. arXiv:2210.03629, 2022.

[3] MOREAU L, MISSIER P, eds. [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/)[EB/OL]. W3C Recommendation, 2013-04-30.

[4] REITER R. [A Theory of Diagnosis from First Principles](https://www.sciencedirect.com/science/article/pii/0004370287900622)[J]. Artificial Intelligence, 1987, 32(1): 57-95. DOI: 10.1016/0004-3702(87)90062-2.

[5] LANGCHAIN. [LangGraph Documentation: Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)[EB/OL].

[6] POSTGRESQL GLOBAL DEVELOPMENT GROUP. [PostgreSQL Documentation: Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)[EB/OL].

[7] OWASP. [LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)[EB/OL]. OWASP Gen AI Security Project.

[8] YAO S, SHINN N, RAZAVI P, et al. [τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://openreview.net/pdf?id=roNSXZpUDN)[C]//International Conference on Learning Representations. 2025.

在线资料访问日期均为 2026-09-27。外部文献和网站按其自身授权访问，本仓库不分发论文全文。
