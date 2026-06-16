"""
M18 ERP API Connector
=====================
Reusable Python module for all agents interacting with the Multiable M18 ERP system.
Handles OAuth 2.0 authentication, SqlEntity CRUD, search, inventory, pricing,
EBI report extraction, and structured error handling.

Usage:
    from m18_api import M18Client
    client = M18Client()  # reads credentials from config/m18.{env}.yaml
    token = client.get_token()
    result = client.read_entity("oldso", 123)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
import yaml

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("m18_api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Module Constants — MenuCode / Table mappings
# ---------------------------------------------------------------------------

# Sales
MENU_SALES_QUOTATION = "oldqu"
TABLE_SALES_QUOTATION_MAIN = "mainqu"
TABLE_SALES_QUOTATION_LINE = "qut"

MENU_SALES_ORDER = "oldso"
TABLE_SALES_ORDER_MAIN = "mainso"
TABLE_SALES_ORDER_LINE = "sot"

MENU_CUSTOMER_SHIPMENT = "aso"
TABLE_CUSTOMER_SHIPMENT_MAIN = "mainaso"
TABLE_CUSTOMER_SHIPMENT_LINE = "asot"

MENU_DELIVERY_NOTE = "dn"
TABLE_DELIVERY_NOTE_MAIN = "maindn"
TABLE_DELIVERY_NOTE_LINE = "dnt"

MENU_SALES_INVOICE = "si"
TABLE_SALES_INVOICE_MAIN = "mainsi"
TABLE_SALES_INVOICE_LINE = "sit"

# Purchase
MENU_PURCHASE_QUOTATION = "vqu"
TABLE_PURCHASE_QUOTATION_MAIN = "mainvqu"
TABLE_PURCHASE_QUOTATION_LINE = "vqut"

MENU_PURCHASE_ORDER = "po"
TABLE_PURCHASE_ORDER_MAIN = "mainpo"
TABLE_PURCHASE_ORDER_LINE = "pot"

MENU_VENDOR_SHIPMENT = "asi"
TABLE_VENDOR_SHIPMENT_MAIN = "mainasi"
TABLE_VENDOR_SHIPMENT_LINE = "asit"

MENU_GOODS_RECEIPT = "an"
TABLE_GOODS_RECEIPT_MAIN = "mainan"
TABLE_GOODS_RECEIPT_LINE = "ant"

MENU_PURCHASE_RETURN = "pr"
TABLE_PURCHASE_RETURN_MAIN = "mainpr"
TABLE_PURCHASE_RETURN_LINE = "prt"

MENU_PURCHASE_INVOICE = "pi"
TABLE_PURCHASE_INVOICE_MAIN = "mainpi"
TABLE_PURCHASE_INVOICE_LINE = "pit"

# Stock
MENU_OPENING_STOCK = "os"
TABLE_OPENING_STOCK_MAIN = "mainos"
TABLE_OPENING_STOCK_LINE = "ost"

MENU_STOCK_ADJUSTMENT = "k"
TABLE_STOCK_ADJUSTMENT_MAIN = "maink"
TABLE_STOCK_ADJUSTMENT_LINE = "kt"

MENU_INTERNAL_TRANSFER = "move"
TABLE_INTERNAL_TRANSFER_MAIN = "mainmove"
TABLE_INTERNAL_TRANSFER_LINE = "movet"

MENU_DEFECTIVE_STOCK = "defstkreg"
TABLE_DEFECTIVE_STOCK_MAIN = "maindefstkreg"
TABLE_DEFECTIVE_STOCK_LINE = "defstkregt"

MENU_DEFECT_WRITEOFF = "dstn"
TABLE_DEFECT_WRITEOFF_MAIN = "maindstn"
TABLE_DEFECT_WRITEOFF_LINE = "dstnt"

# Item Master
MENU_PRODUCT = "pro"

# Convenience lookup: menuCode -> (mainTable, lineTable)
MENU_TABLE_MAP: Dict[str, tuple] = {
    "oldqu": ("mainqu", "qut"),
    "oldso": ("mainso", "sot"),
    "aso": ("mainaso", "asot"),
    "dn": ("maindn", "dnt"),
    "si": ("mainsi", "sit"),
    "vqu": ("mainvqu", "vqut"),
    "po": ("mainpo", "pot"),
    "asi": ("mainasi", "asit"),
    "an": ("mainan", "ant"),
    "pr": ("mainpr", "prt"),
    "pi": ("mainpi", "pit"),
    "os": ("mainos", "ost"),
    "k": ("maink", "kt"),
    "move": ("mainmove", "movet"),
    "defstkreg": ("maindefstkreg", "defstkregt"),
    "dstn": ("maindstn", "dstnt"),
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class M18APIError(Exception):
    """Base exception for M18 API errors."""

    def __init__(self, message: str, status_code: int = 0, raw_response: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.raw_response = raw_response


class M18AuthError(M18APIError):
    """Authentication / token errors (401, 403)."""
    pass


class M18ValidationError(M18APIError):
    """BsRule validation failure (400) — contains parsed CheckMsg details."""

    def __init__(self, message: str, check_messages: List[Dict], **kwargs):
        super().__init__(message, **kwargs)
        self.check_messages = check_messages


class M18NotFoundError(M18APIError):
    """Entity not found (404)."""
    pass


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class M18Client:
    """Multiable M18 ERP REST API client."""

    # Token buffer — refresh this many seconds before actual expiry
    TOKEN_REFRESH_BUFFER_SECONDS = 120

    # Retry settings for 5xx errors
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2  # seconds

    def __init__(self, config_path: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialise the client by loading app credentials from a YAML config file.

        Config loaded from config/m18.{env}.yaml where env defaults to "uat".
        Set M18_ENV env var to switch environments (e.g. M18_ENV=prod).

        Args:
            config_path: Explicit path (highest priority, overrides env).
            username: M18 login username (required).
            password: M18 login plain-text password (required, converted to SHA1).
        """
        if config_path is None:
            project_root = Path(__file__).resolve().parent
            env = os.environ.get("M18_ENV", "uat")
            env_path = project_root / "config" / f"m18.{env}.yaml"
            config_path = str(env_path) if env_path.exists() else str(project_root / "config" / "m18.uat.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.client_id: str = cfg["client_id"]
        self.client_secret: str = cfg["client_secret"]

        resolved_username = username or cfg.get("username") or os.environ.get("M18_USERNAME")
        resolved_password = password or cfg.get("password") or os.environ.get("M18_PASSWORD")
        resolved_password_sha1 = cfg.get("password_sha1") or os.environ.get("M18_PASSWORD_SHA1")
        if not resolved_username:
            raise ValueError("username is required for M18Client")
        if not resolved_password and not resolved_password_sha1:
            raise ValueError("password or password_sha1 is required for M18Client")

        self.username: str = resolved_username
        self.password_sha1: str = (
            resolved_password_sha1
            if resolved_password_sha1
            else hashlib.sha1(str(resolved_password).encode("utf-8")).hexdigest()
        )
        self.token_method: str = str(cfg.get("token_method", "POST")).upper()

        # Base URLs — the token URL from config ends with '?', strip it
        token_url_raw: str = cfg["url"]
        self.token_url: str = token_url_raw.rstrip("?")

        # Derive the API base from the token URL
        # Token URL: https://uat.smartecgr.com/jsf/rfws/oauth/token
        # API base:  https://uat.smartecgr.com/jsf/rfws
        if "/oauth/token" in self.token_url:
            self.api_base = self.token_url.rsplit("/oauth/token", 1)[0]
        elif "/oauth2/token" in self.token_url:
            self.api_base = self.token_url.rsplit("/oauth2/token", 1)[0]
        else:
            raise ValueError(
                "Token URL must contain '/oauth/token' or '/oauth2/token' so the API base can be derived."
            )

        # Token state
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0  # epoch timestamp

        # Requests session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

        logger.info("M18Client initialised — API base: %s", self.api_base)

    # ------------------------------------------------------------------
    # 1. OAuth Token Management
    # ------------------------------------------------------------------

    def get_token(self) -> Dict[str, str]:
        """
        Obtain or refresh the OAuth bearer token.

        Returns:
            dict with ``authorization`` and ``client_id`` headers ready to
            be merged into any request.
        """
        if self._access_token and time.time() < self._token_expiry:
            return self._auth_headers()

        logger.info("Requesting new OAuth token from %s", self.token_url)

        params = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password_sha1,
        }

        if self.token_method == "GET":
            resp = self._session.get(self.token_url, params=params, timeout=30)
        else:
            resp = self._session.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=params,
                timeout=30,
            )

        if resp.status_code != 200:
            raise M18AuthError(
                f"Token request failed [{resp.status_code}]: {resp.text}",
                status_code=resp.status_code,
                raw_response=resp.text,
            )

        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = time.time() + expires_in - self.TOKEN_REFRESH_BUFFER_SECONDS

        logger.info(
            "Token obtained — expires in %d s (refresh at %d s before expiry)",
            expires_in,
            self.TOKEN_REFRESH_BUFFER_SECONDS,
        )
        return self._auth_headers()

    def _auth_headers(self) -> Dict[str, str]:
        """Return auth headers dict."""
        return {
            "authorization": f"Bearer {self._access_token}",
            "client_id": self.client_id,
        }

    def _ensure_token(self) -> Dict[str, str]:
        """Get token, refreshing if needed."""
        return self.get_token()

    # ------------------------------------------------------------------
    # Internal request helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_body: Optional[Any] = None,
        retries: int = 0,
    ) -> requests.Response:
        """
        Send an authenticated request with retry and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: URL path relative to api_base (e.g. "/root/api/read/oldso").
            params: Query parameters.
            json_body: JSON request body.
            retries: Current retry count (internal).

        Returns:
            requests.Response on success.

        Raises:
            M18AuthError, M18ValidationError, M18NotFoundError, M18APIError
        """
        url = f"{self.api_base}{path}"
        headers = self._ensure_token()
        headers["Content-Type"] = "application/json"

        logger.debug("%s %s params=%s", method, url, params)

        resp = self._session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=60,
        )

        # --- Error handling ---
        if resp.status_code == 200:
            return resp

        if resp.status_code == 401:
            if retries < 1:
                logger.warning("401 — refreshing token and retrying")
                self._access_token = None  # force refresh
                return self._request(method, path, params, json_body, retries + 1)
            raise M18AuthError(
                "Authentication failed after token refresh",
                status_code=401,
                raw_response=resp.text,
            )

        if resp.status_code == 400:
            check_messages = self._parse_check_messages(resp)
            human_msg = self._format_check_messages(check_messages)
            raise M18ValidationError(
                f"Validation error: {human_msg}",
                check_messages=check_messages,
                status_code=400,
                raw_response=resp.text,
            )

        if resp.status_code == 403:
            raise M18AuthError(
                f"Insufficient permissions: {resp.text}",
                status_code=403,
                raw_response=resp.text,
            )

        if resp.status_code == 404:
            raise M18NotFoundError(
                f"Entity not found: {path}",
                status_code=404,
                raw_response=resp.text,
            )

        if resp.status_code >= 500:
            if retries < self.MAX_RETRIES:
                wait = self.RETRY_BACKOFF_BASE ** (retries + 1)
                logger.warning(
                    "Server error %d — retry %d/%d in %ds",
                    resp.status_code, retries + 1, self.MAX_RETRIES, wait,
                )
                time.sleep(wait)
                return self._request(method, path, params, json_body, retries + 1)
            raise M18APIError(
                f"Server error after {self.MAX_RETRIES} retries: {resp.text}",
                status_code=resp.status_code,
                raw_response=resp.text,
            )

        raise M18APIError(
            f"Unexpected status {resp.status_code}: {resp.text}",
            status_code=resp.status_code,
            raw_response=resp.text,
        )

    # ------------------------------------------------------------------
    # CheckMsg parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_check_messages(resp: requests.Response) -> List[Dict]:
        """Extract CheckMsg array from error_info header or response body."""
        # Try header first
        error_info = resp.headers.get("error_info", "")
        if error_info:
            try:
                parsed = json.loads(error_info)
                if isinstance(parsed, dict) and "messages" in parsed:
                    return parsed["messages"]
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Try response body
        try:
            body = resp.json()
            if isinstance(body, dict):
                if "messages" in body:
                    return body["messages"]
                if "info" in body and isinstance(body["info"], list):
                    return body["info"]
        except (json.JSONDecodeError, ValueError):
            pass

        return [{"msgType": "error", "msgDesc": resp.text[:500]}]

    @staticmethod
    def _format_check_messages(messages: List[Dict]) -> str:
        """Convert CheckMsg list to human-readable string."""
        parts = []
        for msg in messages:
            msg_type = msg.get("msgType", "error")
            msg_desc = msg.get("msgDesc", msg.get("msg", str(msg)))
            parts.append(f"[{msg_type}] {msg_desc}")
        return "; ".join(parts) if parts else "Unknown validation error"

    # ------------------------------------------------------------------
    # 2. Core CRUD Operations
    # ------------------------------------------------------------------

    def read_entity(self, menu_code: str, record_id: int, irev: Optional[int] = None) -> Dict:
        """
        Read an entity by ID.

        Args:
            menu_code: M18 menu code (e.g. "oldso", "po", "pro").
            record_id: The record ID to read.
            irev: Optional revision number for historical versions.

        Returns:
            Parsed JSON response dict containing entity data.

        Raises:
            M18NotFoundError: If the entity does not exist (M18 returns 200
                with ``status: false`` for missing records).
        """
        params: Dict[str, Any] = {"menuCode": menu_code, "id": record_id}
        if irev is not None:
            params["iRev"] = irev

        resp = self._request("GET", f"/root/api/read/{menu_code}", params=params)
        result = resp.json()

        # M18 returns HTTP 200 with {"status": false} for missing records
        if isinstance(result, dict) and result.get("status") is False:
            msgs = result.get("messages", [])
            detail = msgs[0].get("msgDetail", str(msgs)) if msgs else "Record not found"
            raise M18NotFoundError(
                f"Entity {menu_code} id={record_id} not found: {detail}",
                status_code=200,
                raw_response=json.dumps(result, ensure_ascii=False),
            )

        return result

    def search_entities(
        self,
        menu_code: str,
        be_id: Optional[int] = None,
        start_row: int = 0,
        end_row: int = 100,
        format_id: Optional[int] = None,
        quick_search: Optional[str] = None,
    ) -> Dict:
        """
        Search / list entities.

        Args:
            menu_code: The stSearch lookup type (same as menuCode in most cases).
            be_id: Business Entity ID to filter by.
            start_row: Pagination start (0-based).
            end_row: Pagination end.
            format_id: Optional Lookup Query ID.
            quick_search: Optional quick search text.

        Returns:
            Parsed JSON with search results.
        """
        params: Dict[str, Any] = {
            "stSearch": menu_code,
            "startRow": start_row,
            "endRow": end_row,
        }
        if be_id is not None:
            params["beId"] = be_id
        if format_id is not None:
            params["formatId"] = format_id
        if quick_search is not None:
            params["quickSearchStr"] = quick_search

        resp = self._request("GET", "/search/search", params=params)
        return resp.json()

    def create_entity_template(self, menu_code: str) -> Dict:
        """
        Get an empty entity structure (template) for a given menu code.

        Args:
            menu_code: M18 menu code.

        Returns:
            Parsed JSON with empty entity structure.
        """
        resp = self._request("POST", f"/entity/create/{menu_code}")
        return resp.json()

    def save_entity(self, menu_code: str, data: Dict) -> Dict:
        """
        Create a new entity using the standard SqlEntity pattern.

        The data dict should follow M18's nested structure, e.g.::

            {
                "mainso": {"values": [{"beId": 304, "tDate": "2022-03-30", "cusId": 1}]},
                "sot": {"values": [{"proId": 4197, "qty": 1, "unitId": 39151}]}
            }

        Args:
            menu_code: M18 menu code.
            data: Entity data in M18 format.

        Returns:
            Parsed JSON with recordId, status, messages.
        """
        logger.info("SAVE %s — data keys: %s", menu_code, list(data.keys()))
        resp = self._request(
            "PUT",
            f"/root/api/save/{menu_code}",
            params={"menuCode": menu_code},
            json_body=data,
        )
        result = resp.json()
        logger.info(
            "SAVE %s — result: recordId=%s status=%s",
            menu_code,
            result.get("recordId"),
            result.get("status"),
        )
        return result

    def save_entity_auto(self, menu_code: str, data: Dict) -> Dict:
        """
        Auto-completion create via bsFlow — accepts codes instead of IDs.

        The data dict uses code-based fields, e.g.::

            {
                "beCode": "CAT2019",
                "cusCode": "C001",
                "sot": [{"proCode": "PRO001", "unitCode": "PCS", "qty": 1, "up": 10}]
            }

        Args:
            menu_code: M18 menu code.
            data: Entity data with code-based fields.

        Returns:
            Dict with tranId, tranCode, status.
        """
        logger.info("BSFLOW SAVE %s — data keys: %s", menu_code, list(data.keys()))
        resp = self._request("POST", f"/erp/bsFlow/save/{menu_code}", json_body=data)
        result = resp.json()
        logger.info(
            "BSFLOW SAVE %s — result: tranId=%s tranCode=%s status=%s",
            menu_code,
            result.get("tranId"),
            result.get("tranCode"),
            result.get("status"),
        )
        return result

    def delete_entity(self, menu_code: str, record_id: int) -> Dict:
        """
        Delete is NOT supported in this system.

        Args:
            menu_code: M18 menu code.
            record_id: The record ID to delete.

        Raises:
            M18APIError: Always raised — delete is disabled.
        """
        raise M18APIError(
            f"Delete not allowed: this system is create-only. "
            f"Cannot delete {menu_code} id={record_id}."
        )
        return resp.json()

    # ------------------------------------------------------------------
    # 3. Specialized Queries
    # ------------------------------------------------------------------

    def get_inventory(self, be_id: int, product_id: int) -> Dict:
        """
        Get location-level inventory for a product.

        Args:
            be_id: Business Entity ID.
            product_id: Product (Item) ID.

        Returns:
            Inventory data by location.
        """
        resp = self._request("GET", f"/erp/trdg/stock/viewLocLvl/{be_id}/{product_id}")
        return resp.json()

    def get_pricing(
        self,
        be_id: int,
        cus_id: Optional[int] = None,
        pro_ids: Optional[List[int]] = None,
        **extra_params,
    ) -> Dict:
        """
        Multi-product pricing lookup.

        Args:
            be_id: Business Entity ID.
            cus_id: Customer ID (for customer-specific pricing).
            pro_ids: List of product IDs.
            **extra_params: Additional query parameters.

        Returns:
            Pricing data.
        """
        params: Dict[str, Any] = {"beId": be_id}
        if cus_id is not None:
            params["cusId"] = cus_id
        if pro_ids is not None:
            params["proIds"] = ",".join(str(p) for p in pro_ids)
        params.update(extra_params)

        resp = self._request("GET", "/erp/trdg/price/multiPro", params=params)
        return resp.json()

    def get_ebi_report(
        self,
        report_id: int,
        be_id: Optional[int] = None,
        offset: int = 0,
        rows: int = 1000,
    ) -> Dict:
        """
        Extract an EBI report by format ID.

        Args:
            report_id: The EBI format/report ID.
            be_id: Optional Business Entity filter.
            offset: Pagination start.
            rows: Number of rows to fetch.

        Returns:
            Report data with size and rows.
        """
        params: Dict[str, Any] = {
            "formatId": report_id,
            "offset": offset,
            "rows": rows,
        }
        if be_id is not None:
            params["beId"] = be_id

        resp = self._request("GET", "/ebiWidget/loadReport", params=params)
        return resp.json()

    def list_ebi_reports(
        self,
        format_type: str = "ebiFormat",
        search_text: Optional[str] = None,
        offset: int = 0,
        rows: int = 50,
    ) -> Dict:
        """
        List available EBI report formats.

        Args:
            format_type: One of 'ebiFormat', 'chart', 'pivot'.
            search_text: Optional keyword filter.
            offset: Pagination start.
            rows: Number of results.

        Returns:
            List of available report formats.
        """
        params: Dict[str, Any] = {
            "formatType": format_type,
            "offset": offset,
            "rows": rows,
        }
        if search_text:
            params["searchText"] = search_text

        resp = self._request("GET", "/ebiWidget/reportList", params=params)
        return resp.json()

    # ------------------------------------------------------------------
    # Additional search helpers
    # ------------------------------------------------------------------

    def search_by_code(self, table_name: str, code: str) -> Dict:
        """
        Look up a record by its code in a specific table.

        Args:
            table_name: Database table name (e.g. "mainso", "mainpo").
            code: The record code to search for.

        Returns:
            Matching record data.
        """
        resp = self._request("GET", f"/erp/search/code/{table_name}/{code}")
        return resp.json()

    def search_by_id(self, table_name: str, record_id: int) -> Dict:
        """
        Look up a record by its ID in a specific table.

        Args:
            table_name: Database table name.
            record_id: The record ID.

        Returns:
            Matching record data.
        """
        resp = self._request("GET", f"/erp/search/id/{table_name}/{record_id}")
        return resp.json()

    def search_by_condition(self, table_name: str, condition: str) -> Dict:
        """
        Search a table using a SQL-like condition string.

        Args:
            table_name: Database table name.
            condition: SQL WHERE condition (e.g. "status='Y' AND beId=304").

        Returns:
            Matching records.
        """
        resp = self._request(
            "GET",
            f"/erp/search/cond/{table_name}",
            params={"cond": condition},
        )
        return resp.json()


# ---------------------------------------------------------------------------
# Convenience — module-level functions for simple scripting
# ---------------------------------------------------------------------------

_default_client: Optional[M18Client] = None


def _get_client() -> M18Client:
    global _default_client
    if _default_client is None:
        _default_client = M18Client()
    return _default_client


def get_token() -> Dict[str, str]:
    """Obtain bearer token headers using default config."""
    return _get_client().get_token()


def read_entity(menu_code: str, record_id: int, **kwargs) -> Dict:
    """Read entity via default client."""
    return _get_client().read_entity(menu_code, record_id, **kwargs)


def search_entities(menu_code: str, **kwargs) -> Dict:
    """Search entities via default client."""
    return _get_client().search_entities(menu_code, **kwargs)


def create_entity_template(menu_code: str) -> Dict:
    """Get empty entity template via default client."""
    return _get_client().create_entity_template(menu_code)


def save_entity(menu_code: str, data: Dict) -> Dict:
    """Save entity via default client."""
    return _get_client().save_entity(menu_code, data)


def save_entity_auto(menu_code: str, data: Dict) -> Dict:
    """Auto-completion save via default client."""
    return _get_client().save_entity_auto(menu_code, data)


def delete_entity(menu_code: str, record_id: int) -> Dict:
    """Delete entity via default client."""
    return _get_client().delete_entity(menu_code, record_id)


def get_inventory(be_id: int, product_id: int) -> Dict:
    """Get inventory via default client."""
    return _get_client().get_inventory(be_id, product_id)


def get_pricing(params: Dict) -> Dict:
    """Get pricing via default client."""
    return _get_client().get_pricing(**params)


def get_ebi_report(report_id: int, **kwargs) -> Dict:
    """Get EBI report via default client."""
    return _get_client().get_ebi_report(report_id, **kwargs)
