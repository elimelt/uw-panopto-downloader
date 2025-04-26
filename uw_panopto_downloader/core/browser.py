"""Browser session manager for Panopto Downloader."""

import time
from typing import List, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from ..utils.logging import get_logger

logger = get_logger(__name__)


class BrowserSession:
    """Manages the browser session for Panopto Downloader."""

    def __init__(self, headless: bool = False):
        """Initialize the browser session.

        Args:
            headless: Whether to run the browser in headless mode
        """
        self.driver = None
        self.headless = headless
        self.session = requests.Session()
        self.base_url = None

    def setup(self) -> bool:
        """Set up the Selenium WebDriver.

        Returns:
            bool: Whether setup was successful
        """
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Install and setup Chrome driver
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            return True
        except Exception as e:
            logger.error(f"Error setting up Selenium: {e}")
            return False

    def manual_login(self, url: str, console=None) -> bool:
        """Open browser for manual login and wait for user confirmation.

        Args:
            url: The URL to open for login

        Returns:
            bool: Whether login was successful
        """
        if not self.driver:
            if not self.setup():
                logger.error("Failed to set up Selenium driver")
                return False

        try:
            logger.info(f"Opening {url} for manual login")
            self.driver.get(url)

            logger.info("Waiting for manual login...")

            input("Press Enter to continue after logging in...")

            # Get the cookies from selenium session after login
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])

            # Get current URL to use as base for API calls
            current_url = self.driver.current_url
            self.base_url = self._get_base_url(current_url)

            return True
        except Exception as e:
            logger.error(f"Error during manual login: {e}")
            return False

    def navigate_to(self, url: str) -> bool:
        """Navigate to a new URL within the same session.

        Args:
            url: The URL to navigate to

        Returns:
            bool: Whether navigation was successful
        """
        if not self.driver:
            logger.error("Selenium driver not initialized")
            return False

        try:
            logger.info(f"Navigating to {url}")
            self.driver.get(url)

            # Wait for page to load
            time.sleep(2)

            # Update base URL if domain has changed
            current_url = self.driver.current_url
            new_base_url = self._get_base_url(current_url)

            if new_base_url != self.base_url:
                logger.info(f"Base URL changed from {self.base_url} to {new_base_url}")
                self.base_url = new_base_url

                # Update session cookies
                cookies = self.driver.get_cookies()
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'])

            return True
        except Exception as e:
            logger.error(f"Error navigating to URL: {e}")
            return False

    def extract_links(self) -> List[Tuple[str, str]]:
        """Extract video links and titles from the current page.

        Returns:
            list: List of (link, title) tuples
        """
        if not self.driver:
            logger.error("Selenium driver not initialized")
            return []

        try:
            logger.info("Extracting video links from current page")
            # Wait for page to fully load
            WebDriverWait(self.driver, 20).until(
                ec.presence_of_element_located((By.CSS_SELECTOR, "a.detail-title, .list-item"))
            )
            logger.info("Page loaded successfully")

            # Get current page HTML
            html_content = self.driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')

            links = []
            # Try different selectors that might be present in Panopto pages
            detail_titles = soup.find_all('a', class_='detail-title')

            if detail_titles:
                for a in detail_titles:
                    link = a.get('href')
                    # Try to get title from aria-label first, then from text content
                    title = a.get('aria-label') or a.text.strip()

                    if link and title:
                        # Clean the title for use as filename
                        title = self._clean_filename(title)

                        # Make sure the link is absolute
                        if not link.startswith('http'):
                            link = f"{self.base_url}{link}"

                        links.append((link, title))
            else:
                # Alternative approach if the first selector doesn't work
                items = soup.select('.list-item')
                for item in items:
                    a_tag = item.select_one('a')
                    if a_tag:
                        link = a_tag.get('href')
                        title_elem = item.select_one('.title-text')
                        if title_elem:
                            title = title_elem.text.strip()
                        else:
                            title = a_tag.text.strip()

                        if link and title:
                            title = self._clean_filename(title)

                            # Make sure the link is absolute
                            if not link.startswith('http'):
                                link = f"{self.base_url}{link}"

                            links.append((link, title))

            logger.info(f"Found {len(links)} videos on current page")
            return links
        except Exception as e:
            logger.error(f"Error extracting links from page: {e}")
            return []

    def close(self) -> None:
        """Close the browser session."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _get_base_url(self, url: str) -> str:
        """Extract the base URL (domain) from a full URL.

        Args:
            url: The full URL

        Returns:
            str: The base URL
        """
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return base_url

    @staticmethod
    def _clean_filename(filename: str) -> str:
        """Clean a string to make it suitable for use as a filename.

        Args:
            filename: The original filename

        Returns:
            str: The cleaned filename
        """
        import re
        # Replace invalid characters with underscore
        cleaned = re.sub(r'[\\/*?:"<>|]', '_', filename)
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
