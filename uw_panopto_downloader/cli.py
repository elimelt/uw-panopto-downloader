import os
import re
import time
import argparse
import requests
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import concurrent.futures
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("panopto_downloader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PanoptoDownloader:
    def __init__(self, max_workers=3):
        self.max_workers = max_workers
        self.session = requests.Session()
        self.driver = None
        self.base_url = None

    def setup_selenium(self, headless=False):
        """
        Set up the Selenium WebDriver
        """
        chrome_options = Options()
        if headless:
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
            
    def manual_login(self, url):
        """
        Open browser for manual login and wait for user confirmation
        """
        if not self.driver:
            if not self.setup_selenium(headless=False):
                return False
                
        try:
            logger.info(f"Opening {url} for manual login")
            self.driver.get(url)

            print("\n" + "="*50)
            print("Please log in manually in the browser window.")
            print("After logging in, navigate to the page with the video list.")
            input("Press Enter when you're ready to continue...")
            print("="*50 + "\n")

            # Get the cookies from selenium session
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])

            # Get current URL to use as base for API calls
            current_url = self.driver.current_url
            self.base_url = self.get_base_url_from_url(current_url)

            return True
        except Exception as e:
            logger.error(f"Error during manual login: {e}")
            return False

    def navigate_to(self, url):
        """
        Navigate to a new URL within the same session
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
            new_base_url = self.get_base_url_from_url(current_url)

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

    def extract_links_from_page(self):
        """
        Extract video links and titles from the current page
        """
        if not self.driver:
            logger.error("Selenium driver not initialized")
            return []

        try:
            # Wait for page to fully load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.detail-title, .list-item"))
            )

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
                        title = self.clean_filename(title)

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
                            title = self.clean_filename(title)

                            # Make sure the link is absolute
                            if not link.startswith('http'):
                                link = f"{self.base_url}{link}"

                            links.append((link, title))

            logger.info(f"Found {len(links)} videos on current page")
            return links
        except Exception as e:
            logger.error(f"Error extracting links from page: {e}")
            return []
    
    def clean_filename(self, filename):
        """
        Clean a string to make it suitable for use as a filename
        """
        # Replace invalid characters with underscore
        cleaned = re.sub(r'[\\/*?:"<>|]', '_', filename)
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def get_video_id_from_url(self, url):
        """
        Extract the video ID from a Panopto URL
        """
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # The ID parameter can be either 'id' or 'Id'
        video_id = query_params.get('id', [None])[0] or query_params.get('Id', [None])[0]
        
        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")
        
        return video_id
    
    def get_base_url_from_url(self, url):
        """
        Extract the base URL (domain) from a full URL
        """
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return base_url
    
    def request_delivery_info(self, video_id, base_url=None):
        """
        Request the delivery info for a video ID, similar to what the userscript does
        """
        if base_url is None:
            base_url = self.base_url

        logger.info(f"Requesting delivery info for video ID: {video_id}")
        
        url = f"{base_url}/Panopto/Pages/Viewer/DeliveryInfo.aspx"
        data = {
            'deliveryId': video_id,
            'isEmbed': 'true',
            'responseType': 'json'
        }
        
        try:
            response = self.session.post(url, data=data)
            response.raise_for_status()
            data = response.json()
            
            if data.get('ErrorCode'):
                error_msg = data.get('ErrorMessage', 'Unknown error')
                logger.error(f"Error requesting delivery info: {error_msg}")
                return None, []
            
            stream_url = data.get('Delivery', {}).get('PodcastStreams', [{}])[0].get('StreamUrl')
            additional_streams = data.get('Delivery', {}).get('Streams', [])
            
            # Filter out the main stream from additional streams
            additional_streams = [s for s in additional_streams if s.get('StreamUrl') != stream_url]
            
            if not stream_url:
                logger.error("Stream URL not found in delivery info")
                # Try to get any available stream
                for stream in additional_streams:
                    if stream.get('StreamUrl'):
                        stream_url = stream.get('StreamUrl')
                        break
            
            return stream_url, additional_streams
        except Exception as e:
            logger.error(f"Error requesting delivery info: {e}")
            return None, []
    
    def download_m3u8(self, m3u8_url, output_path, max_retries=3):
        """
        Download a video from an m3u8 URL using FFmpeg
        """
        try:
            # Check if FFmpeg is installed
            try:
                subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.error("FFmpeg is not installed. Please install FFmpeg to download HLS streams.")
                return False
            
            # Download with FFmpeg
            cmd = ["ffmpeg", "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", output_path, "-y"]
            
            retries = 0
            while retries < max_retries:
                logger.info(f"Downloading to {output_path}")
                result = subprocess.run(cmd, capture_output=True)
                
                if result.returncode == 0:
                    logger.info(f"Successfully downloaded {output_path}")
                    return True
                
                retries += 1
                logger.warning(f"Download failed, retrying ({retries}/{max_retries})...")
                time.sleep(2)
            
            logger.error(f"Failed to download after {max_retries} attempts")
            return False
        except Exception as e:
            logger.error(f"Error downloading m3u8: {e}")
            return False
    
    def download_direct(self, url, output_path, chunk_size=8192, max_retries=3):
        """
        Download a direct video link
        """
        retries = 0
        while retries < max_retries:
            try:
                logger.info(f"Downloading to {output_path}")
                response = self.session.get(url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Calculate progress
                            if total_size > 0:
                                progress = downloaded / total_size * 100
                                print(f"\rProgress: {progress:.1f}% ", end='')
                
                print()  # New line after progress
                logger.info(f"Successfully downloaded {output_path}")
                return True
            
            except Exception as e:
                retries += 1
                logger.warning(f"Download failed ({e}), retrying ({retries}/{max_retries})...")
                time.sleep(2)
        
        logger.error(f"Failed to download after {max_retries} attempts")
        return False
    
    def process_video(self, video_info, download_dir):
        """
        Process a single video: get delivery info and download
        """
        url, title = video_info
        video_id = self.get_video_id_from_url(url)
        
        if not video_id:
            return False
        
        # Get the stream URL
        stream_url, additional_streams = self.request_delivery_info(video_id)
        
        if not stream_url:
            logger.error(f"Could not get stream URL for {title}")
            return False
        
        logger.info(f"Got stream URL for {title}: {stream_url}")
        
        # Determine file extension based on URL
        file_ext = '.mp4'  # Default extension
        
        # Create output directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)

        # Create output path
        output_path = os.path.join(download_dir, f"{title}{file_ext}")

        # Check if file already exists
        if os.path.exists(output_path):
            logger.info(f"File already exists: {output_path}")
            return True

        # Download based on stream type
        if stream_url.endswith('.m3u8'):
            # HLS stream
            return self.download_m3u8(stream_url, output_path)
        else:
            # Direct video URL
            return self.download_direct(stream_url, output_path)
    
    def process_videos(self, video_list, download_dir):
        """
        Process multiple videos in parallel
        """
        successful = 0
        failed = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Create a function that includes the download_dir parameter
            def process_with_dir(video):
                return self.process_video(video, download_dir)

            future_to_video = {
                executor.submit(process_with_dir, video): video
                for video in video_list
            }
            
            for future in concurrent.futures.as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    result = future.result()
                    if result:
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Error processing {video[1]}: {e}")
                    failed += 1
        
        logger.info(f"Processing complete. Successful: {successful}, Failed: {failed}")
        return successful, failed

    def close(self):
        """
        Clean up resources
        """
        if self.driver:
            self.driver.quit()

def main():
    parser = argparse.ArgumentParser(description="Selenium Panopto Video Downloader")
    parser.add_argument("--url", default="", help="Starting URL (optional)")
    parser.add_argument("--output", "-o", default="downloads", help="Default output directory for downloaded videos")
    parser.add_argument("--workers", "-w", type=int, default=3, help="Number of concurrent downloads")
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = PanoptoDownloader(max_workers=args.workers)
    
    try:
        # Get starting URL
        start_url = args.url
        if not start_url:
            start_url = input("Enter the Panopto URL to start with: ")

        # Manual login and navigation
        if not downloader.manual_login(start_url):
            logger.error("Failed to set up browser session")
            return

        # Main loop for multiple download jobs
        while True:
            # Extract links from current page
            video_links = downloader.extract_links_from_page()

            if not video_links:
                print("\nNo video links found on the current page.")
                choice = input("Would you like to navigate to another page? (y/n): ").lower().strip()
                if choice != 'y':
                    break
                new_url = input("Enter the URL to navigate to: ")
                if not downloader.navigate_to(new_url):
                    logger.error("Failed to navigate to new URL")
                    break
                continue

            print(f"\nFound {len(video_links)} videos. Do you want to download them?")
            print("Sample videos:")
            for i, (_, title) in enumerate(video_links[:3], 1):
                print(f"  {i}. {title}")

            if len(video_links) > 3:
                print(f"  ... and {len(video_links) - 3} more")

            confirm = input("\nProceed with download? (y/n): ").lower().strip()
            if confirm != 'y':
                print("Download canceled")
            else:
                # Ask for output directory for this job
                default_dir = args.output
                job_output_dir = input(f"Enter output directory for this job (default: {default_dir}): ").strip() or default_dir

                # Process and download videos
                print(f"\nDownloading {len(video_links)} videos to {job_output_dir}...")
                successful, failed = downloader.process_videos(video_links, job_output_dir)

                print(f"\nDownload process completed!")
                print(f"Successfully downloaded: {successful}")
                print(f"Failed: {failed}")

            # Ask if user wants to navigate to another page
            choice = input("\nWould you like to navigate to another page? (y/n): ").lower().strip()
            if choice != 'y':
                break

            new_url = input("Enter the URL to navigate to: ")
            if not downloader.navigate_to(new_url):
                logger.error("Failed to navigate to new URL")
                break

    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        downloader.close()
        print("\nBrowser session closed. Goodbye!")

if __name__ == "__main__":
    main()