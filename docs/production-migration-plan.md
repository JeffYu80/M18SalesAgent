# Production 迁移计划

## 1. 配置文件准备

### 1.1 创建 `config/m18.prod.yaml`

| 配置项 | 说明 | 当前 UAT 值 | Production 需填写 |
|---|---|---|---|
| `url` | M18 API 地址 | `https://uat.smartecgr.com/...` | 生产环境地址 |
| `client_id` / `client_secret` | 应用凭证 | UAT 值 | 生产环境值 |
| `be_mapping` | 业务实体映射 | PUS:7, SHK:4, OHK:5, PHK:6, SDG:3 | 生产环境 ID（可能不同）|
| `customer_part_report_id` | 客户料号报表 ID | 102 | 生产环境 ID |
| `customer_list_report_id` | 客户列表报表 ID | 103 | 生产环境 ID |
| `app_name` / `app_version` | 系统标识 | SalesAgent / 1.0.0 | 可保留 |

### 1.2 UAT vs Production 差异确认

| 项目 | UAT | Production | 风险 |
|---|---|---|---|
| be_id | 3,4,5,6,7 | 可能不同 | **高** — be_mapping 需确认 |
| EBI 报表 ID | 102, 103 | 可能不同 | **高** — 报表 ID 需确认 |
| 客户/产品数据 | 测试数据 | 真实数据 | **低** — 工具通用 |
| flowTypeId | PUS=5, SHK=3 | 可能不同 | **中** — bsFlow 自动适配 |

## 2. 部署步骤

### 2.1 代码部署

```bash
# 克隆代码
git clone https://github.com/JeffYu80/M18SalesAgent.git
cd M18SalesAgent

# 安装依赖
pip install mcp openai requests pyyaml
```

### 2.2 配置生产环境

```bash
# 把收到的 m18.prod.yaml 放到 config/ 目录下
# 设置环境变量
set M18_ENV=prod
# 或
$env:M18_ENV='prod'
```

### 2.3 启动服务

```bash
python mcp_sales.py
```

## 3. 验证清单

启动后按以下顺序验证 25 个工具：

### 3.1 基础连接
- [ ] `business_entity_lookup("PUS")` 返回正确 be_id
- [ ] `customer_search(be_id=X, username, password)` 返回客户数据
- [ ] `product_search(be_id=X, quick_search="PGD798MB")` 返回产品

### 3.2 销售流程
- [ ] `quotation_create_draft` — 创建报价成功
- [ ] `sales_order_create_draft` — 创建订单成功
- [ ] `create_quotation_and_order` — 报价→确认→订单，SO 正确引用报价
- [ ] `create_sales_orders_by_declaration` — 按类型分单成功

### 3.3 NOI
- [ ] `noi_search` — 搜索 NOI
- [ ] `noi_create_draft` — 在 SDG 下创建 NOI

### 3.4 客户料号
- [ ] `customer_part_lookup` — EBI 报表 ID 正确
- [ ] `customer_list_all` — 客户列表报表 ID 正确

## 4. 已知风险

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| be_id 不同 | 所有操作需重新确认 | 上线前在 m18.prod.yaml 填写正确映射 |
| EBI 报表 ID 不同 | 客户料号/列表查询失败 | 上线前确认生产环境报表 ID |
| flowTypeId 不同 | 标准保存可能失败 | bsFlow 路径不受影响（自动适配）|
| UDF 字段名不同 | NOI 字段可能不存在 | 需确认生产环境 `udfnoips` 模块配置 |
| 网络限制 | 无法连接 GitHub/Git | 通过内网 Git 或直接复制代码 |

## 5. 回滚方案

```bash
# 切回 UAT
set M18_ENV=uat
python mcp_sales.py
```

代码本身不需要回滚，只需切换环境变量即可在 UAT 和 Production 之间切换。
