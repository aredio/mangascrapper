import os
import zipfile
from PIL import Image
from natsort import natsorted
import logging

logger = logging.getLogger(__name__)

class MangaExporter:
    def __init__(self, output_dir="exports"):
        """Define onde os PDFs e CBZs finais serão salvos."""
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def get_all_images(self, source_folder):
        """
        Get all images from source folder with proper natural sorting.
        
        This method:
        a. Finds all chapter subdirectories inside the source_folder
        b. Sorts chapter directories using natural sorting
        c. For each sorted chapter directory, finds all image files
        d. Sorts image files naturally as well
        e. Returns a flat list of image paths in sequential reading order
        """
        image_paths = []
        
        # a. Find all chapter subdirectories
        chapter_dirs = []
        if os.path.exists(source_folder):
            for item in os.listdir(source_folder):
                item_path = os.path.join(source_folder, item)
                if os.path.isdir(item_path):
                    chapter_dirs.append(item_path)
        
        # b. Sort chapter directories using natural sorting
        chapter_dirs = natsorted(chapter_dirs)
        
        # c. For each sorted chapter directory, find all image files
        for chapter_dir in chapter_dirs:
            chapter_images = []
            for file in os.listdir(chapter_dir):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Prefer upscaled versions, fallback to originals
                    if "_upscaled" in file or not any("_upscaled" in f for f in os.listdir(chapter_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))):
                        chapter_images.append(os.path.join(chapter_dir, file))
            
            # d. Sort image files naturally as well
            chapter_images = natsorted(chapter_images)
            
            # e. Append to flat list in sequential reading order
            image_paths.extend(chapter_images)
        
        return image_paths

    def export_to_cbz(self, source_folder, manga_name, group_name):
        """Generate CBZ file with naturally sorted images and continuous numbering."""
        images = self.get_all_images(source_folder)
        if not images:
            logger.warning(f"No images found in {source_folder} for CBZ export.")
            return

        cbz_filename = f"{manga_name} - {group_name}.cbz"
        cbz_path = os.path.join(self.output_dir, cbz_filename)

        logger.info(f"Creating CBZ: {cbz_path} with {len(images)} pages...")
        
        # ZIP_STORED is used because images are already compressed
        with zipfile.ZipFile(cbz_path, 'w', zipfile.ZIP_STORED) as cbz:
            for i, img_path in enumerate(images):
                # Rename images internally using global counter with zero-padding
                # This ensures comic readers treat the entire volume as continuous
                ext = os.path.splitext(img_path)[1].lower()
                if not ext:
                    ext = '.jpg'  # Default extension if none found
                arcname = f"{i+1:04d}{ext}"  # Start from 0001, not 0000
                cbz.write(img_path, arcname)
                
        logger.info(f"✓ CBZ export completed: {cbz_filename}")

    def export_to_pdf(self, source_folder, manga_name, group_name):
        """Generate PDF file with naturally sorted images."""
        images = self.get_all_images(source_folder)
        if not images:
            logger.warning(f"No images found in {source_folder} for PDF export.")
            return

        pdf_filename = f"{manga_name} - {group_name}.pdf"
        pdf_path = os.path.join(self.output_dir, pdf_filename)

        logger.info(f"Creating PDF: {pdf_path} with {len(images)} pages...")

        pil_images = []
        for img_path in images:
            try:
                img = Image.open(img_path)
                # PDFs require images to be in RGB mode (removing Alpha/Transparency if present)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                pil_images.append(img)
            except Exception as e:
                logger.warning(f"Warning: Could not process image {img_path}: {e}")
                continue

        # Save first image and append the rest to the same file
        if pil_images:
            try:
                pil_images[0].save(
                    pdf_path,
                    save_all=True,
                    append_images=pil_images[1:],
                    resolution=100.0  # Base pixel density
                )
                logger.info(f"✓ PDF export completed: {pdf_filename}")
            except Exception as e:
                logger.error(f"Failed to create PDF: {e}")
        else:
            logger.warning("No valid images found for PDF export.")

    def run_exports(self, source_folder, manga_name, group_name, make_cbz=True, make_pdf=True):
        """
        Unified method to run exports conditionally based on boolean flags.
        
        Args:
            source_folder: Path to the folder containing images
            manga_name: Name of the manga
            group_name: Name of the volume/group
            make_cbz: Whether to create CBZ export
            make_pdf: Whether to create PDF export
        """
        if make_cbz:
            self.export_to_cbz(source_folder, manga_name, group_name)
        
        if make_pdf:
            self.export_to_pdf(source_folder, manga_name, group_name)
        
        if not make_cbz and not make_pdf:
            print("No export formats selected.")