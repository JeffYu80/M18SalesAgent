# Skill: M18 ERP API Connector

## Purpose
Provide a reusable abstraction layer for all agents that interact with the Multiable M18 ERP system via its REST API. Handles OAuth 2.0 authentication, SqlEntity CRUD operations, data search, EBI report extraction, and error handling. All ERP-touching agents depend on this skill.

## API Documentation Sources
- Core API (CE01): https://m18doc.multiable.com/en/api/ce01/
- Web Services: https://m18doc.multiable.com/en/wsdoc/
- Core Services: https://m18doc.multiable.com/en/m18/m18core_ws.html

## Authentication

### OAuth 2.0 Setup
1. Register application in M18 [Authorized Application List] module to obtain `Client ID` and `Client Secret`
2. Create dedicated API users with scoped permissions:
   - **Read-only user**: For analytics agents (supply-chain-analytics, demand-forecasting)
   - **Read-write user**: For draft-creation agents (oem-sales-admin, cra-returns, sku-parts)
3. Password must be encrypted with SHA1 for token requests
4. All requests require two headers:
   - `authorization: Bearer {access_token}`
   - `client_id: {application_id}`

### Token Management
- Implement token refresh before expiry
- Store tokens securely (environment variables, not in code)
- Log all token refreshes for audit trail

## Core Operations

### 1. Entity CRUD

**Create Entity Template** (get empty structure):
```
POST /jsf/rfws/entity/create/{menuCode}
```

**Read Entity**:
```
GET /jsf/rfws/root/api/read/{menuCode}?id={recordId}
```
- Supports `iRev` parameter for historical versions

**Save Entity** (create or update):
```
PUT /jsf/rfws/root/api/save/{menuCode}
Content-Type: application/json

{
  "main{entity}": {
    "values": [{ "field1": "value1", ... }]
  },
  "{entity}t": {
    "values": [{ "lineField1": "value1", ... }]
  }
}
```

**Auto-Completion Save** (supports codes instead of IDs):
```
POST /jsf/rfws/erp/bsFlow/save/{menuCode}
Content-Type: application/json

{
  "beCode": "...",
  "cusCode": "...",
  "{entity}t": [{
    "proCode": "...",
    "unitCode": "PCS",
    "qty": 1,
    "up": 10
  }]
}
```
Response: `{ "tranId": 123, "tranCode": "SO0220888", "status": true }`

**Delete Entity**:
```
DELETE /jsf/rfws/root/api/delete/{menuCode}?id={recordId}
```

### 2. Data Search
```
GET /jsf/rfws/search/search?stSearch={menuCode}&beId={beId}&startRow=0&endRow=100
```
- Supports filtering, sorting, pagination
- `stSearch` lookup types discoverable via Data Dictionary

### 3. EBI Report Extraction
```
GET /jsf/rfws/ebiWidget/loadReport?formatId={reportId}
```
- Returns formatted report data (inventory aging, stock turn, sales summaries)
- Critical for analytics agents that need pre-computed KPIs

### 4. Inventory Location Query
```
GET /jsf/rfws/erp/trdg/stock/viewLocLvl/{beId}/{proId}
```
- Real-time inventory by location — replaces manual M18 exports

### 5. Pricing Query
```
GET /jsf/rfws/erp/trdg/price/multiPro
```
- Multi-product pricing lookup — for PI/SO draft validation

## Module Reference — MenuCodes

### Sales Module
| Entity | menuCode | Main Table | Line Table | Remarks Table |
|--------|----------|------------|------------|---------------|
| Sales Quotation | `oldqu` | `mainqu` | `qut` | `remqu` |
| Sales Order | `oldso` | `mainso` | `sot` | `remso` |
| Customer Shipment Note | `aso` | `mainaso` | `asot` | `remaso` |
| Delivery Note | `dn` | `maindn` | `dnt` | `remdn` |
| Sales Invoice | `si` | `mainsi` | `sit` | `remsi` |

**Sales Order Key Fields**:
- Header (`mainso`): `beId`, `tDate`, `curId`, `cusId`, `rate`, `code`, `status`, `flowTypeId`, `staffId`, `amt`, `dDate`
- Lines (`sot`): `proId`, `qty`, `unitId`, `up`, `disc`, `amt`, `sourceType`, `locId`
- Shipping (`remso`): `shipAd1-4`, `recipient`, `country`, `city`, `province`, `zipcode`

### Purchase Module
| Entity | menuCode | Main Table | Line Table |
|--------|----------|------------|------------|
| Purchase Quotation | `vqu` | `mainvqu` | `vqut` |
| Purchase Order | `po` | `mainpo` | `pot` |
| Vendor Shipment Note | `asi` | `mainasi` | `asit` |
| Goods Receipt Note | `an` | `mainan` | `ant` |
| Purchase Return | `pr` | `mainpr` | `prt` |
| Purchase Invoice | `pi` | `mainpi` | `pit` |

**Purchase Order Key Fields**:
- Header (`mainpo`): `beId`, `code`, `tDate`, `dDate`, `venId`, `curId`, `rate`, `flowTypeId`, `staffId`, `status`, `amt`
- Lines (`pot`): `sourceType`, `proId`, `unitId`, `qty`, `up`, `disc`

### Stock Module
| Entity | menuCode | Main Table | Line Table |
|--------|----------|------------|------------|
| Opening Stock | `os` | `mainos` | `ost` |
| Stock Adjustment | `k` | `maink` | `kt` |
| Internal Transfer | `move` | `mainmove` | `movet` |
| Defective Stock Register | `defstkreg` | `maindefstkreg` | `defstkregt` |
| Defect Write-Off | `dstn` | `maindstn` | `dstnt` |

**Transfer Order Key Fields**:
- Header (`mainmove`): `beId`, `code`, `tDate`, `locId`, `staffId`, `status`
- Lines (`movet`): `proId`, `unitId`, `qty`, `alocId`, `lotno`

### Item Master
| Entity | menuCode | Description |
|--------|----------|-------------|
| Product | `pro` | Item/SKU master data |

## BsRule Considerations

M18 enforces server-side business rules (`BsRule`) that fire automatically on API writes:
- **Before Save**: Validation rules (mandatory fields, value range checks, cross-field consistency)
- **After Save**: Cascading updates (inventory recalculation, pipeline updates)
- **On Approval**: BPM workflow triggers

**Implications for agents**:
1. API-created entities will be validated by existing BsRules — no need to duplicate validation logic
2. If a BsRule rejects the save, the API returns HTTP 400 with `error_info` header containing `CheckMsg` JSON array
3. Agents must parse `CheckMsg` and present human-readable error descriptions
4. BPM approval gates still apply — API-created drafts enter the approval queue just like manual entries

## Error Handling

### HTTP Status Codes
- `200`: Success
- `400`: BsRule validation failure — parse `error_info` header for `CheckMsg` details
- `401`: Token expired — refresh and retry
- `403`: Insufficient permissions — check API user scope
- `404`: Entity not found
- `500`: Server error — retry with backoff

### CheckMsg Error Format
```json
{
  "messages": [
    { "msgType": "error", "msgDesc": "Field [cusId] is required" }
  ]
}
```

## Reusable Across Agents
- **OEM Sales Admin Agent** — SO/PO creation drafts, price list queries
- **CRA & Returns Agent** — Replacement SO creation, DN creation, credit note queries
- **SKU & Parts Agent** — Item master (`pro`) CRUD for NIRF setup
- **Supply Chain Analytics Agent** — Inventory queries, EBI reports, stock data
- **Demand Forecasting Agent** — Sales data extraction, pending sales queries

## Implementation Notes

### Session-Based Architecture
This skill is implemented as a Claude Code reusable prompt + code pattern, not a standalone service. Each agent session:
1. Reads OAuth credentials from environment variables
2. Obtains/refreshes bearer token
3. Executes API calls using `curl` or Python `requests`
4. Parses JSON responses
5. Handles errors per the patterns above

### Vibe-Coding Estimate
- **Session 1**: OAuth flow, token management, basic CRUD wrapper functions, error handling
- **Session 2**: Module-specific helpers (SO/PO/DN/TO/Item creation with field mapping), search queries, EBI report extraction
- **Total**: 2 Claude Code sessions

### Security Requirements
- OAuth credentials stored as environment variables, never committed to repo
- API user permissions must follow principle of least privilege
- All write operations logged with timestamp, user, entity type, and record ID
- Read-only API user for analytics; read-write for draft creation with BPM gates
