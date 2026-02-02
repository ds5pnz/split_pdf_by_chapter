import fitz  # PyMuPDF
import os
import sys
import re
import tkinter as tk
from tkinter import filedialog, messagebox

def sanitize_filename(filename):
    """파일명으로 사용할 수 없는 문자를 제거합니다."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def split_pdf_by_chapters(input_path, log_callback=None):
    if not os.path.exists(input_path):
        msg = f"Error: File not found - {input_path}"
        if log_callback: log_callback(msg)
        else: print(msg)
        return

    try:
        doc = fitz.open(input_path)
    except Exception as e:
        msg = f"Error opening PDF: {e}"
        if log_callback: log_callback(msg)
        else: print(msg)
        return

    toc = doc.get_toc()  # [[lvl, title, page, ...], ...]

    if not toc:
        msg = "No table of contents found in the PDF."
        if log_callback: log_callback(msg)
        else: print(msg)
        doc.close()
        return

    # 최상위 챕터(level 1)만 필터링
    chapters = [entry for entry in toc if entry[0] == 1]

    if not chapters:
        msg = "No top-level chapters (level 1) found."
        if log_callback: log_callback(msg)
        else: print(msg)
        doc.close()
        return

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_dir = os.path.dirname(input_path)
    if not output_dir:
        output_dir = "."
    
    # 원본 파일 이름의 하위 디렉토리 생성
    output_subdir = os.path.join(output_dir, base_name)
    if not os.path.exists(output_subdir):
        os.makedirs(output_subdir)
        if log_callback: log_callback(f"디렉토리 생성: {output_subdir}")

    count = 0
    for i, chapter in enumerate(chapters):
        level, title, start_page = chapter[:3]
        
        # 마지막 챕터인 경우 문서의 끝까지, 아니면 다음 챕터의 시작 페이지 전까지
        if i < len(chapters) - 1:
            end_page = chapters[i+1][2] - 1
        else:
            end_page = doc.page_count

        # doc.get_toc()에서 반환되는 페이지 번호는 1-based입니다.
        # fitz의 insert_pdf 등에서 사용하는 인덱스는 0-based입니다.
        start_idx = start_page - 1
        end_idx = end_page - 1

        if start_idx < 0: start_idx = 0
        if end_idx >= doc.page_count: end_idx = doc.page_count - 1
        
        # 유효한 페이지 범위인지 확인
        if start_idx > end_idx:
            msg = f"Skipping chapter '{title}': invalid page range ({start_page} to {end_page})"
            if log_callback: log_callback(msg)
            else: print(msg)
            continue

        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
        
        safe_title = sanitize_filename(title).strip()
        output_filename = f"{base_name} - {safe_title}.pdf"
        output_path = os.path.join(output_subdir, output_filename)
        
        try:
            new_doc.save(output_path)
            msg = f"Saved: {os.path.join(base_name, output_filename)} (Pages {start_page} to {end_page})"
            if log_callback: log_callback(msg)
            else: print(msg)
            count += 1
        except Exception as e:
            msg = f"Error saving {output_path}: {e}"
            if log_callback: log_callback(msg)
            else: print(msg)
        finally:
            new_doc.close()

    doc.close()
    if log_callback:
        log_callback(f"\n작업 완료: 총 {count}개의 파일이 생성되었습니다.")

class PDFSplitterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Chapter Splitter")
        self.root.geometry("600x400")

        # 파일 선택 섹션
        self.file_frame = tk.Frame(root, pady=20)
        self.file_frame.pack(fill=tk.X)

        self.file_label = tk.Label(self.file_frame, text="선택된 파일: 없음", wraplength=500)
        self.file_label.pack(side=tk.TOP, pady=5)

        self.select_button = tk.Button(self.file_frame, text="PDF 파일 선택", command=self.select_file)
        self.select_button.pack(side=tk.TOP)

        # 로그 영역
        self.log_frame = tk.Frame(root, padx=10, pady=10)
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(self.log_frame, state=tk.DISABLED, height=10)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=self.scrollbar.set)

        # 실행 버튼
        self.run_button = tk.Button(root, text="분할 시작", command=self.run_split, state=tk.DISABLED, height=2, width=20)
        self.run_button.pack(pady=10)

        self.selected_file = None

    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="PDF 파일을 선택하세요",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.selected_file = file_path
            self.file_label.config(text=f"선택된 파일: {os.path.basename(file_path)}")
            self.run_button.config(state=tk.NORMAL)
            self.log_message(f"파일이 선택되었습니다: {file_path}")

    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def run_split(self):
        if not self.selected_file:
            return

        self.run_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.DISABLED)
        
        self.log_message("\n작업을 시작합니다...")
        try:
            split_pdf_by_chapters(self.selected_file, self.log_message)
            messagebox.showinfo("완료", "PDF 분할 작업이 완료되었습니다.")
        except Exception as e:
            self.log_message(f"오류 발생: {e}")
            messagebox.showerror("오류", f"작업 중 오류가 발생했습니다: {e}")
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.select_button.config(state=tk.NORMAL)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # CLI 인자가 있으면 기존처럼 동작 (호환성 유지)
        split_pdf_by_chapters(sys.argv[1])
    else:
        # 인자가 없으면 GUI 실행
        root = tk.Tk()
        gui = PDFSplitterGUI(root)
        root.mainloop()
