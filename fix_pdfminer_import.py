"""
PDFMiner 导入修复补丁
修复 unstructured 库中 PSSyntaxError 导入错误的问题
"""

import sys
from pdfminer import pdfparser

# 直接创建一个全局的 PSSyntaxError 别名
PSSyntaxError = pdfparser.PDFSyntaxError

# 现在导入 unstructured 相关的模块
try:
    import unstructured.partition.pdf_image.pdfminer_utils as pdfminer_utils_module
    
    # 替换 pdfminer_utils 模块中的 PSSyntaxError 引用
    pdfminer_utils_module.PSSyntaxError = PSSyntaxError
    
    print("成功修复 PDFMiner 导入问题")
    
except ImportError as e:
    print(f"导入 unstructured 时出错: {e}")
    print("可能需要安装或更新 unstructured 库")
