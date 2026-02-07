import fitz  # PyMuPDF
import os
import sys
import re
import tkinter as tk
from tkinter import filedialog, messagebox

def sanitize_filename(filename):
    """파일명으로 사용할 수 없는 문자를 제거합니다."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def get_pdf_chapters(input_path):
    """PDF에서 최상위 챕터 목록을 추출합니다."""
    if not os.path.exists(input_path):
        return []
    try:
        doc = fitz.open(input_path)
        toc = doc.get_toc()
        chapters = []
        for i, entry in enumerate(toc):
            if entry[0] == 1:
                level, title, start_page = entry[:3]
                # 다음 챕터의 시작 페이지를 찾아 현재 챕터의 끝 페이지 계산
                end_page = doc.page_count
                for next_entry in toc[i+1:]:
                    if next_entry[0] == 1:
                        end_page = next_entry[2] - 1
                        break
                chapters.append({
                    "title": title,
                    "start_page": start_page,
                    "end_page": end_page
                })
        doc.close()
        return chapters
    except Exception:
        return []

def split_pdf_by_chapters(input_path, selected_indices=None, log_callback=None):
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

    toc = doc.get_toc()
    chapters_info = []
    for i, entry in enumerate(toc):
        if entry[0] == 1:
            level, title, start_page = entry[:3]
            end_page = doc.page_count
            for next_entry in toc[i+1:]:
                if next_entry[0] == 1:
                    end_page = next_entry[2] - 1
                    break
            chapters_info.append((title, start_page, end_page))

    if not chapters_info:
        msg = "No top-level chapters (level 1) found."
        if log_callback: log_callback(msg)
        else: print(msg)
        doc.close()
        return

    # 선택된 인덱스가 있으면 해당 챕터만 필터링
    if selected_indices is not None:
        chapters_to_process = [chapters_info[i] for i in selected_indices if i < len(chapters_info)]
    else:
        chapters_to_process = chapters_info

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_dir = os.path.dirname(input_path)
    if not output_dir:
        output_dir = "."
    
    output_subdir = os.path.join(output_dir, base_name)
    if not os.path.exists(output_subdir):
        os.makedirs(output_subdir)
        if log_callback: log_callback(f"디렉토리 생성: {output_subdir}")

    count = 0
    for title, start_page, end_page in chapters_to_process:
        start_idx = start_page - 1
        end_idx = end_page - 1

        if start_idx < 0: start_idx = 0
        if end_idx >= doc.page_count: end_idx = doc.page_count - 1
        
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
        self.root.geometry("700x600")

        # 파일 선택 섹션
        self.file_frame = tk.Frame(root, pady=10)
        self.file_frame.pack(fill=tk.X)

        self.file_label = tk.Label(self.file_frame, text="선택된 파일: 없음", wraplength=600)
        self.file_label.pack(side=tk.TOP, pady=5)

        self.select_button = tk.Button(self.file_frame, text="PDF 파일 선택", command=self.select_file)
        self.select_button.pack(side=tk.TOP)

        # 챕터 선택 섹션
        self.chapter_frame = tk.LabelFrame(root, text="분할할 챕터 선택", padx=10, pady=10)
        self.chapter_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 체크박스 리스트를 위한 캔버스와 스크롤바
        self.canvas = tk.Canvas(self.chapter_frame)
        self.scrollbar_v = tk.Scrollbar(self.chapter_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar_v.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar_v.pack(side="right", fill="y")

        # 전체 선택/해제 버튼
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(fill=tk.X, padx=10)
        
        self.select_all_btn = tk.Button(self.btn_frame, text="전체 선택", command=self.select_all, state=tk.DISABLED)
        self.select_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.deselect_all_btn = tk.Button(self.btn_frame, text="전체 해제", command=self.deselect_all, state=tk.DISABLED)
        self.deselect_all_btn.pack(side=tk.LEFT, padx=5)

        # 로그 영역
        self.log_frame = tk.LabelFrame(root, text="로그", padx=10, pady=5)
        self.log_frame.pack(fill=tk.X, padx=10, pady=5)

        self.log_text = tk.Text(self.log_frame, state=tk.DISABLED, height=8)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar_log = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.scrollbar_log.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=self.scrollbar_log.set)

        # 실행 버튼
        self.run_button = tk.Button(root, text="분할 시작", command=self.run_split, state=tk.DISABLED, height=2, width=20)
        self.run_button.pack(pady=10)

        self.selected_file = None
        self.chapters = []
        self.chapter_vars = []

    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="PDF 파일을 선택하세요",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.selected_file = file_path
            self.file_label.config(text=f"선택된 파일: {os.path.basename(file_path)}")
            self.load_chapters(file_path)

    def load_chapters(self, file_path):
        # 기존 체크박스 제거
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.chapters = get_pdf_chapters(file_path)
        self.chapter_vars = []

        if not self.chapters:
            self.log_message("목차를 찾을 수 없거나 최상위 챕터가 없습니다.")
            self.run_button.config(state=tk.DISABLED)
            self.select_all_btn.config(state=tk.DISABLED)
            self.deselect_all_btn.config(state=tk.DISABLED)
            return

        for i, chap in enumerate(self.chapters):
            var = tk.BooleanVar(value=True)
            self.chapter_vars.append(var)
            cb = tk.Checkbutton(
                self.scrollable_frame, 
                text=f"{chap['title']} (P.{chap['start_page']} ~ P.{chap['end_page']})", 
                variable=var,
                anchor="w",
                justify=tk.LEFT
            )
            cb.pack(fill=tk.X, anchor="w")

        self.run_button.config(state=tk.NORMAL)
        self.select_all_btn.config(state=tk.NORMAL)
        self.deselect_all_btn.config(state=tk.NORMAL)
        self.log_message(f"총 {len(self.chapters)}개의 챕터를 찾았습니다.")

    def select_all(self):
        for var in self.chapter_vars:
            var.set(True)

    def deselect_all(self):
        for var in self.chapter_vars:
            var.set(False)

    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def run_split(self):
        if not self.selected_file:
            return

        selected_indices = [i for i, var in enumerate(self.chapter_vars) if var.get()]
        
        if not selected_indices:
            messagebox.showwarning("경고", "분할할 챕터를 하나 이상 선택해 주세요.")
            return

        self.run_button.config(state=tk.DISABLED)
        self.select_button.config(state=tk.DISABLED)
        
        self.log_message("\n작업을 시작합니다...")
        try:
            split_pdf_by_chapters(self.selected_file, selected_indices, self.log_message)
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
