# RAGFlow 二次开发基线

## 项目定位

本仓库用于开发“车险理赔辅助审核平台”，在 RAGFlow Python 后端基础上增加车险案件、保单、理赔材料、确定性审核规则、条款检索和带引用审核报告能力。

该项目是个人学习和求职作品，不用于真实理赔，也不输出自动赔付结论。

## 上游信息

| 项目 | 内容 |
| --- | --- |
| 上游项目 | RAGFlow |
| 上游仓库 | https://github.com/infiniflow/ragflow |
| 许可协议 | Apache License 2.0 |
| 基线版本 | `v0.27.2` |
| 基线提交 | `a024bea0cd93f39e6652a42bf84dd20c55bc560b` |
| 本地开发分支 | `custom/claim-review-mvp` |
| 二次开发建立日期 | 2026-11-03 |

方案文档中的参考提交为 `db471cee7`，但当前仓库实际检出的 `v0.27.2` 标签指向 `a024bea`。本项目以实际检出提交为唯一基线。

## 当前二次开发范围

P1 已增加理赔领域的数据基础：

- `ClaimCase`、`ClaimPolicy`、`ClaimMaterial`、`ClaimReview`、`ClaimSetting` 五张业务表；
- 可校验的车险材料规则 `conf/claim_rules.yaml`；
- 20 个虚构案件、20 份虚构保单及关联材料的幂等种子服务和命令；
- 针对规则、演示数据和模型约束的单元测试。

案件 API、Agent 工具、RAG 检索和审核报告尚未实现。RAGFlow 原生的用户、租户、知识库、文档解析、检索和 Agent 能力均属于上游实现。

后续新增内容将集中记录在本文件中，并遵循以下边界：

- 业务模型和服务放在独立命名空间；
- 只在模型注册和迁移等必要位置修改上游核心文件；
- 业务规则由确定性代码计算，LLM 只负责归纳已有事实和检索证据；
- 所有理赔接口使用 RAGFlow 现有登录和租户隔离机制；
- 每条条款结论必须保留文档、chunk 和原文引用；
- 证据不足或工具失败时不得返回“审核通过”。

## 二次开发改动记录

| 提交 | 改动 |
| --- | --- |
| 基线建立提交 | 新增本文件，并在 README 增加二次开发入口；未修改业务代码。 |
| P1 理赔数据基础 | 新增理赔五表、材料规则、虚构演示数据和单元测试。 |

## 二次开发文件

本人新增：

- `api/claim/`：理赔领域包、规则加载器和演示数据服务；
- `conf/claim_rules.yaml`：虚构车险材料规则；
- `scripts/seed_claim_demo.py`：租户级演示数据命令；
- `test/unit_test/claims/`：理赔基础单元测试。

本人修改：

- `api/db/db_models.py`：注册理赔领域模型和 GaussDB 复制表配置；
- `api/ragflow_server.py`：启动时校验理赔规则；
- `UPSTREAM.md`：维护基线、改动和验证记录。

其余目录、文件和 RAGFlow 原生能力均来自上游基线。

## 基线验证状态

当前已确认仓库检出提交、Python 包版本和 Git 远端信息。Python 后端、数据库、检索服务和模型连通性仍需在实际运行环境中验证。

## 演示数据命令

```powershell
python scripts/seed_claim_demo.py --tenant-id <当前租户ID>
python scripts/seed_claim_demo.py --tenant-id <当前租户ID> --reset-demo
```

种子脚本只操作指定租户的 `claim-demo-v1` 虚构数据，并在覆盖同名非演示案件或保单前终止。
