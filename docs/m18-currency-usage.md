# M18 Currency and Exchange-Rate Usage

This guide applies to both UAT and Production. Production base currencies are
read from the local `config/m18.prod.yaml` entity mapping.

## Rules

- Send `currency` as an ISO currency code (for example, `USD`) only when the
  requested document currency differs from the customer master.
- If `currency` is omitted, the service reads the customer's `cusacc.curId`.
- Send `t_date` when the business document has a specified date; otherwise the
  service uses today.
- The service resolves M18 `curId`, looks up M18 `getRate` for that date, and
  sends explicit `curId` and `rate` to M18. Callers must not send fixed values
  for either calculated field.
- Rates are not cached. Every new quotation and sales order queries M18 again.
- Production requires an explicit base-currency mapping for every `be_id`.
  An unmapped entity is rejected rather than falling back to `default_cur_id`.

## New quotation or sales order

`create_sales_orders_by_declaration` follows the same rule and also accepts
the optional `currency` parameter for all generated orders.

Customer-master currency:

```json
{
  "be_id": 4,
  "be_code": "SHK",
  "customer_code": "320",
  "t_date": "2026-07-31"
}
```

Explicit USD:

```json
{
  "be_id": 4,
  "be_code": "SHK",
  "customer_code": "320",
  "currency": "USD",
  "t_date": "2026-07-31"
}
```

## Quotation to order

The order keeps the source quotation's currency. Under the configured
`refresh` policy, its rate is queried again using `order_t_date`; when absent,
the quotation `t_date` is used.

```json
{
  "be_id": 4,
  "be_code": "SHK",
  "customer_code": "320",
  "currency": "USD",
  "t_date": "2026-07-31",
  "order_t_date": "2026-08-15"
}
```

## Terminal chat shortcuts

The optional final arguments are `[currency] [tDate]`:

```text
/quotation-draft 7 PUS 320 PGD798MB 1 130 000001
/quotation-draft 7 PUS 320 PGD798MB 1 130 000001 USD 2026-07-31
/sales-order-draft 7 PUS 320 PGD798MB 1 130 000001 USD 2026-07-31
```

For quotation-to-order with `order_t_date`, use the MCP tool directly or the
terminal `/run` command with its JSON parameters.

## Parameter names by entry point

- MCP tools use `currency`, `t_date`, and (for quotation-to-order)
  `order_t_date`.
- The Ops JSON dispatcher accepts both `t_date` and `tDate`, and normalizes the
  value before calling the service.
- The terminal shortcut uses `[currency] [tDate]` because it maps directly to
  the M18-style JSON payload.
