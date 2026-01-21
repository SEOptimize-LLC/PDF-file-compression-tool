"""
PDF Compression Module

This module provides PDF compression functionality using Ghostscript (primary)
and pypdf/Pillow (fallback). Supports various compression quality levels and
image optimization.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from PIL import Image


class CompressionQuality:
    """Compression quality presets with Ghostscript settings."""

    MAXIMUM = {
        'name': 'Maximum Compression',
        'dpi': 72,
        'image_quality': 30,
        'gs_setting': '/screen'
    }

    HIGH = {
        'name': 'High Compression',
        'dpi': 150,
        'image_quality': 50,
        'gs_setting': '/ebook'
    }

    MEDIUM = {
        'name': 'Medium Compression',
        'dpi': 200,
        'image_quality': 70,
        'gs_setting': '/printer'
    }

    LOW = {
        'name': 'Low Compression',
        'dpi': 300,
        'image_quality': 85,
        'gs_setting': '/prepress'
    }

    @classmethod
    def get_preset(cls, level: str) -> Dict:
        """Get compression preset by name."""
        presets = {
            'maximum': cls.MAXIMUM,
            'high': cls.HIGH,
            'medium': cls.MEDIUM,
            'low': cls.LOW
        }
        return presets.get(level.lower(), cls.MEDIUM)


class PDFCompressor:
    """
    PDF compression utility supporting Ghostscript and pypdf methods.

    Attributes:
        use_ghostscript (bool): Whether Ghostscript is available
        optimize_images (bool): Whether to optimize images in PDFs
    """

    def __init__(self, optimize_images: bool = True):
        """
        Initialize PDF compressor.

        Args:
            optimize_images: Whether to optimize images during compression
        """
        self.optimize_images = optimize_images
        self.use_ghostscript = self._check_ghostscript()

    def _check_ghostscript(self) -> bool:
        """
        Check if Ghostscript is available in the system.

        Returns:
            bool: True if Ghostscript is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['gs', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def compress_pdf(
        self,
        input_file: BytesIO,
        quality_level: str = 'medium',
        remove_metadata: bool = False
    ) -> Tuple[BytesIO, Dict[str, any]]:
        """
        Compress a PDF file.

        Args:
            input_file: Input PDF file as BytesIO object
            quality_level: Compression quality ('maximum', 'high', 'medium', 'low')
            remove_metadata: Whether to remove PDF metadata

        Returns:
            Tuple of (compressed PDF as BytesIO, compression stats dict)

        Raises:
            ValueError: If input file is invalid
            RuntimeError: If compression fails
        """
        quality = CompressionQuality.get_preset(quality_level)
        original_size = len(input_file.getvalue())

        # Try Ghostscript first (better compression)
        if self.use_ghostscript:
            try:
                compressed = self._compress_with_ghostscript(
                    input_file,
                    quality
                )
                compressed_size = len(compressed.getvalue())
            except Exception as e:
                # Fallback to pypdf if Ghostscript fails
                compressed = self._compress_with_pypdf(
                    input_file,
                    quality,
                    remove_metadata
                )
                compressed_size = len(compressed.getvalue())
        else:
            # Use pypdf method
            compressed = self._compress_with_pypdf(
                input_file,
                quality,
                remove_metadata
            )
            compressed_size = len(compressed.getvalue())

        stats = {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'savings_bytes': original_size - compressed_size,
            'savings_percent': self._calculate_savings_percent(
                original_size,
                compressed_size
            ),
            'method': 'ghostscript' if self.use_ghostscript else 'pypdf'
        }

        return compressed, stats

    def _compress_with_ghostscript(
        self,
        input_file: BytesIO,
        quality: Dict
    ) -> BytesIO:
        """
        Compress PDF using Ghostscript.

        Args:
            input_file: Input PDF as BytesIO
            quality: Quality settings dict

        Returns:
            Compressed PDF as BytesIO
        """
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.pdf'
        ) as tmp_input:
            tmp_input.write(input_file.getvalue())
            tmp_input_path = tmp_input.name

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.pdf'
        ) as tmp_output:
            tmp_output_path = tmp_output.name

        try:
            cmd = [
                'gs',
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.4',
                f'-dPDFSETTINGS={quality["gs_setting"]}',
                '-dNOPAUSE',
                '-dQUIET',
                '-dBATCH',
                f'-r{quality["dpi"]}',
                '-dCompressFonts=true',
                '-dSubsetFonts=true',
                '-dColorImageDownsampleType=/Bicubic',
                f'-dColorImageResolution={quality["dpi"]}',
                '-dGrayImageDownsampleType=/Bicubic',
                f'-dGrayImageResolution={quality["dpi"]}',
                f'-sOutputFile={tmp_output_path}',
                tmp_input_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Ghostscript compression failed: {result.stderr}"
                )

            with open(tmp_output_path, 'rb') as f:
                compressed_data = f.read()

            return BytesIO(compressed_data)

        finally:
            # Cleanup temp files
            try:
                os.unlink(tmp_input_path)
                os.unlink(tmp_output_path)
            except OSError:
                pass

    def _compress_with_pypdf(
        self,
        input_file: BytesIO,
        quality: Dict,
        remove_metadata: bool
    ) -> BytesIO:
        """
        Compress PDF using pypdf library.

        Args:
            input_file: Input PDF as BytesIO
            quality: Quality settings dict
            remove_metadata: Whether to remove metadata

        Returns:
            Compressed PDF as BytesIO
        """
        input_file.seek(0)
        reader = PdfReader(input_file)
        writer = PdfWriter()

        for page in reader.pages:
            # Compress page content
            page.compress_content_streams()

            # Optimize images if enabled
            if self.optimize_images:
                page = self._optimize_images_in_page(page, quality)

            writer.add_page(page)

        # Remove metadata if requested
        if remove_metadata:
            writer.add_metadata({})

        # Compress the output
        output = BytesIO()
        writer.write(output)
        output.seek(0)

        return output

    def _optimize_images_in_page(self, page, quality: Dict):
        """
        Optimize images within a PDF page.

        Args:
            page: PDF page object
            quality: Quality settings dict

        Returns:
            Page with optimized images
        """
        try:
            if '/XObject' in page['/Resources']:
                xobjects = page['/Resources']['/XObject'].get_object()

                for obj_name in xobjects:
                    obj = xobjects[obj_name]

                    if obj['/Subtype'] == '/Image':
                        # Extract and compress image
                        try:
                            # Get image data
                            img_data = obj.get_data()

                            # Convert to PIL Image
                            img = Image.open(BytesIO(img_data))

                            # Resize if needed based on DPI
                            max_dimension = quality['dpi'] * 10  # Reasonable size
                            if max(img.size) > max_dimension:
                                ratio = max_dimension / max(img.size)
                                new_size = tuple(int(dim * ratio) for dim in img.size)
                                img = img.resize(new_size, Image.Resampling.LANCZOS)

                            # Compress image
                            output_img = BytesIO()
                            img_format = 'JPEG' if img.mode == 'RGB' else 'PNG'
                            img.save(
                                output_img,
                                format=img_format,
                                quality=quality['image_quality'],
                                optimize=True
                            )

                            # Update image data
                            obj._data = output_img.getvalue()

                        except Exception:
                            # Skip problematic images
                            continue

        except Exception:
            # If image optimization fails, return page unchanged
            pass

        return page

    @staticmethod
    def _calculate_savings_percent(
        original_size: int,
        compressed_size: int
    ) -> float:
        """
        Calculate compression savings percentage.

        Args:
            original_size: Original file size in bytes
            compressed_size: Compressed file size in bytes

        Returns:
            Savings as percentage
        """
        if original_size == 0:
            return 0.0

        savings = ((original_size - compressed_size) / original_size) * 100
        return max(0.0, min(100.0, savings))  # Clamp between 0-100

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "2.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
