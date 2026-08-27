import time

import httpx

from .config import settings
from .local_store import LocalStore

class CaseStore:
    def __init__(self):
        self.local = LocalStore()
        self._tenant_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def enabled(self) -> bool:
        return all(
            [
                settings.feishu_app_id,
                settings.feishu_app_secret,
                settings.feishu_app_token,
                settings.feishu_case_table_id,
            ]
        )

    async def _token(self) -> str:
        if self._tenant_token and time.monotonic() < self._token_expires_at:
            return self._tenant_token

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": settings.feishu_app_id,
                    "app_secret": settings.feishu_app_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {data}")

        self._tenant_token = data["tenant_access_token"]
        expires_in = int(data.get("expire", 7200))
        self._token_expires_at = time.monotonic() + max(60, expires_in - 60)
        return self._tenant_token

    async def create_case(self, fields: dict) -> str:
        if not self.enabled:
            return self.local.create_case(fields)

        token = await self._token()
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{settings.feishu_app_token}/tables/{settings.feishu_case_table_id}/records"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"fields": fields},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Feishu create record failed: {data}")
        return data["data"]["record"]["record_id"]

    async def update_case(self, record_id: str | None, fields: dict) -> None:
        if not record_id:
            return
        if not self.enabled or record_id.startswith("local_"):
            self.local.update_case(record_id, fields)
            return

        token = await self._token()
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{settings.feishu_app_token}/tables/{settings.feishu_case_table_id}/records/{record_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"fields": fields},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Feishu update record failed: {data}")

    async def list_cases(self, lesson_id: int) -> list[dict]:
        if not self.enabled:
            return self.local.list_cases(lesson_id)

        token = await self._token()
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{settings.feishu_app_token}/tables/{settings.feishu_case_table_id}/records"
        )

        items: list[dict] = []
        page_token: str | None = None
        async with httpx.AsyncClient(timeout=45) as client:
            while True:
                params = {"page_size": 500}
                if page_token:
                    params["page_token"] = page_token
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("code") != 0:
                    raise RuntimeError(f"Feishu list records failed: {data}")

                for item in data.get("data", {}).get("items", []):
                    row = {"record_id": item.get("record_id"), **item.get("fields", {})}
                    if str(row.get("课次")) == str(lesson_id):
                        items.append(row)

                if not data.get("data", {}).get("has_more"):
                    break
                page_token = data["data"].get("page_token")

        return items

    async def save_report(self, fields: dict) -> str | None:
        if not self.enabled:
            return self.local.save_report(fields)
        if not settings.feishu_report_table_id:
            raise RuntimeError("FEISHU_REPORT_TABLE_ID is required to save lesson reports")

        token = await self._token()
        url = (
            "https://open.feishu.cn/open-apis/bitable/v1/apps/"
            f"{settings.feishu_app_token}/tables/{settings.feishu_report_table_id}/records"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"fields": fields},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Feishu save report failed: {data}")
        return data["data"]["record"]["record_id"]
