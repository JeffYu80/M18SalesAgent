---
name: M18SalesOrder
description: >
  M18 sales order skill for the official `oldso` object. Use for
  sales order list/search, load, auto-completion create, standard
  create/update, and validation/error translation.
---

# M18 Sales Order Skill

This skill defines the domain rules for the M18 ERP sales order object.
It is built on top of the shared M18 API client and keeps order-specific
knowledge out of the user-facing agent.

## Official Object Definition

- Menu code: `oldso`
- Main table: `mainso`
- Line table: `sot`
- Remarks table: `remso`

## Official API Patterns

- Search list: `GET /jsf/rfws/search/search?stSearch=oldso&beId={beId}`
- Load entity: `GET /jsf/rfws/root/api/read/oldso?menuCode=oldso&id={id}`
- Auto-completion create: `POST /jsf/rfws/erp/bsFlow/save/oldso`
- Standard create/update: `PUT /jsf/rfws/root/api/save/oldso?menuCode=oldso`

## When To Use Which Write Path

Use auto-completion create when:

- the request uses business codes like `beCode`, `cusCode`, `proCode`
- the goal is quick draft creation
- M18 should fill defaults such as currency, staff, or document date

Use standard create/update when:

- the request already has internal IDs
- the caller needs precise field-level control
- the operation is an update to an existing order

## Minimum Payloads

### Auto-Completion Create

```json
{
  "beCode": "CAT2019",
  "cusCode": "000",
  "sot": [
    {
      "proCode": "00001",
      "unitCode": "PCS",
      "qty": 1,
      "up": 5,
      "disc": 5
    }
  ]
}
```

### Standard Create / Update

```json
{
  "mainso": {
    "values": [
      {
        "beId": 304,
        "tDate": "2022-03-11",
        "cusId": 119,
        "curId": 1,
        "staffId": 700,
        "flowTypeId": 15918,
        "rate": 1,
        "amt": 4
      }
    ]
  },
  "sot": {
    "values": [
      {
        "sourceType": "pro",
        "proId": 4197,
        "unitId": 39151,
        "qty": 1,
        "up": 5,
        "disc": 10,
        "amt": 5
      }
    ]
  }
}
```

## Skill Actions

This skill should expose these business actions:

- `sales_order.search`
- `sales_order.load`
- `sales_order.create_draft`
- `sales_order.save`

## Expected Response Shapes

Search:

- `stSearch`
- `size`
- `values`

Auto-completion create:

- `tranId`
- `tranCode`
- `message`
- `status`

Standard save:

- `recordId`
- `messages`
- `status`

## Field Reference

### Header Fields (`mainso`)

| Field | Type | Required | Write Path | Description |
|---|---|---|---|---|
| `beId` | int | yes | standard | Business entity ID |
| `beCode` | string | yes | bsFlow | Business entity code |
| `cusId` | int | yes | standard | Customer internal ID |
| `cusCode` | string | yes | bsFlow | Customer business code |
| `tDate` | string (YYYY-MM-DD) | no | both | Transaction date (default today) |
| `staffCode` | string | yes | both | Staff code (resolved to `staffId`) |
| `staffId` | int | yes | standard | Staff internal ID |
| `curId` | int | yes | standard | Currency ID |
| `flowTypeId` | int | yes | standard | Flow type ID |
| `rate` | float | no | both | Exchange rate (default 1) |
| `amt` | float | no | both | Header total amount |
| `manId` | int | no | both | Contact person ID (resolved from contact name) |
| `cuspono` | string | yes | both | Customer purchase order number |
| `dDate` | string (YYYY-MM-DD) | no | both | Delivery date / 去货日 |
| `cusDDate` | string (YYYY-MM-DD) | no | both | Customer required delivery date |

### Line Fields (`sot`)

| Field | Type | Required | Write Path | Description |
|---|---|---|---|---|
| `proId` | int | yes | standard | Product internal ID |
| `proCode` | string | yes | bsFlow | Product business code |
| `qty` | float | yes | both | Quantity |
| `up` | float | yes | both | Unit price |
| `unitId` | int | yes | standard | Unit internal ID (use `proId` in this environment) |
| `unitCode` | string | yes | bsFlow | Unit business code (e.g. "PCS") |
| `sourceType` | string | yes | standard | Source type (default "pro") |
| `disc` | float | no | both | Discount percentage (default 0) |
| `amt` | float | no | both | Line amount (default = qty × up) |
| `refCode` | string | no | both | 客户料号（从 EBI 102 自动获取） |
| `bDesc_en` | string | no | both | 英文产品说明（有客户料号时取客户说明，否则取产品主档 desc_en） |
| `bDesc_zh-CN` | string | no | both | 简体中文产品说明（仅无客户料号时从产品主档获取） |
| `bDesc_zh-TW` | string | no | both | 繁体中文产品说明（仅无客户料号时从产品主档获取） |

### Remark Fields (`remso`)

| Field | Type | Required | Description |
|---|---|---|---|
| `remark` | string | no | Free-text remark |

## MCP Tools

This skill's actions are exposed as MCP tools via `mcp_sales.py`:

| Skill Action | MCP Tool |
|---|---|
| `sales_order.search` | `sales_order_search` |
| `sales_order.load` | `sales_order_load` |
| `sales_order.create_draft` | `sales_order_create_draft` |
| `sales_order.save` | `sales_order_save` |

## Error Translation

Translate common M18 failures into business language:

- `core_101905`: required field is missing
- `core_141019`: record not found or no access
- `core_201`: unit ID conflict — the resolved unit is already in use; use `proId` as `unitId` instead

If M18 returns structured `messages`, prefer those over generic HTTP text.

## Cooperation Contract

The agent should call this skill for:

- object identity rules
- write-path selection
- minimum required business inputs
- payload field naming for order headers and lines

The API script should be called for:

- authentication
- retry
- request execution
- raw response parsing
