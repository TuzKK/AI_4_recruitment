"""PyInstaller hook for pdfminer.six — collect CMap data files for CJK text extraction."""
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("pdfminer")
