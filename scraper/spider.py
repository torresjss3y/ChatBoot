import json

def leer_json_arreglado(nombre_archivo):
    datos = []
    try:
        with open(nombre_archivo, "r", encoding="utf-8") as f:
            contenido = f.read().strip()
        
        # Intento 1: Leer todo como lista JSON directamente
        try:
            datos = json.loads(contenido)
            print(f"✅ Carga directa exitosa: {len(datos)} elementos en '{nombre_archivo}'")
            return datos
        except Exception:
            pass

        # Intento 2: Procesar elemento por elemento
        lineas = contenido.splitlines()
        for linea in lineas:
            linea_limpia = linea.strip().rstrip(",")
            # Saltar solo los corchetes iniciales o finales
            if linea_limpia in ["[", "]", "[],", ""]:
                continue
            try:
                objeto = json.loads(linea_limpia)
                datos.append(objeto)
            except Exception:
                continue

        print(f"✅ Carga por líneas exitosa: {len(datos)} elementos recuperados de '{nombre_archivo}'")

    except FileNotFoundError:
        print(f"⚠️ El archivo '{nombre_archivo}' no existe.")
    except Exception as e:
        print(f"❌ Error al procesar '{nombre_archivo}': {e}")

    return datos

# 1. Cargar ambas bases de datos
html_data = leer_json_arreglado("ucss_data.json")
pdf_data = leer_json_arreglado("ucss_pdf_data.json")

# 2. Combinar los arreglos
base_completa = html_data + pdf_data

# 3. Guardar en un JSON limpio y bien formateado
if base_completa:
    with open("ucss_completo.json", "w", encoding="utf-8") as f:
        json.dump(base_completa, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 ¡Proceso completado! Se creó 'ucss_completo.json' con {len(base_completa)} registros en total.")
else:
    print("\n❌ No se encontraron datos para guardar.")