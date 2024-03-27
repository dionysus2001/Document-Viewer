import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk, ImageSequence
import fitz  # PyMuPDF for handling PDFs
import io
import json

class DocumentViewer(tk.Tk):
    
    def __init__(self):
        super().__init__()
        self.title("Document Viewer")
        self.geometry("1000x600")
        self.image_list = []
        self.current_index = -1
        self.zoom_level = 1.0
        self.animation_frames = []  # For storing GIF frames
        self.animate_after_id = None  # For GIF animation control
        self.current_image_path = None  # Track the current image displayed
        self.current_pdf_path = None  # Track the current PDF displayed
        self.setup_ui()

    def setup_ui(self):
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=5)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Sidebar setup
        self.sidebar = ttk.Frame(self)
        self.file_listbox = tk.Listbox(self.sidebar, exportselection=False)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)
        self.scrollbar = ttk.Scrollbar(self.sidebar, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.paned_window.add(self.sidebar, width=200)

        # Canvas frame setup
        self.canvas_frame = ttk.Frame(self)
        self.canvas = tk.Canvas(self.canvas_frame, bg="gray", scrollregion=(0, 0, 1000, 1000))
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Adding a scrollbar for the canvas
        self.canvas_scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.config(yscrollcommand=self.canvas_scrollbar.set)
        self.canvas_scrollbar.pack(side="right", fill="y")

        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.paned_window.add(self.canvas_frame, width=800)

        # Toolbar setup
        self.toolbar = ttk.Frame(self)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Buttons on the toolbar
        self.load_button = ttk.Button(self.toolbar, text="Load Files", command=self.load_files)
        self.load_button.pack(side=tk.LEFT)
        self.prev_button = ttk.Button(self.toolbar, text="< Prev", command=lambda: self.navigate(-1))
        self.prev_button.pack(side=tk.LEFT)
        self.next_button = ttk.Button(self.toolbar, text="Next >", command=lambda: self.navigate(1))
        self.next_button.pack(side=tk.LEFT)
        self.zoom_in_button = ttk.Button(self.toolbar, text="Zoom In", command=lambda: self.zoom(1.25))
        self.zoom_in_button.pack(side=tk.LEFT)
        self.zoom_out_button = ttk.Button(self.toolbar, text="Zoom Out", command=lambda: self.zoom(0.8))
        self.zoom_out_button.pack(side=tk.LEFT)
        self.save_library_button = ttk.Button(self.toolbar, text="Save Library", command=self.save_library)
        self.save_library_button.pack(side=tk.LEFT)
        self.load_library_button = ttk.Button(self.toolbar, text="Load Library", command=self.load_library)
        self.load_library_button.pack(side=tk.LEFT)
        self.remove_file_button = ttk.Button(self.toolbar, text="Remove File", command=self.remove_file)
        self.remove_file_button.pack(side=tk.LEFT)

        # Event binding for dynamic canvas resizing
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def on_canvas_resize(self, event=None):
        # Redraw the current document to fit the resized canvas
        if self.current_index >= 0 and not self.animate_after_id:
            self.display_document(self.current_index)

    def on_file_select(self, event=None):
        # Display the document selected from the listbox
        selection = self.file_listbox.curselection()
        if selection:
            self.current_index = selection[0]
            self.display_document(self.current_index)

    def display_document(self, index):
        # Ensure the index is within the bounds of the image_list
        if not 0 <= index < len(self.image_list):
            return
        self.current_index = index
        file_path = self.image_list[index]
        self.canvas.delete("all")  # Clear the canvas for new content

        # Cancel any ongoing animation
        if self.animate_after_id:
            self.after_cancel(self.animate_after_id)
            self.animate_after_id = None
            self.animation_frames.clear()

        # Check file type and display accordingly
        if file_path.lower().endswith(('.pdf', '.PDF')):
            self.display_pdf(file_path)
        else:
            self.display_image_or_gif(file_path)

    def display_image_or_gif(self, file_path):
        # Load the image and check if it is animated (GIF)
        image = Image.open(file_path)
        if getattr(image, "is_animated", False):
            self.process_gif(image)
        else:
            self.display_static_image(image, file_path)

    def display_static_image(self, image, file_path):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img_width, img_height = image.size

        # Apply zoom to the image dimensions
        zoomed_width = int(img_width * self.zoom_level)
        zoomed_height = int(img_height * self.zoom_level)

        img_ratio = zoomed_width / zoomed_height
        canvas_ratio = canvas_width / canvas_height

        if canvas_ratio > img_ratio:
            new_height = min(canvas_height, zoomed_height)
            new_width = int(new_height * img_ratio)
        else:
            new_width = min(canvas_width, zoomed_width)
            new_height = int(new_width / img_ratio)

        # Use Image.Resampling.LANCZOS for high-quality downsampling
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)

        # Center the image on the canvas
        x_position = (canvas_width - new_width) // 2
        y_position = (canvas_height - new_height) // 2

        self.canvas.create_image(x_position, y_position, anchor='nw', image=photo)
        self.current_image = photo  # Keep a reference to avoid garbage collection
        self.current_image_path = file_path  # For tracking if needed

    def process_gif(self, image):
        self.animation_frames.clear()
        try:
            for frame_number in range(image.n_frames):
                image.seek(frame_number)
                frame = ImageTk.PhotoImage(image.resize((int(image.width * self.zoom_level), int(image.height * self.zoom_level)), Image.Resampling.LANCZOS))
                self.animation_frames.append(frame)
            self.animate_gif(0)
        except EOFError:
            pass  # End of GIF frames

    def animate_gif(self, index):
        frame = self.animation_frames[index]
        self.canvas.create_image(0, 0, anchor='nw', image=frame)
        self.current_image = frame  # Keep reference to prevent garbage collection
        next_index = (index + 1) % len(self.animation_frames)
        self.animate_after_id = self.after(100, lambda: self.animate_gif(next_index))

    def display_pdf(self, file_path):
        try:
            self.doc = fitz.open(file_path)
            total_height = 0
            self.canvas.delete("all")  # Clear the canvas
            images = []  # Store references to the images (to prevent garbage collection)
            
            # Load each page of the PDF
            for page_num in range(len(self.doc)):
                page = self.doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom_level, self.zoom_level))
                img = Image.open(io.BytesIO(pix.tobytes()))
                photo = ImageTk.PhotoImage(img)
                images.append(photo)  # Keep reference
                
                # Place the image on the canvas
                self.canvas.create_image(0, total_height, anchor='nw', image=photo)
                total_height += pix.height  # Update total height
            
            # Configure the scroll region based on the total height of the PDF pages
            self.canvas.config(scrollregion=(0, 0, pix.width, total_height))
            self.canvas.images = images  # Keep a reference to the images
        except Exception as e:
            messagebox.showerror("PDF Loading Error", str(e))

    def load_files(self):
        file_types = [
            ("JPEG files", "*.jpg *.jpeg"), 
            ("PNG files", "*.png"), 
            ("GIF files", "*.gif"), 
            ("PDF files", "*.pdf"), 
            ("All files", "*.*")
        ]
        file_paths = filedialog.askopenfilenames(title="Select files", filetypes=file_types)
        for path in file_paths:
            if path not in self.image_list:
                self.image_list.append(path)
                self.file_listbox.insert(tk.END, path.split('/')[-1])
        if file_paths:
            self.file_listbox.select_set(0)  # Automatically select the first loaded file
            self.file_listbox.event_generate('<<ListboxSelect>>')

    def navigate(self, direction):
        new_index = self.current_index + direction
        if 0 <= new_index < len(self.image_list):
            self.current_index = new_index
            # Update the Listbox selection
            self.file_listbox.selection_clear(0, tk.END)  # Clear existing selection
            self.file_listbox.selection_set(self.current_index)  # Set new selection
            self.file_listbox.see(self.current_index)  # Ensure the new selection is visible
            self.display_document(self.current_index)

    def zoom(self, factor):
        self.zoom_level *= factor
        if self.current_index >= 0:
            self.display_document(self.current_index)

    def load_library(self):
        file_path = filedialog.askopenfilename(title="Load Library", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.image_list = json.load(f)
                self.file_listbox.delete(0, tk.END)  # Clear existing entries
                for image_path in self.image_list:
                    self.file_listbox.insert(tk.END, image_path.split('/')[-1])

    def save_library(self):
        file_path = filedialog.asksaveasfilename(title="Save Library", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.image_list, f, indent=4)
            messagebox.showinfo("Success", "Library saved successfully.")

    def remove_file(self):
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "No file selected.")
            return
        for index in reversed(selected_indices):
            del self.image_list[index]
            self.file_listbox.delete(index)
        messagebox.showinfo("Success", "Selected file(s) removed.")

if __name__ == "__main__":
    app = DocumentViewer()
    app.mainloop()

# (C) Dr Dennis Chapman, 2024
