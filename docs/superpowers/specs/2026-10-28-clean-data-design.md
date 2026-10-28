# HRC clean 数据设计

## 意图

在不削弱原始证据和质量审计信息的前提下，为直接分析提供结构稳定的 clean 数据。clean 版严格只保留 `river`、`station`、`observed_at`、`water_level_value`、`flow_value` 五个字段。

## 已选方案

采用每日、最新、月度三层 clean 输出。仅生成 latest 的方案不能支持历史复算；只生成每日和 latest 的方案会迫使使用者自行合并月数据，因此不采用。

## 输出

- 每次采集：`data/daily/YYYY-MM-DD/<capture>/water_clean.json` 与 `water_clean.csv`。
- 每日归档：`snapshots/YYYY/MM/YYYY-MM-DD_clean.json` 与 `YYYY-MM-DD_clean.csv`。
- 最新成功数据：`data/latest/water_clean.json`、`data/latest/water_clean.csv`、`latest/clean.json`、`latest/clean.csv`。
- 月度归档：`data/YYYY-MM/HRC_clean.csv`，按站点和观测时间去重。

## 数据规则

- CSV 表头和 JSON 对象键严格按五字段顺序输出，不加入单位、采集时间、质量标记或来源字段。
- 空流量在 JSON 中为 `null`、CSV 中为空单元格。
- 同站同观测时间的冲突值不猜测、不平均，对应 clean 数值为 `null`；完整版本继续保存冲突变体和来源。
- clean 文件是完整验证数据的精简投影，不替代 `water.json`、站点月文件、原始 HTML 证据和质量报告。
- 只使用 Python 标准库；GitHub Actions 自动提交并上传 clean 文件。

## 验收

测试必须验证字段精确一致、空值行为、冲突行为、每日/latest/月度路径以及工作流上传范围。完成后手动触发一次公有仓库工作流，并从远端读回 clean 文件核验。
