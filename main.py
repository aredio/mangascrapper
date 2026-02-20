#!/usr/bin/env python3
"""
MangaDex Chapter Downloader
Handles MangaDex Chapter UUIDs and creates folders for chapter downloads.
"""

import os
import uuid
import time
import re
import shutil
from pathlib import Path
from tqdm import tqdm
from md_client import MangaDexDownloader
from downloader import HighResDownloader
# from enhacer import MangaEnhancer  # Commented out due to dependency issues
from exporter import MangaExporter


class MangaDownloader:
    def __init__(self, base_download_dir="downloads"):
        self.base_download_dir = Path(base_download_dir)
        self.base_download_dir.mkdir(exist_ok=True)
        self.api_client = MangaDexDownloader()
        self.image_downloader = HighResDownloader()
    
    def download_chapter_images_high_res(self, chapter_id: str, chapter_dir: Path) -> bool:
        """Download high-quality images for a chapter."""
        try:
            print(f"Fetching high-quality image URLs for chapter {chapter_id}...")
            base_url, image_urls = self.api_client.get_chapter_assets(chapter_id)
            
            print(f"Downloading {len(image_urls)} high-quality images concurrently...")
            
            # Download images concurrently
            results = self.image_downloader.download_images_concurrent(image_urls, chapter_dir)
            
            if results['successful']:
                print(f"Successfully downloaded {len(results['successful'])} high-quality images")
                
                # Report any failures
                if results['failed']:
                    print(f"Failed to download {len(results['failed'])} images:")
                    for failure in results['failed']:
                        print(f"  - {failure.get('path', 'Unknown file')}")
                
                # Enhancement temporarily disabled due to dependency issues
                # print("Starting enhancement for downloaded images...")
                # enhancer = MangaEnhancer()
                # enhancer.process_chapter(chapter_dir)
                # print("✓ Chapter enhancement completed")
                
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
    
    def create_chapter_folder_structure_enhanced(self, chapter_id: str, base_dir: Path) -> Path:
        """
        Create enhanced folder structure with volume or chapter grouping.
        
        Args:
            chapter_id: Chapter UUID
            base_dir: Base download directory
            
        Returns:
            Path to the created chapter folder
        """
        try:
            chapter_info = self.api_client.get_chapter_info(chapter_id)
            attr = chapter_info.get('attributes', {})
            
            volume = attr.get('volume')
            chapter = attr.get('chapter')
            
            # Build folder path
            folder_parts = []
            
            if volume and volume.strip():
                # Use volume-based structure: Volume_XX/Chapter_YY/
                volume_num = int(float(volume)) if volume.replace('.', '').isdigit() else volume
                folder_parts.append(f"Volume_{volume_num:02d}" if isinstance(volume_num, int) else f"Volume_{volume}")
                
                if chapter and chapter.strip():
                    chapter_num = int(float(chapter)) if chapter.replace('.', '').isdigit() else chapter
                    if isinstance(chapter_num, int):
                        folder_parts.append(f"Chapter_{chapter_num:03d}")
                    else:
                        folder_parts.append(f"Chapter_{chapter}")
                else:
                    folder_parts.append(f"Chapter_{chapter_id[:8]}")
            else:
                # Group chapters by tens: Chapters_001-010/Chapter_003/, etc.
                if chapter and chapter.strip():
                    # Handle fractional chapter numbers like 15.5
                    try:
                        chapter_num = float(chapter)
                        base_chapter_num = int(chapter_num)  # Get base number (15.5 -> 15)
                        
                        # Calculate chapter group (1-10, 11-20, etc.) using base number
                        group_start = ((base_chapter_num - 1) // 10) * 10 + 1
                        group_end = group_start + 9
                        group_folder = f"Chapters_{group_start:03d}-{group_end:03d}"
                        folder_parts.append(group_folder)
                        
                        # Use the full chapter number for the chapter folder (including decimals)
                        if chapter_num.is_integer():
                            folder_parts.append(f"Chapter_{int(chapter_num):03d}")
                        else:
                            # For fractional chapters, preserve the decimal but zero-pad the integer part
                            int_part = int(chapter_num)
                            decimal_part = str(chapter_num).split('.')[1] if '.' in str(chapter_num) else '0'
                            folder_parts.append(f"Chapter_{int_part:03d}.{decimal_part}")
                    except (ValueError, TypeError):
                        # Fallback for non-numeric chapters
                        folder_parts.append("Chapters_Unknown")
                        folder_parts.append(f"Chapter_{chapter_id[:8]}")
                else:
                    # Fallback for chapters without numbers
                    folder_parts.append("Chapters_Unknown")
                    folder_parts.append(f"Chapter_{chapter_id[:8]}")
            
            chapter_dir = base_dir / Path(*folder_parts)
            chapter_dir.mkdir(parents=True, exist_ok=True)
            
            return chapter_dir
            
        except Exception as e:
            print(f"Error creating enhanced folder structure: {e}")
            # Fallback to simple UUID-based folder
            fallback_dir = base_dir / chapter_id
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir
    
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
    
    def extract_manga_id_from_url(self, url_or_uuid: str) -> str:
        """Extract manga ID from MangaDex URL or return UUID if it's already a UUID."""
        # Check if it's already a UUID
        try:
            uuid.UUID(url_or_uuid)
            # If it's a UUID, determine if it's a chapter or manga UUID
            if len(url_or_uuid) == 36:  # Full UUID length
                return url_or_uuid
        except ValueError:
            pass
        
        # Extract UUID from MangaDex URL
        # Pattern: https://mangadex.org/chapter/uuid or https://mangadex.org/title/uuid
        patterns = [
            r'mangadex\.org/chapter/([a-f0-9-]{36})',
            r'mangadex\.org/title/([a-f0-9-]{36})',
            r'mangadex\.org/manga/([a-f0-9-]{36})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url_or_uuid)
            if match:
                return match.group(1)
        
        # If no pattern matches, assume it's a UUID
        return url_or_uuid
    
    def get_manga_id_from_input(self, url_or_uuid: str) -> str:
        """Get manga ID from user input (URL or UUID)."""
        extracted_id = self.extract_manga_id_from_url(url_or_uuid)
        
        try:
            # Try to get manga info directly
            manga_url = f"https://api.mangadex.org/manga/{extracted_id}"
            response = self.api_client.session.get(manga_url)
            if response.status_code == 200:
                print(f"Found manga directly: {extracted_id}")
                return extracted_id
        except:
            pass
        
        try:
            # Try to get chapter info and extract manga ID from relationships
            chapter_info = self.api_client.get_chapter_info(extracted_id)
            for rel in chapter_info.get('relationships', []):
                if rel.get('type') == 'manga':
                    manga_id = rel['id']
                    print(f"Found manga ID from chapter: {manga_id}")
                    return manga_id
        except Exception as e:
            print(f"Error getting manga ID from chapter: {e}")
        
        raise ValueError(f"Could not extract manga ID from: {url_or_uuid}")
    
    def get_download_queue(self, manga_id: str) -> list:
        """Get the download queue for a manga (pt-br chapters in ascending order)."""
        print(f"Fetching download queue for manga {manga_id}...")
        
        # Get raw manga feed
        try:
            feed_url = f"https://api.mangadex.org/manga/{manga_id}/feed"
            params = {
                'translatedLanguage[]': 'pt-br',
                'order[chapter]': 'asc'
            }
            
            response = self.api_client.session.get(feed_url, params=params)
            response.raise_for_status()
            
            feed_data = response.json()
            chapters = feed_data.get('data', [])
            
            if not chapters:
                print("No chapters found in pt-br for this manga")
                return []
            
            # Group chapters by chapter number to find best version
            chapter_groups = {}
            for chapter in chapters:
                attrs = chapter.get('attributes', {})
                chapter_num = attrs.get('chapter')
                
                if chapter_num:
                    if chapter_num not in chapter_groups:
                        chapter_groups[chapter_num] = []
                    chapter_groups[chapter_num].append(chapter)
            
            # Select best chapter for each group
            best_chapters = []
            for chapter_num, group in chapter_groups.items():
                best_chapter = self.image_downloader.get_best_chapter_group(group)
                if best_chapter:
                    best_chapters.append(best_chapter)
            
            # Sort by chapter number
            def sort_key(chapter):
                chapter_num = chapter.get('attributes', {}).get('chapter', '0')
                try:
                    return float(chapter_num)
                except:
                    return 0
            
            best_chapters.sort(key=sort_key)
            
            # Extract chapter IDs
            chapter_queue = [chapter['id'] for chapter in best_chapters]
            
            print(f"Download queue created with {len(chapter_queue)} chapters (best versions selected)")
            return chapter_queue
            
        except Exception as e:
            print(f"Error creating download queue: {e}")
            return []
    
    def download_manga_queue(self, manga_id: str):
        """Download all chapters from a manga feed queue and export per volume/group."""
        # Get the download queue with best chapter selection
        chapter_queue = self.get_download_queue(manga_id)
        
        if not chapter_queue:
            print("No chapters found to download")
            return
        
        # Get manga title for folder structure
        manga_title = self.get_manga_title(chapter_queue[0])
        manga_title = ''.join(c for c in manga_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        manga_base_dir = self.base_download_dir / manga_title
        
        # Print folder structure summary
        self.image_downloader.print_folder_structure_summary(manga_title, chapter_queue, manga_base_dir)
        
        # Initialize exporter
        exporter = MangaExporter()
        
        # Track completed volumes/groups for export
        completed_groups = set()
        successful_downloads = 0
        failed_downloads = 0
        
        for i, chapter_id in enumerate(chapter_queue):
            print(f"\n=== Processing Chapter {i+1}/{len(chapter_queue)}: {chapter_id} ===")
            
            try:
                # Create enhanced chapter folder structure
                chapter_dir = self.create_chapter_folder_structure_enhanced(chapter_id, manga_base_dir)
                print(f"Chapter directory: {chapter_dir}")
                
                # Download with verification and high-quality assets
                success = self.image_downloader.download_chapter_with_verification(chapter_id, chapter_dir)
                
                if success:
                    successful_downloads += 1
                    print(f"✓ Successfully downloaded chapter {i+1}")
                    
                    # Check if the volume/group is now complete and export it
                    group_folder = chapter_dir.parent  # This is the Volume_X or Chapters_XXX-YYY folder
                    group_name = group_folder.name
                    
                    # Count chapters in this group
                    chapters_in_group = len([d for d in group_folder.iterdir() if d.is_dir()])
                    
                    # Determine if this group should be exported
                    should_export = False
                    
                    if group_name.startswith("Volume_"):
                        # For volumes, we need to check if all chapters for this volume are downloaded
                        # This is complex, so we'll export when we reach the last chapter in queue for this volume
                        # or when we detect the volume is "complete" based on chapter count
                        volume_chapters = [c for c in chapter_queue if self._get_volume_for_chapter(c) == group_name]
                        downloaded_volume_chapters = len([d for d in group_folder.iterdir() if d.is_dir()])
                        should_export = downloaded_volume_chapters == len(volume_chapters)
                    else:
                        # For grouped chapters (Chapters_XXX-YYY), export when we have 10 chapters or reach the end
                        group_range = group_name.split('_')[1]  # Extract "001-010" from "Chapters_001-010"
                        if group_range:
                            start_num = int(group_range.split('-')[0])
                            end_num = int(group_range.split('-')[1])
                            expected_count = end_num - start_num + 1
                            should_export = chapters_in_group == expected_count
                    
                    # Also export if this is the last chapter in the entire queue
                    if i == len(chapter_queue) - 1:
                        should_export = True
                    
                    if should_export and group_name not in completed_groups:
                        print(f"\n--- Exporting completed {group_name} ---")
                        try:
                            # Export to CBZ and PDF
                            exporter.export_to_cbz(str(group_folder), manga_title, group_name)
                            exporter.export_to_pdf(str(group_folder), manga_title, group_name)
                            
                            # Clean up raw image folders to save space
                            print(f"Cleaning up raw images in {group_folder}...")
                            for chapter_subdir in group_folder.iterdir():
                                if chapter_subdir.is_dir():
                                    try:
                                        shutil.rmtree(chapter_subdir)
                                        print(f"  Removed: {chapter_subdir.name}")
                                    except Exception as e:
                                        print(f"  Failed to remove {chapter_subdir.name}: {e}")
                            
                            completed_groups.add(group_name)
                            print(f"✓ Exported {group_name}")
                            
                        except Exception as e:
                            print(f"✗ Failed to export {group_name}: {e}")
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
        print(f"Exported volumes/groups: {len(completed_groups)}")
        
        # Export any remaining groups that weren't exported during the loop
        remaining_groups = []
        for group_folder in manga_base_dir.iterdir():
            if group_folder.is_dir() and group_folder.name not in completed_groups:
                remaining_groups.append(group_folder)
        
        if remaining_groups:
            print(f"\n=== Exporting Remaining Groups ===")
            for group_folder in remaining_groups:
                group_name = group_folder.name
                print(f"\n--- Exporting remaining {group_name} ---")
                try:
                    exporter.export_to_cbz(str(group_folder), manga_title, group_name)
                    exporter.export_to_pdf(str(group_folder), manga_title, group_name)
                    
                    # Clean up
                    for chapter_subdir in group_folder.iterdir():
                        if chapter_subdir.is_dir():
                            try:
                                shutil.rmtree(chapter_subdir)
                                print(f"  Removed: {chapter_subdir.name}")
                            except Exception as e:
                                print(f"  Failed to remove {chapter_subdir.name}: {e}")
                    
                    print(f"✓ Exported {group_name}")
                except Exception as e:
                    print(f"✗ Failed to export {group_name}: {e}")
        
        print(f"\n=== Complete Workflow Finished ===")
        print(f"Downloaded, enhanced, and exported manga to CBZ and PDF formats")
    
    def _get_volume_for_chapter(self, chapter_id: str) -> str:
        """Helper method to determine which volume a chapter belongs to."""
        try:
            url = f"https://api.mangadex.org/chapter/{chapter_id}"
            response = self.api_client.session.get(url)
            if response.status_code == 200:
                data = response.json()
                attrs = data.get('data', {}).get('attributes', {})
                volume = attrs.get('volume')
                if volume and volume.strip():
                    return f"Volume_{int(float(volume)):02d}"
        except:
            pass
        return None
    
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
                # Create enhanced chapter folder structure
                chapter_dir = self.create_chapter_folder_structure_enhanced(current_chapter_id, manga_base_dir)
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


def main_workflow():
    """Main workflow that combines downloading and export."""
    downloader = MangaDownloader()
    # enhancer = MangaEnhancer()  # Temporarily disabled due to dependency issues
    
    print("=== MangaDex Downloader Workflow ===")
    print("Enter a MangaDex URL or Chapter UUID to download and export")
    print("Examples:")
    print("  - https://mangadex.org/chapter/d9f90199-79fb-403f-a313-a054f1a77b0c")
    print("  - https://mangadex.org/title/a9232d4b-9e89-49bb-bb7c-3a0c6e4b5c1a")
    print("  - d9f90199-79fb-403f-a313-a054f1a77b0c")
    print()
    
    # Get user input
    user_input = input("Enter MangaDex URL or Chapter UUID: ").strip()
    
    if not user_input:
        print("No input provided. Exiting.")
        return
    
    try:
        # Extract manga ID from user input
        manga_id = downloader.get_manga_id_from_input(user_input)
        
        # Get manga title for display
        try:
            manga_url = f"https://api.mangadex.org/manga/{manga_id}"
            response = downloader.api_client.session.get(manga_url)
            if response.status_code == 200:
                manga_data = response.json()
                attributes = manga_data.get('data', {}).get('attributes', {})
                title = attributes.get('title', {})
                manga_title = title.get('en') or title.get('ja') or list(title.values())[0] if title else "Unknown Manga"
                print(f"\nManga: {manga_title}")
        except:
            manga_title = "Unknown Manga"
        
        # Get download queue
        download_queue = downloader.get_download_queue(manga_id)
        
        if not download_queue:
            print("No chapters found to download.")
            return
        
        print(f"\nFound {len(download_queue)} chapters in pt-br")
        print("Starting download and export workflow...")
        
        # Download chapters (enhancement temporarily disabled)
        downloader.download_manga_queue(manga_id)
        
        print(f"\n=== Complete Workflow Finished ===")
        print(f"Downloaded and exported manga to CBZ and PDF formats")
        print("Note: Enhancement temporarily disabled due to dependency issues")
        
    except KeyboardInterrupt:
        print("\nWorkflow interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        print("Please check your input and try again.")


def main():
    """Main function to download manga chapters."""
    downloader = MangaDownloader()
    
    print("=== MangaDex Chapter Downloader ===")
    print("Choose workflow:")
    print("1. Download only")
    print("2. Download + Export (recommended)")
    print("Note: Enhancement temporarily disabled due to dependency issues")
    
    choice = input("Enter choice (1 or 2, default=2): ").strip()
    
    if choice == "1":
        # Original download workflow
        print("\n=== Download Only Mode ===")
        print("Enter a MangaDex URL or Chapter UUID to download")
        print("Examples:")
        print("  - https://mangadex.org/chapter/d9f90199-79fb-403f-a313-a054f1a77b0c")
        print("  - https://mangadex.org/title/a9232d4b-9e89-49bb-bb7c-3a0c6e4b5c1a")
        print("  - d9f90199-79fb-403f-a313-a054f1a77b0c")
        print()
        
        # Get user input
        user_input = input("Enter MangaDex URL or Chapter UUID: ").strip()
        
        if not user_input:
            print("No input provided. Exiting.")
            return
        
        try:
            # Extract manga ID from user input
            manga_id = downloader.get_manga_id_from_input(user_input)
            
            # Get manga title for display
            try:
                manga_url = f"https://api.mangadex.org/manga/{manga_id}"
                response = downloader.api_client.session.get(manga_url)
                if response.status_code == 200:
                    manga_data = response.json()
                    attributes = manga_data.get('data', {}).get('attributes', {})
                    title = attributes.get('title', {})
                    manga_title = title.get('en') or title.get('ja') or list(title.values())[0] if title else "Unknown Manga"
                    print(f"\nManga: {manga_title}")
            except:
                manga_title = "Unknown Manga"
            
            # Get download queue
            download_queue = downloader.get_download_queue(manga_id)
            
            if not download_queue:
                print("No chapters found to download.")
                return
            
            print(f"\nFound {len(download_queue)} chapters in pt-br")
            print("Starting download...")
            
            # Start the download
            downloader.download_manga_queue(manga_id)
            
        except KeyboardInterrupt:
            print("\nDownload interrupted by user")
        except Exception as e:
            print(f"Error: {e}")
            print("Please check your input and try again.")
    else:
        # Download + enhance workflow
        main_workflow()


if __name__ == "__main__":
    main()
