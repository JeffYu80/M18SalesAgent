# M18 Sales Agent — 调用说明

## 1. 项目概述

M18 Sales Agent 是一个 MCP 服务，将 Multiable M18 ERP 的销售报价、销售订单、客户、产品等操作封装为 17 个 MCP tool，供 AI Agent 调用。

## 2. 启动方式

```bash
cd M18SalesAgent
python mcp_sales.py
```

默认使用 UAT 环境。如需切换环境，设置 `M18_ENV` 环境变量：

```bash
# Windows PowerShell
$env:M18_ENV='prod'; python mcp_sales.py
```

## 3. Agent 连接配置

### 方式一：MCP 协议连接（推荐）

```json
{
  "mcpServers": {
    "m18-erp": {
      "command": "python",
      "args": ["/path/to/M18SalesAgent/mcp_sales.py"]
    }
  }
}
```

### 方式二：SSE 模式（远程访问）

服务端：
```bash
python mcp_sales.py --sse
```

客户端配置：
```json
{
  "mcpServers": {
    "m18-erp": {
      "url": "http://服务器IP:8000/sse"
    }
  }
}
```

## 4. 可用工具

连接成功后，Agent 自动发现 17 个工具：

| 工具名 | 说明 |
|---|---|
| `customer_search` | 按代码或名称搜索客户 |
| `customer_load` | 按 ID 加载客户详情 |
| `customer_contacts` | 查询客户联系人 |
| `customer_part_lookup` | 按客户料号查内部产品代码 |
| `product_search` | 搜索产品 |
| `product_load` | 按 ID 加载产品详情 |
| `product_units` | 查询产品单位信息 |
| `product_customer_item_codes` | 查询客户料号映射 |
| `business_entity_lookup` | 查询 be_code 对应的 be_id |
| `quotation_search` | 搜索销售报价 |
| `quotation_load` | 按 ID 加载报价单 |
| `quotation_create_draft` | 创建报价草稿（bsFlow） |
| `quotation_save` | 保存报价单（标准） |
| `sales_order_search` | 搜索销售订单 |
| `sales_order_load` | 按 ID 加载销售订单 |
| `sales_order_create_draft` | 创建订单草稿（bsFlow） |
| `sales_order_save` | 保存销售订单（标准） |

## 5. 调用前提

每次操作需要用户提供：
- `username` — M18 登录用户名
- `password` — M18 登录密码（明文，系统自动 SHA1）
- `be_id` — 业务实体 ID（公司 ID）

## 6. Agent 定义文件（可选）

如需让 Agent 了解完整业务规则，可将 AGENT.md 作为 system prompt：

```python
# Python Agent 示例

# 只加载报价 Agent
system_prompt = open("M18SalesAgent/agents/m18-sales-quotation-agent/AGENT.md").read()

# 只加载订单 Agent
system_prompt = open("M18SalesAgent/agents/m18-sales-order-agent/AGENT.md").read()

# 同时加载报价和订单 Agent
q = open("M18SalesAgent/agents/m18-sales-quotation-agent/AGENT.md").read()
s = open("M18SalesAgent/agents/m18-sales-order-agent/AGENT.md").read()
system_prompt = q + "\n\n---\n\n" + s
```

AGENT.md 包含：角色定义、行为规则、必填字段说明、输入输出示例。

## 7. 注意事项

- 所有写操作（创建、保存）需要用户提供 `customer_po`（客户采购订单号）
- `staffCode` 是必填参数
- 搜索客户名称返回多个结果时，需用户确认
- 环境配置通过 `config/m18.uat.yaml` 或 `config/m18.prod.yaml` 管理
- 运行时无需修改任何代码
