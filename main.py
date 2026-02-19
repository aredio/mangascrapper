#!/usr/bin/env python3
"""
MangaDex Chapter Downloader
Handles MangaDex Chapter UUIDs and creates folders for chapter downloads.
"""

import os
import uuid
import time
from pathlib import Path
from tqdm import tqdm
from md_client import MangaDexDownloader
from downloader import HighResDownloader


class MangaDownloader:
    def __init__(self, base_download_dir="downloads"):
        self.base_download_dir = Path(base_download_dir)
        self.base_download_dir.mkdir(exist_ok=True)
        self.api_client = MangaDexDownloader()
        self.image_downloader = HighResDownloader()
    
    def download_chapter_images_high_res(self, chapter_id: str, chapter_dir: Path) -> bool:
        """Download high-quality images for a chapter using concurrent downloads."""
        try:
            print(f"Fetching high-quality image URLs for chapter {chapter_id}...")
            base_url, image_urls = self.api_client.get_chapter_assets(chapter_id)
            
            print(f"Downloading {len(image_urls)} high-quality images concurrently...")
            
            # Use concurrent download method
            results = self.image_downloader.download_images_concurrent(image_urls, chapter_dir)
            
            if results['successful']:
                print(f"Successfully downloaded {len(results['successful'])} high-quality images")
                
                # Report any failures
                if results['failed']:
                    print(f"Failed to download {len(results['failed'])} images:")
                    for failure in results['failed']:
                        print(f"  - {failure.get('path', 'Unknown file')}")
                
                return len(results['failed']) == 0  # Return True only if all succeeded
            else:
                print("No images were downloaded successfully")
                return False
            
        except Exception as e:
            print(f"Error downloading high-quality chapter images: {e}")
            return False
    
    def get_manga_title(self, chapter_id: str) -> str:
        """Get manga title for folder naming."""
        try:
            chapter_info = self.api_client.get_chapter_info(chapter_id)
            
            # Find manga relationship
            for rel in chapter_info.get('relationships', []):
                if rel.get('type') == 'manga':
                    manga_id = rel['id']
                    # Get manga details
                    manga_url = f"https://api.mangadex.org/manga/{manga_id}"
                    response = self.api_client.session.get(manga_url)
                    if response.status_code == 200:
                        manga_data = response.json()
                        attributes = manga_data.get('data', {}).get('attributes', {})
                        title = attributes.get('title', {})
                        # Prefer English title, fallback to first available
                        return title.get('en') or title.get('ja') or list(title.values())[0] if title else "Unknown Manga"
            
            return "Unknown Manga"
        except Exception as e:
            print(f"Error getting manga title: {e}")
            return "Unknown Manga"
    
    def get_full_manga_feed(self, manga_id: str) -> list:
        """Get the complete manga feed with pt-br chapters in order."""
        try:
            print(f"Fetching full manga feed for {manga_id}...")
            chapters = self.api_client.get_manga_feed(manga_id, "pt-br")
            
            # Extract chapter IDs in order
            chapter_ids = [chapter['id'] for chapter in chapters]
            
            print(f"Found {len(chapter_ids)} chapters in pt-br")
            return chapter_ids
            
        except Exception as e:
            print(f"Error fetching manga feed: {e}")
            return []
    
    def download_manga_queue(self, manga_id: str):
        """Download all chapters from a manga feed queue."""
        # Get the download queue
        chapter_queue = self.get_full_manga_feed(manga_id)
        
        if not chapter_queue:
            print("No chapters found to download")
            return
        
        # Get manga title for folder structure
        manga_title = self.get_manga_title(chapter_queue[0])
        manga_title = ''.join(c for c in manga_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        manga_base_dir = self.base_download_dir / manga_title
        
        print(f"\nStarting download for: {manga_title}")
        print(f"Download queue: {len(chapter_queue)} chapters")
        
        successful_downloads = 0
        failed_downloads = 0
        
        for i, chapter_id in enumerate(chapter_queue):
            print(f"\n=== Processing Chapter {i+1}/{len(chapter_queue)}: {chapter_id} ===")
            
            try:
                # Create chapter folder structure
                chapter_dir = self.api_client.create_chapter_folder_structure(chapter_id, manga_base_dir)
                print(f"Chapter directory: {chapter_dir}")
                
                # Download high-quality images
                success = self.download_chapter_images_high_res(chapter_id, chapter_dir)
                
                if success:
                    successful_downloads += 1
                    print(f"✓ Successfully downloaded chapter {i+1}")
                else:
                    failed_downloads += 1
                    print(f"✗ Failed to download chapter {i+1}")
                
                # Be polite to the API
                if i < len(chapter_queue) - 1:  # Don't sleep after the last chapter
                    print("Waiting 1 second before next chapter...")
                    time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nDownload interrupted by user")
                break
            except Exception as e:
                failed_downloads += 1
                print(f"Error processing chapter {chapter_id}: {e}")
                continue
        
        print(f"\n=== Download Summary ===")
        print(f"Total chapters: {len(chapter_queue)}")
        print(f"Successful: {successful_downloads}")
        print(f"Failed: {failed_downloads}")
        print(f"Completed: {successful_downloads + failed_downloads}")
    
    def download_chapters_sequence(self, start_chapter_id: str):
        """Download a sequence of chapters starting from the given ID."""
        current_chapter_id = start_chapter_id
        chapter_count = 0
        
        # Get manga title for folder structure
        manga_title = self.get_manga_title(current_chapter_id)
        manga_title = ''.join(c for c in manga_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        manga_base_dir = self.base_download_dir / manga_title
        
        print(f"Starting download for: {manga_title}")
        
        while current_chapter_id:
            chapter_count += 1
            print(f"\n=== Processing Chapter {chapter_count}: {current_chapter_id} ===")
            
            try:
                # Create chapter folder structure
                chapter_dir = self.api_client.create_chapter_folder_structure(current_chapter_id, manga_base_dir)
                print(f"Chapter directory: {chapter_dir}")
                
                # Download high-quality images
                success = self.download_chapter_images_high_res(current_chapter_id, chapter_dir)
                
                if not success:
                    print(f"Failed to download chapter {current_chapter_id}, stopping...")
                    break
                
                # Find next chapter
                print("Finding next chapter...")
                next_chapter_id = self.api_client.get_next_chapter(current_chapter_id)
                
                if not next_chapter_id:
                    print("Finished - No more chapters found")
                    break
                
                print(f"Next chapter: {next_chapter_id}")
                current_chapter_id = next_chapter_id
                
                # Be polite to the API
                print("Waiting 1 second before next chapter...")
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nDownload interrupted by user")
                break
            except Exception as e:
                print(f"Error processing chapter {current_chapter_id}: {e}")
                break
        
        print(f"\nDownload completed. Processed {chapter_count} chapters.")


def main():
    """Main function to download manga chapters."""
    downloader = MangaDownloader()
    
    # Option 1: Start with the provided UUID (sequential download)
    start_uuid = "d9f90199-79fb-403f-a313-a054f1a77b0c"
    
    # Option 2: Get manga ID and download full queue
    # First get the manga ID from the chapter
    try:
        chapter_info = downloader.api_client.get_chapter_info(start_uuid)
        manga_id = None
        for rel in chapter_info.get('relationships', []):
            if rel.get('type') == 'manga':
                manga_id = rel['id']
                break
        
        if manga_id:
            print(f"Found manga ID: {manga_id}")
            print("Choose download method:")
            print("1. Sequential from starting chapter")
            print("2. Full manga queue (recommended)")
            
            choice = input("Enter choice (1 or 2, default=2): ").strip()
            
            if choice == "1":
                downloader.download_chapters_sequence(start_uuid)
            else:
                downloader.download_manga_queue(manga_id)
        else:
            print("Could not find manga ID, falling back to sequential download")
            downloader.download_chapters_sequence(start_uuid)
            
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
