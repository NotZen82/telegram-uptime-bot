import asyncio
import re
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
    domain_days: int | None


def normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url

    return f"https://{url}"


def extract_domain(url: str) -> str:
    url = url.replace("https://", "").replace("http://", "")
    return url.split("/")[0]


def domain_candidates(url: str) -> list[str]:
    domain = extract_domain(url).split(":")[0].lower()
    candidates = []

    if domain:
        candidates.append(domain)

    if domain.startswith("www."):
        candidates.append(domain[4:])

    parts = domain.split(".")
    if len(parts) > 2:
        candidates.append(".".join(parts[-2:]))

    return list(dict.fromkeys(candidates))


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


def parse_rdap_datetime(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def parse_whois_datetime(value: str) -> datetime | None:
    value = value.strip().strip(".")
    value = re.sub(r"\s*\(.+\)\s*$", "", value)
    match = re.search(r"\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)?|\d{2}[.-]\d{2}[.-]\d{4}", value)
    if match:
        value = match.group(0)

    formats = (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d-%m-%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def check_kz_domain_expiry(domain: str) -> int | None:
    try:
        with socket.create_connection(("whois.nic.kz", 43), timeout=10) as sock:
            sock.sendall(f"{domain}\r\n".encode("utf-8"))
            chunks = []

            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)

        response = b"".join(chunks).decode("utf-8", errors="ignore")
        patterns = (
            r"Expiration Date\s*[:.]+\s*(.+)",
            r"Expires\s*[:.]+\s*(.+)",
            r"Valid Until\s*[:.]+\s*(.+)",
            r"Paid Till\s*[:.]+\s*(.+)",
            r"Registry Expiry Date\s*[:.]+\s*(.+)",
            r"Registrar Registration Expiration Date\s*[:.]+\s*(.+)",
        )

        for pattern in patterns:
            match = re.search(pattern, response, flags=re.IGNORECASE)
            if not match:
                continue

            expires_date = parse_whois_datetime(match.group(1).strip())
            if expires_date:
                return (expires_date - datetime.now(timezone.utc)).days

    except Exception:
        return None

    return None


async def check_domain_expiry(session: aiohttp.ClientSession, url: str) -> int | None:
    for domain in domain_candidates(url):
        try:
            async with session.get(
                f"https://rdap.org/domain/{domain}",
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=True,
                headers={"User-Agent": "TelegramUptimeBot/1.0"}
            ) as response:
                data = await response.json(content_type=None) if response.status < 400 else {}

            for event in data.get("events", []):
                action = (event.get("eventAction") or "").lower()
                if action in {"expiration", "expiry"}:
                    event_date = event.get("eventDate")
                    if not event_date:
                        continue

                    expires_date = parse_rdap_datetime(event_date)
                    return (expires_date - datetime.now(timezone.utc)).days

        except Exception:
            pass

        if domain.endswith(".kz"):
            kz_days = await asyncio.to_thread(check_kz_domain_expiry, domain)
            if kz_days is not None:
                return kz_days

    return None


async def check_site(session: aiohttp.ClientSession, url: str) -> CheckResult:
    full_url = normalize_url(url)
    domain_days = await check_domain_expiry(session, url)

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
            return CheckResult(url, status, icon, result, ssl_days, domain_days)

    except asyncio.TimeoutError:
        return CheckResult(url, "TIMEOUT", "🔴", "timeout", None, domain_days)

    except aiohttp.ClientConnectorCertificateError:
        return CheckResult(url, "SSL ERROR", "🔴", "ssl error", None, domain_days)

    except aiohttp.ClientConnectorError:
        return CheckResult(url, "CONNECTION ERROR", "🔴", "dns/connection error", None, domain_days)

    except aiohttp.InvalidURL:
        return CheckResult(url, "INVALID URL", "🔴", "invalid url", None, domain_days)

    except aiohttp.TooManyRedirects:
        return CheckResult(url, "TOO MANY REDIRECTS", "🔴", "too many redirects", None, domain_days)

    except aiohttp.ClientError:
        return CheckResult(url, "CLIENT ERROR", "🔴", "client error", None, domain_days)

    except Exception:
        return CheckResult(url, "UNKNOWN ERROR", "🔴", "unknown error", None, domain_days)


async def check_many_sites(urls: list[str]) -> list[CheckResult]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            check_site(session, url)
            for url in urls
        ]

        return await asyncio.gather(*tasks)


def ssl_text(ssl_days: int | None, lang: str = "ru") -> str:
    if ssl_days is None:
        return ""

    if ssl_days < 0:
        if lang == "en":
            return f"🔐 SSL expired {abs(ssl_days)} days ago"
        return f"🔐 SSL истек {abs(ssl_days)} дн. назад"

    if ssl_days <= 7:
        if lang == "en":
            return f"🔐 SSL expires in {ssl_days} days ⚠️"
        return f"🔐 SSL истекает через {ssl_days} дн. ⚠️"

    if ssl_days <= 30:
        if lang == "en":
            return f"🔐 SSL expires in {ssl_days} days"
        return f"🔐 SSL истекает через {ssl_days} дн."

    if lang == "en":
        return f"🔐 SSL: {ssl_days} days"
    return f"🔐 SSL: {ssl_days} дн."


def domain_text(domain_days: int | None, lang: str = "ru") -> str:
    if domain_days is None:
        return ""

    if domain_days < 0:
        if lang == "en":
            return f"📅 Domain expired {abs(domain_days)} days ago"
        return f"📅 Домен истек {abs(domain_days)} дн. назад"

    if domain_days <= 14:
        if lang == "en":
            return f"📅 Domain expires in {domain_days} days ⚠️"
        return f"📅 Домен истекает через {domain_days} дн. ⚠️"

    if domain_days <= 30:
        if lang == "en":
            return f"📅 Domain expires in {domain_days} days"
        return f"📅 Домен истекает через {domain_days} дн."

    if lang == "en":
        return f"📅 Domain: {domain_days} days"
    return f"📅 Домен: {domain_days} дн."


def short_url(url: str) -> str:
    return (
        url
        .replace("https://", "")
        .replace("http://", "")
    )


