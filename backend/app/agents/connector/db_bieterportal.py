"""Connector: DB Bieterportal (e-Vergabe Deutsche Bahn).

Kapitel 3: "Vermutlich stark JavaScript-basiert (Single-Page-Anwendung) - Headless-Browser-
Ansatz einplanen." Daher hier mit Playwright statt httpx umgesetzt. Selektoren sind - wie bei
den anderen beiden Connectoren - bis zur echten Analyse (siehe base.py-Docstring) Platzhalter.

Verifiziert am 31.08.2026, nachdem Netzzugriff in dieser Session freigeschaltet wurde:
ein einfacher HTTP-Abruf (siehe `polite_get`) liefert nur die leere SPA-Startseite (Angular +
Telerik Kendo UI, SignalR/WebSocket-Datenkanal laut Bundle-Analyse) - Playwright ist also wie
in Kapitel 3 vorgesehen nötig. In dieser konkreten Sandbox-Umgebung scheitert jede
Chromium-Navigation zu genau diesem Host allerdings am Egress-Proxy (der die Verbindung als
WebSocket-Upgrade behandelt und abbricht, siehe docs/portal-notes.md) - kein Login/CAPTCHA auf
der Zielseite erkennbar, sondern eine Einschränkung dieser Session. fetch_list_page/
fetch_detail fangen das sauber als TechnicalFailure ab, statt hart zu crashen; in einer
Umgebung ohne diese Proxy-Einschränkung sollte der Connector funktionieren (Selektoren dann
gegen die tatsächlich gerenderte Seite verifizieren, siehe TODOs unten).
"""
from __future__ import annotations

import os
from urllib.parse import urljoin

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import AccessBlocked, TechnicalFailure

BASE_URL = "https://bieterportal.noncd.db.de/evergabe.bieter/eva/supplierportal/portal/tabs/vergaben"

# TODO(portal-analyse): Selektoren gegen die echte, gerenderte Seite verifizieren.
LIST_ITEM_SELECTOR = "[data-testid='vergabe-row'], tr.vergabe-zeile, .vergabe-liste-item"
LIST_TITLE_SELECTOR = "a, [data-testid='vergabe-titel']"
NEXT_PAGE_SELECTOR = "button[aria-label='Nächste Seite'], .pagination-next:not([disabled])"
DETAIL_TITLE_SELECTOR = "h1, [data-testid='vergabe-detail-titel']"
DETAIL_MAIN_SELECTOR = "main, [data-testid='vergabe-detail']"


class DbBieterportalConnector(BaseConnector):
    slug = "db-bieterportal"
    name = "DB Bieterportal (e-Vergabe Deutsche Bahn)"
    base_url = BASE_URL
    vorgegeben = True

    def _new_page(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise TechnicalFailure(
                "Playwright ist nicht installiert (pip install playwright && playwright install chromium)."
            ) from exc

        # In dieser Entwicklungsumgebung ist unter /opt/pw-browsers ein vorinstallierter
        # Chromium hinterlegt (siehe Systemhinweis), dessen Revision nicht zu der von der
        # Python-Playwright-Version standardmäßig erwarteten Build-Nummer passt - deshalb
        # expliziter Pfad statt Playwrights Auto-Erkennung. In einer anderen Umgebung (z. B.
        # bei Vincent nach `playwright install chromium`) einfach die Umgebungsvariable
        # `CRAWLER_PLAYWRIGHT_EXECUTABLE_PATH` leer lassen bzw. nicht setzen.
        executable_path = os.environ.get("CRAWLER_PLAYWRIGHT_EXECUTABLE_PATH", "/opt/pw-browsers/chromium")
        launch_kwargs = {"headless": True}
        if executable_path and os.path.exists(executable_path):
            launch_kwargs["executable_path"] = executable_path

        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if https_proxy:
            launch_kwargs["proxy"] = {"server": https_proxy}

        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:  # Browser-Binary fehlt o.ä.
            raise TechnicalFailure(
                f"Playwright-Browser konnte nicht gestartet werden ('playwright install chromium' nötig): {exc}"
            ) from exc

        context = browser.new_context(user_agent=self._user_agent())
        # WebSocket-Upgrades werden von manchen Sandbox-Egress-Proxies nicht unterstützt
        # (siehe docs/portal-notes.md) und können sonst die ganze Navigation per
        # Connection-Reset abbrechen, obwohl die eigentlichen Seiteninhalte per HTTP laden.
        context.route("**/*", lambda route, request: route.abort() if request.resource_type == "websocket" else route.continue_())
        return playwright, browser, context

    def _user_agent(self) -> str:
        from app.config import settings

        return settings.http_user_agent

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        playwright, browser, context = self._new_page()
        try:
            self._respect_rate_limit()
            pw_page = context.new_page()
            try:
                pw_page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                raise TechnicalFailure(f"DB Bieterportal: Navigation fehlgeschlagen: {exc}") from exc
            pw_page.wait_for_timeout(2000)

            html = pw_page.content()
            block = self._detect_block(html)
            if block is not None:
                raise block

            for _ in range(page - 1):
                next_btn = pw_page.query_selector(NEXT_PAGE_SELECTOR)
                if next_btn is None:
                    return [], False
                next_btn.click()
                pw_page.wait_for_load_state("networkidle", timeout=15000)

            items = pw_page.query_selector_all(LIST_ITEM_SELECTOR)
            candidates: list[RawCandidate] = []
            for item in items:
                link = item.query_selector(LIST_TITLE_SELECTOR)
                href = link.get_attribute("href") if link else None
                titel = link.inner_text().strip() if link else None
                if not href:
                    continue
                detail_url = urljoin(self.base_url, href)
                externe_id = detail_url.rstrip("/").rsplit("/", 1)[-1]
                candidates.append(RawCandidate(externe_id=externe_id, detail_url=detail_url, titel_hint=titel))

            if not items and page == 1:
                raise TechnicalFailure(
                    "DB Bieterportal: keine Listeneinträge über LIST_ITEM_SELECTOR gefunden - "
                    "Selektoren müssen nach echter Analyse der gerenderten Seite angepasst werden."
                )

            has_more = pw_page.query_selector(NEXT_PAGE_SELECTOR) is not None
            return candidates, has_more
        finally:
            context.close()
            browser.close()
            playwright.stop()

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        playwright, browser, context = self._new_page()
        try:
            self._respect_rate_limit()
            pw_page = context.new_page()
            try:
                pw_page.goto(candidate.detail_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as exc:
                raise TechnicalFailure(f"DB Bieterportal: Navigation zur Detailseite fehlgeschlagen: {exc}") from exc
            pw_page.wait_for_timeout(2000)

            html = pw_page.content()
            block = self._detect_block(html)
            if block is not None:
                raise block

            title_el = pw_page.query_selector(DETAIL_TITLE_SELECTOR)
            main_el = pw_page.query_selector(DETAIL_MAIN_SELECTOR)
            dokument_links = [
                urljoin(candidate.detail_url, a.get_attribute("href"))
                for a in pw_page.query_selector_all("a[href*='dokument'], a[href$='.pdf']")
                if a.get_attribute("href")
            ]

            return RawDetail(
                externe_id=candidate.externe_id,
                detail_url=candidate.detail_url,
                felder={
                    "titel": title_el.inner_text().strip() if title_el else candidate.titel_hint,
                    "volltext": main_el.inner_text().strip() if main_el else None,
                    "vergabestelle": "Deutsche Bahn AG",
                    "dokumente_links": dokument_links,
                    # Kapitel 10.3-Beispiel: Dokumente evtl. erst nach Bieter-Login sichtbar - falls die
                    # gerenderte Detailseite selbst schon einen Login-Hinweis zeigt, greift _detect_block
                    # oben und löst eine Eskalation statt eines stillen Leerfelds aus.
                },
            )
        finally:
            context.close()
            browser.close()
            playwright.stop()

    @staticmethod
    def _detect_block(html: str) -> AccessBlocked | None:
        from app.agents.connector.base import detect_access_block

        return detect_access_block(html)
