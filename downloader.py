#!/usr/bin/env python3
"""
High-Resolution Image Downloader
Handles downloading of high-quality manga images with progress tracking and retry logic.
"""

import requests
import time
from pathlib import Path
from typing import Optional
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed


class HighResDownloader:
    def __init__(self, max_workers: int = 3):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MangaDex-HighRes-Downloader/1.0'
        })
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.max_workers = max_workers
    
    def download_high_res_image(self, url: str, path: Path) -> bool:
        """
        Download a high-resolution image with progress tracking and retry logic.
        
        Args:
            url: URL of the image to download
            path: Local path where to save the image
            
        Returns:
            True if download succeeded, False if failed after all retries
        """
        for attempt in range(self.max_retries):
            try:
                return self._download_with_progress(url, path)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    print(f"Download attempt {attempt + 1} failed: {e}")
                    print(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"Download failed after {self.max_retries} attempts: {e}")
                    return False
        return False
    
    def _download_with_progress(self, url: str, path: Path) -> bool:
        """
        Download image with progress bar.
        
        Args:
            url: URL of the image
            path: Local path where to save the image
            
        Returns:
            True if successful
            
        Raises:
            requests.RequestException: If download fails
            IOError: If file operations fail
        """
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get file info first
        response = self.session.head(url, allow_redirects=True)
        response.raise_for_status()
        
        # Get file size for progress bar
        content_length = response.headers.get('content-length')
        total_size = int(content_length) if content_length else None
        
        # Download with streaming
        response = self.session.get(url, stream=True)
        response.raise_for_status()
        
        # Setup progress bar
        progress_desc = path.name
        if total_size:
            progress_bar = tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=progress_desc
            )
        else:
            progress_bar = tqdm(
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=progress_desc
            )
        
        try:
            with open(path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress_bar.update(len(chunk))
            
            progress_bar.close()
            
            # Verify file was created and has content
            if path.exists() and path.stat().st_size > 0:
                return True
            else:
                raise IOError(f"File was not created properly: {path}")
                
        except Exception as e:
            progress_bar.close()
            # Clean up partial file on failure
            if path.exists():
                path.unlink()
            raise e
    
    def download_multiple_images(self, urls: list, base_dir: Path) -> dict:
        """
        Download multiple images and return results.
        
        Args:
            urls: List of image URLs
            base_dir: Base directory for downloads
            
        Returns:
            Dictionary with download results
        """
        results = {
            'successful': [],
            'failed': [],
            'total': len(urls)
        }
        
        for i, url in enumerate(urls):
            # Generate filename from URL or index
            filename = f"{i+1:03d}.jpg"  # Default to jpg, could be extracted from URL
            save_path = base_dir / filename
            
            print(f"Downloading image {i+1}/{len(urls)}")
            
            if self.download_high_res_image(url, save_path):
                results['successful'].append(save_path)
            else:
                results['failed'].append({'url': url, 'path': save_path})
        
        return results
    
    def download_images_concurrent(self, urls: list, base_dir: Path) -> dict:
        """
        Download multiple images concurrently using ThreadPoolExecutor.
        
        Args:
            urls: List of image URLs
            base_dir: Base directory for downloads
            
        Returns:
            Dictionary with download results
        """
        results = {
            'successful': [],
            'failed': [],
            'total': len(urls)
        }
        
        # Create parent directory
        base_dir.mkdir(parents=True, exist_ok=True)
        
        def download_single_image(args):
            """Helper function for concurrent downloads."""
            index, url = args
            filename = f"{index+1:03d}.jpg"
            save_path = base_dir / filename
            
            success = self.download_high_res_image(url, save_path)
            return success, url, save_path, filename
        
        # Prepare arguments for concurrent execution
        download_args = [(i, url) for i, url in enumerate(urls)]
        
        print(f"Downloading {len(urls)} images with {self.max_workers} concurrent workers...")
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_args = {
                executor.submit(download_single_image, args): args 
                for args in download_args
            }
            
            # Create progress bar
            with tqdm(total=len(urls), desc="Downloading images") as pbar:
                for future in as_completed(future_to_args):
                    try:
                        success, url, save_path, filename = future.result()
                        
                        if success:
                            results['successful'].append(save_path)
                            pbar.set_postfix({"status": "✓", "file": filename})
                        else:
                            results['failed'].append({'url': url, 'path': save_path})
                            pbar.set_postfix({"status": "✗", "file": filename})
                            
                    except Exception as e:
                        args = future_to_args[future]
                        index, url = args
                        filename = f"{index+1:03d}.jpg"
                        save_path = base_dir / filename
                        results['failed'].append({'url': url, 'path': save_path, 'error': str(e)})
                        pbar.set_postfix({"status": "✗", "file": filename})
                    
                    pbar.update(1)
        
        return results
    
    def get_image_info(self, url: str) -> dict:
        """
        Get information about an image without downloading it.
        
        Args:
            url: URL of the image
            
        Returns:
            Dictionary with image information
        """
        try:
            response = self.session.head(url, allow_redirects=True)
            response.raise_for_status()
            
            return {
                'content_length': response.headers.get('content-length'),
                'content_type': response.headers.get('content-type'),
                'size_mb': int(response.headers.get('content-length', 0)) / (1024 * 1024) if response.headers.get('content-length') else None
            }
        except requests.RequestException as e:
            return {'error': str(e)}
