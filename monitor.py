import asyncio
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp


@dataclass
class CheckResult:
    url: str
    status: str
    icon: str
    result: str
    ssl_days: int | None


def normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url

    return f"https://{url}"


def extract_domain(url: str) -> str:
    url = url.replace("https://", "").replace("http://", "")
    return url.split("/")[0]


def status_to_icon(status: str) -> str:
    if status == "UP":
        return "🟢"

    if status.startswith("HTTP 4"):
        return "🟠"

    return "🔴"


def check_ssl_expiry(url: str) -> int | None:
    try:
        domain = extract_domain(url)

        context = ssl.create_default_context()

        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        expires_str = cert["notAfter"]

        expires_date = datetime.strptime(
            expires_str,
            "%b %d %H:%M:%S %Y %Z"
        ).replace(tzinfo=timezone.utc)

        return (expires_date - datetime.now(timezone.utc)).days

    except Exception:
        return None


async def check_site(session: aiohttp.ClientSession, url: str) -> CheckResult:
    full_url = normalize_url(url)

    try:
        start = time.time()

        async with session.get(
            full_url,
            timeout=aiohttp.ClientTimeout(total=10),
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"}
        ) as response:
            elapsed = round((time.time() - start) * 1000)
            code = response.status

            if code < 400:
                status = "UP"

                if elapsed > 3000:
                    icon = "🟡"
                else:
                    icon = "🟢"

                result = f"HTTP {code} — {elapsed}ms"

            elif code < 500:
                status = f"HTTP {code}"
                icon = "🟠"
                result = f"HTTP {code} — {elapsed}ms"

            else:
                status = f"HTTP {code}"
                icon = "🔴"
                result = f"HTTP {code} — {elapsed}ms"

            ssl_days = check_ssl_expiry(url) if status == "UP" else None

            return CheckResult(url, status, icon, result, ssl_days)

    except asyncio.TimeoutError:
        return CheckResult(url, "TIMEOUT", "🔴", "timeout", None)

    except aiohttp.ClientConnectorCertificateError:
        return CheckResult(url, "SSL ERROR", "🔴", "ssl error", None)

    except aiohttp.ClientConnectorError:
        return CheckResult(url, "CONNECTION ERROR", "🔴", "dns/connection error", None)

    except aiohttp.InvalidURL:
        return CheckResult(url, "INVALID URL", "🔴", "invalid url", None)

    except aiohttp.TooManyRedirects:
        return CheckResult(url, "TOO MANY REDIRECTS", "🔴", "too many redirects", None)

    except aiohttp.ClientError:
        return CheckResult(url, "CLIENT ERROR", "🔴", "client error", None)

    except Exception:
        return CheckResult(url, "UNKNOWN ERROR", "🔴", "unknown error", None)


async def check_many_sites(urls: list[str]) -> list[CheckResult]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            check_site(session, url)
            for url in urls
        ]

        return await asyncio.gather(*tasks)


def ssl_text(ssl_days: int | None) -> str:
    if ssl_days is None:
        return ""

    if ssl_days < 0:
        return f"🔐 SSL expired {abs(ssl_days)} days ago"

    if ssl_days <= 7:
        return f"🔐 SSL expires in {ssl_days} days ⚠️"

    if ssl_days <= 30:
        return f"🔐 SSL expires in {ssl_days} days"

    return f"🔐 SSL: {ssl_days} days"


def short_url(url: str) -> str:
    return (
        url
        .replace("https://", "")
        .replace("http://", "")
    )


