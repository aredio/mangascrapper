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


class MangaDownloader:
    def __init__(self, base_download_dir="downloads"):
        self.base_download_dir = Path(base_download_dir)
        self.base_download_dir.mkdir(exist_ok=True)
        self.api_client = MangaDexDownloader()
    
    def download_chapter_images(self, chapter_id: str, chapter_dir: Path) -> bool:
        """Download all images for a chapter to the specified directory."""
        try:
            print(f"Fetching image list for chapter {chapter_id}...")
            base_url, chapter_hash, filenames = self.api_client.get_chapter_data(chapter_id)
            
            print(f"Downloading {len(filenames)} images...")
            
            # Download each image with progress bar
            for i, filename in enumerate(tqdm(filenames, desc="Downloading pages")):
                image_url = self.api_client.build_page_url(base_url, chapter_hash, filename)
                save_path = chapter_dir / f"{i+1:03d}_{filename}"
                
                success = self.api_client.download_page(image_url, save_path)
                if not success:
                    print(f"Failed to download {filename}")
                    return False
            
            print(f"Successfully downloaded {len(filenames)} images")
            return True
            
        except Exception as e:
            print(f"Error downloading chapter images: {e}")
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
                
                # Download images
                success = self.download_chapter_images(current_chapter_id, chapter_dir)
                
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
    
    # Start with the provided UUID
    start_uuid = "d9f90199-79fb-403f-a313-a054f1a77b0c"
    
    try:
        downloader.download_chapters_sequence(start_uuid)
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
