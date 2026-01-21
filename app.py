"""
PDF Compressor - Streamlit Web Application

A web application for compressing PDF files with support for bulk uploads,
adjustable compression levels, and progress tracking.
"""

import streamlit as st
import io
import zipfile
from typing import List, Dict
from pathlib import Path

from pdf_compressor import PDFCompressor, CompressionQuality
import utils


# Page configuration
st.set_page_config(
    page_title="PDF Compressor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)


def initialize_session_state():
    """Initialize session state variables."""
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = []
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False


def render_sidebar() -> Dict:
    """
    Render sidebar with compression settings.

    Returns:
        Dictionary with compression settings
    """
    st.sidebar.title("⚙️ Compression Settings")

    st.sidebar.markdown("---")

    # Quality selector
    quality_options = {
        'Maximum Compression (72 DPI)': 'maximum',
        'High Compression (150 DPI)': 'high',
        'Medium Compression (200 DPI)': 'medium',
        'Low Compression (300 DPI)': 'low'
    }

    selected_quality = st.sidebar.selectbox(
        "Compression Quality",
        options=list(quality_options.keys()),
        index=2,  # Default to Medium
        help="Higher compression = smaller file size but lower quality"
    )

    quality_level = quality_options[selected_quality]

    # Display quality details
    quality_preset = CompressionQuality.get_preset(quality_level)
    st.sidebar.info(
        f"**DPI:** {quality_preset['dpi']}\n\n"
        f"**Image Quality:** {quality_preset['image_quality']}%\n\n"
        f"**Use Case:** {quality_preset['name']}"
    )

    st.sidebar.markdown("---")

    # Advanced options
    st.sidebar.subheader("Advanced Options")

    optimize_images = st.sidebar.checkbox(
        "Optimize Images",
        value=True,
        help="Compress and resize images within PDFs"
    )

    remove_metadata = st.sidebar.checkbox(
        "Remove Metadata",
        value=False,
        help="Remove document metadata (author, creation date, etc.)"
    )

    st.sidebar.markdown("---")

    # File size limits info
    st.sidebar.subheader("📊 File Size Limits")
    st.sidebar.caption("Max file size: 200 MB per file")
    st.sidebar.caption("Recommended: 50+ files for bulk processing")

    return {
        'quality_level': quality_level,
        'optimize_images': optimize_images,
        'remove_metadata': remove_metadata
    }


def process_files(
    uploaded_files: List,
    settings: Dict
) -> List[Dict]:
    """
    Process uploaded PDF files with compression.

    Args:
        uploaded_files: List of uploaded file objects
        settings: Compression settings dictionary

    Returns:
        List of processing results
    """
    compressor = PDFCompressor(optimize_images=settings['optimize_images'])
    results = []

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    total_files = len(uploaded_files)

    for idx, uploaded_file in enumerate(uploaded_files):
        # Update progress
        progress = (idx + 1) / total_files
        progress_bar.progress(progress)
        status_text.text(
            f"Processing {idx + 1}/{total_files}: {uploaded_file.name}"
        )

        try:
            # Validate file
            if not uploaded_file.name.lower().endswith('.pdf'):
                results.append({
                    'filename': uploaded_file.name,
                    'status': 'error',
                    'error': 'Not a PDF file',
                    'original_size': 0,
                    'compressed_size': 0,
                    'savings_percent': 0
                })
                continue

            # Check file size (200 MB limit)
            file_size = uploaded_file.size
            if file_size > 200 * 1024 * 1024:  # 200 MB in bytes
                results.append({
                    'filename': uploaded_file.name,
                    'status': 'error',
                    'error': 'File exceeds 200 MB limit',
                    'original_size': file_size,
                    'compressed_size': 0,
                    'savings_percent': 0
                })
                continue

            # Convert to BytesIO
            input_file = io.BytesIO(uploaded_file.read())

            # Compress PDF
            compressed_file, stats = compressor.compress_pdf(
                input_file=input_file,
                quality_level=settings['quality_level'],
                remove_metadata=settings['remove_metadata']
            )

            # Store result
            results.append({
                'filename': uploaded_file.name,
                'status': 'success',
                'original_size': stats['original_size'],
                'compressed_size': stats['compressed_size'],
                'savings_bytes': stats['savings_bytes'],
                'savings_percent': stats['savings_percent'],
                'method': stats['method'],
                'compressed_data': compressed_file.getvalue()
            })

        except Exception as e:
            results.append({
                'filename': uploaded_file.name,
                'status': 'error',
                'error': str(e),
                'original_size': file_size if 'file_size' in locals() else 0,
                'compressed_size': 0,
                'savings_percent': 0
            })

    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()

    return results


def render_results_table(results: List[Dict]):
    """
    Render results table with compression statistics.

    Args:
        results: List of processing results
    """
    st.subheader("📊 Compression Results")

    # Calculate summary statistics
    total_files = len(results)
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = total_files - successful

    total_original = sum(r['original_size'] for r in results)
    total_compressed = sum(r['compressed_size'] for r in results)
    total_savings = total_original - total_compressed
    avg_savings = (total_savings / total_original * 100) if total_original > 0 else 0

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Files", total_files)

    with col2:
        st.metric("Successful", successful, delta=f"{failed} failed" if failed > 0 else None)

    with col3:
        st.metric(
            "Total Saved",
            PDFCompressor.format_file_size(total_savings)
        )

    with col4:
        st.metric("Avg. Savings", f"{avg_savings:.1f}%")

    st.markdown("---")

    # Results table
    table_data = []
    for result in results:
        table_data.append({
            'Filename': result['filename'],
            'Status': '✅ Success' if result['status'] == 'success' else '❌ Error',
            'Original Size': PDFCompressor.format_file_size(result['original_size']),
            'Compressed Size': PDFCompressor.format_file_size(result['compressed_size']) if result['status'] == 'success' else 'N/A',
            'Savings': f"{result['savings_percent']:.1f}%" if result['status'] == 'success' else result.get('error', 'Unknown error'),
            'Method': result.get('method', 'N/A').upper() if result['status'] == 'success' else 'N/A'
        })

    st.dataframe(
        table_data,
        use_container_width=True,
        hide_index=True
    )


def render_download_section(results: List[Dict]):
    """
    Render download buttons for compressed files.

    Args:
        results: List of processing results
    """
    st.subheader("⬇️ Download Compressed Files")

    successful_results = [r for r in results if r['status'] == 'success']

    if not successful_results:
        st.warning("No files were successfully compressed.")
        return

    # Tabs for individual and bulk download
    tab1, tab2 = st.tabs(["Individual Downloads", "Bulk Download (ZIP)"])

    with tab1:
        st.markdown("Download compressed PDFs individually:")

        # Create columns for download buttons
        cols = st.columns(3)

        for idx, result in enumerate(successful_results):
            col = cols[idx % 3]

            with col:
                # Generate download filename
                original_name = Path(result['filename']).stem
                download_name = f"{original_name}_compressed.pdf"

                st.download_button(
                    label=f"📄 {result['filename']}",
                    data=result['compressed_data'],
                    file_name=download_name,
                    mime="application/pdf",
                    key=f"download_{idx}"
                )

                st.caption(
                    f"Saved {result['savings_percent']:.1f}% "
                    f"({PDFCompressor.format_file_size(result['savings_bytes'])})"
                )

    with tab2:
        st.markdown("Download all compressed PDFs as a single ZIP file:")

        # Create ZIP file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for result in successful_results:
                original_name = Path(result['filename']).stem
                compressed_name = f"{original_name}_compressed.pdf"

                zip_file.writestr(
                    compressed_name,
                    result['compressed_data']
                )

        zip_buffer.seek(0)

        st.download_button(
            label=f"📦 Download All ({len(successful_results)} files as ZIP)",
            data=zip_buffer.getvalue(),
            file_name="compressed_pdfs.zip",
            mime="application/zip",
            key="download_zip"
        )

        total_savings = sum(r['savings_bytes'] for r in successful_results)
        st.info(
            f"Total space saved: {PDFCompressor.format_file_size(total_savings)}"
        )


def main():
    """Main application logic."""
    initialize_session_state()

    # Header
    st.title("📄 PDF Compressor")
    st.markdown(
        "Compress your PDF files quickly and easily. "
        "Supports bulk uploads (50+ files) and large files (up to 200 MB)."
    )

    st.markdown("---")

    # Sidebar settings
    settings = render_sidebar()

    # File uploader
    st.subheader("📤 Upload PDF Files")

    uploaded_files = st.file_uploader(
        "Choose PDF files to compress",
        type=['pdf'],
        accept_multiple_files=True,
        help="You can upload multiple PDF files at once. Max 200 MB per file."
    )

    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) uploaded")

        # Show file list
        with st.expander("📋 View uploaded files"):
            for file in uploaded_files:
                file_size = PDFCompressor.format_file_size(file.size)
                st.text(f"• {file.name} ({file_size})")

        st.markdown("---")

        # Compress button
        if st.button("🚀 Compress PDFs", type="primary", use_container_width=True):
            with st.spinner("Processing PDFs..."):
                results = process_files(uploaded_files, settings)
                st.session_state.processed_files = results
                st.session_state.processing_complete = True

    # Display results if processing is complete
    if st.session_state.processing_complete and st.session_state.processed_files:
        st.markdown("---")
        render_results_table(st.session_state.processed_files)
        st.markdown("---")
        render_download_section(st.session_state.processed_files)

        # Clear results button
        if st.button("🔄 Process New Files"):
            st.session_state.processed_files = []
            st.session_state.processing_complete = False
            st.rerun()

    else:
        # Show instructions when no files uploaded
        if not uploaded_files:
            st.info(
                "👆 Upload one or more PDF files to get started. "
                "Configure compression settings in the sidebar."
            )


if __name__ == "__main__":
    main()
