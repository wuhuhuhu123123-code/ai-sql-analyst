# AI 辅助开发记录

这个项目从需求到测试都有AI编程工具（Claude Code / 这类命令行 Agent）参与。

## 我是怎么用的

| 环节 | AI 做什么 | 我做什么 |
| --- | --- | --- |
| 需求拆解 | 把「自然语言查数」拆成 schema 内省 / 提示词 / 护栏 / 执行 / 缓存 五块，并给出模块边界 | 砍掉不需要的部分（向量检索、多轮对话、前端），把范围压到能在一周内做完 |
| 代码骨架 | 生成 dataclass、FastAPI 路由、urllib 请求封装 | 重新设计 `QueryService.ask()` 的主流程与错误分类 |
| Prompt | 起草 System Prompt 与 3 条 few-shot | 逐条改规则：只输出 SQL、必须带 LIMIT、禁止 `SELECT *`、金额口径写死 |
| 测试 | 生成大部分用例骨架 | 补边界用例（注释绕过、`REPLACE()` 误杀、多语句、只读连接） |
| 文档 | 起草 README 结构与表格 | 用真实输出替换示例，删掉没跑通的说法 |



## 给读代码的人

如果你在评审这个项目：先看 `src/nl2sql/guard.py`（安全边界），
再看 `src/nl2sql/service.py`（主流程），最后看 `tests/test_guard.py` 与
`tests/test_service.py`（怎么证明前两者是对的）。
