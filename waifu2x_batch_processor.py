#!/usr/bin/env python3
"""
Waifu2x Batch Image Processor

A Python script to improve all images in a folder using waifu2x.
Supports various image formats and provides batch processing capabilities.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional
import time


class Waifu2xProcessor:
    """Main class for processing images with waifu2x."""
    
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    
    def __init__(self, waifu2x_path: str = "waifu2x-ncnn-vulkan"):
        """
        Initialize the processor.
        
        Args:
            waifu2x_path: Path to waifu2x-ncnn-vulkan executable
        """
        self.waifu2x_path = waifu2x_path
        self.verify_waifu2x()
    
    def verify_waifu2x(self):
        """Verify that waifu2x is available and accessible."""
        try:
            result = subprocess.run([self.waifu2x_path, '-h'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError(f"waifu2x executable returned error: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise RuntimeError(f"waifu2x not found at '{self.waifu2x_path}'. "
                           f"Please install waifu2x-ncnn-vulkan or specify the correct path.") from e
    
    def get_image_files(self, folder_path: str) -> List[Path]:
        """
        Get all supported image files in the specified folder.
        
        Args:
            folder_path: Path to the folder containing images
            
        Returns:
            List of Path objects for supported image files
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        if not folder.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {folder_path}")
        
        image_files = []
        for file_path in folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                image_files.append(file_path)
        
        return sorted(image_files)
    
    def process_image(self, input_path: Path, output_path: Path, 
                     noise_level: int = 2, scale_ratio: int = 2,
                     model: str = "photo") -> bool:
        """
        Process a single image using waifu2x.
        
        Args:
            input_path: Path to input image
            output_path: Path for output image
            noise_level: Noise reduction level (0-3)
            scale_ratio: Upscaling ratio (1, 2, 4, 8, 16, 32)
            model: Model to use (photo, art)
            
        Returns:
            True if processing was successful, False otherwise
        """
        try:
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build waifu2x command
            cmd = [
                self.waifu2x_path,
                '-i', str(input_path),
                '-o', str(output_path),
                '-n', str(noise_level),
                '-s', str(scale_ratio),
                '-m', model
            ]
            
            # Run waifu2x
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"✓ Processed: {input_path.name} -> {output_path.name}")
                return True
            else:
                print(f"✗ Failed to process {input_path.name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"✗ Timeout processing {input_path.name}")
            return False
        except Exception as e:
            print(f"✗ Error processing {input_path.name}: {str(e)}")
            return False
    
    def process_folder(self, input_folder: str, output_folder: Optional[str] = None,
                      noise_level: int = 2, scale_ratio: int = 2,
                      model: str = "photo", preserve_structure: bool = True) -> None:
        """
        Process all images in a folder using waifu2x's native directory support.
        
        Args:
            input_folder: Path to folder containing images
            output_folder: Path to output folder (default: input_folder_enhanced)
            noise_level: Noise reduction level (0-3)
            scale_ratio: Upscaling ratio (1, 2, 4, 8, 16, 32)
            model: Model to use (photo, art)
            preserve_structure: Whether to preserve folder structure (waifu2x handles this automatically)
        """
        if output_folder is None:
            output_folder = f"{input_folder}_enhanced"
        
        input_path = Path(input_folder)
        output_path = Path(output_folder)
        
        # Validate input folder
        if not input_path.exists():
            raise FileNotFoundError(f"Input folder not found: {input_folder}")
        
        if not input_path.is_dir():
            raise NotADirectoryError(f"Input path is not a directory: {input_folder}")
        
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Processing folder: {input_folder}")
        print(f"Output folder: {output_folder}")
        print(f"Settings: Noise Level={noise_level}, Scale={scale_ratio}x, Model={model}")
        print("-" * 50)
        
        try:
            # Build waifu2x command with exact format required
            cmd = [
                self.waifu2x_path,
                '-i', str(input_folder),
                '-o', str(output_folder),
                '-n', str(noise_level),
                '-s', str(scale_ratio)
            ]
            
            # Add model parameter if specified
            if model:
                cmd.extend(['-m', model])
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Run waifu2x with timeout
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1 hour timeout
            
            elapsed_time = time.time() - start_time
            
            if result.returncode == 0:
                print("-" * 50)
                print("Processing complete!")
                print(f"Total time: {elapsed_time:.2f} seconds")
                
                # Count processed files
                processed_files = 0
                for root, dirs, files in os.walk(output_folder):
                    for file in files:
                        if Path(file).suffix.lower() in self.SUPPORTED_FORMATS:
                            processed_files += 1
                
                print(f"Files processed: {processed_files}")
                if processed_files > 0:
                    print(f"Average time per file: {elapsed_time/processed_files:.2f} seconds")
            else:
                print("-" * 50)
                print(f"Processing failed!")
                print(f"Error: {result.stderr}")
                print(f"Return code: {result.returncode}")
                
        except subprocess.TimeoutExpired:
            print("✗ Timeout: Processing took too long (1 hour limit reached)")
        except Exception as e:
            print(f"✗ Error during processing: {str(e)}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Batch process images using waifu2x",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/images
  %(prog)s /path/to/images -o /path/to/output -n 1 -s 4
  %(prog)s /path/to/images --model art --noise-level 3
        """
    )
    
    parser.add_argument('input_folder', help='Folder containing images to process')
    parser.add_argument('-o', '--output', help='Output folder (default: input_folder_enhanced)')
    parser.add_argument('-n', '--noise-level', type=int, choices=[0, 1, 2, 3], 
                       default=2, help='Noise reduction level (0-3, default: 2)')
    parser.add_argument('-s', '--scale', type=int, choices=[1, 2, 4, 8, 16, 32], 
                       default=2, help='Upscaling ratio (default: 2)')
    parser.add_argument('-m', '--model', choices=['photo', 'art'], 
                       default='photo', help='Model to use (photo/art, default: photo)')
    parser.add_argument('--waifu2x-path', default='waifu2x-ncnn-vulkan',
                       help='Path to waifu2x-ncnn-vulkan executable')
    parser.add_argument('--flatten', action='store_true',
                       help='Flatten output structure (don\'t preserve subdirectories)')
    
    args = parser.parse_args()
    
    try:
        # Initialize processor
        processor = Waifu2xProcessor(args.waifu2x_path)
        
        # Process folder
        processor.process_folder(
            input_folder=args.input_folder,
            output_folder=args.output,
            noise_level=args.noise_level,
            scale_ratio=args.scale,
            model=args.model,
            preserve_structure=not args.flatten
        )
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
