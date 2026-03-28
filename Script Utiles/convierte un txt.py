import os
from datetime import datetime


def extraer_py_html_a_txt(ruta_principal, nombre_txt=None):
    """
    Extrae todos los archivos .py, .html, .css y .js y los consolida en un solo TXT.

    Args:
        ruta_principal (str): Ruta de la carpeta principal a escanear.
        nombre_txt (str): Nombre del archivo TXT de salida (opcional).
    """

    if not os.path.exists(ruta_principal):
        print(f"Error: La ruta {ruta_principal} no existe")
        return False

    # Si no se proporciona nombre, se genera con fecha y hora.
    if nombre_txt is None:
        fecha_actual = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_txt = f"analisis_codigo_{fecha_actual}.txt"

    carpetas_excluidas = {"venv", "__pycache__", ".git", ".idea", "env"}

    archivos_procesados = 0
    lineas_totales = 0

    try:
        with open(nombre_txt, "w", encoding="utf-8") as txt_file:
            txt_file.write("=" * 80 + "\n")
            txt_file.write("ANALISIS DE CODIGO - PROYECTO ALIANZA BACKEND\n")
            txt_file.write(f"Fecha de generacion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            txt_file.write(f"Ruta principal: {ruta_principal}\n")
            txt_file.write("=" * 80 + "\n\n")

            for root, dirs, files in os.walk(ruta_principal):
                dirs[:] = [d for d in dirs if d not in carpetas_excluidas]

                for file in sorted(files):
                    if file.endswith((".py", ".html", ".css", ".js", ".env", ".unit", ".md", ".bat")):
                        ruta_completa = os.path.join(root, file)

                        if "venv" in root.split(os.sep):
                            continue

                        ruta_relativa = os.path.relpath(ruta_completa, ruta_principal)

                        txt_file.write("\n" + "=" * 80 + "\n")
                        txt_file.write(f"ARCHIVO: {ruta_relativa}\n")
                        txt_file.write(f"TIPO: {file.split('.')[-1].upper()}\n")
                        txt_file.write(f"RUTA COMPLETA: {ruta_completa}\n")
                        txt_file.write("=" * 80 + "\n\n")

                        try:
                            with open(ruta_completa, "r", encoding="utf-8") as f:
                                contenido = f.read()
                            lineas = contenido.split("\n")
                            lineas_totales += len(lineas)

                            for i, linea in enumerate(lineas, 1):
                                txt_file.write(f"{i:4d} | {linea}\n")

                            archivos_procesados += 1
                            print(f"Procesado: {ruta_relativa} ({len(lineas)} lineas)")

                        except UnicodeDecodeError:
                            try:
                                with open(ruta_completa, "r", encoding="latin-1") as f:
                                    contenido = f.read()
                                txt_file.write("[ARCHIVO LEIDO CON CODIFICACION LATIN-1]\n\n")
                                txt_file.write(contenido)
                                archivos_procesados += 1
                                print(f"Procesado (latin-1): {ruta_relativa}")
                            except Exception as e:
                                error_msg = f"Error al leer archivo: {str(e)}"
                                txt_file.write(f"\n[ERROR: {error_msg}]\n")
                                print(f"Error al procesar {ruta_relativa}: {error_msg}")

                        except Exception as e:
                            error_msg = f"Error al leer archivo: {str(e)}"
                            txt_file.write(f"\n[ERROR: {error_msg}]\n")
                            print(f"Error al procesar {ruta_relativa}: {error_msg}")

                        txt_file.write("\n" + "-" * 80 + "\n")

        print("\n" + "=" * 80)
        print("RESUMEN DE PROCESAMIENTO")
        print("=" * 80)
        print(f"Ruta principal: {ruta_principal}")
        print(f"Archivo TXT creado: {nombre_txt}")
        print(f"Archivos procesados: {archivos_procesados}")
        print(f"Lineas totales: {lineas_totales}")

        tamano_txt = os.path.getsize(nombre_txt)
        print(f"Tamano del TXT: {tamano_txt/1024:.2f} KB ({tamano_txt/1024/1024:.2f} MB)")

        print("\nArchivo generado exitosamente")
        print(f"Puedes encontrar el archivo en: {os.path.abspath(nombre_txt)}")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"Error al crear el archivo: {e}")
        return False


def main():
    ruta_principal = r"C:\alianza_backend"

    print("INICIANDO ANALISIS DE CODIGO")
    print("=" * 80)
    print(f"Escaneando: {ruta_principal}")
    print("Excluyendo: venv, __pycache__, .git, .idea")
    print("=" * 80 + "\n")

    # Solo crear TXT con fecha y hora en el nombre.
    extraer_py_html_a_txt(ruta_principal)


if __name__ == "__main__":
    main()
