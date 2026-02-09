import tkinter as tk
from tkinter import ttk, messagebox
from mesaxy import MesaXY

class MesaXYApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Control Mesa XY - Lock-in SR830")
        self.root.geometry("400x400")
        self.root.resizable(False, False)

        # Instancia de la mesa
        try:
            self.mesa = MesaXY(port='COM6')  # Ajusta el puerto según tu sistema
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo inicializar MesaXY:\n{e}")
            self.mesa = None

        # Estilo
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 12), padding=1)
        style.configure("TLabel", font=("Arial", 11))

        # --- Sliders ---
        frame_sliders = ttk.LabelFrame(root, text="Parámetros de Barrido", padding=10)
        frame_sliders.pack(pady=15, fill="x", padx=15)

        # X max
        ttk.Label(frame_sliders, text="X max (mm)").pack(anchor="w")
        self.slider_x = tk.Scale(frame_sliders, from_=0.1, to=10, orient="horizontal",
                                 resolution=0.1, length=300)
        self.slider_x.set(1)
        self.slider_x.pack()

        # Y max
        ttk.Label(frame_sliders, text="Y max (mm)").pack(anchor="w")
        self.slider_y = tk.Scale(frame_sliders, from_=0.1, to=10, orient="horizontal",
                                 resolution=0.1, length=300)
        self.slider_y.set(1)
        self.slider_y.pack()

        # Resolución
        ttk.Label(frame_sliders, text="Resolución (mm)").pack(anchor="w")
        self.slider_res = tk.Scale(frame_sliders, from_=0.005, to=1, orient="horizontal",
                                   resolution=0.005, length=300)
        self.slider_res.set(0.01)
        self.slider_res.pack()

        # --- Botones ---
        frame_buttons = ttk.Frame(root, padding=10)
        frame_buttons.pack(pady=10)

        self.btn_home = ttk.Button(frame_buttons, text="Home", command=self.go_home)
        self.btn_home.grid(row=0, column=0, padx=10, pady=10)

        self.btn_medir = ttk.Button(frame_buttons, text="Medir", command=self.do_measure)
        self.btn_medir.grid(row=0, column=1, padx=10, pady=10)

        self.btn_exit = ttk.Button(frame_buttons, text="Salir", command=self.on_exit)
        self.btn_exit.grid(row=0, column=2, padx=10, pady=10)

    def go_home(self):
        if self.mesa:
            try:
                self.mesa.home()
                messagebox.showinfo("Info", "Mesa enviada a posición HOME.")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo hacer HOME:\n{e}")

    def do_measure(self):
        if self.mesa:
            try:
                x_max = self.slider_x.get()
                y_max = self.slider_y.get()
                res = self.slider_res.get()
                self.mesa.sweep_and_measure(x_max, y_max, res)
                self.mesa.plot_3d()
            except Exception as e:
                messagebox.showerror("Error", f"Fallo durante medición:\n{e}")

    def on_exit(self):
        if self.mesa:
            try:
                self.mesa.close()
            except:
                pass
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = MesaXYApp(root)
    root.mainloop()
