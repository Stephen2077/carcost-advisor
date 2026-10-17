# 买车总成本顾问 · CarCost Advisor
Money Talks 2 NYC · Track 1 Money Intelligence · **只用虚构样本数据 / sample data only**

确定性工具算数 → LLM(Nicrron `nicrron/auto`)只负责中英双语解释,**不算任何数字**。
```
用户输入 → validate_inputs → kb_search → calculate_loan → (calculate_lease) → estimate_insurance(区间,虚构表)
        → total_cost → llm_explain(Nicrron) → number_guard(LLM 文本里出现工具结果之外的数字 = 拦截并换成确定性文本) → sanity_check
```
每次 run = 1 条 PRISM trace(`POST /api/traces`)+ 8–9 个 span(`POST /api/spans/ingest`,Steps tab 可见)+ SDK trajectory(`prismtrace.PRISMtrace.submit_trajectory`)。

## 运行(无需任何 key,mock LLM 兜底)
```bash
cd /workspace/carcost-advisor
./run.sh            # 创建 .venv、装依赖、监听 0.0.0.0:8090
# 打开 http://localhost:8090      (http://localhost:8090/#demo 自动跑一次)
```
状态:`GET /api/health`(显示 LLM live/mock、PRISM sending/local-only)。无 key 时 trace 只写 `runs/traces.jsonl`。

## 配 key(Stephen 拿到后)
```bash
cp .env.example .env   # 填 NICRRON_API_KEY、PRISM_API_KEY(pt-sk-…,ingest 范围够用;KB 读写若 403 换 read/operate key)、PRISM_PROJECT_ID(UUID)
pkill -f "uvicorn app.main"; ./run.sh &     # 重启即生效,无需改代码
. .venv/bin/activate && python prism_setup.py --handshake   # 验证 key + 测试 trace + setup-doctor
```
Nicrron 调用:`POST https://api.nicrron.ai/v1/chat/completions`,`Authorization: Bearer $NICRRON_API_KEY`,model `nicrron/auto`,temperature 0。失败会自动回落到 mock 并在 UI/trace 里标 `mock_fallback`(需要充值 credits 才能调通)。
PRISM trace 里的 `model` 字段 = 实际返回的模型名(Devpost 要求写清楚用了 Nicrron)。

## 灌 10 条 trace(3 个证明的共同前提)
```bash
. .venv/bin/activate
python prism_setup.py --upload-kb          # 一次:把 kb/carcost_faq.md 传到 PRISM Knowledge Base(项目级)
python run_scenarios.py                    # 10 runs = 5 个输入 × v1 + v2;trace_id 形如 carcost-s1-alaska-v1-<batch>
```
- **v1 `carcost-advisor-v1`(故意有缺陷的基线)**:不校验输入、不调 kb_search、遇到不支持的州/年龄悄悄把保险算成 $0、把 APR 0.065 当 0.065%。5 个里 **4 个失败**:s1 Alaska、s2 19 岁、s3 Hawaii(**同一根因:不支持的假设被静默忽略→保险 $0**,形成 ≥3 条同簇)、s4 APR 小数误读。s5 正常通过。
- **v2 `carcost-advisor-v2`(修复版)**:校验+警告、kb_search、州不在表里用通用示例基数并**明示**、APR 小数明示换算、number_guard。5/5 通过。
- 重跑用新 batch:`python run_scenarios.py --batch b2`(同 batch 重发是幂等的)。想只补 v1 失败样本:`--only v1`。
- 注意 PRISM 自动评分每天 100 条上限(Free),别灌太多。

## ⚠️ 首次发送后必须确认(我无法在无 key 情况下验证 PRISM 的真实行为)
1. PRISM → Traces:能看到 10 条,agent_id 为 `carcost-advisor-v1/v2`;点开一条 v2,**Steps / Agent Runs** 里有 `validate_inputs, kb_search, calculate_loan, …, sanity_check`。
2. 如果同一个 trace 出现重复/Steps 空:试 `PRISM_MODE=spans`(只发 spans+trajectory,PRISM 由 spans 建 trace)或 `PRISM_MODE=http`(只发 /api/traces),改 `.env` 后重启再 `--batch` 新值。已用本地假 PRISM 服务验证 payload 能发出(traces/spans/trajectories/KB 路径均命中),真实字段校验待 key。
3. `GET /api/setup-doctor` 或 `python prism_setup.py --handshake` 看 `live_connected`。

---
## Track 1 的 3 个 PRISM 证明(逐步)
### Proof 1 — Knowledge Base + kb_search run
1. PRISM → Knowledge Base:确认 `carcost_faq.md` 已上传(`--upload-kb` 或网页拖入 `kb/carcost_faq.md`);可选:分配给 agent `carcost-advisor-v2`(首条 trace 之后才能选)。我们的 kb_search **不传 agent_id**(项目级搜索),所以分配与否都能命中。
2. 跑 `python run_scenarios.py`,或在 UI 里问提前还款(问题框走 API:`curl -XPOST localhost:8090/api/advise -H 'content-type: application/json' -d '{"price":30000,"down":6000,"term_months":48,"apr":6.5,"state":"NJ","age":40,"want_lease":true,"question":"Can I pay it off early? 可以提前还款吗?"}'`)。
3. Traces → 打开 `carcost-s5-normal-kb-v2-<batch>` → Steps:**`kb_search` 一步**,output 里 `"backend": "prism"`、results 来自 `prism-kb`(若是 `local` 说明 PRISM KB 没命中,检查上传/key)。
4. 截图:① Knowledge Base 页(文档已上传);② 该 trace 的 Steps(kb_search 展开)。
(也可用 `python prism_setup.py --kb-test "early payoff"` 直接看检索结果。)

### Proof 2 — Root Cause cluster(≥3 条失败 run)
1. Traces 页筛 agent `carcost-advisor-v1`,勾选 4 条失败:s1-alaska、s2-young-driver、s3-hawaii、s4-apr-decimal(失败原因在 metadata.failure_reason 与 `sanity_check` span 的 error 里)。等自动评分跑完(有延迟)。
2. **Analyse selected**(1 credit/条,共 4)→ Root Cause 页 **Analyze now**(5 credits)。
3. 预期:一个 cluster 含 ≥3 条(“不支持的州/年龄被静默忽略→保险 $0 / 无校验”)。若 PRISM 把它们拆开,再灌一批:`python run_scenarios.py --only v1 --batch b2` 并全选 8 条重新 Analyze。
4. 截图 Root Cause 页的 cluster(显示 ≥3 条 trace)。修复叙事:v2 加了输入校验+明示回退+number_guard,同输入重跑 v2 全部通过。

### Proof 3 — 自定义 Evaluator,v1 vs v2(需 Builder 计划)
1. Evaluators Hub → Create:名称 `CarCost numeric grounding & disclosure`,rubric 用 `evaluator_rubric.md` 里的文本(用了 {input} {output} {context};{context} 来自 kb_search/calculate/insurance 等 tool span)。
2. 在 Traces 里分别选 v1 的 5 条、v2 的 5 条 → Run evaluator(1 credit/条,共 10)。
3. 预期:v1 多数 FAIL(保险 $0、无工具/无 kb 上下文),v2 全 PASS → 截图并排对比(或按 agent_id 分组的结果表)。
4. 没有 Builder?→ 去 Discord/现场问主办方要升级;Free 下 Guardrails 和 Evaluators Hub 锁住,这是 Proof 3 的硬阻塞。

---
## Devpost 提交清单(截止今天 4:00 PM ET,留 10 分钟缓冲)
- [ ] 项目名 + 一句话:“CarCost Advisor 买车总成本顾问 — deterministic loan/insurance math, LLM explains only, traced end-to-end in PRISM”
- [ ] Track:Track 1 Money Intelligence
- [ ] 描述:问题(买车总成本被月供迷惑)、做法(工具算数/LLM 只解释/number_guard)、v1→v2 的真实失败与修复、**只用虚构样本数据**、保险为估算区间非报价、非财务建议
- [ ] **3 个 PRISM 证明截图**:KB+kb_search run / Root Cause cluster(≥3) / Evaluator v1 vs v2;并写明 PRISM 的判断是否合理
- [ ] 说明如何使用 NicrronNinoo:模型调用走 `api.nicrron.ai/v1`,model `nicrron/auto`(trace 的 model 字段可佐证)
- [ ] 团队成员(2–5 人,按规则核对)
- [ ] **Live demo 链接**(见下:需要公网地址,当前只在 box 的 8090 端口)
- [ ] Prototype 链接(ninoo.app 或同一 demo 链接,按规则)
- [ ] **代码仓库链接**(本目录已 `git init`;`.env` 在 .gitignore,推送前确认没有 key)
- [ ] 演示视频/录屏(可选但建议:跑一次 UI → 展示 PRISM Steps)
- [ ] 提交前自检:`/api/health` 显示 LLM live、PRISM sending;PRISM 里 10 条 trace 都在

## 公网 demo
box 上监听 `0.0.0.0:8090`。需要公网 URL 时:Vercel 不适合(单进程 Python+本地 jsonl),建议 `cloudflared tunnel --url http://localhost:8090` 或 ngrok;key 只放服务端 `.env`,不要放前端。

## 文件
`app/calc.py` 贷款/租赁(精确到分的摊销)· `app/insurance.py` 虚构保险表(区间)· `app/kb.py` + `kb/carcost_faq.md` 知识库与 kb_search · `app/llm.py` Nicrron 调用+mock+number_guard · `app/tracing.py` PRISM(trace+spans+trajectory)· `app/agent.py` v1/v2 流程 · `run_scenarios.py` · `prism_setup.py` · `evaluator_rubric.md`

## 实测记录(2:50 PM ET)
- Nicrron live:`nicrron/auto` 实际路由到 `anthropic/claude-haiku-5-5`,10/10 run 为 live,v2 的 number_guard 10/10 通过。
- PRISM `PRISM_MODE=both` 实测正确:`/api/traces` 先建 trace,`/api/spans/ingest` 返回 `trace_created:false`(挂到同一 trace,无重复),每条 trace 有 9–10 个 db_spans,v2 的 kb_search 步 `backend: prism`。
- 已知问题:PRISM 自动评分对这批 trace 报 `analyze_trace error: 401 from api.anthropic.com invalid x-api-key`(PRISM 服务端的评分模型 key 问题);当前 key 所属 org 的 `/api/entitlements` 显示 plan=free(evaluators_hub/guardrails write=false)—— 确认升级 Builder 的是同一个 org/project。
- 公网:box 出站 7844(cloudflared)和 SSH 隧道被拦;需另想办法(见报告)。

## 更新(3:10 PM ET):Steps 修复 — 默认 `PRISM_MODE=steps`
- 原因:PRISM 的 trace 页 Steps 来自“同一 session 下多条 trace 行(带 `step_order` + `invocation_id`,和官方 ADK adapter 同形)”,而不是 /api/spans/ingest 的 span。
- 现在每个 run 用官方 SDK `PRISMtrace.trace_llm` 发多行:工具步骤 `carcost:tool:<name>`(validate_inputs / kb_search / calculate_loan / calculate_lease / estimate_insurance / total_cost / number_guard / sanity_check),最终回答那一行用真实模型名、`trace_id` 就是 `carcost-<scenario>-<v1|v2>-<batch>`(**点这条**),工具行 id 为 `<main>.NN-<tool>`。PRISM 自动装配 1 条 trajectory/run(已用 API 读回:r2 的 10 个 session 各 1 条,无重复 trace_id)。
- v1 失败 run 的主 trace metadata.status=error + error_message=失败原因;v2 正常。
- batch r1 的 10 条是旧格式(无 Steps),Proof 请只用 `-r2` 的 trace。`dbg-*` 是调试用,忽略。
