#!/usr/bin/env python3
"""
MangaDex API Client
Handles communication with MangaDex API for chapter downloads.
"""

import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re


class MangaDexDownloader:
    def __init__(self):
        self.base_url = "https://api.mangadex.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MangaDex-Downloader/1.0'
        })
    
    def get_chapter_data(self, chapter_id: str) -> Tuple[str, str, List[str]]:
        """
        Get chapter data from MangaDex API.
        
        Args:
            chapter_id: The chapter UUID
            
        Returns:
            Tuple of (base_url, chapter_hash, filenames)
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If response format is invalid
        """
        url = f"{self.base_url}/at-home/server/{chapter_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            if 'baseUrl' not in data or 'chapter' not in data:
                raise ValueError("Invalid response format from MangaDex API")
            
            chapter_info = data['chapter']
            if 'hash' not in chapter_info or 'data' not in chapter_info:
                raise ValueError("Invalid chapter data format")
            
            base_url = data['baseUrl']
            chapter_hash = chapter_info['hash']
            
            # Prefer data-saver images if available, otherwise use original
            filenames = chapter_info.get('dataSaver', chapter_info['data'])
            
            return base_url, chapter_hash, filenames
            
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to fetch chapter data: {e}")
    
    def download_page(self, url: str, save_path: Path) -> bool:
        """
        Download a single page image.
        
        Args:
            url: URL of the image to download
            save_path: Path where to save the image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            # Create parent directories if they don't exist
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
            
        except requests.RequestException as e:
            print(f"Failed to download {url}: {e}")
            return False
        except IOError as e:
            print(f"Failed to save file {save_path}: {e}")
            return False
    
    def build_page_url(self, base_url: str, chapter_hash: str, filename: str, data_saver: bool = True) -> str:
        """
        Build the full URL for a page image.
        
        Args:
            base_url: Base URL from API response
            chapter_hash: Chapter hash from API response
            filename: Image filename
            data_saver: Whether to use data-saver endpoint
            
        Returns:
            Full URL for the image
        """
        if data_saver:
            return f"{base_url}/data-saver/{chapter_hash}/{filename}"
        else:
            return f"{base_url}/data/{chapter_hash}/{filename}"
    
    def get_chapter_info(self, chapter_id: str) -> Dict:
        """
        Get detailed chapter information including manga ID and chapter number.
        
        Args:
            chapter_id: The chapter UUID
            
        Returns:
            Dictionary containing chapter information
            
        Raises:
            requests.RequestException: If API request fails
            ValueError: If response format is invalid
        """
        url = f"{self.base_url}/chapter/{chapter_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' not in data:
                raise ValueError("Invalid response format from MangaDex API")
            
            return data['data']
            
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to fetch chapter info: {e}")
    
    def get_manga_feed(self, manga_id: str, language: str = "pt-br") -> List[Dict]:
        """
        Get manga feed (list of chapters) for a specific manga.
        
        Args:
            manga_id: The manga UUID
            language: Language code (default: pt-br)
            
        Returns:
            List of chapter dictionaries
            
        Raises:
            requests.RequestException: If API request fails
        """
        params = {
            'translatedLanguage[]': language,
            'order[chapter]': 'asc'  # Get chapters in ascending order
        }
        
        url = f"{self.base_url}/manga/{manga_id}/feed"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return data.get('data', [])
            
        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to fetch manga feed: {e}")
    
    def parse_chapter_number(self, chapter_attr: Dict) -> Optional[float]:
        """
        Parse chapter number from chapter attributes.
        
        Args:
            chapter_attr: Chapter attributes dictionary
            
        Returns:
            Chapter number as float, or None if not found
        """
        chapter_str = chapter_attr.get('chapter')
        if chapter_str is None:
            return None
        
        try:
            return float(chapter_str)
        except (ValueError, TypeError):
            return None
    
    def get_next_chapter(self, current_chapter_id: str) -> Optional[str]:
        """
        Find the next sequential chapter ID in pt-br.
        
        Args:
            current_chapter_id: Current chapter UUID
            
        Returns:
            Next chapter UUID, or None if not found
        """
        try:
            # Get current chapter info
            current_chapter = self.get_chapter_info(current_chapter_id)
            
            # Extract manga ID and current chapter number
            manga_id = current_chapter.get('relationships', [])
            manga_id = next((rel['id'] for rel in manga_id if rel.get('type') == 'manga'), None)
            
            if not manga_id:
                raise ValueError("Manga ID not found in chapter relationships")
            
            current_attr = current_chapter.get('attributes', {})
            current_chapter_num = self.parse_chapter_number(current_attr)
            
            if current_chapter_num is None:
                raise ValueError("Current chapter number not found or invalid")
            
            # Get all chapters for this manga in pt-br
            chapters = self.get_manga_feed(manga_id, "pt-br")
            
            # Find the next chapter
            next_chapter_id = None
            next_chapter_num = None
            
            for chapter in chapters:
                if chapter['id'] == current_chapter_id:
                    continue  # Skip current chapter
                
                attr = chapter.get('attributes', {})
                chapter_num = self.parse_chapter_number(attr)
                
                if chapter_num is None:
                    continue
                
                # Find the smallest chapter number greater than current
                if chapter_num > current_chapter_num:
                    if next_chapter_num is None or chapter_num < next_chapter_num:
                        next_chapter_num = chapter_num
                        next_chapter_id = chapter['id']
            
            return next_chapter_id
            
        except (requests.RequestException, ValueError) as e:
            print(f"Error finding next chapter: {e}")
            return None
    
    def create_chapter_folder_structure(self, chapter_id: str, base_dir: Path) -> Path:
        """
        Create folder structure with volume and chapter nesting.
        
        Args:
            chapter_id: Chapter UUID
            base_dir: Base download directory
            
        Returns:
            Path to the created chapter folder
        """
        try:
            chapter_info = self.get_chapter_info(chapter_id)
            attr = chapter_info.get('attributes', {})
            
            volume = attr.get('volume')
            chapter = attr.get('chapter')
            
            # Build folder path
            folder_parts = []
            
            if volume:
                folder_parts.append(f"Vol_{volume}")
            
            if chapter:
                folder_parts.append(f"Ch_{chapter}")
            else:
                folder_parts.append(f"Chapter_{chapter_id[:8]}")
            
            chapter_dir = base_dir / Path(*folder_parts)
            chapter_dir.mkdir(parents=True, exist_ok=True)
            
            return chapter_dir
            
        except (requests.RequestException, ValueError) as e:
            print(f"Error creating folder structure: {e}")
            # Fallback to UUID-based folder
            fallback_dir = base_dir / chapter_id
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir
""