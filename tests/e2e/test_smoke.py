import json
import os
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:5001").rstrip("/")
ARTIFACT_DIR = Path(
    os.environ.get("E2E_ARTIFACT_DIR", "/tests/artifacts")
)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
PDF_ARTIFACT_DIR = Path(
    os.environ.get("PDF_ARTIFACT_DIR", "/tests/pdf-artifacts")
)
PDF_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


class BrowserTestCase(unittest.TestCase):
    browser_name = "chromium"

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        browser_type = getattr(cls.playwright, cls.browser_name)
        cls.browser = browser_type.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.console_errors = []
        self.page_errors = []
        self.api_traffic = []
        self.context = self.browser.new_context(
            locale="pl-PL",
            viewport={"width": 1440, "height": 1000},
        )
        self.page = self.context.new_page()
        self._observe_page()

    def tearDown(self):
        self.context.close()

    def _observe_page(self):
        self.page.on(
            "console",
            lambda message: (
                self.console_errors.append(message.text)
                if message.type == "error"
                else None
            ),
        )
        self.page.on(
            "pageerror",
            lambda error: self.page_errors.append(str(error)),
        )
        self.page.on("response", self._record_api_response)

    def _record_api_response(self, response):
        if "/api/" not in response.url:
            return
        self.api_traffic.append({
            "method": response.request.method,
            "path": urlparse(response.url).path,
            "status": response.status,
        })

    def _replace_context(self, *, viewport):
        self.context.close()
        self.context = self.browser.new_context(
            locale="pl-PL",
            viewport=viewport,
        )
        self.page = self.context.new_page()
        self._observe_page()

    def _debug_login(self, account_label):
        self.page.goto(f"{BASE_URL}/login")
        self.page.get_by_role(
            "button", name=account_label, exact=True,
        ).click()
        self.page.wait_for_url(f"{BASE_URL}/")

    def _screenshot(self, filename, *, full_page=True):
        self.page.screenshot(
            path=str(ARTIFACT_DIR / filename),
            full_page=full_page,
        )

    def _save_api_traffic(self, filename):
        path = ARTIFACT_DIR / filename
        path.write_text(
            json.dumps(self.api_traffic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _assert_no_browser_errors(self):
        self.assertEqual(self.page_errors, [], "JavaScript page errors detected")
        self.assertEqual(self.console_errors, [], "Browser console errors detected")


class ChromiumUserInterfaceTests(BrowserTestCase):
    browser_name = "chromium"

    def test_01_anonymous_user_is_redirected_to_login(self):
        self.page.goto(f"{BASE_URL}/")

        self.assertEqual(urlparse(self.page.url).path, "/login")
        self.assertTrue(
            self.page.get_by_role(
                "heading", name="Panel logowania", exact=True,
            ).is_visible()
        )
        self._screenshot("01-login-chromium.png")
        self._assert_no_browser_errors()

    def test_02_admin_can_open_all_form_views(self):
        self._debug_login("Admin")
        links = self.page.locator('.sidebar-link[href^="/zal"]')
        form_urls = sorted(set(
            links.nth(index).get_attribute("href")
            for index in range(links.count())
        ))
        self.assertGreaterEqual(len(form_urls), 12)

        for path in form_urls:
            response = self.page.goto(BASE_URL + path)
            self.assertIsNotNone(response)
            self.assertLess(response.status, 400, path)
            self.assertTrue(self.page.locator(".page-form").is_visible(), path)

        self._screenshot("02-all-forms-last-view.png")
        self._assert_no_browser_errors()

    def test_03_admin_rest_panel_runs_get_post_put_delete(self):
        self._debug_login("Admin")
        with self.page.expect_response(
            lambda response: (
                response.request.method == "GET"
                and response.url.endswith("/api/students")
            )
        ) as initial_get:
            self.page.get_by_role(
                "link", name="Administracja", exact=True,
            ).click()
        self.assertEqual(initial_get.value.status, 200)
        self.page.wait_for_selector("#apiStudentsBody tr")

        suffix = str(int(time.time() * 1000))[-8:]
        album_number = suffix
        email = f"ui.{suffix}@example.test"
        self.page.locator("#apiFirstName").fill("Ewa")
        self.page.locator("#apiLastName").fill("Testowa")
        self.page.locator("#apiAlbumNumber").fill(album_number)
        self.page.locator("#apiEmail").fill(email)

        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith("/api/students")
            )
        ) as created:
            self.page.locator("#apiSaveStudent").click()
        self.assertEqual(created.value.status, 201)
        row = self.page.locator(
            f'#apiStudentsBody tr:has-text("{album_number}")'
        )
        row.wait_for(state="visible")
        self._screenshot("03-api-post-201.png")

        row.get_by_role("button", name="Edytuj PUT").click()
        self.page.locator("#apiLastName").fill("Zmieniona")
        with self.page.expect_response(
            lambda response: (
                response.request.method == "PUT"
                and "/api/students/" in response.url
            )
        ) as updated:
            self.page.locator("#apiSaveStudent").click()
        self.assertEqual(updated.value.status, 200)
        self.page.locator(
            f'#apiStudentsBody tr:has-text("{album_number}")'
        ).get_by_text("Ewa Zmieniona").wait_for(state="visible")

        row = self.page.locator(
            f'#apiStudentsBody tr:has-text("{album_number}")'
        )
        self.page.once("dialog", lambda dialog: dialog.accept())
        with self.page.expect_response(
            lambda response: (
                response.request.method == "DELETE"
                and "/api/students/" in response.url
            )
        ) as deleted:
            row.get_by_role("button", name="Usuń DELETE").click()
        self.assertEqual(deleted.value.status, 204)
        self.page.locator(
            f'#apiStudentsBody tr:has-text("{album_number}")'
        ).wait_for(state="detached")
        self._screenshot("04-api-crud-http-log.png")
        self._save_api_traffic("api-traffic-crud.json")
        methods = {entry["method"] for entry in self.api_traffic}
        self.assertTrue({"GET", "POST", "PUT", "DELETE"} <= methods)
        self._assert_no_browser_errors()

    def test_04_api_panel_handles_conflict_and_lost_connection(self):
        self._debug_login("Admin")
        self.page.goto(f"{BASE_URL}/administracja/")
        self.page.wait_for_selector("#apiStudentsBody tr")

        self.page.locator("#apiFirstName").fill("Konflikt")
        self.page.locator("#apiLastName").fill("Albumu")
        self.page.locator("#apiAlbumNumber").fill("21001")
        self.page.locator("#apiEmail").fill("conflict@example.test")
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith("/api/students")
            )
        ) as conflict:
            self.page.locator("#apiSaveStudent").click()
        self.assertEqual(conflict.value.status, 409)
        self.assertTrue(
            self.page.locator("#apiStudentStatus.is-error").is_visible()
        )
        self._screenshot("05-api-error-409.png")

        self.page.route(
            "**/api/students",
            lambda route: route.abort("failed"),
        )
        self.page.locator("#apiReloadStudents").click()
        self.page.get_by_text(
            "Brak połączenia z API. Spróbuj ponownie.",
            exact=True,
        ).wait_for()
        self._screenshot("06-api-offline-error.png")
        self.page.unroute("**/api/students")
        self.assertTrue(
            any(
                "409" in message or "ERR_FAILED" in message
                for message in self.console_errors
            )
        )
        self.assertEqual(self.page_errors, [])

    def test_05_student_form_client_validation(self):
        self._debug_login("Student")
        self.page.goto(f"{BASE_URL}/zal1")

        name = self.page.locator('[name="imie_nazwisko"]')
        name.fill("")
        name.blur()
        self.assertTrue(
            self.page.locator(
                ".vmsg-err", has_text="Pole jest wymagane."
            ).is_visible()
        )

        name.fill("Jan 123")
        name.blur()
        self.assertTrue(
            self.page.locator(
                ".vmsg-err",
                has_text="Tylko litery, łącznik i apostrof (bez cyfr).",
            ).is_visible()
        )

        nip = self.page.locator('[name="nip_zakladu"]')
        nip.fill("123")
        nip.blur()
        self.assertTrue(
            self.page.locator(
                ".vmsg-err", has_text="NIP to 10 cyfr."
            ).is_visible()
        )

        self.page.locator('[name="data_start"]').fill("2026-08-10")
        self.page.locator('[name="data_end"]').fill("2026-08-01")
        self.page.locator('[name="data_end"]').blur()
        self.assertTrue(
            self.page.locator(
                ".vmsg-err",
                has_text="Data zakończenia musi być po dacie rozpoczęcia.",
            ).is_visible()
        )
        self._screenshot("07-validation-zal1.png")
        self._assert_no_browser_errors()

    def test_06_diary_client_validation(self):
        self._debug_login("Student")
        self.page.goto(f"{BASE_URL}/zal6")

        day = self.page.locator(".day-input").first
        hours = self.page.locator(".hours-input").first
        description = self.page.locator(".opis-textarea").first
        day.fill("121")
        day.blur()
        hours.fill("9")
        hours.blur()
        description.fill("Za krótki opis.")
        description.blur()

        self.assertTrue(
            self.page.locator(
                ".vmsg-err",
                has_text="Numer dnia musi mieścić się w zakresie 1-120.",
            ).is_visible()
        )
        self.assertTrue(
            self.page.locator(
                ".vmsg-err",
                has_text="Liczba godzin musi mieścić się w zakresie 1-8.",
            ).is_visible()
        )
        self.assertTrue(
            self.page.get_by_text("Za krótki", exact=False).is_visible()
        )
        self._screenshot("08-validation-diary.png")
        self._assert_no_browser_errors()

    def test_07_admin_can_add_and_edit_internship_part(self):
        self._debug_login("Admin")
        self.page.goto(f"{BASE_URL}/czesci-praktyki?nr=21001")
        create_form = self.page.locator(".internship-part-create form")
        create_form.locator('[name="name"]').fill("Część testowa E2E")
        create_form.locator('[name="company_name"]').fill("Firma E2E")
        create_form.locator('[name="start_date"]').fill("2026-07-01")
        create_form.locator('[name="end_date"]').fill("2026-07-15")
        create_form.locator('[name="planned_hours"]').fill("80")
        create_form.get_by_role(
            "button", name="Dodaj część praktyki", exact=True,
        ).click()
        self.page.wait_for_load_state("networkidle")
        card = self.page.locator(
            '.internship-part-card:has-text("Część testowa E2E")'
        )
        self.assertTrue(card.is_visible())

        card.locator('[name="name"]').fill("Część testowa E2E po edycji")
        card.locator('[name="total_hours"]').fill("40")
        card.get_by_role(
            "button", name="Zapisz część", exact=True,
        ).click()
        self.page.wait_for_load_state("networkidle")
        self.assertTrue(
            self.page.get_by_role(
                "heading", name="Część testowa E2E po edycji", exact=True,
            ).is_visible()
        )
        self._screenshot("09-internship-add-edit.png")
        self._assert_no_browser_errors()

    def test_08_mobile_navigation_is_available(self):
        self._replace_context(viewport={"width": 390, "height": 844})
        self._debug_login("Student")

        sidebar = self.page.locator("#siteSidebar")
        before = sidebar.bounding_box()
        self.assertIsNotNone(before)
        self.assertLess(before["x"], 0)

        self.page.locator("#sidebarToggle").click()
        self.page.wait_for_timeout(250)
        after = sidebar.bounding_box()
        self.assertIsNotNone(after)
        self.assertGreaterEqual(after["x"], 0)
        self.assertTrue(self.page.locator("#sidebarOverlay").is_visible())
        self._screenshot("10-mobile-menu.png", full_page=False)

        self.page.get_by_role("link", name="Mój profil", exact=True).click()
        self.page.wait_for_url(f"{BASE_URL}/profil")
        self.assertFalse(
            self.page.locator("body").evaluate(
                "element => element.classList.contains('mobile-sidebar-open')"
            )
        )
        self._assert_no_browser_errors()

    def test_09_student_downloads_pdf_in_chromium(self):
        self._debug_login("Student")
        self.page.goto(f"{BASE_URL}/student/21001")
        link = self.page.locator(
            'a[href="/student/21001/zal1/pobierz"]'
        )
        link.wait_for(state="visible")
        self._screenshot("13-pdf-download-chromium.png")

        with self.page.expect_download(timeout=120000) as download_info:
            with self.page.expect_response(
                lambda response: response.url.endswith(
                    "/student/21001/zal1/pobierz"
                ),
                timeout=120000,
            ) as response_info:
                link.click()

        response = response_info.value
        download = download_info.value
        self.assertEqual(response.status, 200)
        self.assertIn("application/pdf", response.headers["content-type"])
        self.assertEqual(download.suggested_filename, "Zal_1_21001.pdf")
        target = PDF_ARTIFACT_DIR / "chromium-Zal_1_21001.pdf"
        download.save_as(target)
        self.assertTrue(target.read_bytes().startswith(b"%PDF-"))
        self._assert_no_browser_errors()


class FirefoxCompatibilityTests(BrowserTestCase):
    browser_name = "firefox"

    def test_01_admin_dashboard_and_api_get_work_in_firefox(self):
        self._debug_login("Admin")
        with self.page.expect_response(
            lambda response: response.url.endswith("/api/students")
        ) as api_response:
            self.page.get_by_role(
                "link", name="Administracja", exact=True,
            ).click()
        self.assertEqual(api_response.value.status, 200)
        self.assertTrue(
            self.page.get_by_role(
                "heading", name="Studenci przez REST API", exact=True,
            ).is_visible()
        )
        self._screenshot("11-firefox-api-panel.png")
        self._assert_no_browser_errors()

    def test_02_login_email_validation_and_student_navigation_in_firefox(self):
        self.page.goto(f"{BASE_URL}/login")
        email = self.page.locator("#email")
        email.fill("niepoprawny-email")
        self.assertFalse(email.evaluate("element => element.checkValidity()"))

        self.page.get_by_role(
            "button", name="Student", exact=True,
        ).click()
        self.page.wait_for_url(f"{BASE_URL}/")
        self.page.get_by_role(
            "link", name="Części praktyki", exact=True,
        ).click()
        self.page.wait_for_url(f"{BASE_URL}/czesci-praktyki")
        self.assertTrue(
            self.page.get_by_role(
                "heading", name="Części praktyki", exact=True,
            ).is_visible()
        )
        self._screenshot("12-firefox-student-view.png")
        self._assert_no_browser_errors()

    def test_03_student_downloads_pdf_in_firefox(self):
        self._debug_login("Student")
        self.page.goto(f"{BASE_URL}/student/21001")
        link = self.page.locator(
            'a[href="/student/21001/zal1/pobierz"]'
        )
        link.wait_for(state="visible")
        self._screenshot("14-pdf-download-firefox.png")

        with self.page.expect_download(timeout=120000) as download_info:
            link.click()
        download = download_info.value
        self.assertEqual(download.suggested_filename, "Zal_1_21001.pdf")
        target = PDF_ARTIFACT_DIR / "firefox-Zal_1_21001.pdf"
        download.save_as(target)
        self.assertTrue(target.read_bytes().startswith(b"%PDF-"))
        self._assert_no_browser_errors()


if __name__ == "__main__":
    unittest.main()
