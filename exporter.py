import os
import zipfile
import logging
from PIL import Image
from natsort import natsorted
import img2pdf

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
        """Generate PDF file with naturally sorted images using memory-efficient img2pdf."""
        images = self.get_all_images(source_folder)
        if not images:
            logger.warning(f"No images found in {source_folder} for PDF export.")
            return

        pdf_filename = f"{manga_name} - {group_name}.pdf"
        pdf_path = os.path.join(self.output_dir, pdf_filename)

        logger.info(f"Creating PDF: {pdf_path} with {len(images)} pages...")

        try:
            # Use img2pdf for memory-efficient PDF generation
            # This processes images directly from files without loading them all into RAM
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(images))
            
            logger.info(f"✓ PDF export completed: {pdf_filename}")
            
        except Exception as e:
            logger.error(f"Failed to create PDF with img2pdf: {e}")
            
            # Fallback to Pillow method if img2pdf fails (still more memory-efficient than before)
            logger.info("Attempting fallback to Pillow method...")
            try:
                self._export_to_pdf_pillow_fallback(images, pdf_path, pdf_filename)
            except Exception as fallback_e:
                logger.error(f"Both img2pdf and Pillow fallback failed: {fallback_e}")

    def _export_to_pdf_pillow_fallback(self, images, pdf_path, pdf_filename):
        """Memory-efficient Pillow fallback for PDF generation."""
        logger.info(f"Using Pillow fallback for PDF generation...")
        
        # Process images one by one to minimize memory usage
        first_image_processed = False
        
        with Image.open(images[0]) as first_img:
            # Convert first image to RGB if needed
            if first_img.mode != 'RGB':
                first_img = first_img.convert('RGB')
            
            # Save with remaining images
            remaining_images = []
            
            # Process remaining images one by one without keeping them all in memory
            for img_path in images[1:]:
                try:
                    with Image.open(img_path) as img:
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        remaining_images.append(img)
                except Exception as e:
                    logger.warning(f"Warning: Could not process image {img_path}: {e}")
                    continue
            
            if remaining_images:
                first_img.save(
                    pdf_path,
                    save_all=True,
                    append_images=remaining_images,
                    resolution=100.0
                )
            else:
                first_img.save(pdf_path, resolution=100.0)
            
            # Close all remaining images to free memory
            for img in remaining_images:
                img.close()
        
        logger.info(f"✓ PDF export completed (fallback): {pdf_filename}")

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