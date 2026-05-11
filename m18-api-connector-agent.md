# Agent: M18 API Connector (Shared Infrastructure Agent)

**Domain**: ERP
**Tag**: ERP-INFRA-01

## Purpose

Provide a shared middleware layer for all ERP-domain agents to authenticate with and query the Multiable M18 ERP system. This is not a user-facing agent — it is an infrastructure component that other agents call. It handles OAuth 2.0 token management, request routing, error handling, rate limiting, permission enforcement, and response normalization.

Every ERP-tagged agent in the system depends on this connector. Building it once as a shared skill prevents each agent from reimplementing authentication, error handling, and M18-specific quirks.

## Model Recommendation

Claude Sonnet 4 — this agent executes well-defined API calls with structured error handling. No creative reasoning or large context window needed.

## Tools Allowed

- Bash (Python requests for M18 API calls, curl as fallback)
- Read (configuration files, credential references)
- Write (token cache, request logs, error logs)

## Architecture

```
┌─────────────────────────────────────────┐
│          CALLING AGENT                  │
│  (Supply Chain / SKU / CRA / etc.)      │
│                                         │
│  Calls: m18_read(), m18_search(),       │
│         m18_create_draft(),             │
│         m18_check_inventory()           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      M18 API CONNECTOR                  │
│                                         │
│  1. Permission Check                    │
│     - Is this agent allowed to write?   │
│     - Is the target entity permitted?   │
│                                         │
│  2. Token Management                    │
│     - Check token cache                 │
│     - Refresh if expired                │
│     - Select correct service account    │
│       (readonly vs draft)               │
│                                         │
│  3. Request Execution                   │
│     - Add auth headers                  │
│     - Apply rate limiting               │
│     - Execute request                   │
│                                         │
│  4. Response Handling                   │
│     - Parse M18 response format         │
│     - Normalize to standard JSON        │
│     - Handle errors (401/400/404/500)   │
│     - Log for audit trail               │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│          M18 ERP SERVER                 │
│  REST API (OAuth 2.0)                   │
└─────────────────────────────────────────┘
```

## Service Accounts

| Account Name | Access Level | Used By |
|-------------|-------------|---------|
| `agent-readonly` | Read access to: `oldso`, `po`, `oldgrn`, `dn`, `oldinvoice`, `oldstock`, `pro`, `oldbom`, `move`, EBI reports | Supply Chain Analytics, Demand Forecasting, PO Recommendation, Excess Inventory |
| `agent-draft` | Read + draft-create for: `pro` (Item Master), `oldso` (Sales Order), `dn` (Delivery Note) | SKU & Parts Agent, CRA & Returns Agent |

## Core Functions

### 1. Authentication

```python
# Token request (Client Credentials Grant)
POST {m18_base_url}/jsf/rfws/oauth2/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={client_id}
&client_secret={client_secret}

# Response
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Token cache**: Store in memory with TTL = `expires_in - 60` (refresh 60 seconds early). Never write tokens to disk.

**Headers for all subsequent requests**:
```
Authorization: Bearer {access_token}
client_id: {client_id}
```

### 2. Entity Read

```python
def m18_read(menu_code: str, entity_id: int, be_id: int = None) -> dict:
    """Read a single entity by ID.

    Args:
        menu_code: M18 menu code (e.g., 'oldso', 'po', 'pro', 'dn')
        entity_id: Record ID
        be_id: Business entity ID (for multi-company queries)

    Returns:
        Normalized entity dict with standard field names

    Raises:
        M18NotFoundError: Entity does not exist
        M18AuthError: Token expired or insufficient permissions
        M18ServerError: M18 server error (500)
    """
    # GET /jsf/rfws/root/api/read/{menu_code}?id={entity_id}
```

### 3. Entity Search

```python
def m18_search(menu_code: str, filters: dict, be_id: int = None,
               page: int = 1, page_size: int = 100) -> list:
    """Search entities with filters.

    Args:
        menu_code: M18 menu code
        filters: Dict of field -> value conditions
        be_id: Business entity ID
        page, page_size: Pagination

    Returns:
        List of matching entity summaries (ID + key fields)

    Notes:
        - Uses GET /jsf/rfws/search/search?stSearch={menu_code}
        - Supports M18 search syntax for date ranges, wildcards
        - Always paginate; never request all records at once
    """
```

### 4. Stock Query

```python
def m18_stock_query(be_id: int, pro_id: int = None,
                     loc_id: int = None) -> dict:
    """Query inventory levels.

    Args:
        be_id: Business entity ID
        pro_id: Product/item ID (optional; omit for all items)
        loc_id: Location/warehouse ID (optional; omit for all locations)

    Returns:
        Dict with on_hand, allocated, available quantities by location

    Notes:
        - Uses GET /jsf/rfws/erp/trdg/stock/viewLocLvl/{beId}/{proId}
        - For multi-warehouse queries, iterate over locations
    """
```

### 5. Draft Creation (agent-draft account only)

```python
def m18_create_draft(menu_code: str, entity_data: dict,
                      be_code: str) -> dict:
    """Create a new entity in DRAFT/PENDING status.

    RESTRICTED: Only callable by agents using agent-draft account.
    Only allowed for: 'pro' (Item Master), 'oldso' (Sales Order), 'dn' (Delivery Note)

    Args:
        menu_code: Must be in ALLOWED_WRITE_ENTITIES
        entity_data: Dict of field values per M18 schema
        be_code: Business entity code (e.g., 'PGI')

    Returns:
        Created entity with assigned ID and DRAFT status

    Raises:
        M18PermissionError: Agent not authorized for write
        M18BsRuleError: Business rule validation failed (includes rule details)
        M18ValidationError: Required fields missing

    SAFETY:
        - NEVER sets status to APPROVED, CONFIRMED, or POSTED
        - NEVER modifies existing approved records
        - Logs every creation for audit trail
    """
    ALLOWED_WRITE_ENTITIES = {'pro', 'oldso', 'dn'}
    if menu_code not in ALLOWED_WRITE_ENTITIES:
        raise M18PermissionError(f"Write not permitted for {menu_code}")
```

### 6. EBI Report Query

```python
def m18_ebi_report(format_id: int, params: dict = None) -> dict:
    """Fetch pre-built EBI (Enterprise Business Intelligence) report.

    Args:
        format_id: M18 EBI report format ID
        params: Optional filter parameters

    Returns:
        Report data as structured dict

    Notes:
        - Uses GET /jsf/rfws/ebiWidget/loadReport?formatId={id}
        - Useful for aging reports, stock turn reports, sales summaries
        - Report format IDs must be documented by Jeff/Lynn
    """
```

## Error Handling

| HTTP Status | M18 Meaning | Connector Response |
|-------------|------------|-------------------|
| 200 | Success | Return normalized data |
| 400 | BsRule validation failure or bad request | Parse error details; return `M18BsRuleError` with specific rule that failed |
| 401 | Token expired or invalid | Auto-refresh token; retry once; if still 401, raise `M18AuthError` |
| 403 | Insufficient permissions | Raise `M18PermissionError`; log for Jeff Yu review |
| 404 | Entity not found | Raise `M18NotFoundError` |
| 429 | Rate limited | Exponential backoff (1s, 2s, 4s, 8s); max 4 retries; then raise `M18RateLimitError` |
| 500 | Server error | Retry 3x with backoff; then raise `M18ServerError`; alert Jeff Yu |
| Timeout | Network/server timeout | Retry 2x; then raise `M18TimeoutError` |

## Audit Logging

Every M18 API call is logged with:
- Timestamp
- Calling agent name
- Service account used (readonly vs draft)
- HTTP method + endpoint
- Entity type + ID (if applicable)
- Response status
- For WRITE operations: full request payload (redacted of sensitive fields)

Log location: `logs/m18-api-audit.jsonl`

Jeff Yu reviews audit logs weekly during initial deployment, monthly once stable.

## Configuration

```json
{
  "m18_base_url": "https://m18.company.com",
  "readonly_client_id": "${M18_READONLY_CLIENT_ID}",
  "readonly_client_secret": "${M18_READONLY_CLIENT_SECRET}",
  "draft_client_id": "${M18_DRAFT_CLIENT_ID}",
  "draft_client_secret": "${M18_DRAFT_CLIENT_SECRET}",
  "default_be_id": 1,
  "rate_limit_per_minute": 60,
  "token_refresh_buffer_seconds": 60,
  "max_retries": 3,
  "timeout_seconds": 30,
  "multi_company_be_ids": [1, 2, 3, 4, 5],
  "allowed_write_entities": ["pro", "oldso", "dn"],
  "audit_log_path": "logs/m18-api-audit.jsonl"
}
```

**CRITICAL**: Client secrets are stored as environment variables, never in code or configuration files checked into version control.

## Implementation Plan

| Step | Owner | Timeline | Dependencies |
|------|-------|----------|-------------|
| 1. Jeff Yu creates OAuth apps in M18 admin | Jeff Yu | Week 1, Day 1-2 | M18 admin access |
| 2. Jeff Yu tests token flow manually (curl) | Jeff Yu | Week 1, Day 2-3 | Step 1 |
| 3. Claude Code builds connector Python module | Claude Code + Jeff steering | Week 1, Day 3-5 | Step 2 |
| 4. Test read operations against production data | Jeff Yu validates | Week 2, Day 1-3 | Step 3 |
| 5. Test draft-create operations in M18 sandbox | Jeff Yu + Lynn validate | Week 2, Day 3-5 | Step 4 |
| 6. Document all custom BsRules per entity | Lynn Liu | Week 1-2 (parallel) | M18 system knowledge |
| 7. Deploy to production; enable for first agent | Jeff Yu | Week 3 | Steps 4-6 |

**Estimated build effort**: 2-3 Claude Code sessions + 4-6 hours Jeff Yu steering/validation.

## Cross-References

- Used by: `supply-chain-analytics-agent.md`, `demand-forecasting-agent.md`, `sku-parts-agent.md`, `cra-returns-agent.md`
- Validates against: `/mnt/d/workspace/atp-mc/reports/erp-validation.md`
- M18 API docs: https://m18doc.multiable.com/en/api/ce01/
- M18 web services: https://m18doc.multiable.com/en/wsdoc/

---

*This spec is a prerequisite for all ERP-domain agents. No ERP agent should be deployed until this connector is tested and validated by Jeff Yu against the production M18 instance.*
