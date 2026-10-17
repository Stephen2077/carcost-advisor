# CarCost Advisor Knowledge Base (SAMPLE DATA ONLY / 仅示例数据)

All content below is generic educational sample text written for a hackathon demo. It is not financial, legal or insurance advice and contains no real rates. 以下内容为黑客松演示用的通用示例,不构成财务、法律或保险建议,不含真实费率。

## What is APR? / 什么是 APR
APR (annual percentage rate) is the yearly cost of borrowing expressed as a percent. A higher APR means a higher monthly payment and more total interest. Enter APR as a percent, for example 6.9 for 6.9 percent. APR(年化利率)是以百分比表示的年度借款成本。APR 越高,月供和总利息越高。请以百分数输入,例如 6.9 表示 6.9%。

## How is the monthly loan payment calculated? / 月供是怎么算的
The monthly payment uses the standard amortization formula: payment = P x r / (1 - (1 + r)^-n), where P is the amount financed (price minus down payment), r is the monthly rate as a decimal (APR percent / 1200, e.g. 6.5% APR gives r = 6.5 / 1200 = 0.005417; equivalently APR as a decimal / 12) and n is the number of months. In the early months a larger share of each payment is interest, and that share shrinks over time (e.g. $24,000 at 6.5% for 48 months: the first month's interest is about $130 of the $569.16 payment). 月供用标准等额本息公式:月供 = P x r / (1 - (1 + r)^-n),P 为贷款额(车价减首付),r 为月利率(小数形式:APR 百分数 / 1200,例如 APR 6.5% 则 r = 6.5 / 1200 = 0.005417;等价于小数形式的 APR / 12),n 为月数。前期月供中利息占比较高并逐月下降(例如 $24,000、6.5%、48 个月:首月利息约 $130,月供 $569.16)。

## Down payment effect / 首付的影响
A larger down payment lowers the amount financed, the monthly payment and total interest. It also reduces the chance of owing more than the car is worth (negative equity). 首付越高,贷款额、月供和总利息越低,也降低"欠款高于车值"(负资产)的风险。

## Loan term trade-off / 贷款期限的取舍
A longer term lowers the monthly payment but raises total interest, and a 72-84 month term keeps you in debt longer. A shorter term has a higher monthly payment but costs less in total. 期限越长月供越低,但总利息越高,72–84 个月会让你负债更久;期限短则月供高、总成本低。

## Loan vs lease / 贷款买车 vs 租赁
With a loan you build ownership and can keep the car after the last payment. A lease usually has a lower monthly payment, but you pay for depreciation and a finance charge and own nothing at the end; mileage limits and wear fees may apply. 贷款买车最终拥有车辆;租赁月供通常更低,但你支付的是折旧加融资费用,期末不拥有车辆,还可能有里程和损耗限制。

## Money factor for leases / 租赁的 Money Factor
Lease finance charges are often quoted as a money factor. Money factor is roughly APR divided by 2400. This demo uses that approximation with an invented 58 percent residual value. 租赁融资费常以 money factor 表示,约等于 APR/2400。本演示用此近似并采用虚构的 58% 残值。

## What does car insurance cost depend on? / 车险保费取决于什么
Typical factors include state, driver age and experience, vehicle type and value, coverage level, and driving record. Young drivers usually pay much more. The estimator in this demo uses invented sample tables and always returns a range, not a quote. 常见因素包括所在州、驾驶人年龄和驾龄、车型和车价、保障额度及驾驶记录。年轻司机通常保费高得多。本演示的估算器使用虚构示例表,只给区间,不是报价。

## Is the insurance number a quote? / 保险数字是报价吗
No. The insurance figure is a sample estimate range from invented tables. Real premiums must come from a licensed insurer or broker. 不是。保险数字来自虚构示例表的估算区间,真实保费必须向持牌保险公司或经纪人获取。

## Total cost of ownership / 总拥有成本
In this demo, total cost equals down payment plus all loan payments plus the sample insurance over the loan term. It excludes sales tax, registration fees, fuel, parking, maintenance and depreciation. 本演示中总成本 = 首付 + 全部贷款月供 + 贷款期内的示例保险;不含销售税、注册费、油费、停车、保养和折旧。

## Can I pay the loan off early? / 可以提前还款吗
Many auto loans allow early payoff and some charge a prepayment penalty; check the contract. Extra principal payments reduce total interest. 许多车贷允许提前还款,部分有提前还款违约金,请查看合同。多还本金可减少总利息。

## Negative equity / 负资产
Negative equity means you owe more than the car is worth. It is more likely with small down payments, long terms, and fast-depreciating vehicles. 负资产指欠款高于车辆价值。首付少、期限长、贬值快的车型更容易出现。

## Credit score and APR / 信用分与利率
Better credit usually qualifies for a lower APR. Shop for rates from several lenders before signing. This demo does not look at any credit data. 信用越好通常利率越低。签约前多比较几家贷款方。本演示不读取任何信用数据。
