from playwright.sync_api import sync_playwright

class BrowserAgent:

    def search_and_extract(self, query):

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto("https://duckduckgo.com/")
                page.fill("input[name='q']", query)
                page.keyboard.press("Enter")

                page.wait_for_selector("a[data-testid='result-title-a']")

                results = page.locator("a[data-testid='result-title-a']").all()

                texts = []
                for r in results[:5]:
                    try:
                        texts.append(r.inner_text())
                    except:
                        pass

                browser.close()

                return " | ".join(texts)

        except Exception as e:
            return f"Browser error: {str(e)}"


    def open_page(self, url):

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(url)
                return f"Opened {url}"
        except Exception as e:
            return str(e)