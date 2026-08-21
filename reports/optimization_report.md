# LaDe 动态配送路径优化：算法实验报告

## 实验范围

- 数据：LaDe 吉林真实末端配送订单；
- 实例：12 个“区域—日期”实例；
- 规模：每个实例 48–188 单、3–9 名历史活跃骑手；
- 动态调度周期：300 秒；
- 合成 SLA：2.0 小时；
- 假设速度：20 km/h；
- 单点服务时间：120 秒；
- CP-SAT 单实例总时间限制：6 秒；
- PyVRP 静态基线：250 次迭代；
- 离线 ALNS：250 次迭代；
- 动态滚动 ALNS：每次重规划 30 次迭代。

## 方法

1. `dynamic_online_greedy`：只使用当前时点已释放订单，按完成时间、迟到和负载进行在线指派；
2. `dynamic_rolling_alns`：每个调度周期重建未服务订单池，使用 ALNS 规划，并冻结每名空闲骑手的下一站；
3. `greedy_regret2_offline`：全量信息下的 Regret-2 构造基线；
4. `ortools_cp_sat_decomposed`：OR-Tools CP-SAT 完成骑手分配，并对每名骑手的开放路径进行 CP-SAT 排序；
5. `pyvrp_static_distance`：PyVRP 多起点静态距离基线，每名骑手对应一个车辆类型，以零成本返仓弧匹配开放路线口径；
6. `alns_offline`：Random/Worst/Shaw/Route-Segment Destroy，Greedy/Regret-2/Regret-3 Repair，自适应权重、模拟退火和 2-opt。

## 聚合结果

| method | instances | mean_distance_km | mean_objective | mean_runtime_seconds | median_workload_std | mean_synthetic_late_rate | mean_total_lateness_minutes | mean_replans |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dynamic_rolling_alns | 12.0000 | 163.1760 | 167028.2182 | 0.4888 | 3.2150 | 0.0214 | 58.7551 | 47.3333 |
| dynamic_online_greedy | 12.0000 | 211.6703 | 215714.4878 | 0.0024 | 3.1795 | 0.0255 | 61.8067 |  |
| ortools_cp_sat_decomposed | 12.0000 | 101.7394 | 259279.7518 | 3.7399 | 0.4714 | 0.1021 | 2623.4191 |  |
| alns_offline | 12.0000 | 50.7467 | 903894.0981 | 3.6117 | 10.6855 | 0.5034 | 14201.6515 |  |
| pyvrp_static_distance | 12.0000 | 44.9836 | 1098677.6165 | 0.1814 | 11.8884 | 0.5539 | 17542.2651 |  |
| greedy_regret2_offline | 12.0000 | 72.4189 | 1323190.5344 | 0.1452 | 13.6103 | 0.6059 | 20823.5073 |  |

## 相对改进

- 离线 ALNS 相对 Regret-2 的平均综合目标改进：19.89%；
- 离线 ALNS 相对 Regret-2 的平均距离改进：26.07%；
- 动态滚动 ALNS 相对在线 Greedy 的平均综合目标改进：22.05%；
- 动态滚动 ALNS 相对在线 Greedy 的平均合成迟到率改进：15.28%。

## 口径与边界

- 优化距离采用 Web Mercator 投影直线距离，路线为开放路线，不强制返回起点；
- 路网数据用于道路图构建、连通性审计和订单点吸附；当前算法实验没有把投影直线距离表述成真实道路行驶时间；
- LaDe 不提供平台承诺送达时间，2 小时 SLA 是透明的压力测试假设，不是真实平台超时率；
- 在线方法只能看到当时已释放订单，离线方法可看到实例内全部订单，两类结果用于不同目的，不能只依据距离直接判定公平优劣；
- CP-SAT 使用“分配—单骑手路径”分解，以便在 48–188 单实例上稳定生成可行解；它不是对完整多骑手 VRP 最优性的证明。
- PyVRP 基线优化整数化投影距离，不直接优化本项目的合成 SLA 迟到或负载均衡项，因此只作为外部静态求解器参照。
