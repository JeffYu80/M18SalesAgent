---
name: M18NOI
description: >
  M18 NOI (Notice of Intention) skill for the official `udfnoips` object.
  Use for NOI list/search, load, and auto-completion create.
---

# M18 NOI Skill

This skill defines the domain rules for the M18 ERP NOI object.
NOI is a UDF module used for Notice of Intention documentation.

## Official Object Definition

- Menu code: `udfnoips`
- Main table: `udfnoips`
- Line table: `udfnoizb`
- Sub tables: `udfnoips_black`, `udfnoips_white`, `udfnoips_attach`, `udfnoips_delinfo`

## Official API Patterns

- Search list: `GET /jsf/rfws/search/search?stSearch=udfnoips&beId={beId}`
- Load entity: `GET /jsf/rfws/root/api/read/udfnoips?menuCode=udfnoips&id={id}`
- Auto-completion create: `POST /jsf/rfws/erp/bsFlow/save/udfnoips`
- Standard create/update: `PUT /jsf/rfws/root/api/save/udfnoips?menuCode=udfnoips`

## Header Fields (`udfnoips`)

| Field | Type | Required | Description |
|---|---|---|---|
| `beId` | int | yes | Business entity ID |
| `code` | string | auto | Document code (auto-generated) |
| `status` | string | auto | Status (N=New) |
| `desc` | string | yes | NOI description |
| `desc_en` | string | no | English description |
| `desc_zh-CN` | string | no | Simplified Chinese description |
| `desc_zh-TW` | string | no | Traditional Chinese description |
| `udfkh2` | string | yes | Customer code |
| `udfpmcyj` | string | no | Review opinion |
| `udfpeyj` | string | no | PE opinion |
| `udfshzyj` | string | no | Audit opinion |
| `udfocbz` | string | no | OC remark |

## Line Fields (`udfnoizb`)

| Field | Type | Required | Description |
|---|---|---|---|
| `udfcpwl2` | int | yes | Product ID (resolved from proCode) |
| `udfsl` | string | yes | Quantity |
| `udfkgldl` | string | yes | Customer part code |
| `udfkhcpbh` | string | no | Customer product code |
| `udfkh` | string | no | Customer (alternate) |
| `udfcpwl` | string | no | Product material (alternate) |
| `udfyjcdrq` | timestamp | no | Estimated ship date |
| `udfwgr` | timestamp | no | Completion date |
| `udfbgslzcht` | string | no | Customs declaration / China-HK-TW |
| `udfscdjgs` | string | no | Production unit price company |
| `udfpeqcgs` | string | no | PE QC company |
| `udfsjxygsps` | string | no | Design/selection company review |
| `udfrgcbps` | string | no | Engineering department review |
| `udfmzkryqwgr` | string | no | Meet customer required completion date |
| `udfwnmzwg` | string | no | Unable to meet completion date |
| `udfxhjjwgr` | string | no | Scare delivery date |
| `udfxhjjjq` | string | no | Scare price |
| `udfjhwlxhj` | string | no | Delivery rate total |
| `udfbz` | string | no | Remark |

## MCP Tools

This skill's actions are exposed as MCP tools via `mcp_sales.py`:

| Skill Action | MCP Tool |
|---|---|
| `noi.create_draft` | `noi_create_draft` |
| `noi.search` | `noi_search` |
| `noi.load` | `noi_load` |
