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
import subprocess
import logging
import gc
from pathlib import Path
from tqdm import tqdm
from md_client import MangaDexDownloader
from downloader import HighResDownloader
from exporter import MangaExporter

# Setup root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('py_tana_session.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def handle_finished_volume(manga_name, volume_name, raw_folder_path, config):
    """
    Orchestrate post-download processing for a finished volume.
    
    Args:
        manga_name: Name of the manga
        volume_name: Name of the volume/group
        raw_folder_path: Path to the raw downloaded folder
        config: Dictionary containing user choices ('do_upscale', 'export_cbz', 'export_pdf')
    """
    # Validation: Check if folder contains valid image files
    try:
        raw_path = Path(raw_folder_path)
        if not raw_path.exists():
            logger.warning(f"Folder does not exist, skipping: {raw_folder_path}")
            return
        
        # Scan for valid image files
        valid_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
        image_files = []
        
        for file_path in raw_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                image_files.append(file_path)
        
        # If no images found, skip processing and clean up
        if len(image_files) == 0:
            logger.warning(f"Skipping empty/failed folder with no images: {volume_name}")
            try:
                shutil.rmtree(raw_folder_path, ignore_errors=True)
                logger.info(f"Cleaned up empty directory: {raw_folder_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup empty directory {raw_folder_path}: {e}")
            return
        
        logger.info(f"Processing folder with {len(image_files)} images: {volume_name}")
        
    except Exception as e:
        logger.error(f"Error validating folder {raw_folder_path}: {e}")
        return
    
    working_folder = raw_folder_path
    upscaled_folder = None
    
    try:
        # Step 1: Upscaling if requested
        if config.get('do_upscale', False):
            logger.info(f"Starting AI upscaling for {volume_name}...")
            
            # Define upscaled folder path
            upscaled_folder_path = Path(f"upscaled_temp/{manga_name}/{volume_name}")
            # Forcefully create output directory to prevent C++ execution errors
            os.makedirs(upscaled_folder_path, exist_ok=True)
            
            # Run waifu2x binary directly on each chapter subdirectory
            try:
                # Iterate through chapter subdirectories inside raw_folder_path
                processed_chapters = 0
                for item in os.listdir(raw_folder_path):
                    chapter_in = os.path.join(raw_folder_path, item)
                    
                    if os.path.isdir(chapter_in):
                        chapter_out = os.path.join(upscaled_folder_path, item)
                        os.makedirs(chapter_out, exist_ok=True)
                        
                        logger.info(f"Upscaling chapter: {item}")
                        
                        cmd = [
                            'waifu2x-ncnn-vulkan',
                            '-i', str(chapter_in),
                            '-o', str(chapter_out),
                            '-n', '2',
                            '-s', '2',
                            '-f', 'jpg',
                            '-g', '0',
                            '-j', '1:1:1'
                        ]
                        
                        try:
                            subprocess.run(cmd, check=True, capture_output=True, text=True)
                            processed_chapters += 1
                            logger.info(f"✓ Upscaled chapter: {item}")
                        except subprocess.CalledProcessError as e:
                            logger.error(f"Waifu2x failed on {item}: {e.stderr}")
                            raise  # Re-raise to trigger the fallback logic
                
                if processed_chapters > 0:
                    logger.info(f"✓ AI upscaling completed for {volume_name} ({processed_chapters} chapters)")
                    working_folder = upscaled_folder_path
                else:
                    logger.warning(f"No chapters found to upscale in {volume_name}")
                    working_folder = raw_folder_path
                
            except subprocess.CalledProcessError as e:
                logger.error(f"✗ AI upscaling failed for {volume_name}: {e}")
                logger.error(f"stdout: {e.stdout}")
                logger.error(f"stderr: {e.stderr}")
                # Fall back to raw folder if upscaling fails
                working_folder = raw_folder_path
            except Exception as e:
                logger.error(f"✗ Unexpected error during upscaling: {e}")
                working_folder = raw_folder_path
        else:
            working_folder = raw_folder_path
            
        # Step 2: Export if requested
        if config.get('export_cbz', False) or config.get('export_pdf', False):
            logger.info(f"Starting export for {volume_name}...")
            
            exporter = MangaExporter()
            exporter.run_exports(
                source_folder=str(working_folder),
                manga_name=manga_name,
                group_name=volume_name,
                make_cbz=config.get('export_cbz', False),
                make_pdf=config.get('export_pdf', False)
            )
            logger.info(f"✓ Export completed for {volume_name}")
        
        # Step 3: Cleanup if export was performed
        if config.get('export_cbz', False) or config.get('export_pdf', False):
            print(f"Cleaning up raw images in {raw_folder_path}...")
            
            # Delete raw folder
            if os.path.exists(raw_folder_path):
                shutil.rmtree(raw_folder_path)
                print(f"✓ Removed raw folder: {raw_folder_path}")
            
            # Delete upscaled folder if it exists and was used
            if config.get('do_upscale', False) and 'upscaled_folder_path' in locals() and os.path.exists(upscaled_folder_path):
                shutil.rmtree(upscaled_folder_path)
                print(f"✓ Removed upscaled folder: {upscaled_folder_path}")
        
        print(f"✓ Processing completed for {volume_name}")
        
        # Force garbage collection to release unused memory back to OS
        # Clear any temporary variables storing large lists
        working_folder = None
        upscaled_folder_path = None
        
        # Collect garbage to prevent RAM bloat during long sessions
        collected = gc.collect()
        logger.info(f"Garbage collection completed: {collected} objects reclaimed")
        
    except Exception as e:
        logger.error(f"✗ Error processing {volume_name}: {e}")
        # Don't delete folders on error to allow manual recovery


class MangaDownloader:
    def __init__(self, base_download_dir="downloads"):
        self.base_download_dir = Path(base_download_dir)
        self.base_download_dir.mkdir(exist_ok=True)
        self.api_client = MangaDexDownloader()
        self.image_downloader = HighResDownloader(self.api_client)
    
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
    
    def _get_chapter_number_from_id(self, chapter_id: str) -> str:
        """
        Get chapter number from chapter ID by fetching chapter info.
        
        Args:
            chapter_id: The chapter UUID
            
        Returns:
            Chapter number as string, or "unknown" if not found
        """
        try:
            response = self.api_client.session.get(f"https://api.mangadex.org/chapter/{chapter_id}")
            response.raise_for_status()
            
            chapter_data = response.json().get('data', {})
            chapter_attrs = chapter_data.get('attributes', {})
            chapter_num = chapter_attrs.get('chapter')
            
            return chapter_num if chapter_num else "unknown"
            
        except Exception as e:
            logger.warning(f"Error getting chapter number for {chapter_id}: {e}")
            return "unknown"
    
    def _safe_parse_chapter_number(self, chapter_str: str) -> float:
        """
        Safely parse chapter number string to float.
        
        Args:
            chapter_str: Chapter number as string (can be "15.5", "15", etc.)
            
        Returns:
            float: Parsed chapter number, or 0.0 if parsing fails
        """
        try:
            if not chapter_str or chapter_str.strip() == "":
                return 0.0
            return float(chapter_str.strip())
        except (ValueError, TypeError):
            print(f"Aviso: Não foi possível parsear número do capítulo '{chapter_str}'. Usando 0.0")
            return 0.0
    
    def _filter_chapters_by_number(self, chapters: list, start_float: float, end_float: float) -> list:
        """
        Filter chapters by chapter number range.
        
        Args:
            chapters: List of chapter data dictionaries
            start_float: Start chapter number (inclusive)
            end_float: End chapter number (inclusive)
            
        Returns:
            list: Filtered chapter data within the specified range
        """
        filtered_chapters = []
        
        for chapter in chapters:
            try:
                chapter_attrs = chapter.get('attributes', {})
                chapter_num_str = chapter_attrs.get('chapter')
                
                # Parse chapter number safely
                chapter_float = self._safe_parse_chapter_number(chapter_num_str)
                
                # Check if chapter is within range (inclusive)
                if start_float <= chapter_float <= end_float:
                    filtered_chapters.append(chapter)
                    
            except Exception as e:
                logger.warning(f"Error filtering chapter {chapter.get('id', 'unknown')}: {e}")
                # If we can't get chapter info, skip it
                continue
        
        return filtered_chapters
    
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
    
    def get_download_queue_with_data(self, manga_id: str) -> tuple:
        """
        Get the complete download queue with full chapter data for filtering.
        
        Args:
            manga_id: The manga ID to fetch chapters for
            
        Returns:
            tuple: (chapter_ids, chapter_data) where chapter_ids is for existing workflow
                   and chapter_data is for filtering operations
        """
        try:
            limit = 100
            offset = 0
            all_chapters = []
            
            logger.info(f"Fetching chapters for manga {manga_id}...")
            
            while True:
                params = {
                    "limit": limit,
                    "offset": offset,
                    "translatedLanguage[]": ["pt-br"],
                    "order[chapter]": "asc",
                    "includes[]": ["scanlation_group"]
                }

                response = self.api_client.session.get(f"https://api.mangadex.org/manga/{manga_id}/feed", params=params)
                response.raise_for_status()
                
                data = response.json().get("data", [])
                all_chapters.extend(data)
                
                logger.info(f"Fetched {len(data)} chapters (offset: {offset})")
                
                # If the API returned less than our limit, we reached the end of the manga
                if len(data) < limit:
                    break
                    
                # Otherwise, turn the page
                offset += limit

            logger.info(f"Total chapters fetched: {len(all_chapters)}")
            
            if not all_chapters:
                logger.warning("No chapters found in pt-br for this manga")
                return [], []
            
            # Group chapters by chapter number to find best version
            chapter_groups = {}
            for chapter in all_chapters:
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
            
            # Extract chapter IDs for existing workflow
            chapter_ids = [chapter['id'] for chapter in best_chapters]
            
            logger.info(f"Download queue created with {len(chapter_ids)} chapters (best versions selected)")
            return chapter_ids, best_chapters
            
        except Exception as e:
            logger.error(f"Error creating download queue: {e}")
            return [], []
    
    def get_download_queue(self, manga_id: str) -> list:
        """Get the download queue for a manga (pt-br chapters in ascending order)."""
        logger.info(f"Fetching download queue for manga {manga_id}...")
        
        # Get raw manga feed with pagination
        try:
            limit = 100
            offset = 0
            all_chapters = []

            logger.info(f"Buscando lista completa de capítulos na API...")

            while True:
                params = {
                    "limit": limit,
                    "offset": offset,
                    "translatedLanguage[]": ["pt-br"],
                    "order[chapter]": "asc",
                    "includes[]": ["scanlation_group"]
                }

                response = self.api_client.session.get(f"https://api.mangadex.org/manga/{manga_id}/feed", params=params)
                response.raise_for_status()
                
                data = response.json().get("data", [])
                all_chapters.extend(data)
                
                logger.info(f"Fetched {len(data)} chapters (offset: {offset})")
                
                # If the API returned less than our limit, we reached the end of the manga
                if len(data) < limit:
                    break
                    
                # Otherwise, turn the page
                offset += limit

            logger.info(f"Total chapters fetched: {len(all_chapters)}")
            
            if not all_chapters:
                logger.warning("No chapters found in pt-br for this manga")
                return []
            
            # Group chapters by chapter number to find best version
            chapter_groups = {}
            for chapter in all_chapters:
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
            
            logger.info(f"Download queue created with {len(chapter_queue)} chapters (best versions selected)")
            return chapter_queue
            
        except Exception as e:
            logger.error(f"Error creating download queue: {e}")
            return []
    
    def download_manga_queue(self, manga_id: str, config=None):
        """Download all chapters from a manga feed queue and export per volume/group.
        
        Args:
            manga_id: The manga ID to download
            config: Configuration dictionary with 'do_upscale', 'export_cbz', 'export_pdf' keys
        """
        # Default configuration if not provided
        if config is None:
            config = {'do_upscale': False, 'export_cbz': False, 'export_pdf': False}
        # Get the download queue with best chapter selection and full data
        all_chapter_ids, all_chapter_data = self.get_download_queue_with_data(manga_id)
        
        if not all_chapter_ids:
            print("No chapters found to download")
            return
        
        # Chapter Selection Step
        print(f"\n=== Seleção de Capítulos ===")
        print(f"Total de capítulos encontrados: {len(all_chapter_ids)}")
        print("1 - Baixar tudo (Full)")
        print("2 - Baixar capítulo específico")
        print("3 - Baixar um intervalo (Range)")
        
        while True:
            try:
                choice = input("Escolha uma opção (1-3): ").strip()
                if choice in ['1', '2', '3']:
                    break
                else:
                    print("Opção inválida. Escolha 1, 2 ou 3.")
            except KeyboardInterrupt:
                print("\nDownload cancelado pelo usuário.")
                return
        
        filtered_chapter_data = []
        
        if choice == '1':
            # Full download
            filtered_chapter_data = all_chapter_data
            print(f"Opção selecionada: Baixar tudo ({len(filtered_chapter_data)} capítulos)")
            
        elif choice == '2':
            # Specific chapter
            try:
                target_chapter = input("Digite o número do capítulo: ").strip()
                target_float = self._safe_parse_chapter_number(target_chapter)
                
                # Filter chapters by matching chapter number
                filtered_chapter_data = self._filter_chapters_by_number(all_chapter_data, target_float, target_float)
                print(f"Opção selecionada: Capítulo específico {target_chapter} ({len(filtered_chapter_data)} capítulos encontrados)")
                
            except ValueError:
                print("Número de capítulo inválido. Usando download completo.")
                filtered_chapter_data = all_chapter_data
                
        elif choice == '3':
            # Range download
            try:
                start_chapter = input("Digite o capítulo inicial: ").strip()
                end_chapter = input("Digite o capítulo final: ").strip()
                
                start_float = self._safe_parse_chapter_number(start_chapter)
                end_float = self._safe_parse_chapter_number(end_chapter)
                
                if start_float > end_float:
                    print("Capítulo inicial maior que o final. Invertendo...")
                    start_float, end_float = end_float, start_float
                
                # Filter chapters within range
                filtered_chapter_data = self._filter_chapters_by_number(all_chapter_data, start_float, end_float)
                print(f"Opção selecionada: Intervalo {start_chapter} a {end_chapter} ({len(filtered_chapter_data)} capítulos encontrados)")
                
            except ValueError:
                print("Número de capítulo inválido. Usando download completo.")
                filtered_chapter_data = all_chapter_data
        
        if not filtered_chapter_data:
            print("Nenhum capítulo encontrado com os critérios selecionados.")
            return
        
        # Extract chapter IDs from filtered data
        chapter_queue = [chapter['id'] for chapter in filtered_chapter_data]
        print(f"Fila atualizada: {len(chapter_queue)} capítulos selecionados para download.")
        
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
        failed_chapters_summary = []  # Track completely failed chapters
        
        for i, chapter_id in enumerate(chapter_queue):
            print(f"\n=== Processing Chapter {i+1}/{len(chapter_queue)}: {chapter_id} ===")
            
            try:
                # Create enhanced chapter folder structure
                chapter_dir = self.create_chapter_folder_structure_enhanced(chapter_id, manga_base_dir)
                print(f"Chapter directory: {chapter_dir}")
                
                # Get chapter number for fallback logic
                chapter_number = self._get_chapter_number_from_id(chapter_id)
                
                # Download with retry and fallback mechanism
                download_success = False
                
                # Attempt 1: Try original chapter
                try:
                    success = self.image_downloader.download_chapter_with_verification(chapter_id, chapter_dir)
                    if success:
                        download_success = True
                        print(f"✓ Successfully downloaded chapter {i+1}")
                    else:
                        raise Exception("Download verification failed")
                except Exception as e:
                    print(f"⚠️ First attempt failed for chapter {chapter_number}: {e}")
                    
                    # Retry: Wait 10 seconds and try again
                    print("Waiting 10 seconds before retry...")
                    time.sleep(10)
                    
                    try:
                        success = self.image_downloader.download_chapter_with_verification(chapter_id, chapter_dir)
                        if success:
                            download_success = True
                            print(f"✓ Successfully downloaded chapter {i+1} (retry)")
                        else:
                            raise Exception("Download verification failed on retry")
                    except Exception as retry_e:
                        print(f"⚠️ Retry failed for chapter {chapter_number}: {retry_e}")
                        
                        # Fallback Trigger: Try English version
                        print(f"Falha definitiva no capítulo {chapter_number} (pt-br). Buscando fallback em inglês...")
                        
                        fallback_chapter = self.api_client.get_single_chapter_by_number(manga_id, chapter_number, "en")
                        
                        if fallback_chapter:
                            fallback_id = fallback_chapter['id']
                            print(f"Found English fallback: {fallback_id}")
                            
                            try:
                                success = self.image_downloader.download_chapter_with_verification(fallback_id, chapter_dir)
                                if success:
                                    download_success = True
                                    print(f"✓ Successfully downloaded English fallback for chapter {i+1}")
                                else:
                                    raise Exception("English fallback verification failed")
                            except Exception as fallback_e:
                                print(f"⚠️ English fallback also failed: {fallback_e}")
                        else:
                            print(f"⚠️ No English fallback found for chapter {chapter_number}")
                
                if download_success:
                    successful_downloads += 1
                    
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
                        print(f"\n--- Processing completed {group_name} ---")
                        try:
                            # Get manga title for this volume
                            manga_title = self.get_manga_title(chapter_id)
                            manga_title = ''.join(c for c in manga_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            
                            # Call the orchestrator function
                            handle_finished_volume(manga_title, group_name, group_folder, config)
                            
                            completed_groups.add(group_name)
                            print(f"✓ Processed {group_name}")
                            
                        except Exception as e:
                            print(f"✗ Failed to process {group_name}: {e}")
                else:
                    failed_downloads += 1
                    print(f"✗ Failed to download chapter {i+1} (all attempts failed)")
                    # Track completely failed chapter
                    failed_chapters_summary.append(f"Capítulo {chapter_number} (ID: {chapter_id})")
                
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
            print(f"\n=== Processing Remaining Groups ===")
            for group_folder in remaining_groups:
                group_name = group_folder.name
                print(f"\n--- Processing remaining {group_name} ---")
                try:
                    # Get manga title
                    manga_title = self.get_manga_title(chapter_queue[0])
                    manga_title = ''.join(c for c in manga_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    
                    # Call the orchestrator function
                    handle_finished_volume(manga_title, group_name, group_folder, config)
                    
                    print(f"✓ Processed {group_name}")
                except Exception as e:
                    print(f"✗ Failed to process {group_name}: {e}")
        
        print(f"\n=== Complete Workflow Finished ===")
        print(f"Downloaded, enhanced, and exported manga to CBZ and PDF formats")
        
        # Final execution summary
        logging.info("=== Resumo da Execução ===")
        if not failed_chapters_summary:
            logging.info("✓ Sucesso absoluto! Todos os capítulos foram baixados e processados sem erros críticos.")
        else:
            logging.warning("⚠ Atenção! Os seguintes capítulos falharam completamente e não puderam ser baixados:")
            for failed_chapter in failed_chapters_summary:
                logging.warning(f"  - {failed_chapter}")
    
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


def display_main_menu():
    """Display the main menu options"""
    print("\n=== py-tana - your manga shelf extender ===")
    print("1 - Baixar Imagens")
    print("2 - Baixar e exportar (PDF/CBZ)")
    print("3 - Baixar, aprimorar as imagens e exportar (PDF/CBZ)")
    print("4 - Baixar da lista (yet to be developed)")
    print("5 - Baixar de outras fontes (non-mangadex) (yet to be developed)")

def display_export_submenu():
    """Display the export format submenu"""
    print("\n=== Escolher formato de exportação ===")
    print("A - Somente CBZ")
    print("B - Somente PDF")
    print("C - Ambos (CBZ e PDF)")

def get_manga_input():
    """Get manga input from user"""
    print("\n=== Entrada MangaDex ===")
    print("Enter a MangaDex URL or Chapter UUID to download")
    print("Examples:")
    print("  - https://mangadex.org/chapter/d9f90199-79fb-403f-a313-a054f1a77b0c")
    print("  - https://mangadex.org/title/a9232d4b-9e89-49bb-bb7c-3a0c6e4b5c1a")
    print("  - d9f90199-79fb-403f-a313-a054f1a77b0c")
    print()
    
    user_input = input("Enter MangaDex URL or Chapter UUID: ").strip()
    
    if not user_input:
        print("No input provided.")
        return None
    
    return user_input

def main():
    """Main function with interactive CLI menu"""
    downloader = MangaDownloader()
    
    # Configuration variables
    do_upscale = False
    export_cbz = False
    export_pdf = False
    
    while True:
        display_main_menu()
        choice = input("\nEscolha uma opção (1-5): ").strip().upper()
        
        if choice == "1":
            # Download only
            do_upscale = False
            export_cbz = False
            export_pdf = False
            
            user_input = get_manga_input()
            if user_input:
                execute_download_workflow(downloader, user_input, do_upscale, export_cbz, export_pdf)
                
        elif choice == "2":
            # Download and export
            do_upscale = False
            export_cbz, export_pdf = get_export_format_choice()
            
            if export_cbz or export_pdf:
                user_input = get_manga_input()
                if user_input:
                    execute_download_workflow(downloader, user_input, do_upscale, export_cbz, export_pdf)
                    
        elif choice == "3":
            # Download, enhance and export
            do_upscale = True
            export_cbz, export_pdf = get_export_format_choice()
            
            if export_cbz or export_pdf:
                user_input = get_manga_input()
                if user_input:
                    execute_download_workflow(downloader, user_input, do_upscale, export_cbz, export_pdf)
                    
        elif choice == "4":
            print("\nOpção não implementada ainda.")
            continue
            
        elif choice == "5":
            print("\nOpção não implementada ainda.")
            continue
            
        else:
            print("\nOpção inválida. Tente novamente.")
            continue
            
        # Ask if user wants to continue
        continue_choice = input("\nDeseja continuar? (S/N): ").strip().upper()
        if continue_choice != 'S':
            break
    
    print("\nObrigado por usar py-tana!")

def get_export_format_choice():
    """Get export format choice from user"""
    while True:
        display_export_submenu()
        format_choice = input("\nEscolha o formato (A-C): ").strip().upper()
        
        if format_choice == "A":
            return True, False  # CBZ only
        elif format_choice == "B":
            return False, True  # PDF only
        elif format_choice == "C":
            return True, True   # Both
        else:
            print("Opção inválida. Tente novamente.")

def execute_download_workflow(downloader, user_input, do_upscale, export_cbz, export_pdf):
    """Execute the download workflow with given configuration"""
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
        
        # Display configuration
        print(f"\n=== Configuração ===")
        print(f"Aprimorar imagens: {'Sim' if do_upscale else 'Não'}")
        print(f"Exportar CBZ: {'Sim' if export_cbz else 'Não'}")
        print(f"Exportar PDF: {'Sim' if export_pdf else 'Não'}")
        
        # Get download queue
        download_queue = downloader.get_download_queue(manga_id)
        
        if not download_queue:
            print("Nenhum capítulo encontrado para download.")
            return
        
        print(f"\nFound {len(download_queue)} chapters in pt-br")
        
        # Create configuration dictionary
        config = {
            'do_upscale': do_upscale,
            'export_cbz': export_cbz,
            'export_pdf': export_pdf
        }
        
        # Pass configuration to download method
        if do_upscale or export_cbz or export_pdf:
            print("Starting download and export workflow...")
            downloader.download_manga_queue(manga_id, config)
        else:
            print("Starting download workflow...")
            downloader.download_manga_queue(manga_id, config)
        
        print(f"\n=== Workflow concluído ===")
        
    except KeyboardInterrupt:
        print("\nWorkflow interrompido pelo usuário")
    except Exception as e:
        print(f"Erro: {e}")
        print("Por favor, verifique sua entrada e tente novamente.")


if __name__ == "__main__":
    main()
