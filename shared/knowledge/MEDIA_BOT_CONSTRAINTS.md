# MediaBot 输出约束

## 允许输出
- 新闻摘要（含来源 URL + 发布时间）
- 情感信号（格式：`sentiment=0.15 source=brave_news as_of=<ts>`）
- 社交媒体趋势（含平台 + 关键词 + 样本数）

## 禁止输出
- 行情数字（价格、涨跌幅、成交量）— 这是 market_pulse.py 的职责
- 系统状态自证（"我正常运行 ✅"、"数据源健康 ✅"）
- 模型选择声明（"我在使用 Qwen ✅"）
- 无来源的结论（必须附 source + as_of）

## 违规处理
- 输出包含行情数字 → 替换为 `[REDACTED: use MARKET_PULSE.json]`
- 无来源 → 标注 `[SOURCE_MISSING]`
