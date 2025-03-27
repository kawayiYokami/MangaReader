import os
import shutil

def clean_pycache():
    for root, dirs, files in os.walk('.'):
        # 跳过需要保留的logs目录
        if 'logs' in root.split(os.sep):
            continue
            
        # 删除__pycache__目录
        if '__pycache__' in dirs:
            dir_path = os.path.join(root, '__pycache__')
            shutil.rmtree(dir_path)
            print(f'Removed directory: {dir_path}')
        
        # 删除.pyc/.pyo文件
        for file in files:
            if file.endswith(('.pyc', '.pyo')) or file in ('code_review_report.txt', 'vulture_report.txt'):
                file_path = os.path.join(root, file)
                os.remove(file_path)
                print(f'Removed file: {file_path}')

if __name__ == '__main__':
    print('开始清理Python临时文件...')
    clean_pycache()
    print('清理完成！')