from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RECEIPTS_DIR = APP_DIR / "receipts"
DB_PATH = DATA_DIR / "store.db"

COLORS = {
    "navy": "#132238",
    "blue": "#246BFD",
    "cyan": "#2EC4B6",
    "paper": "#F5F7FA",
    "white": "#FFFFFF",
    "ink": "#17202A",
    "muted": "#64748B",
    "danger": "#C0392B",
}


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return salt.hex(), digest.hex()


def password_matches(password: str, salt_hex: str, digest_hex: str) -> bool:
    _, candidate = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, digest_hex)


class StoreDatabase:
    def __init__(self, path: Path = DB_PATH) -> None:
        DATA_DIR.mkdir(exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()
        self._seed_demo_data()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'customer'))
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0)
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                total REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS sale_items (
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY(sale_id) REFERENCES sales(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            );
            """
        )
        self.connection.commit()

    def _seed_demo_data(self) -> None:
        for email, password, role in (
            ("admin@demo.local", "DemoAdmin123!", "admin"),
            ("cliente@demo.local", "DemoCliente123!", "customer"),
        ):
            if not self.connection.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ).fetchone():
                salt, digest = hash_password(password)
                self.connection.execute(
                    "INSERT INTO users(email, salt, password_hash, role) VALUES (?, ?, ?, ?)",
                    (email, salt, digest, role),
                )

        products = (
            ("Shield Basic", "Proteccion esencial para un dispositivo", 399.0, 12),
            ("Shield Plus", "Proteccion avanzada para tres dispositivos", 699.0, 8),
            ("Cloud Guard", "Monitoreo y respaldo seguro en la nube", 899.0, 6),
            ("Business Defense", "Administracion de cinco equipos", 1299.0, 5),
        )
        self.connection.executemany(
            "INSERT OR IGNORE INTO products(name, description, price, stock) VALUES (?, ?, ?, ?)",
            products,
        )
        self.connection.commit()

    def authenticate(self, email: str, password: str):
        user = self.connection.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        if user and password_matches(password, user["salt"], user["password_hash"]):
            return user
        return None

    def register(self, email: str, password: str) -> None:
        salt, digest = hash_password(password)
        self.connection.execute(
            "INSERT INTO users(email, salt, password_hash, role) VALUES (?, ?, ?, 'customer')",
            (email.lower().strip(), salt, digest),
        )
        self.connection.commit()

    def products(self):
        return self.connection.execute("SELECT * FROM products ORDER BY id").fetchall()

    def update_stock(self, product_id: int, stock: int) -> None:
        self.connection.execute(
            "UPDATE products SET stock = ? WHERE id = ?", (stock, product_id)
        )
        self.connection.commit()

    def checkout(self, user_id: int, cart: dict[int, int]) -> tuple[int, list, float]:
        items = []
        total = 0.0
        with self.connection:
            for product_id, quantity in cart.items():
                product = self.connection.execute(
                    "SELECT * FROM products WHERE id = ?", (product_id,)
                ).fetchone()
                if not product or product["stock"] < quantity:
                    raise ValueError("El inventario cambio. Actualiza el catalogo.")
                subtotal = product["price"] * quantity
                total += subtotal
                items.append((product, quantity, subtotal))

            cursor = self.connection.execute(
                "INSERT INTO sales(user_id, created_at, total) VALUES (?, ?, ?)",
                (user_id, datetime.now().isoformat(timespec="seconds"), total),
            )
            sale_id = cursor.lastrowid
            for product, quantity, _ in items:
                self.connection.execute(
                    "INSERT INTO sale_items VALUES (?, ?, ?, ?)",
                    (sale_id, product["id"], quantity, product["price"]),
                )
                self.connection.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (quantity, product["id"]),
                )
        return sale_id, items, total


class LicenseStoreApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Secure License Store")
        self.geometry("1040x680")
        self.minsize(880, 600)
        self.configure(bg=COLORS["paper"])
        self.db = StoreDatabase()
        self.user = None
        self.cart: dict[int, int] = {}
        self._configure_styles()
        self.show_login()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["paper"])
        style.configure("Card.TFrame", background=COLORS["white"])
        style.configure("TLabel", background=COLORS["paper"], foreground=COLORS["ink"])
        style.configure("Card.TLabel", background=COLORS["white"], foreground=COLORS["ink"])
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=9)
        style.map("Primary.TButton", background=[("active", COLORS["cyan"])])

    def clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_login(self) -> None:
        self.clear()
        shell = ttk.Frame(self, padding=50)
        shell.pack(expand=True)
        card = ttk.Frame(shell, style="Card.TFrame", padding=32)
        card.pack()
        ttk.Label(card, text="Secure License Store", style="Title.TLabel", background=COLORS["white"]).grid(row=0, column=0, columnspan=2, pady=(0, 8))
        ttk.Label(card, text="Acceso a la demostracion", style="Card.TLabel").grid(row=1, column=0, columnspan=2, pady=(0, 24))
        ttk.Label(card, text="Correo", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        email = ttk.Entry(card, width=38)
        email.grid(row=3, column=0, columnspan=2, pady=(0, 12))
        email.insert(0, "cliente@demo.local")
        ttk.Label(card, text="Contrasena", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=6)
        password = ttk.Entry(card, width=38, show="*")
        password.grid(row=5, column=0, columnspan=2, pady=(0, 18))
        password.insert(0, "DemoCliente123!")
        ttk.Button(card, text="Iniciar sesion", style="Primary.TButton", command=lambda: self.login(email.get(), password.get())).grid(row=6, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(card, text="Crear cuenta", command=self.show_register).grid(row=6, column=1, sticky="ew", padx=(5, 0))

    def show_register(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Crear cuenta")
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=24)
        frame.pack()
        ttk.Label(frame, text="Nueva cuenta", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, pady=(0, 15))
        ttk.Label(frame, text="Correo").grid(row=1, column=0, sticky="w")
        email = ttk.Entry(frame, width=35)
        email.grid(row=2, column=0, columnspan=2, pady=(4, 10))
        ttk.Label(frame, text="Contrasena (minimo 10 caracteres)").grid(row=3, column=0, sticky="w")
        password = ttk.Entry(frame, width=35, show="*")
        password.grid(row=4, column=0, columnspan=2, pady=(4, 15))

        def submit() -> None:
            if "@" not in email.get() or len(password.get()) < 10:
                messagebox.showwarning("Datos invalidos", "Ingresa un correo valido y una contrasena de al menos 10 caracteres.", parent=dialog)
                return
            try:
                self.db.register(email.get(), password.get())
            except sqlite3.IntegrityError:
                messagebox.showerror("Cuenta existente", "Ese correo ya esta registrado.", parent=dialog)
                return
            messagebox.showinfo("Cuenta creada", "Ya puedes iniciar sesion.", parent=dialog)
            dialog.destroy()

        ttk.Button(frame, text="Registrar", style="Primary.TButton", command=submit).grid(row=5, column=0, columnspan=2, sticky="ew")

    def login(self, email: str, password: str) -> None:
        self.user = self.db.authenticate(email, password)
        if not self.user:
            messagebox.showerror("Acceso denegado", "Correo o contrasena incorrectos.")
            return
        self.cart.clear()
        self.show_dashboard()

    def show_dashboard(self) -> None:
        self.clear()
        header = tk.Frame(self, bg=COLORS["navy"], height=72)
        header.pack(fill="x")
        tk.Label(header, text="Secure License Store", bg=COLORS["navy"], fg="white", font=("Segoe UI", 18, "bold")).pack(side="left", padx=24, pady=18)
        tk.Button(header, text="Cerrar sesion", command=self.show_login, bg=COLORS["navy"], fg="white", relief="flat", cursor="hand2").pack(side="right", padx=24)

        body = ttk.Frame(self, padding=24)
        body.pack(fill="both", expand=True)
        role = "Administrador" if self.user["role"] == "admin" else "Cliente"
        ttk.Label(body, text=f"Catalogo | {role}", style="Title.TLabel").pack(anchor="w", pady=(0, 15))
        columns = ("id", "producto", "descripcion", "precio", "stock")
        self.product_tree = ttk.Treeview(body, columns=columns, show="headings", height=13)
        widths = (55, 170, 330, 100, 80)
        for column, width in zip(columns, widths):
            self.product_tree.heading(column, text=column.capitalize())
            self.product_tree.column(column, width=width, anchor="center" if column != "descripcion" else "w")
        self.product_tree.pack(fill="both", expand=True)
        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=14)
        ttk.Button(actions, text="Agregar al carrito", style="Primary.TButton", command=self.add_to_cart).pack(side="left")
        ttk.Button(actions, text="Ver carrito", command=self.show_cart).pack(side="left", padx=8)
        if self.user["role"] == "admin":
            ttk.Button(actions, text="Actualizar existencias", command=self.change_stock).pack(side="left")
        self.cart_label = ttk.Label(actions, text="Carrito: 0 articulos")
        self.cart_label.pack(side="right")
        self.refresh_products()

    def refresh_products(self) -> None:
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        for product in self.db.products():
            self.product_tree.insert("", "end", values=(product["id"], product["name"], product["description"], f"${product['price']:,.2f}", product["stock"]))

    def selected_product_id(self) -> int | None:
        selected = self.product_tree.selection()
        if not selected:
            messagebox.showwarning("Seleccion requerida", "Selecciona un producto.")
            return None
        return int(self.product_tree.item(selected[0], "values")[0])

    def add_to_cart(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None:
            return
        product = next(p for p in self.db.products() if p["id"] == product_id)
        current = self.cart.get(product_id, 0)
        if current >= product["stock"]:
            messagebox.showwarning("Sin existencias", "No hay mas unidades disponibles.")
            return
        self.cart[product_id] = current + 1
        self.cart_label.config(text=f"Carrito: {sum(self.cart.values())} articulos")

    def show_cart(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Carrito")
        dialog.geometry("560x420")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Resumen de compra", style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        products = {p["id"]: p for p in self.db.products()}
        tree = ttk.Treeview(frame, columns=("producto", "cantidad", "subtotal"), show="headings")
        for name in ("producto", "cantidad", "subtotal"):
            tree.heading(name, text=name.capitalize())
        total = 0.0
        for product_id, quantity in self.cart.items():
            product = products[product_id]
            subtotal = product["price"] * quantity
            total += subtotal
            tree.insert("", "end", values=(product["name"], quantity, f"${subtotal:,.2f}"))
        tree.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Total: ${total:,.2f}", style="Heading.TLabel").pack(anchor="e", pady=10)
        ttk.Button(frame, text="Confirmar compra", style="Primary.TButton", command=lambda: self.finish_purchase(dialog)).pack(anchor="e")

    def finish_purchase(self, dialog: tk.Toplevel) -> None:
        if not self.cart:
            messagebox.showwarning("Carrito vacio", "Agrega productos antes de comprar.", parent=dialog)
            return
        try:
            sale_id, items, total = self.db.checkout(self.user["id"], self.cart)
        except ValueError as error:
            messagebox.showerror("Compra no completada", str(error), parent=dialog)
            return
        receipt = self.create_receipt(sale_id, items, total)
        self.cart.clear()
        dialog.destroy()
        self.refresh_products()
        self.cart_label.config(text="Carrito: 0 articulos")
        messagebox.showinfo("Compra completada", f"Comprobante generado en:\n{receipt}")

    def create_receipt(self, sale_id: int, items: list, total: float) -> Path:
        RECEIPTS_DIR.mkdir(exist_ok=True)
        output = RECEIPTS_DIR / f"receipt_{sale_id:04d}.pdf"
        pdf = canvas.Canvas(str(output), pagesize=letter)
        pdf.setTitle(f"Receipt {sale_id}")
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(60, 735, "Secure License Store")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(60, 712, f"Venta: {sale_id:04d}")
        pdf.drawString(60, 696, f"Fecha: {datetime.now():%Y-%m-%d %H:%M}")
        pdf.drawString(60, 680, f"Cliente: {self.user['email']}")
        y = 640
        for product, quantity, subtotal in items:
            pdf.drawString(70, y, f"{product['name']} x {quantity}")
            pdf.drawRightString(540, y, f"${subtotal:,.2f}")
            y -= 22
        pdf.line(60, y, 540, y)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawRightString(540, y - 28, f"Total: ${total:,.2f} MXN")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(60, 70, "Documento de demostracion. No representa una operacion comercial real.")
        pdf.save()
        return output

    def change_stock(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Actualizar existencias")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack()
        ttk.Label(frame, text="Nueva cantidad").pack(anchor="w")
        stock = ttk.Spinbox(frame, from_=0, to=999, width=18)
        stock.pack(pady=8)

        def save() -> None:
            try:
                value = int(stock.get())
                if value < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Valor invalido", "Ingresa un numero entero mayor o igual a cero.", parent=dialog)
                return
            self.db.update_stock(product_id, value)
            dialog.destroy()
            self.refresh_products()

        ttk.Button(frame, text="Guardar", style="Primary.TButton", command=save).pack(fill="x")


if __name__ == "__main__":
    LicenseStoreApp().mainloop()
