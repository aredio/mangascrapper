#!/usr/bin/env python3
"""
High-Resolution Image Downloader
Handles downloading of high-quality manga images with progress tracking and retry logic.
"""

import requests
import time
from pathlib import Path
from typing import Optional, List, Dict
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
    
    def verify_chapter_language(self, chapter_id: str) -> bool:
        """
        Verify that chapter is translated to pt-br.
        
        Args:
            chapter_id: Chapter UUID
            
        Returns:
            True if chapter is pt-br, False otherwise
        """
        try:
            url = f"https://api.mangadex.org/chapter/{chapter_id}"
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            attributes = data.get('data', {}).get('attributes', {})
            translated_lang = attributes.get('translatedLanguage')
            
            return translated_lang == 'pt-br'
            
        except Exception as e:
            print(f"Error verifying chapter language: {e}")
            return False
    
    def get_best_chapter_group(self, chapter_feed: List[Dict]) -> Optional[Dict]:
        """
        Select the best chapter group from multiple groups providing same translation.
        
        Args:
            chapter_feed: List of chapter dictionaries from manga feed
            
        Returns:
            Best chapter dictionary or None
        """
        if not chapter_feed:
            return None
        
        # Filter only pt-br chapters
        pt_br_chapters = [
            ch for ch in chapter_feed 
            if ch.get('attributes', {}).get('translatedLanguage') == 'pt-br'
        ]
        
        if not pt_br_chapters:
            return None
        
        # Sort by version (highest first), then by creation date (newest first)
        def sort_key(chapter):
            attrs = chapter.get('attributes', {})
            version = attrs.get('version', 0)
            created_at = attrs.get('createdAt', '')
            return (-version, created_at)
        
        pt_br_chapters.sort(key=sort_key)
        
        return pt_br_chapters[0]  # Return the best one
    
    def print_folder_structure_summary(self, manga_title: str, chapter_queue: List[str], manga_base_dir: Path):
        """
        Print a summary of the folder structure before starting download.
        
        Args:
            manga_title: Title of the manga
            chapter_queue: List of chapter IDs to download
            manga_base_dir: Base directory for downloads
        """
        print(f"\n=== Folder Structure Summary ===")
        print(f"Manga: {manga_title}")
        print(f"Base Directory: {manga_base_dir}")
        print(f"Total Chapters: {len(chapter_queue)}")
        print(f"Language: pt-br (Portuguese Brazilian)")
        print(f"Image Quality: High (original size)")
        print(f"Concurrent Downloads: {self.max_workers} workers")
        
        # Try to show sample folder structure
        try:
            if len(chapter_queue) > 0:
                # Get info for first few chapters to show structure pattern
                sample_chapters = chapter_queue[:3] if len(chapter_queue) >= 3 else chapter_queue
                
                print(f"\nSample Folder Structure:")
                for i, chapter_id in enumerate(sample_chapters):
                    try:
                        url = f"https://api.mangadex.org/chapter/{chapter_id}"
                        response = self.session.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            attrs = data.get('data', {}).get('attributes', {})
                            volume = attrs.get('volume')
                            chapter = attrs.get('chapter')
                            
                            if volume and volume.strip():
                                volume_num = int(float(volume))
                                if chapter and chapter.strip():
                                    try:
                                        ch_num = float(chapter)
                                        if ch_num.is_integer():
                                            print(f"  Volume_{volume_num:02d}/Chapter_{int(ch_num):03d}/")
                                        else:
                                            int_part = int(ch_num)
                                            decimal_part = str(ch_num).split('.')[1] if '.' in str(ch_num) else '0'
                                            print(f"  Volume_{volume_num:02d}/Chapter_{int_part:03d}.{decimal_part}/")
                                    except:
                                        print(f"  Volume_{volume_num:02d}/Chapter_{chapter}/")
                                else:
                                    print(f"  Volume_{volume_num:02d}/Chapter_{chapter_id[:8]}/")
                            else:
                                if chapter and chapter.strip():
                                    try:
                                        ch_num = float(chapter)
                                        base_chapter_num = int(ch_num)  # Get base number for grouping
                                        
                                        # Calculate chapter group using base number
                                        group_start = ((base_chapter_num - 1) // 10) * 10 + 1
                                        group_end = group_start + 9
                                        
                                        if ch_num.is_integer():
                                            print(f"  Chapters_{group_start:03d}-{group_end:03d}/Chapter_{int(ch_num):03d}/")
                                        else:
                                            int_part = int(ch_num)
                                            decimal_part = str(ch_num).split('.')[1] if '.' in str(ch_num) else '0'
                                            print(f"  Chapters_{group_start:03d}-{group_end:03d}/Chapter_{int_part:03d}.{decimal_part}/")
                                    except:
                                        print(f"  Chapters_Unknown/Chapter_{chapter}/")
                                else:
                                    print(f"  Chapters_Unknown/Chapter_{chapter_id[:8]}/")
                    except:
                        print(f"  Chapter_{chapter_id[:8]}/")
                
                if len(chapter_queue) > 3:
                    print(f"  ... and {len(chapter_queue) - 3} more chapters")
        
        except Exception as e:
            print(f"Could not generate folder structure preview: {e}")
        
        print("=" * 40)
    
    def download_chapter_with_verification(self, chapter_id: str, base_dir: Path) -> bool:
        """
        Download chapter with language verification and high-quality assets.
        
        Args:
            chapter_id: Chapter UUID
            base_dir: Directory to save images
            
        Returns:
            True if successful, False otherwise
        """
        # Verify language first
        if not self.verify_chapter_language(chapter_id):
            print(f"Skipping chapter {chapter_id}: Not pt-br language")
            return False
        
        # Get high-quality assets
        try:
            manga_url = f"https://api.mangadex.org/at-home/server/{chapter_id}"
            response = self.session.get(manga_url)
            response.raise_for_status()
            
            data = response.json()
            
            if 'baseUrl' not in data or 'chapter' not in data:
                print(f"Invalid response format for chapter {chapter_id}")
                return False
            
            chapter_info = data['chapter']
            if 'hash' not in chapter_info or 'data' not in chapter_info:
                print(f"Invalid chapter data format for chapter {chapter_id}")
                return False
            
            base_url = data['baseUrl']
            chapter_hash = chapter_info['hash']
            filenames = chapter_info['data']  # Use high-quality data array
            
            # Build full image URLs
            image_urls = []
            for filename in filenames:
                full_url = f"{base_url}/data/{chapter_hash}/{filename}"
                image_urls.append(full_url)
            
            # Download images concurrently
            results = self.download_images_concurrent(image_urls, base_dir)
            
            return len(results['successful']) > 0
            
        except Exception as e:
            print(f"Error downloading chapter {chapter_id}: {e}")
            return False
