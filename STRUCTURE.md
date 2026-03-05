# 项目结构说明

```
crypto-trader-pro/
├── src/                    # 源代码
│   ├── ws/                # WebSocket 客户端
│   │   ├── binance_ws.py
│   │   └── okx_ws.py
│   ├── exchange/          # 交易所接口封装
│   │   └── ccxt_exchange.py
│   ├── engine/            # 核心引擎
│   │   ├── strategy_engine.py
│   │   ├── executor.py
│   │   └── risk_manager.py
│   ├── data/
│   │   └── simulation_db.py
│   ├── dashboard/
│   │   ├── app.py
│   │   ├── templates/
│   │   │   └── index.html
│   │   └── static/
│   │       └── app.js
│   ├── notifier.py        # 通知管理器
│   └── main.py
├── config/                # 配置文件
│   ├── modes.json         # 运行模式：local | testnet | live
│   ├── strategies/        # 策略配置
│   │   └── ma_cross.json
│   ├── exchanges/         # 交易所配置
│   │   ├── binance.json
│   │   └── okx.json
│   ├── simulation/        # 模拟参数
│   │   └── local.json
│   └── risk.json          # 风控参数
├── tests/                 # 单元测试
├── docs/                  # 文档
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```
