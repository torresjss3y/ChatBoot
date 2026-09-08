import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

class SitioPhpSpider(CrawlSpider):
    name = "ucss_data_chatboot"

    # Dominio base limpio (sin https:// ni slashes)
    allowed_domains = ["ucss.edu.pe", "www.ucss.edu.pe"]
    start_urls = ["https://www.ucss.edu.pe/"]

    # Regla de extracción ignorando archivos multimedia y documentos pesados
    rules = (
        Rule(
            LinkExtractor(
                deny_extensions=[
                    # Documentos y comprimidos
                    'pdf', 'docx', 'doc', 'xlsx', 'xls', 'ppt', 'pptx',
                    'zip', 'rar', 'gz', 'tar', '7z',
                    # Imágenes y multimedia
                    'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico', 'webp',
                    'mp4', 'mp3', 'avi', 'mov', 'flv',
                    # Archivos de estilo y ejecutables
                    'css', 'js', 'exe', 'dmg'
                ]
            ),
            callback="parse_page",
            follow=True
        ),
    )

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "DOWNLOAD_DELAY": 0.2,                 # Pausa breve para rapidez
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,  # Solicitudes en paralelo
        "COOKIES_ENABLED": False,              # Ahorro de memoria
        "RETRY_TIMES": 1,                      # Omitir enlaces rotos rápidos
    }

    def parse_page(self, response):
        # Filtrar para asegurarse de procesar solo páginas web HTML
        content_type = response.headers.get("Content-Type", b"").decode("utf-8").lower()
        if "text/html" not in content_type:
            return

        # Extracción y limpieza de párrafos de texto
        parrafos = response.css("p::text, li::text").getall()
        texto_limpio = " ".join([p.strip() for p in parrafos if p.strip()])

        # Extracción de encabezados
        encabezados_raw = response.css("h1::text, h2::text, h3::text").getall()
        encabezados = [h.strip() for h in encabezados_raw if h.strip()]

        # Retornar únicamente información de texto
        yield {
            "url": response.url,
            "titulo": response.css("title::text").get(default="").strip(),
            "encabezados": encabezados,
            "contenido_texto": texto_limpio,
        }