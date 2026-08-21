# LaDe 即时配送动态路径优化

基于 LaDe 公开配送数据集的动态末端配送离线研究项目。仓库覆盖数据审计、订单事件回放、构造启发式、分解 CP-SAT、完整 ALNS 与 Rolling Horizon，并提交 12 个处理后的小型基准实例用于复现。

## 方法

- 在线 Greedy：每次只看到当前已经释放的订单；
- 离线 Regret-2：作为构造基线；
- 分解 CP-SAT：先做骑手—订单分配，再做每名骑手的开放路径排序；
- ALNS：Random、Worst、Shaw、Route Segment destroy，配合 Greedy、Regret-2、Regret-3 repair；
- 自适应算子权重、模拟退火接受、2-opt 局部搜索；
- Rolling Horizon：每 5 分钟吸收新订单，冻结空闲骑手下一站并重排剩余任务；
- C++ 批量插入与 2-opt 核心，缺少动态库时自动回退 Python。

## 快速验证

~~~bash
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/run_optimization.py
~~~

最后一条命令使用 data/processed/benchmark_instances 下已提交的 12 个区域—日期实例，不需要原始大文件。运行会生成逐实例结果和解文件；生成物不会提交到 Git。

## 已验证结果

12 个实例的均值：

| 方法 | 平均投影距离 | 平均综合目标 | 合成 SLA 迟到率 |
| --- | ---: | ---: | ---: |
| Dynamic Online Greedy | 211.67 km | 215,714 | 2.55% |
| Dynamic Rolling ALNS | 163.18 km | 167,028 | 2.14% |

在同一动态信息集下，Rolling ALNS 相对 Online Greedy 的平均综合目标降低 22.05%，合成迟到率降低 15.28%。离线 ALNS 相对离线 Regret-2 的平均综合目标降低 19.89%、投影距离降低 26.07%。

## 数据与指标边界

- 数据来源是 LaDe 公开数据集，结果是离线回放，不是平台线上收益；
- LaDe 不提供承诺送达时间，2 小时 SLA 是透明的压力测试假设；
- 距离矩阵使用 Web Mercator 投影直线距离，不声称是真实道路最短路或行驶时间；
- 道路数据只用于路网构建、连通性审计和订单点吸附；
- 在线算法与离线算法看到的信息不同，不能只按距离作公平比较；
- CP-SAT 是“分配—排序”分解基线，不声称求得完整多骑手 VRP 全局最优。

## 目录

~~~text
src/lade_routing/                     动态回放与优化算法
data/processed/benchmark_instances/   12 个处理后复现实例
scripts/run_optimization.py           统一实验入口
tests/                                约束和算法测试
cpp/route_core.cpp                    可选 C++ 加速源码
reports/                              聚合结果与运行元数据
~~~

详见 [优化报告](reports/optimization_report.md)、[数据与路网审计](reports/initial_data_and_network_audit.md) 和 [C++ 加速报告](reports/cpp_acceleration_report.md)。
