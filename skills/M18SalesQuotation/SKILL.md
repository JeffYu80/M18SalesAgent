---
name: M18SalesQuotation
description: >
  M18 sales quotation skill for the official `oldqu` object. Use for
  sales quotation list/search, load, auto-completion create, standard
  create/update, and validation/error translation.
---

# M18 Sales Quotation Skill

This skill defines the domain rules for the M18 ERP sales quotation object.
It is built on top of the shared M18 API client and keeps quotation-specific
knowledge out of the user-facing agent.

## Official Object Definition

- Menu code: `oldqu`
- Main table: `mainqu`
- Line table: `qut`
- Remarks table: `remqu`

## Official API Patterns

- Search list: `GET /jsf/rfws/search/search?stSearch=oldqu&beId={beId}`
- Load entity: `GET /jsf/rfws/root/api/read/oldqu?menuCode=oldqu&id={id}`
- Auto-completion create: `POST /jsf/rfws/erp/bsFlow/save/oldqu`
- Standard create/update: `PUT /jsf/rfws/root/api/save/oldqu?menuCode=oldqu`

## When To Use Which Write Path

Use auto-completion create when:

- The request uses business codes like `beCode`, `cusCode`, `proCode`
- The goal is quick draft creation
- M18 should fill defaults such as currency, staff, or document date

Use standard create/update when:

- The request already has internal IDs
- The caller needs precise field-level control
- The operation is an update to an existing quotation

## Minimum Payloads

### Auto-Completion Create

```json
{
  "beCode": "CAT2019",
  "cusCode": "000",
  "qut": [
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
  "mainqu": {
    "values": [
      {
        "beId": 304,
        "tDate": "2022-03-30",
        "curId": 1,
        "cusId": 1,
        "rate": 1,
        "amt": 4,
        "flowTypeId": 15918,
        "staffId": 700
      }
    ]
  },
  "qut": {
    "values": [
      {
        "sourceType": "pro",
        "proId": 4197,
        "qty": 1,
        "unitId": 39151,
        "amt": 4,
        "disc": 10,
        "up": 5
      }
    ]
  }
}
```

## Skill Actions

This skill should expose these business actions:

- `quotation.search`
- `quotation.load`
- `quotation.create_draft`
- `quotation.save`

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

### Header Fields (`mainqu`)

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
| `udfcmpo` | string | yes | both | Customer purchase order number |

### Line Fields (`qut`)

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

### Remark Fields (`remqu`)

| Field | Type | Required | Description |
|---|---|---|---|
| `remark` | string | no | Free-text remark |

## MCP Tools

This skill's actions are exposed as MCP tools via `mcp_server.py`:

| Skill Action | MCP Tool |
|---|---|
| `quotation.search` | `quotation_search` |
| `quotation.load` | `quotation_load` |
| `quotation.create_draft` | `quotation_create_draft` |
| `quotation.save` | `quotation_save` |

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
- payload field naming for quotation headers and lines

The API script should be called for:

- authentication
- retry
- request execution
- raw response parsing
