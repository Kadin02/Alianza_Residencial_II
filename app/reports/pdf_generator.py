import os
from jinja2 import Environment, FileSystemLoader


def generate_invoice_pdf(data: dict, output_path: str):
    """
    Genera un PDF de factura usando Jinja2 + WeasyPrint.
    ✅ CORREGIDO: reemplaza la implementación con ReportLab que no usaba
    la plantilla HTML ni pasaba variables dinámicas correctamente.
    """

    # Intentar con WeasyPrint (requiere: pip install weasyprint)
    try:
        import weasyprint

        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        template_dir = os.path.abspath(template_dir)

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("invoice_template.html")

        html_content = template.render(**data)

        weasyprint.HTML(string=html_content).write_pdf(output_path)

    except ImportError:
        # Fallback: si WeasyPrint no está instalado, genera HTML y lo guarda como .html
        # Útil para desarrollo. En producción instalar: pip install weasyprint
        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        template_dir = os.path.abspath(template_dir)

        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template("invoice_template.html")
        html_content = template.render(**data)

        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"[AVISO] WeasyPrint no instalado. Factura guardada como HTML: {html_path}")
        print("Para generar PDFs reales ejecutar: pip install weasyprint")

    return output_path
