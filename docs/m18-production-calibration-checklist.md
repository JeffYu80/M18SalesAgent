# M18 Production Calibration Checklist

## Purpose

This checklist is used before connecting the current architecture to a real
M18 environment such as UAT or production.

The goal is to confirm environment-specific values and structural differences
that cannot be safely assumed from generic documentation alone.

## How To Use

For each item below, record one of:

- confirmed
- needs validation
- not applicable

You can also note the actual value used in your environment.

## 1. Authentication Calibration

### 1.1 OAuth Endpoint

Confirm:

- token endpoint URL
- whether the environment uses `/oauth/token`
- whether request method is `GET` or `POST`
- whether password grant with SHA1 password is required

Record:

- base URL: `https://uat.smartecgr.com`
- token URL: `https://uat.smartecgr.com/jsf/rfws/oauth/token`
- method: `POST`
- grant type: `password`

### 1.2 Credential Storage

Confirm:

- where client ID is stored
- where client secret is stored
- where username is stored
- where password or SHA1 password is stored
- whether environment variables or YAML config will be used

Record:

- storage method: local YAML config
- config path: `config/m18_api_token.yaml`

### 1.3 Access Scope

Confirm:

- read-only account exists
- write-enabled draft account exists
- which objects each account can access

Record:

- readonly account:
- draft account:
- allowed objects:

## 2. Sales Quotation Object Calibration

### 2.1 Object Identity

Confirm:

- quotation menu code is `oldqu`
- main table is `mainqu`
- line table is `qut`
- remarks table is `remqu`

Record:

- menu code: `oldqu`
- main table: `mainqu`
- line table: `qut`
- remarks table: `remqu`

### 2.2 Write Path Rule

Confirm:

- `bsFlow/save/oldqu` works in your environment
- standard `save/oldqu` works in your environment
- both paths return the documented response structures

Record:

- bsFlow available: confirmed
- standard save available: confirmed
- bsFlow sample result: `tranId=42`, `tranCode=PUSPI26000004`, `status=true`
- standard save sample result: `recordId=43`, `status=true`

### 2.3 Required Header Fields

Confirm actual required quotation header fields for standard save.

Typical candidates:

- `beId`
- `cusId`
- `curId`
- `flowTypeId`
- `staffId`
- `tDate`
- `rate`

Record:

- required header fields: `beId`, `tDate`, `curId`, `cusId`, `rate`, `amt`, `flowTypeId`, `staffId`
- optional header fields: remarks and shipping-related fields can be omitted in the verified minimal path

### 2.4 Required Line Fields

Confirm actual required quotation line fields for standard save.

Typical candidates:

- `sourceType`
- `proId`
- `unitId`
- `qty`
- `up`
- `disc`
- `amt`

Record:

- required line fields: `sourceType`, `proId`, `qty`, `unitId`, `amt`, `disc`, `up`
- optional line fields: `locId` and many descriptive fields are optional in the verified minimal path
- **Corrected rule (2026-07-31)**: `qut.unitId` MUST be the matching product `price.id`; it must not be `proId` or global `unit.id`.
- **Products verified**: PGD798MB (proId=497), ABBL-US-CFP56030A-V1 (proId=594), ADG1301200000 (proId=371), AX3R-US-CFP56020A-V1 (proId=599)

## 3. Customer Object Calibration

### 3.1 Customer Identity

Confirm:

- customer menu code is `cus`
- search path works with `stSearch=cus`
- read path works with `read/cus`

Record:

- menu code: `cus`
- search works: confirmed for `beId=7`
- read works: confirmed

### 3.2 Customer Search Row Shape

Confirm which fields are actually returned by customer search.

Typical candidates:

- `id`
- `code`
- `desc`
- `desc__lang`
- `lastModifyDate`

Record:

- returned fields: `id`, `code`, `desc__lang`, `lastModifyDate`, `tel`, `st_desc`, `st_id`, `st_code`
- preferred display field: `desc__lang`

## 4. Customer Contact Calibration

This is one of the most important environment-specific checks.

### 4.1 Contact Source Type

Confirm whether customer contacts are stored as:

- a child table inside customer read payload
- a separate object
- a separate lookup endpoint

Record:

- contact storage model: child table inside customer read payload under `data`

### 4.2 Contact Table Name

If contacts are in a child table, confirm the real table name.

Current code checks these candidates:

- `contact`
- `contactt`
- `cuscontact`
- `cuscont`
- `cont`
- `ocf`

Record:

- actual contact table name: `data.cust`
- candidate list sufficient: yes

### 4.3 Contact Field Names

Confirm the actual contact row fields.

Typical candidates:

- name
- code
- phone
- email
- department
- position

Record:

- actual contact fields: `code`, `man`, `position`, `tel`, `fax`, `email`, `whatsappNo`, `default`, `expired`
- preferred display fields: `man`, `position`, `tel`, `email`

## 5. Reference Resolver Calibration

### 5.1 Customer Resolution

Confirm:

- customer code is unique within the selected `beId`
- `quickSearchStr` is enough to find exact customer matches
- exact `code` comparison works reliably

Record:

- uniqueness rule: exact customer code match works within `beId=7`
- exact match behavior: confirmed

### 5.2 Product Resolution

Confirm:

- product search should use `stSearch=pro`
- returned rows include `id` and `code`
- exact `proCode` match works reliably

Record:

- menu code: `pro`
- exact match behavior: confirmed for `PGD798MB -> proId=497`

### 5.3 Unit Resolution

Confirm the real unit lookup strategy.

This is currently the least certain part of the implementation.

Current code originally assumed:

- `search_by_code("unit", code)`

You must confirm:

- actual unit object or table name
- whether a generic code lookup works
- whether unit belongs to another object or child structure

Record:

- real unit lookup object/table: `unit` can resolve `PCS -> id=1` at the master-data level
- current implementation valid: partially
- replacement completed: standard quotation `qut.unitId` resolves to the matching product `price.id`.
- **Calibrated 2026-05-09**: `pro_id` strategy confirmed for all 4 tested products; `unit_master` strategy fails with `core_201` "unit already used"
- **Rule corrected**: `qut.unitId` and `sot.unitId` must equal the matching product `price.id` for standard save.
- **Superseded 2026-07-31**: do not use `pro_id` or `unit_master`; standard
  sales lines resolve `unitId` to the product's matching `price.id`.

## 6. Quotation Defaults And Reference Values

### 6.1 Business Entity Values

Confirm:

- valid `beId`
- valid `beCode`

Record:

- default `beId`: `7`
- default `beCode`: `PUS`

### 6.2 Currency

Confirm:

- default `curId`
- whether `bsFlow` auto-fills currency
- whether standard save requires explicit currency

Record:

- default `curId`: `3`
- auto-fill behavior: draft create worked without explicit `curId`; standard save used explicit `curId=3`

For production, also confirm:

- every `beId` has its entity/base `curId` recorded in `entity_currency_by_be_id`
- the M18 rate policy uses `openRate` or `closeRate` as required by Finance
- a foreign-currency customer returns a positive rate through `getRate` for the transaction date
- a quotation-to-order flow preserves `curId` and refreshes `rate` from M18
  using the order document date

### 6.3 Flow Type

Confirm:

- valid quotation `flowTypeId`
- whether it is required on standard save

Record:

- default `flowTypeId`: `5`
- required: yes for the verified standard save path

### 6.4 Staff

Confirm:

- valid `staffId`
- whether `bsFlow` auto-fills staff
- whether standard save requires explicit staff

Record:

- default `staffId`: `197` (removed — staffCode is now required)
- auto-fill behavior: draft create failed until `staffId` was supplied explicitly in this UAT
- **Updated 2026-05-09**: `staffCode` is now **required**. User must provide `staffCode` (e.g. `000001`), and system resolves it to `staffId` via `stSearch=staff`. No default staffId is injected.

## 7. Error Handling Calibration

Confirm how your environment returns errors:

- HTTP 400 + body
- HTTP 400 + `error_info` header
- HTTP 200 with `status=false`
- mixed behavior by endpoint

Record:

- validation error pattern: both `status=false` business messages and structured message JSON were observed
- not-found error pattern: `status=false` with `messages`
- auth error pattern: token endpoint failure would surface as auth exception; token acquisition is confirmed working

## 8. Logging And Audit Calibration

Confirm:

- whether audit logging is required
- what fields must be masked
- where logs should be stored

Record:

- logging required:
- mask fields:
- log path:

## 9. Sample Real Records For Validation

Prepare a safe validation set:

- one valid customer code
- one valid product code
- one valid unit code
- one valid quotation ID
- one customer that has contacts

Record:

- sample customer code: `320`
- sample product code: `PGD798MB`
- sample unit code: `PCS`
- sample quotation ID: `37`, `40`, `41`, `43`
- sample customer with contacts: `320`

## 10. Go-Live Readiness

The current implementation is ready for real integration only when all items
below are confirmed:

- authentication method confirmed
- quotation object fields confirmed
- customer search fields confirmed
- customer contact source confirmed
- unit lookup confirmed
- required default IDs confirmed
- error patterns confirmed
- at least one end-to-end example runs successfully in UAT

## 11. Sales Order Calibration

### 11.1 Object Identity

Confirm:

- sales order menu code is `oldso`
- main table is `mainso`
- line table is `sot`
- remarks table is `remso`

Record:

- menu code: `oldso`
- main table: `mainso`
- line table: `sot`
- remarks table: `remso`

### 11.2 Write Path Rule

Confirm:

- `bsFlow/save/oldso` works in your environment
- standard `save/oldso` works in your environment

Record:

- bsFlow available: confirmed
- standard save available: confirmed
- bsFlow sample result: `tranId=9581`, `tranCode=PUSSO26000040`, `status=true`
- standard save sample result: `recordId=9582`, `status=true`

### 11.3 Verified Header Defaults

Record:

- default `beId`: `7`
- default `curId`: `3`
- default `flowTypeId`: `5`
- default `staffId`: `197`
- verified customer: `cusId=24` for `cusCode=320`

### 11.4 Verified Line Defaults

Record:

- verified product: `proId=497` for `proCode=PGD798MB`
- historical calibration value only; standard-save `unitId` must instead be
  resolved to the product's matching `price.id`.
- verified business `unitCode`: `PCS`
- current rule: standard `sot.unitId` follows the same environment strategy as quotation
- **Corrected 2026-07-31**: both quotation and order use the `product_price` strategy, resolving `unitId` to `price.id`.

## 12. Customer Part Report Calibration

### 12.1 EBI Report Identity

Confirm:

- the customer-part lookup report exists
- the correct format ID is used
- the report is available to the integration account

Record:

- report format ID: `102`
- report code: `Jeff-CustomerPartAPI`
- report description: `客户料号列表`
- availability: confirmed in UAT

### 12.2 Verified Field Mapping

Confirm the report fields used for customer-part lookup.

Record:

- customer code field: `CUS_A_code`
- customer ID field: `CUS_A_id`
- customer name field: `CUS_A_desc__lang`
- product code field: `PRO_A_code`
- product ID field: `PRO_A_id`
- product name field: `PRO_A_desc__lang`
- customer part code field: `F_A_refCode`

### 12.3 Verified Sample Row

Record:

- sample customer code: `320`
- sample product code: `PGD798MB`
- sample customer part code: `ABC798`
- sample row count after filtering: `1`
