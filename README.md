# Secure License Store

Aplicacion de escritorio que simula la venta de licencias de software mediante
un catalogo, carrito de compra, autenticacion de usuarios y generacion de
comprobantes en PDF.

El proyecto es una version publica y mejorada de un ejercicio universitario.
Utiliza productos y datos ficticios y no procesa pagos reales.

## Funciones principales

- Registro e inicio de sesion con contrasenas almacenadas mediante PBKDF2.
- Persistencia local con SQLite.
- Catalogo con control de existencias.
- Carrito de compra y calculo automático de totales.
- Registro de ventas y generacion de comprobantes PDF.
- Panel administrativo para actualizar inventario.
- Consultas parametrizadas para reducir riesgos de inyeccion SQL.

## Tecnologias

- Python 3
- Tkinter
- SQLite
- ReportLab

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

En macOS o Linux, activa el entorno con `source .venv/bin/activate`.

## Acceso de demostracion

- Administrador: `admin@demo.local`
- Contrasena: `DemoAdmin123!`
- Cliente: `cliente@demo.local`
- Contrasena: `DemoCliente123!`

Las cuentas se crean solo en la base local generada al ejecutar la aplicacion.
No deben utilizarse estas credenciales en un sistema real.

## Estructura

```text
SecureLicenseStore-Demo/
|-- app.py
|-- requirements.txt
|-- .gitignore
|-- LICENSE
`-- README.md
```

## Consideraciones de seguridad

Este proyecto es una demostracion educativa. Para produccion se requeririan un
servidor, gestion de secretos, autorizacion centralizada, sesiones con caducidad,
auditoria y una pasarela de pagos certificada.

## Autor

Ernesto Gomez Romero  
[LinkedIn](https://www.linkedin.com/in/ernesto-g%C3%B3mez-romero-4398a541a/)

