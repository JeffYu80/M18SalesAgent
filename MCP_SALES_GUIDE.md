# M18 Sales MCP 使用说明

## 启动与环境

```powershell
$env:M18_ENV='prod'   # 或 uat
python mcp_sales.py
```

客户端从 `config/m18.{M18_ENV}.yaml` 读取配置。目标环境配置缺失时，启动会报错，不会回退到 UAT。

## 主要工具

- `quotation_create_draft`、`quotation_save`：创建或保存销售报价。
- `sales_order_create_draft`、`sales_order_save`：创建或保存销售订单。
- `create_quotation_and_order`：创建报价、确认报价，再由其创建订单。
- `create_sales_orders_by_declaration`：按产品 `DeclarationType` 分单。
- `customer_*`、`product_*`、`business_entity_lookup`：查询客户、产品和实体资料。

## 报价转订单：确认前预检

`create_quotation_and_order` 在确认报价前完成订单侧预检：

- `be_code` 与 `be_id` 必须匹配 `be_mapping`；未知或不匹配的实体直接失败。
- 客户、员工、每个产品和单位必须可以解析。
- 多产品分单时，必须读取每个产品的 `DeclarationType`。
- `t_date` 与 `order_t_date` 必须是有效的 `YYYY-MM-DD` 日期。
- 先取得报价币别与报价日期汇率，并预先读取订单日期汇率。
- 指定 `contact_name` 时，必须恰好解析到一个联系人。

任一预检失败，报价不会被确认，也不会创建订单。报价确认后仅在返回 `status: true` 且有有效 `recordId` 时才继续创建订单；否则直接返回 M18 错误信息。

## 币别与汇率规则

- 调用方只提供可选 `currency`（例如 `USD`）和 `t_date`。
- 未提供 `currency` 时，服务读取客户主档的 `cusacc.curId`。
- 每次新建报价或订单，服务都以 `be_id` 的本位币和 `t_date` 调用 M18 `getRate`；不缓存汇率。
- 服务最终向 M18 明确传入 `curId` 与 `rate`；调用方不要传这两个计算字段。
- Production 中每个 `be_id` 必须在 `entity_currency_by_be_id` 配置本位币；未映射会直接报错。
- 报价转订单保留报价币别；默认 `refresh` 策略会按 `order_t_date`（未传时等于 `t_date`）重新取汇率。

```json
{"be_id":4,"be_code":"SHK","customer_code":"320","currency":"USD","t_date":"2026-07-31"}
```

更完整的参数示例见 [docs/m18-currency-usage.md](docs/m18-currency-usage.md)。

## 终端聊天快捷命令

```text
/quotation-draft <beId> <beCode> <customerCode> <productCode> <qty> <up> <staffCode> [currency=USD] [tDate=YYYY-MM-DD]
/sales-order-draft <beId> <beCode> <customerCode> <productCode> <qty> <up> <staffCode> [currency=USD] [tDate=YYYY-MM-DD]
```

可只指定日期：

```text
/quotation-draft 7 PUS 320 PGD798MB 1 130 000001 tDate=2026-07-31
```
